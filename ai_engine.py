"""
JALWE AI TRADER V3
AI Decision Engine with Integrated ML Predictor
"""
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from market_scanner import MarketCandidate
from news_engine import NewsEngine
from ml_predictor import MLPredictor

logger = logging.getLogger(__name__)

@dataclass
class AIDecision:
    symbol: str
    direction: str
    action: str  # "APPROVE", "REJECT"
    is_approved: bool
    confidence: float
    confidence_score: float
    technical_score: float
    news_score: float
    liquidity_score: float
    ml_score: float
    price: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""


class AIEngine:
    def __init__(self, news_engine: Optional[NewsEngine] = None, database = None):
        self.news_engine = news_engine or NewsEngine()
        self.database = database
        self.ml_predictor = MLPredictor()

    def evaluate_candidate(self, candidate: MarketCandidate) -> AIDecision:
        """Evaluate a market candidate using technicals, news, liquidity, and ML prediction."""
        symbol = candidate.symbol
        direction = getattr(candidate, 'direction', 'CALL')
        price = candidate.technical.price if hasattr(candidate.technical, 'price') else 0.0
        spread_percent = candidate.technical.spread_percent if hasattr(candidate.technical, 'spread_percent') else 0.0
        
        # Calculate scores
        tech_score = self._calculate_technical_score(candidate)
        news_signal = self.news_engine.get_news_sentiment(symbol)
        news_score = news_signal.sentiment_score * 100
        liquidity_score = candidate.technical.liquidity_score if hasattr(candidate.technical, 'liquidity_score') else 80.0
        
        # ML Prediction Score
        tech_data_dict = {
            "rvol": candidate.technical.rvol,
            "rsi": getattr(candidate.technical, 'rsi', 50.0),
            "volume_acceleration": getattr(candidate.technical, 'volume_acceleration', 1.0)
        }
        ml_score = self.ml_predictor.predict_probability(symbol, tech_data_dict)

        # Final weighted confidence calculation (Including ML weight)
        final_confidence = (tech_score * 0.35) + (ml_score * 0.30) + (news_score * 0.20) + (liquidity_score * 0.15)

        approved = final_confidence >= 60.0
        action = "APPROVE" if approved else "REJECT"
        reason = f"Confidence {final_confidence:.1f}% (Tech: {tech_score}, ML: {ml_score}, News: {news_score})."

        metadata = {
            "spread_percent": spread_percent,
            "rvol": candidate.technical.rvol,
            "rsi": getattr(candidate.technical, 'rsi', 50.0),
            "ml_probability": ml_score
        }

        return AIDecision(
            symbol=symbol,
            direction=direction,
            action=action,
            is_approved=approved,
            confidence=final_confidence,
            confidence_score=final_confidence,
            technical_score=tech_score,
            news_score=news_score,
            liquidity_score=liquidity_score,
            ml_score=ml_score,
            price=price,
            metadata=metadata,
            reason=reason
        )

    def _calculate_technical_score(self, candidate: MarketCandidate) -> float:
        """Calculate technical score based on RVOL, VWAP, ATR, and RSI."""
        tech = candidate.technical
        score = 50.0

        if tech.rvol >= 2.5:
            score += 20.0
        elif tech.rvol >= 1.5:
            score += 10.0

        price = tech.price if hasattr(tech, 'price') else 0.0
        if tech.vwap is not None:
            if getattr(candidate, 'direction', 'CALL') == "CALL" and price >= tech.vwap:
                score += 15.0
            elif getattr(candidate, 'direction', 'CALL') == "PUT" and price <= tech.vwap:
                score += 15.0

        if hasattr(tech, 'rsi') and tech.rsi is not None:
            if 45.0 <= tech.rsi <= 65.0:
                score += 15.0
            elif tech.rsi > 70.0:
                score -= 15.0
            elif tech.rsi < 30.0:
                score -= 10.0

        return min(max(score, 0.0), 100.0)