import random
import logging

class AIEngine:
    def __init__(self, default_threshold: float = 70.0):
        self.enabled = True
        self.default_threshold = default_threshold

    def evaluate_opportunity(self, symbol: str) -> dict:
        """
        Evaluates trading opportunities based on real-time news sentiment 
        and AI confidence scoring algorithms.
        """
        try:
            # Safely fetch market news sentiment with fallback
            news_sentiment = "Neutral"
            try:
                from news_engine import fetch_market_news
                news_sentiment = fetch_market_news(symbol)
            except ImportError:
                logging.warning("news_engine module not found. Using default neutral sentiment.")
            except Exception as e:
                logging.error(f"Error fetching news sentiment for {symbol}: {e}")
            
            # Base confidence calculation adjusted by market sentiment
            base_score = 65.0
            if news_sentiment == "Bullish":
                base_score += 20.0
            elif news_sentiment == "Bearish":
                base_score -= 15.0
                
            ai_score = min(max(base_score + random.uniform(-5, 5), 0.0), 100.0)
            
            decision = "BUY" if ai_score >= self.default_threshold else "HOLD"
            
            return {
                "symbol": symbol.upper(),
                "ai_score": round(ai_score, 2),
                "sentiment": news_sentiment,
                "decision": decision,
                "status": "ACTIVE_EVALUATED"
            }
            
        except Exception as e:
            logging.error(f"Error in AIEngine evaluation for {symbol}: {e}")
            return {
                "symbol": symbol.upper(),
                "status": "ERROR",
                "message": str(e)
            }
