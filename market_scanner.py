import os
import requests
import pandas as pd
import logging

class MarketScanner:
    def __init__(self):
        self.api_key = os.getenv("APCA_API_KEY_ID")
        self.api_secret = os.getenv("APCA_API_SECRET_KEY")
        self.base_url = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets")
        self.data_url = "https://data.alpaca.markets/v2"
        
        # Extended watchlist / universe pool for scanning
        self.universe = ["AAPL", "TSLA", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AMD", "NFLX", "SPY", "QQQ"]

    def quick_scan(self) -> list:
        """
        Fast scan phase: filters universe based on basic activity and volume.
        """
        active_symbols = []
        headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret
        }

        for symbol in self.universe:
            try:
                url = f"{self.data_url}/stocks/{symbol}/bars"
                params = {"timeframe": "1Day", "limit": 2}
                response = requests.get(url, headers=headers, params=params, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    bars = data.get("bars", [])
                    if bars and len(bars) > 0:
                        # Add to active scanning pool if data is valid
                        active_symbols.append(symbol)
            except Exception as e:
                logging.warning(f"Scanner skipped {symbol} due to error: {e}")
                
        # Fallback if API restricted
        if not active_symbols:
            active_symbols = ["AAPL", "TSLA", "NVDA"]
            
        return active_symbols

    def deep_scan_symbol(self, symbol: str) -> dict:
        """
        Deep scan phase: evaluates volatility, momentum, and volume acceleration for a single symbol.
        """
        from market_data_engine import MarketDataEngine
        data_engine = MarketDataEngine()
        df = data_engine.fetch_latest_bars(symbol, limit=30)
        
        if df is None or len(df) < 20:
            return {"symbol": symbol, "score": 0.0, "valid": False}

        # Calculate basic metrics for scoring
        df["returns"] = df["close"].pct_change()
        volatility = df["returns"].std()
        rvol = df["volume"].iloc[-1] / df["volume"].mean() if df["volume"].mean() > 0 else 1.0

        score = float(rvol * (1.0 + volatility * 10))

        return {
            "symbol": symbol,
            "score": score,
            "rvol": float(rvol),
            "volatility": float(volatility),
            "valid": True
        }

# Compatibility helper
def scan_market_opportunities():
    scanner = MarketScanner()
    symbols = scanner.quick_scan()
    results = [scanner.deep_scan_symbol(sym) for sym in symbols]
    # Sort by opportunity score descending
    sorted_results = sorted([r for r in results if r["valid"]], key=lambda x: x["score"], reverse=True)
    return sorted_results
