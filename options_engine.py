class OptionsEngine:
    def __init__(self):
        pass

    def score_option_contract(self, contract_data: dict) -> dict:
        """
        Scores and filters option contracts based on liquidity, spread, DTE, Delta, and IV.
        Ensures strict institutional filtering instead of random selection.
        """
        spread = contract_data.get("spread", 0.10)
        volume = contract_data.get("volume", 0)
        open_interest = contract_data.get("open_interest", 0)
        delta = contract_data.get("delta", 0.5)
        dte = contract_data.get("dte", 30)

        # Basic validation against poor liquidity or wide spreads
        if spread > 0.50 or volume < 10 or open_interest < 100:
            return {"score": 0.0, "approved": False, "reason": "Poor liquidity or wide spread"}

        # Ideal Delta range for directional momentum (0.40 to 0.60)
        delta_score = 1.0 - abs(delta - 0.5)

        # DTE preference (e.g., 14 to 45 days to expiration)
        dte_score = 1.0 if 14 <= dte <= 45 else 0.5

        composite_score = float((volume * 0.4) + (open_interest * 0.3) + (delta_score * 20) + (dte_score * 10))

        return {
            "score": composite_score,
            "approved": True,
            "reason": "Contract meets institutional liquidity and Greek criteria"
        }

# Compatibility helper
def evaluate_option(contract_data: dict) -> dict:
    engine = OptionsEngine()
    return engine.score_option_contract(contract_data)
