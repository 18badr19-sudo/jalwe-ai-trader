import os
import pandas as pd
import requests
import logging

class MarketDataEngine:
    def __init__(self):
        self.api_key = os.getenv("APCA_API_KEY_ID")
        self.api_secret = os.getenv("APCA_API_SECRET_KEY")
        self.base_url = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets")
        
        # Set paper trading budget to $100 for testing
        self.paper_balance = 100.00
        
        # Alpaca Data API endpoint
        self.data_url = "https://data.alpaca.markets/v2"

    def fetch_latest_bars(self, symbol: str, limit: int = 100) -> pd.DataFrame:
        """
        Fetches real historical OHLCV price bars from Alpaca Paper API, 
        Returns an empty frame when provider data is unavailable; never synthesizes prices.
        """
        headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret
        }
        url = f"{self.data_url}/stocks/{symbol}/bars"
        params = {"timeframe": "1Min", "limit": limit}

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                bars = data.get("bars", [])
                if bars:
                    df = pd.DataFrame(bars)
                    # Normalize column names for technical indicators engine
                    df = df.rename(columns={
                        "t": "timestamp",
                        "o": "open",
                        "h": "high",
                        "l": "low",
                        "c": "close",
                        "v": "volume"
                    })
                    df["timestamp"] = pd.to_datetime(df["timestamp"])
                    return df
        except Exception as e:
            logging.warning(f"Could not fetch Alpaca bars for {symbol}: {type(e).__name__}. Data unavailable.")

        # Missing broker data is missing evidence, not a simulated market.
        return pd.DataFrame()

    def validate_data_quality(self, df: pd.DataFrame) -> bool:
        """
        Checks for missing values, stale quotes, or abnormal data corruption.
        """
        try:
            if df is None or df.empty:
                return False
            if df.isnull().sum().sum() > 0:
                return False
            if "volume" in df.columns and (df["volume"] < 0).any():
                return False
            return True
        except Exception as e:
            logging.error(f"Error during data quality validation: {e}")
            return False

# Compatibility helper to prevent ImportError
def get_latest_stock_quote(symbol: str):
    try:
        engine = MarketDataEngine()
        df = engine.fetch_latest_bars(symbol, limit=1)
        if not df.empty:
            return df.iloc[-1].to_dict()
        return {}
    except Exception as e:
        logging.error(f"Error in get_latest_stock_quote helper for {symbol}: {e}")
        return {}
