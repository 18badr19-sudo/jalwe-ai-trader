"""
APEX legacy execution compatibility module.

SAFETY:
- APEX is research-only.
- This module MUST NOT submit broker orders.
- JALWE V4 is the only component allowed to submit Alpaca PAPER orders.
"""

from __future__ import annotations

import logging
from typing import Any


logger = logging.getLogger(__name__)


class ExecutionEngine:
    """Fail-closed compatibility shim for old imports."""

    RESEARCH_ONLY = True
    ORDER_EXECUTION_ENABLED = False

    def __init__(self, *_: Any, **__: Any) -> None:
        logger.info(
            "APEX ExecutionEngine compatibility shim loaded | "
            "research_only=True | order_execution=False"
        )

    def execute_order(
        self,
        symbol: str,
        qty: int,
        side: str,
        order_type: str = "market",
        time_in_force: str = "gtc",
    ) -> None:
        raise RuntimeError(
            "APEX is research-only. Broker order execution is disabled. "
            "JALWE V4 is the only PAPER execution authority."
        )

    def get_account_balance(self) -> None:
        raise RuntimeError(
            "APEX execution compatibility module does not read broker balances."
        )


_global_execution_engine = ExecutionEngine()


def place_trade_order(
    symbol: str,
    qty: int,
    side: str,
) -> None:
    return _global_execution_engine.execute_order(
        symbol,
        qty,
        side,
    )
