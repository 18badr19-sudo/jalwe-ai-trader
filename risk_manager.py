"""
JALWE AI TRADER V3
Advanced Risk Manager Engine (with Trailing Stop & Position Sizing)
"""
import logging
from dataclasses import dataclass
from typing import Optional
from config import (
    MAX_DAILY_LOSS_PERCENT,
    MAX_POSITION_SIZE_PERCENT,
    MAX_POSITION_SIZE_DOLLARS,
    STOP_LOSS_ATR_MULTIPLIER,
    TAKE_PROFIT_ATR_MULTIPLIER,
)

logger = logging.getLogger(__name__)

@dataclass
class RiskAssessment:
    is_approved: bool
    position_size: float
    stop_loss: float
    take_profit: float
    reason: str

    @property
    def approved(self) -> bool:
        """Alias for is_approved to satisfy main.py compatibility."""
        return self.is_approved


class RiskManager:
    def __init__(self, account_balance: float = 100000.0, news_engine: Optional[any] = None):
        self.account_balance = account_balance
        self.news_engine = news_engine

    def evaluate_risk(self, symbol: str = "UNKNOWN", price: float = 0.0, atr: float = 1.0, direction: str = "CALL", **kwargs) -> RiskAssessment:
        """Evaluate risk parameters, calculate dynamic stop loss, take profit, and position size."""
        decision = kwargs.get('decision')
        if decision:
            symbol = getattr(decision, 'symbol', symbol)
            price = getattr(decision, 'price', price)

        if price <= 0 or atr <= 0:
            return RiskAssessment(False, 0.0, 0.0, 0.0, "Invalid price or ATR for risk calculation.")

        if direction == "CALL":
            stop_loss = price - (atr * STOP_LOSS_ATR_MULTIPLIER)
            take_profit = price + (atr * TAKE_PROFIT_ATR_MULTIPLIER)
        else:
            stop_loss = price + (atr * STOP_LOSS_ATR_MULTIPLIER)
            take_profit = price - (atr * TAKE_PROFIT_ATR_MULTIPLIER)

        position_dollars = min(
            self.account_balance * (MAX_POSITION_SIZE_PERCENT / 100.0),
            MAX_POSITION_SIZE_DOLLARS
        )
        shares = int(position_dollars / price) if price > 0 else 0

        if shares <= 0:
            return RiskAssessment(False, 0.0, stop_loss, take_profit, "Calculated position size resulted in 0 shares.")

        logger.info(f"Risk Manager approved {symbol}: Shares={shares}, SL={stop_loss:.2f}, TP={take_profit:.2f}")

        return RiskAssessment(
            is_approved=True,
            position_size=float(shares),
            stop_loss=round(stop_loss, 2),
            take_profit=round(take_profit, 2),
            reason="Risk limits verified successfully with dynamic ATR levels."
        )

    def evaluate_trade(self, symbol: str = "UNKNOWN", price: float = 0.0, atr: float = 1.0, direction: str = "CALL", **kwargs) -> RiskAssessment:
        """Alias for evaluate_risk supporting decision object or keyword arguments from main.py."""
        return self.evaluate_risk(symbol=symbol, price=price, atr=atr, direction=direction, **kwargs)

    def calculate_trailing_stop(self, current_price: float, highest_price: float, current_stop: float, atr: float) -> float:
        """Trailing Stop Logic: Moves the stop loss upward as the price reaches new highs."""
        if current_price > highest_price:
            potential_stop = current_price - (atr * STOP_LOSS_ATR_MULTIPLIER)
            if potential_stop > current_stop:
                return round(potential_stop, 2)
        return current_stop