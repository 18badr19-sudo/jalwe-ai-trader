import pandas as pd
import numpy as np

class RegimeDetector:
    def __init__(self):
        pass

    def detect_market_regime(self, spy_df: pd.DataFrame) -> str:
        """
        Analyzes SPY or market benchmark data to classify the current Market Regime:
        TRENDING, RANGE, HIGH_VOLATILITY, LOW_VOLATILITY, or RISK_OFF.
        """
        if spy_df is None or len(spy_df) < 20:
            return "UNKNOWN"

        # Calculate returns and volatility
        spy_df = spy_df.copy()
        spy_df["returns"] = spy_df["close"].pct_change()
        volatility = spy_df["returns"].std() * np.sqrt(252) # Annualized volatility
        
        # Calculate moving averages for trend
        sma_20 = spy_df["close"].rolling(window=20).mean().iloc[-1]
        sma_50 = spy_df["close"].rolling(window=50).mean().iloc[-1] if len(spy_df) >= 50 else sma_20
        current_close = spy_df["close"].iloc[-1]

        # Regime classification logic
        if volatility > 0.25:
            return "HIGH_VOLATILITY"
        elif current_close > sma_20 and sma_20 > sma_50:
            return "TRENDING_BULL"
        elif current_close < sma_20 and sma_20 < sma_50:
            return "TRENDING_BEAR"
        elif abs(current_close - sma_20) / sma_20 < 0.015:
            return "RANGE"
        
        return "RISK_ON"

# Compatibility helper
def get_current_market_regime(spy_df: pd.DataFrame = None) -> str:
    detector = RegimeDetector()
    if spy_df is None:
        # Fallback mock benchmark data if none provided
        np.random.seed(42)
        dates = pd.date_range(end=pd.Timestamp.now(), periods=50, freq="1D")
        spy_df = pd.DataFrame({
            "close": 450.0 + np.random.randn(50).cumsum() * 2.0
        }, index=dates)
    return detector.detect_market_regime(spy_df)
