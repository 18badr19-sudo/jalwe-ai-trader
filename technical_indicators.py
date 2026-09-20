import pandas as pd
import numpy as np
import logging

class TechnicalIndicators:
    def __init__(self):
        pass

    def calculate_sma(self, df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
        """
        Calculates Simple Moving Average (SMA) for trend identification safely.
        """
        try:
            df = df.copy()
            if "close" in df.columns:
                df[f"sma_{window}"] = df["close"].rolling(window=window).mean()
            return df
        except Exception as e:
            logging.error(f"Error calculating SMA: {e}")
            return df

    def calculate_rsi(self, df: pd.DataFrame, window: int = 14) -> pd.DataFrame:
        """
        Calculates Relative Strength Index (RSI) for overbought/oversold conditions safely.
        """
        try:
            df = df.copy()
            if "close" in df.columns:
                delta = df["close"].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
                
                rs = gain / (loss + 1e-9)  # Prevent division by zero
                df["rsi"] = 100 - (100 / (1 + rs))
                # Fill NaN values with neutral RSI
                df["rsi"] = df["rsi"].fillna(50.0)
            return df
        except Exception as e:
            logging.error(f"Error calculating RSI: {e}")
            if "rsi" not in df.columns:
                df["rsi"] = 50.0
            return df

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generates buy/sell signals based on technical indicators crossover and RSI thresholds safely.
        """
        try:
            if df is None or df.empty or "close" not in df.columns:
                return df
                
            df = self.calculate_sma(df, window=20)
            df = self.calculate_rsi(df, window=14)
            
            df["signal"] = "HOLD"
            
            # Institutional strategy logic with safety checks
            if f"sma_20" in df.columns and "rsi" in df.columns:
                conditions_buy = (df["rsi"] < 35) & (df["close"] > df["sma_20"])
                conditions_sell = (df["rsi"] > 65)

                df.loc[conditions_buy, "signal"] = "BUY"
                df.loc[conditions_sell, "signal"] = "SELL"
            
            return df
        except Exception as e:
            logging.error(f"Error generating signals: {e}")
            if "signal" not in df.columns:
                df["signal"] = "HOLD"
            return df

# Compatibility helper function
def analyze_market_trends(df: pd.DataFrame) -> pd.DataFrame:
    try:
        ti = TechnicalIndicators()
        return ti.generate_signals(df)
    except Exception as e:
        logging.error(f"Error in analyze_market_trends helper: {e}")
        if df is not None:
            df["signal"] = "HOLD"
        return df
