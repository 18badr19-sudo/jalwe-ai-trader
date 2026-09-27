"""
APEX legacy active-trade compatibility module.

APEX is research-only and never manages broker positions.
JALWE V4 owns PAPER position management.
"""

from __future__ import annotations

import logging
from typing import Any


logger = logging.getLogger(__name__)


class ActiveTradeManager:
    RESEARCH_ONLY = True
    ORDER_EXECUTION_ENABLED = False

    def __init__(self, alpaca_api: Any = None) -> None:
        self.alpaca = alpaca_api

    def monitor_open_positions(self) -> list[dict[str, Any]]:
        """
        Read-only compatibility method.

        It may return a lightweight snapshot when a client is supplied,
        but it never buys, sells, closes, or modifies a position.
        """
        if self.alpaca is None:
            return []

        try:
            positions = self.alpaca.list_positions()
        except Exception as exc:
            logger.warning(
                "APEX read-only position snapshot failed: %s",
                exc,
            )
            return []

        output: list[dict[str, Any]] = []

        for pos in positions or []:
            output.append(
                {
                    "symbol": str(getattr(pos, "symbol", "") or "").upper(),
                    "qty": getattr(pos, "qty", None),
                    "current_price": getattr(pos, "current_price", None),
                    "avg_entry_price": getattr(pos, "avg_entry_price", None),
                }
            )

        return output
