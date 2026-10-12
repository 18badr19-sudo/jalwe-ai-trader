"""Legacy options shim; require real contract evidence before scoring.

The active equity research path does not import this helper. Its old constant
IV, liquidity, and score values were examples rather than broker observations.
"""


class OptionsFlowEngine:
    def __init__(self, alpaca_api=None):
        self.alpaca = alpaca_api

    def evaluate_contract(self, symbol: str, underlying_price: float,
                          target_delta: float = 0.50, otm_pct: float = 0.10) -> dict:
        return {"symbol": str(symbol or "").strip().upper(),
                "status": "UNAVAILABLE", "reason": "REAL_CONTRACT_DATA_REQUIRED"}
