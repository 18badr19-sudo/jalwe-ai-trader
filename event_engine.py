from __future__ import annotations

import logging
from typing import Any


logger = logging.getLogger(__name__)


class EventEngine:
    """
    Research-only macro/event context.

    No fake calendar is used. When no verified calendar provider is
    connected, the engine returns UNKNOWN/REVIEW instead of inventing
    an event or silently allowing execution.
    """

    def __init__(self, provider: Any = None) -> None:
        self.provider = provider

    def check_event_risk(self, symbol: str) -> dict:
        symbol = str(symbol or "").strip().upper()

        if self.provider is None:
            return {
                "symbol": symbol,
                "event_risk": "UNKNOWN",
                "action": "REVIEW",
                "reason": (
                    "No verified macro-event calendar provider is "
                    "connected to APEX."
                ),
                "status": "NO_DATA",
            }

        try:
            result = self.provider.check_event_risk(symbol)

            if not isinstance(result, dict):
                raise TypeError(
                    "Macro-event provider returned an invalid response."
                )

            return result

        except Exception as exc:
            logger.exception(
                "Macro-event provider failed for %s",
                symbol,
            )
            return {
                "symbol": symbol,
                "event_risk": "UNKNOWN",
                "action": "REVIEW",
                "reason": f"Provider error: {exc}",
                "status": "ERROR",
            }
