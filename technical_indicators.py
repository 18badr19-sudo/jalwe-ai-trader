import pandas as pd
import numpy as np

def calculate_rsi(prices: list, period: int = 14) -> float:
    """
    Calculate the Relative Strength Index (RSI) for a list of closing prices.
    """
    if len(prices) < period + 1:
        return 50.0  # Default neutral value if not enough data
        
    series = pd.Series(prices)
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 2)

def calculate_macd(prices: list):
    """
    Calculate MACD and Signal line for trend confirmation.
    """
    if len(prices) < 26:
        return 0.0, 0.0
        
    series = pd.Series(prices)
    exp1 = series.ewm(span=12, adjust=False).mean()
    exp2 = series.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    
    return round(float(macd.iloc[-1]), 4), round(float(signal.iloc[-1]), 4)
