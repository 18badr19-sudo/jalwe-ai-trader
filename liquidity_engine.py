import pandas as pd
import numpy as np

class LiquidityEngine:
    def __init__(self):
        pass

    def calculate_liquidity_flow(self, df: pd.DataFrame) -> dict:
        """
        Calculates a robust liquidity flow score and analyzes volume acceleration,
        VWAP distance, and relative volume (RVOL).
        """
        if df is None or len(df) < 20:
            return {"liquidity_score": 0.0, "rvol": 1.0, "vwap_distance": 0.0, "status": "INSUFFICIENT_DATA"}

        # Calculate VWAP
        typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
        vwap = (typical_price * df["volume"]).cumsum() / df["volume"].cumsum()
        current_close = df["close"].iloc[-1]
        current_vwap = vwap.iloc[-1]
        
        vwap_distance = ((current_close - current_vwap) / current_vwap) * 100.0

        # Calculate RVOL (Relative Volume)
        avg_volume = df["volume"].rolling(window=20).mean().iloc[-1]
        current_volume = df["volume"].iloc[-1]
        rvol = current_volume / avg_volume if avg_volume > 0 else 1.0

        # Volume speed / acceleration
        volume_change = df["volume"].diff().iloc[-1]
        
        # Heuristic Liquidity Flow Score
        liquidity_score = float(rvol * (1.0 + abs(vwap_distance) / 10.0))

        return {
            "liquidity_score": liquidity_score,
            "rvol": float(rvol),
            "vwap_distance": float(vwap_distance),
            "volume_change": float(volume_change),
            "status": "NORMAL" if liquidity_score < 5.0 else "HIGH_ACTIVITY"
        }

# Compatibility helper
def analyze_liquidity(df: pd.DataFrame) -> dict:
    engine = LiquidityEngine()
    return engine.calculate_liquidity_flow(df)
