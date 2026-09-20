class MarketRegimeDetector:
    def __init__(self, high_vix_threshold: float = 25.0, price_change_threshold: float = 0.75):
        # تفعيل المعلمات وتخزين العتبات للتحكم بمرونة النظام
        self.high_vix_threshold = high_vix_threshold
        self.price_change_threshold = price_change_threshold

    def detect_regime(self, spy_price_change: float, vix_level: float) -> dict:
        """
        Detects the current macro market regime (Bull, Bear, High/Low Volatility) 
        to adjust AI risk parameters and confidence thresholds.
        """
        regime = "SIDEWAYS"
        risk_profile = "NEUTRAL"

        if vix_level > self.high_vix_threshold:
            regime = "HIGH_VOLATILITY_PANIC"
            risk_profile = "DEFENSIVE"
        elif spy_price_change > self.price_change_threshold:
            regime = "BULL_TREND"
            risk_profile = "AGGRESSIVE_GROWTH"
        elif spy_price_change < -self.price_change_threshold:
            regime = "BEAR_TREND"
            risk_profile = "CAPITAL_PRESERVATION"

        return {
            "market_regime": regime,
            "vix_level": vix_level,
            "spy_change": spy_price_change,
            "recommended_risk_profile": risk_profile
        }
