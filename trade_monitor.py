"""
Legacy APEX trade monitor — research-only compatibility shim.

APEX does not own broker trades and must not close or mutate them.
JALWE V4 owns PAPER trade lifecycle management.
"""

from __future__ import annotations

import logging
from typing import Any


logger = logging.getLogger(__name__)


class TradeMonitor:
    RESEARCH_ONLY = True
    ORDER_EXECUTION_ENABLED = False

    def __init__(
        self,
        database: Any = None,
        market_provider: Any = None,
    ) -> None:
        self.database = database
        self.market_provider = market_provider

    def check_and_manage_trades(self) -> list[dict[str, Any]]:
        logger.info(
            "APEX TradeMonitor is read-only; "
            "broker trade management is disabled."
        )
        return []


if __name__ == "__main__":
    print(
        "APEX TradeMonitor compatibility shim | "
        "research_only=True | execution=False"
    )
