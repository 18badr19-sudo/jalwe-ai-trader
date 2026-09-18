import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Safe import for external_scanner module
try:
    from external_scanner import get_top_trending_stocks
except ImportError:
    def get_top_trending_stocks():
        logging.info("Using fallback trending stocks scanner.")
        return ["AAPL", "TSLA", "MSFT"]

def main():
    logging.info("Starting JALWE AI TRADER V4...")
    
    # Retrieve target stocks
    stocks = get_top_trending_stocks()
    logging.info(f"Target stocks: {stocks}")

if __name__ == "__main__":
    main()
