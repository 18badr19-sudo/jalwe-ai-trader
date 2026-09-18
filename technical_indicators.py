import pandas as pd
import numpy as np

class TechnicalIndicators:
    def __init__(self):
        pass

    def calculate_sma(self, df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
        """
        Calculates Simple Moving Average (SMA) for trend identification.
        """
        df = df.copy()
        df[f"sma_{window}"] = df["close"].rolling(window=window).mean()
        return df

    def calculate_rsi(self, df: pd.DataFrame, window: int = 14) -> pd.DataFrame:
        """
        Calculates Relative Strength Index (RSI) for overbought/oversold conditions.
        """
        df = df.copy()
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        
        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))
        # Fill NaN values with neutral RSI
        df["rsi"] = df["rsi"].fillna(50.0)
        return df

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generates buy/sell signals based on technical indicators crossover and RSI thresholds.
        """
        df = self.calculate_sma(df, window=20)
        df = self.calculate_rsi(df, window=14)
        
        df["signal"] = "HOLD"
        
        # Example institutional strategy logic:
        # Buy if RSI < 30 (Oversold) and price is near SMA support
        # Sell if RSI > 70 (Overbought)
        conditions_buy = (df["rsi"] < 35) & (df["close"] > df["sma_20"])
        conditions_sell = (df["rsi"] > 65)

        df.loc[conditions_buy, "signal"] = "BUY"
        df.loc[conditions_sell, "signal"] = "SELL"
        
        return df

# Compatibility helper function
def analyze_market_trends(df: pd.DataFrame) -> pd.DataFrame:
    ti = TechnicalIndicators()
    return ti.generate_signals(df)
