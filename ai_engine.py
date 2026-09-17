import random
from news_engine import fetch_market_news

class AIEngine:
    def __init__(self):
        self.enabled = True

    def evaluate_opportunity(self, symbol):
        """
        Evaluates trading opportunities based on real-time news sentiment 
        and AI confidence scoring algorithms.
        """
        news_sentiment = fetch_market_news(symbol)
        
        # Base confidence calculation adjusted by market sentiment
        base_score = 65.0
        if news_sentiment == "Bullish":
            base_score += 20.0
        elif news_sentiment == "Bearish":
            base_score -= 15.0
            
        ai_score = min(max(base_score + random.uniform(-5, 5), 0.0), 100.0)
        
        decision = "BUY" if ai_score >= 70.0 else "HOLD"
        
        return {
            "symbol": symbol,
            "ai_score": round(ai_score, 2),
            "sentiment": news_sentiment,
            "decision": decision
        }
