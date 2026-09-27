"""
Legacy APEX/JALWE monolithic entrypoint — RETIRED.

This repository now uses a strict split of responsibilities:

APEX
    Research/scanning only:
        apex_research_loop.py
        research_orchestrator.py
        scanner_engine.py
        pre_breakout_engine.py
        news_engine.py
        liquidity_engine.py
        jalwe_bridge_client.py

JALWE V4
    Independent decision, risk, recovery and Alpaca PAPER execution.

This legacy file previously contained direct Alpaca order submission.
It is deliberately fail-closed so APEX cannot become a second
execution authority by accident.
"""

from __future__ import annotations


RESEARCH_ONLY = True
ORDER_EXECUTION_ENABLED = False


def main() -> None:
    raise SystemExit(
        "Legacy main.py is retired. "
        "Start Apex with apex_research_loop.py. "
        "Broker execution belongs only to JALWE V4 PAPER."
    )


if __name__ == "__main__":
    main()
