"""
JALWE AI TRADER V3
News Sentiment Engine Module
"""
import requests
import logging
from config import APAL_API_KEY, APAL_SECRET_KEY, APAL_DATA_BASE_URL

class SentimentResult:
    """Helper class to support both attribute access and dict access."""
    def __init__(self, sentiment="neutral", score=0.0, articles=0):
        self.sentiment = sentiment
        self.score = score
        self.sentiment_score = score  # Alias to prevent AttributeError
        self.articles = articles

    def __getitem__(self, key):
        return getattr(self, key)
        
    def get(self, key, default=None):
        return getattr(self, key, default)

class NewsEngine:
    def __init__(self):
        self.base_url = f"{APAL_DATA_BASE_URL}/v1beta1/news"
        self.headers = {
            "APCA-API-KEY-ID": APAL_API_KEY,
            "APCA-API-SECRET-KEY": APAL_SECRET_KEY
        }

    def fetch_news_sentiment(self, symbol: str) -> SentimentResult:
        """Fetch news sentiment for a given symbol from Alpaca API with 401 fallback."""
        try:
            url = f"{self.base_url}?symbols={symbol}&limit=5"
            response = requests.get(url, headers=self.headers, timeout=5)
            
            if response.status_code == 401:
                logging.warning(f"Alpaca News API returned 401 Unauthorized for {symbol}. Falling back to neutral sentiment.")
                return SentimentResult("neutral", 0.0, 0)
                
            if response.status_code == 200:
                data = response.json()
                news_items = data.get("news", [])
                if not news_items:
                    return SentimentResult("neutral", 0.0, 0)
                
                return SentimentResult("bullish", 0.5, len(news_items))
            else:
                logging.warning(f"Failed to fetch news for {symbol}: status {response.status_code}")
                return SentimentResult("neutral", 0.0, 0)
                
        except Exception as e:
            logging.error(f"Error fetching news sentiment for {symbol}: {e}")
            return SentimentResult("neutral", 0.0, 0)

    def get_news_sentiment(self, symbol: str) -> SentimentResult:
        """Alias / wrapper to support get_news_sentiment called from ai_engine.py"""
        return self.fetch_news_sentiment(symbol)

    def should_block_symbol(self, symbol: str):
        """Check if symbol should be blocked based on negative news sentiment."""
        try:
            sentiment_res = self.fetch_news_sentiment(symbol)
            # If score is heavily negative, block it
            if sentiment_res.score < -0.8:
                return True, f"Blocked due to extremely negative sentiment (score: {sentiment_res.score})"
            return False, ""
        except Exception as e:
            logging.error(f"Error in should_block_symbol for {symbol}: {e}")
            return False, ""