from __future__ import annotations

import logging
import os
import time

from datetime import datetime, timezone

from research_orchestrator import ResearchOrchestrator


# ============================================================
# CONFIG
# ============================================================

INTERVAL_SECONDS = max(
    60,
    int(
        os.getenv(
            "APEX_RESEARCH_INTERVAL_SECONDS",
            "300",
        )
    ),
)


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(message)s"
    ),
)

logger = logging.getLogger(__name__)


# ============================================================
# HELPERS
# ============================================================

def utc_now() -> str:

    return (
        datetime.now(
            timezone.utc
        ).isoformat()
    )


def market_is_open(
    orchestrator: ResearchOrchestrator,
) -> bool:

    try:

        clock = (
            orchestrator
            .scanner
            .alpaca
            .get_clock()
        )

        return bool(
            clock.is_open
        )

    except Exception as exc:

        logger.warning(
            "Unable to read Alpaca market clock: %s",
            exc,
        )

        # Fail closed:
        # do not run research cycle if market status is unknown.
        return False


# ============================================================
# PRINT CYCLE
# ============================================================

def print_cycle(
    cycle,
) -> None:

    print()
    print(
        "======================================"
    )

    print(
        "APEX AUTOMATIC RESEARCH CYCLE"
    )

    print(
        "======================================"
    )

    print(
        "TIME:",
        utc_now(),
    )

    print(
        "STATUS:",
        cycle.status,
    )

    print(
        "RADAR:",
        cycle.radar_count,
    )

    print(
        "VALID PRE:",
        cycle.valid_prebreakout_count,
    )

    print(
        "DEEP:",
        cycle.deep_research_count,
    )

    print(
        "PACKETS:",
        cycle.packet_count,
    )

    print(
        "SHORTLIST:",
        cycle.shortlisted_count,
    )

    print(
        "PUBLISHED:",
        cycle.published_count,
    )

    print(
        "BRIDGE:",
        cycle.bridge_status,
    )

    if cycle.bridge_error:

        print(
            "BRIDGE ERROR:",
            cycle.bridge_error,
        )

    if cycle.shortlist:

        print()

        print(
            "----- SENT TO JALWE -----"
        )

        for packet in cycle.shortlist:

            print(
                packet.symbol,
                "| VERDICT:",
                packet.verdict,
                "| SCORE:",
                packet.research_score,
                "| CONF:",
                packet.confidence,
            )

    if cycle.errors:

        print()

        print(
            "ERRORS:",
            len(
                cycle.errors
            ),
        )

        for error in (
            cycle.errors[:10]
        ):

            print(
                "-",
                error,
            )

    print(
        "======================================"
    )


# ============================================================
# MAIN LOOP
# ============================================================

def main() -> None:

    print(
        "======================================"
    )

    print(
        "APEX RESEARCH LOOP V1"
    )

    print(
        "======================================"
    )

    print(
        "INTERVAL:",
        INTERVAL_SECONDS,
        "seconds",
    )

    print(
        "MODE: RESEARCH ONLY"
    )

    print(
        "ORDER EXECUTION: DISABLED"
    )

    print(
        "Press CTRL+C to stop."
    )

    print(
        "======================================"
    )

    orchestrator = (
        ResearchOrchestrator()
    )

    while True:

        try:

            if not market_is_open(
                orchestrator
            ):

                print(
                    utc_now(),
                    "| MARKET CLOSED | waiting..."
                )

                time.sleep(
                    INTERVAL_SECONDS
                )

                continue

            print(
                utc_now(),
                "| MARKET OPEN | starting research..."
            )

            cycle = (
                orchestrator.run_cycle(
                    publish_to_jalwe=True
                )
            )

            print_cycle(
                cycle
            )

        except KeyboardInterrupt:

            print()
            print(
                "APEX research loop stopped by user."
            )

            break

        except Exception as exc:

            logger.exception(
                "Unexpected research loop error: %s",
                exc,
            )

        time.sleep(
            INTERVAL_SECONDS
        )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()
