"""
JALWE AI TRADER V3
Trade Monitor & Exit Engine

Responsibilities:
- Periodically check all OPEN trades against current market prices.
- Trigger automatic exits if Stop Loss or Take Profit is hit.
- Update trade status and calculate PnL in the database.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class TradeMonitor:
    """
    Monitors open trades and manages automatic exit execution.
    """

    def __init__(self, database: Any, market_provider: Any = None) -> None:
        self.database = database
        self.market_provider = market_provider

    def check_and_manage_trades(self) -> None:
        """Fetch open trades and evaluate exit conditions."""
        try:
            open_trades = self.database.get_open_trades()
            if not open_trades:
                return

            logger.info("Monitoring %d open trades for exit conditions...", len(open_trades))

            for trade in open_trades:
                # Get current price (simulated or via market provider)
                current_price = self._get_current_price(trade.symbol, trade.entry_price)

                if current_price is None:
                    continue

                # Check Stop Loss & Take Profit logic based on direction
                if trade.direction.upper() == "BUY" or trade.direction.upper() == "CALL":
                    if current_price <= trade.stop_loss:
                        self._close_position(trade, current_price, "STOP_LOSS")
                    elif current_price >= trade.take_profit:
                        self._close_position(trade, current_price, "TAKE_PROFIT")
                else:  # SHORT / PUT
                    if current_price >= trade.stop_loss:
                        self._close_position(trade, current_price, "STOP_LOSS")
                    elif current_price <= trade.take_profit:
                        self._close_position(trade, current_price, "TAKE_PROFIT")

        except Exception:
            logger.exception("Error occurred while monitoring open trades.")

    def _get_current_price(self, symbol: str, fallback_price: float) -> float:
        """Fetch current price from market provider or use a safe fallback/simulation."""
        try:
            if self.market_provider and hasattr(self.market_provider, "get_latest_price"):
                price = self.market_provider.get_latest_price(symbol)
                if price:
                    return float(price)
        except Exception:
            pass
        
        # Fallback simulation or keeping price steady if live feed is offline
        return fallback_price

    def _close_position(self, trade: Any, exit_price: float, reason: str) -> None:
        """Calculate PnL and close the trade in the database."""
        try:
            if trade.direction.upper() in ["BUY", "CALL"]:
                pnl = (exit_price - trade.entry_price) * trade.quantity
            else:
                pnl = (trade.entry_price - exit_price) * trade.quantity

            self.database.close_trade(trade_id=trade.id, exit_price=exit_price, pnl=pnl, reason=reason)
            logger.info(
                "[EXIT EXECUTED] Closed trade #%d (%s) at %.2f due to %s. PnL: $%.2f",
                trade.id,
                trade.symbol,
                exit_price,
                reason,
                pnl,
            )
        except Exception:
            logger.exception("Failed to close position for trade ID %d", trade.id)


if __name__ == "__main__":
    print("TradeMonitor module ready.")