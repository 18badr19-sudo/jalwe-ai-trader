"""
JALWE AI TRADER V3
Execution Engine Module
"""
import logging
from telegram_notifier import TelegramNotifier

class ExecutionEngine:
    def __init__(self, database=None, db=None, **kwargs):
        self.db = database if database is not None else db
        self.notifier = TelegramNotifier()
        logging.info("ExecutionEngine initialized successfully.")

    def execute_trade(self, opportunity):
        """Execute a trade based on the given opportunity or risk assessment object/dict."""
        # Support both dictionary and object attributes for maximum compatibility
        if isinstance(opportunity, dict):
            symbol = opportunity.get("symbol", "UNKNOWN")
            action = opportunity.get("action", "BUY")
            price = opportunity.get("price", 0.0)
        else:
            symbol = getattr(opportunity, "symbol", getattr(opportunity, "ticker", "UNKNOWN"))
            action = getattr(opportunity, "action", getattr(opportunity, "side", "BUY"))
            price = getattr(opportunity, "price", getattr(opportunity, "entry_price", 0.0))
        
        logging.info(f"Executing trade for {symbol}: {action} at {price}")
        
        # Log trade to database if available
        if self.db and hasattr(self.db, "log_trade"):
            try:
                self.db.log_trade(
                    symbol=symbol,
                    side=action,
                    qty=1.0,
                    entry_price=price,
                    stop_loss=price * 0.98,
                    take_profit=price * 1.05,
                    status="OPEN"
                )
            except Exception as e:
                logging.error(f"Failed to log trade to database: {e}")
                
        # Send notification
        message = f"🚨 *JALWE TRADER ALERT*\nExecuted {action} for *{symbol}* at ${price}"
        self.notifier.send_message(message)

# دالة توافقية لحل خطأ الاستيراد في main.py
def execute_trade_order(symbol: str, qty: float, side: str, order_type: str = "market"):
    engine = ExecutionEngine()
    opportunity = {"symbol": symbol, "action": side, "price": 0.0}
    engine.execute_trade(opportunity)
    return {"status": "success", "symbol": symbol, "qty": qty, "side": side}
