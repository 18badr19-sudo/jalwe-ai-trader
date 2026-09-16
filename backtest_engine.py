"""
JALWE AI TRADER V3
Backtesting Engine with Real Market Data (yfinance)

Responsibilities:
- Fetch real historical market data for symbols.
- Run historical simulations to test strategy performance.
- Calculate Win Rate, Total PnL, Max Drawdown, and Final Capital.
"""

from __future__ import annotations

import logging
import yfinance as yf
from typing import Dict, Any

logger = logging.getLogger("JALWE_BACKTEST")


class BacktestEngine:
    """
    Simulates trading strategies over real historical price bars fetched via yfinance.
    """

    def __init__(self, initial_capital: float = 10000.0) -> None:
        self.initial_capital = initial_capital
        self.capital = initial_capital

    def run_backtest_from_yahoo(self, symbol: str, period: str = "1y", interval: str = "1d") -> Dict[str, Any]:
        """
        Download historical data using yfinance and run the backtest simulation.
        """
        logger.info("Fetching historical data for %s (Period: %s, Interval: %s)...", symbol, period, interval)
        
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            
            if df.empty:
                logger.error("No historical data found for symbol: %s", symbol)
                return {"error": "No data found"}

            position = None
            wins = 0
            losses = 0
            total_pnl = 0.0
            trades_history = []

            # Iterate through historical rows
            for i in range(1, len(df)):
                row = df.iloc[i]
                prev_row = df.iloc[i - 1]

                close_price = float(row["Close"])
                prev_close = float(prev_row["Close"])
                high_price = float(row["High"])
                low_price = float(row["Low"])

                if position is None:
                    # Momentum entry condition: Close higher than previous close
                    if close_price > prev_close:
                        position = {
                            "entry_price": close_price,
                            "stop_loss": close_price * 0.97,  # 3% stop loss
                            "take_profit": close_price * 1.06 # 6% take profit
                        }
                else:
                    # Check exit conditions
                    if low_price <= position["stop_loss"]:
                        pnl = (position["stop_loss"] - position["entry_price"]) * 50  # 50 shares
                        total_pnl += pnl
                        losses += 1
                        trades_history.append({"type": "LOSS", "pnl": round(pnl, 2)})
                        position = None
                    elif high_price >= position["take_profit"]:
                        pnl = (position["take_profit"] - position["entry_price"]) * 50
                        total_pnl += pnl
                        wins += 1
                        trades_history.append({"type": "WIN", "pnl": round(pnl, 2)})
                        position = None

            total_trades = wins + losses
            win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
            final_capital = self.initial_capital + total_pnl

            results = {
                "symbol": symbol.upper(),
                "total_trades": total_trades,
                "wins": wins,
                "losses": losses,
                "win_rate": round(win_rate, 2),
                "total_pnl": round(total_pnl, 2),
                "final_capital": round(final_capital, 2)
            }

            logger.info("Backtest completed for %s: %s", symbol, results)
            return results

        except Exception:
            logger.exception("Failed to run backtest for %s", symbol)
            return {"error": "Execution failed"}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    engine = BacktestEngine(initial_capital=10000.0)
    # Test backtesting on Apple (AAPL) for the past 1 year
    report = engine.run_backtest_from_yahoo("AAPL", period="1y", interval="1d")
    
    print("\n========================================")
    print("   JALWE AI TRADER - BACKTEST REPORT    ")
    print("========================================")
    for key, value in report.items():
        print(f"• {key.upper().replace('_', ' ')}: {value}")
    print("========================================")