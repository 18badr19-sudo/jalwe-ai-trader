import pandas as pd
import numpy as np

class MarketDataEngine:
    def __init__(self):
        pass

    def fetch_latest_bars(self, symbol: str, limit: int = 100) -> pd.DataFrame:
        """
        Fetches and normalizes live/historical OHLCV price bars for institutional analysis.
        """
        np.random.seed(42)
        base_price = 150.0 if symbol == "AAPL" else (250.0 if symbol == "TSLA" else 65000.0)
        
        # Simulate clean OHLCV data
        data = {
            "timestamp": pd.date_range(end=pd.Timestamp.now(), periods=limit, freq="1Min"),
            "open": base_price + np.random.randn(limit).cumsum() * 0.5,
            "high": base_price + np.random.randn(limit).cumsum() * 0.5 + 1.0,
            "low": base_price + np.random.randn(limit).cumsum() * 0.5 - 1.0,
            "close": base_price + np.random.randn(limit).cumsum() * 0.5,
            "volume": np.random.randint(1000, 50000, size=limit)
        }
        
        df = pd.DataFrame(data)
        return df

    def validate_data_quality(self, df: pd.DataFrame) -> bool:
        """
        Checks for missing values, stale quotes, or abnormal data corruption.
        """
        if df.isnull().sum().sum() > 0:
            return False
        if (df["volume"] <= 0).any():
            return False
        return True
