import os
import requests
import logging

class ExecutionEngine:
    def __init__(self):
        self.api_key = os.getenv("APCA_API_KEY_ID")
        self.api_secret = os.getenv("APCA_API_SECRET_KEY")
        self.base_url = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets")
        
        self.headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret,
            "Content-Type": "application/json"
        }

    def execute_order(self, symbol: str, qty: int, side: str, order_type: str = "market", time_in_force: str = "gtc"):
        """
        Submits a real paper trading order to Alpaca API and sends a Telegram notification.
        """
        if qty <= 0:
            logging.warning(f"Invalid quantity {qty} for {symbol}. Order skipped.")
            return None

        url = f"{self.base_url}/v2/orders"
        payload = {
            "symbol": symbol.upper(),
            "qty": str(qty),
            "side": side.lower(),
            "type": order_type.lower(),
            "time_in_force": time_in_force.lower()
        }

        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=10)
            if response.status_code == 201:
                order_data = response.json()
                msg = f"🚨 *JALWE AI TRADER EXECUTION*\n\n✅ Successfully placed *{side.upper()}* order for `{qty}` shares of `{symbol.upper()}`.\n📊 Order ID: `{order_data.get('id')}`"
                logging.info(f"Order executed successfully for {symbol}: {side} {qty} shares.")
                
                # Safe Telegram notification import and send
                try:
                    from telegram_notifier import send_telegram_message
                    send_telegram_message(msg)
                except ImportError:
                    logging.warning("telegram_notifier module not found. Notification skipped.")
                
                return order_data
            else:
                error_msg = f"Failed to execute order for {symbol}: {response.text}"
                logging.error(error_msg)
                try:
                    from telegram_notifier import send_telegram_message
                    send_telegram_message(f"⚠️ *Execution Error*\n\n`{error_msg}`")
                except ImportError:
                    pass
                return None
        except Exception as e:
            logging.error(f"Exception during order execution for {symbol}: {e}")
            return None

    def get_account_balance(self) -> float:
        """
        Fetches the current paper account cash balance from Alpaca.
        """
        url = f"{self.base_url}/v2/account"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                account_data = response.json()
                return float(account_data.get("cash", 100.00))
        except Exception as e:
            logging.warning(f"Could not fetch account balance: {e}. Defaulting to $100.00.")
        return 100.00

# Global engine instance for optimized compatibility
_global_execution_engine = ExecutionEngine()

def place_trade_order(symbol: str, qty: int, side: str):
    return _global_execution_engine.execute_order(symbol, qty, side)
