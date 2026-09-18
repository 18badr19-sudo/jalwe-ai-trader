import os
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Safe import for telegram_notifier module
try:
    from telegram_notifier import send_telegram_message
except (ImportError, AttributeError):
    def send_telegram_message(message: str):
        logging.warning(f"Telegram notification skipped: {message}")

# Safe import for external_scanner module
try:
    from external_scanner import get_top_trending_stocks
except ImportError:
    def get_top_trending_stocks():
        logging.info("Using fallback trending stocks scanner.")
        return ["AAPL", "TSLA", "MSFT"]

def main():
    logging.info("Starting JALWE AI TRADER V4...")
    
    # Send Telegram notification
    send_telegram_message("🚀 *JALWE AI TRADER V4* is now online and running on Railway!")
    
    stocks = get_top_trending_stocks()
    logging.info(f"Target stocks: {stocks}")

if __name__ == "__main__":
    main()
