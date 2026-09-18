import os
import requests
import logging

class NewsEngine:
    def __init__(self):
        self.api_key = os.getenv("APCA_API_KEY_ID")
        self.api_secret = os.getenv("APCA_API_SECRET_KEY")
        self.base_url = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets")
        # Alpaca News API endpoint
        self.news_url = "https://data.alpaca.markets/v1beta1/news"

    def fetch_symbol_news(self, symbol: str) -> dict:
        """
        Fetches and analyzes recent news/catalysts for a given symbol to evaluate sentiment and event risk.
        """
        headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret
        }
        params = {"symbols": symbol, "limit": 5}

        try:
            response = requests.get(self.news_url, headers=headers, params=params, timeout=8)
            if response.status_code == 200:
                data = response.json()
                news_items = data.get("news", [])
                if news_items:
                    # Basic sentiment scoring heuristic based on keywords
                    positive_keywords = ["growth", "beat", "upgrade", "partnership", "approval", "record"]
                    negative_keywords = ["miss", "lawsuit", "downgrade", "investigation", "loss", "recall"]
                    
                    sentiment_score = 0.0
                    for item in news_items:
                        headline = item.get("headline", "").lower()
                        if any(kw in headline for kw in positive_keywords):
                            sentiment_score += 0.2
                        if any(kw in headline for kw in negative_keywords):
                            sentiment_score -= 0.2

                    # Normalize sentiment between -1.0 and 1.0
                    sentiment_score = max(min(sentiment_score, 1.0), -1.0)
                    
                    return {
                        "symbol": symbol,
                        "sentiment_score": float(sentiment_score),
                        "catalyst_detected": len(news_items) > 0,
                        "news_count": len(news_items),
                        "status": "SUCCESS"
                    }
        except Exception as e:
            logging.warning(f"Could not fetch news for {symbol}: {e}")

        # Fallback neutral result if API fails
        return {
            "symbol": symbol,
            "sentiment_score": 0.0,
            "catalyst_detected": False,
            "news_count": 0,
            "status": "FALLBACK_NEUTRAL"
        }

# Compatibility helper
def analyze_news_catalyst(symbol: str) -> dict:
    engine = NewsEngine()
    return engine.fetch_symbol_news(symbol)
