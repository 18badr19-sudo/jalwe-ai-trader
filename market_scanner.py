import os
import logging
import alpaca_trade_api as tradeapi

class MarketScanner:
    def __init__(self):
        self.api_key = os.getenv("APCA_API_KEY_ID")
        self.api_secret = os.getenv("APCA_API_SECRET_KEY")
        self.base_url = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets")
        
        try:
            self.api = tradeapi.REST(self.api_key, self.api_secret, self.base_url, api_version='v2')
        except Exception as e:
            logging.error(f"Failed to initialize Alpaca REST in MarketScanner: {e}")
            self.api = None

    def quick_scan(self) -> list:
        """
        Fetches active, tradeable US equities directly from Alpaca to act as a true market-wide opportunity hunter.
        """
        symbols = []
        try:
            if self.api:
                # Fetch all active US equities
                assets = self.api.list_assets(status='active', asset_class='us_equity')
                
                # Filter tradable assets from major exchanges (NASDAQ, NYSE) and clean symbols
                raw_symbols = [
                    asset.symbol for asset in assets 
                    if asset.tradable and asset.exchange in ['NASDAQ', 'NYSE', 'ARCA'] 
                    and '/' not in asset.symbol and '.' not in asset.symbol
                ]
                
                # Take a robust dynamic pool of up to 200 active symbols to scan thoroughly
                symbols = raw_symbols[:200]
            else:
                raise Exception("API not initialized")
                
        except Exception as e:
            logging.error(f"Error fetching market assets from Alpaca: {e}")
            # Fallback high-momentum pool if network/API hiccups occur
            symbols = ["AAPL", "TSLA", "NVDA", "AMD", "MSFT", "AMZN", "META", "GOOGL", "NFLX", "PLTR", "MARA", "RIOT", "COIN"]

        logging.info(f"Market Hunter Scanner loaded {len(symbols)} symbols across the market.")
        return symbols

# Compatibility helper
def get_top_trending_stocks() -> list:
    scanner = MarketScanner()
    return scanner.quick_scan()
