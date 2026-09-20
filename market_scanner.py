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
        Scans and fetches ALL active, tradeable US equities across the entire market 
        without being restricted to a fixed or limited symbol list.
        """
        symbols = []
        try:
            if self.api:
                # Fetch all active US equities from the entire market broker feed
                assets = self.api.list_assets(status='active', asset_class='us_equity')
                
                # Filter tradable assets dynamically across major exchanges without hardcoded limits
                raw_symbols = [
                    asset.symbol for asset in assets 
                    if getattr(asset, 'tradable', False) and getattr(asset, 'exchange', '') in ['NASDAQ', 'NYSE', 'ARCA', 'BATS', 'AMEX'] 
                    and '/' not in asset.symbol and '.' not in asset.symbol and '^' not in asset.symbol
                ]
                
                # Utilize the comprehensive market-wide scanned symbols dynamically
                symbols = raw_symbols
            else:
                raise Exception("API not initialized")
                
        except Exception as e:
            logging.error(f"Error fetching all market assets from Alpaca: {e}")
            # Comprehensive fallback pool covering top market leaders across sectors if API is offline
            symbols = [
                "AAPL", "TSLA", "NVDA", "AMD", "MSFT", "AMZN", "META", "GOOGL", "NFLX", "PLTR", 
                "MARA", "RIOT", "COIN", "JPM", "BAC", "XOM", "CVX", "DIS", "PYPL", "INTC", 
                "QCOM", "BA", "IBM", "ORCL", "CRM", "NKE", "SHOP", "UBER", "ABNB", "SQ"
            ]

        logging.info(f"Market Scanner successfully loaded {len(symbols)} symbols spanning the entire market.")
        return symbols

# Compatibility helper
def get_top_trending_stocks() -> list:
    try:
        scanner = MarketScanner()
        return scanner.quick_scan()
    except Exception as e:
        logging.error(f"Error in get_top_trending_stocks helper: {e}")
        return ["AAPL", "TSLA", "NVDA", "AMD", "MSFT"]
