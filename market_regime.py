class MarketRegimeDetector:
    def __init__(self):
        pass

    def detect_regime(self, spy_price_change: float, vix_level: float) -> dict:
        """
        Detects the current macro market regime (Bull, Bear, High/Low Volatility) 
        to adjust AI risk parameters and confidence thresholds.
        """
        regime = "SIDEWAYS"
        risk_profile = "NEUTRAL"

        if vix_level > 25.0:
            regime = "HIGH_VOLATILITY_PANIC"
            risk_profile = "DEFENSIVE"
        elif spy_price_change > 0.75:
            regime = "BULL_TREND"
            risk_profile = "AGGRESSIVE_GROWTH"
        elif spy_price_change < -0.75:
            regime = "BEAR_TREND"
            risk_profile = "CAPITAL_PRESERVATION"

        return {
            "market_regime": regime,
            "vix_level": vix_level,
            "spy_change": spy_price_change,
            "recommended_risk_profile": risk_profile
        }
