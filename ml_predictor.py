"""Retired V3 probability shim. No validated prediction model is installed.

The current APEX research loop uses deterministic evidence in ai_engine.py.
Randomized heuristic scores must never be presented as success probabilities.
"""
from typing import Any, Dict


class MLPredictor:
    def predict_probability(self, symbol: str, technical_data: Dict[str, Any]) -> float:
        raise RuntimeError("No validated ML model is configured; probability unavailable.")
