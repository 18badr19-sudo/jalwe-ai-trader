from __future__ import annotations

import os
import sys

from pathlib import Path
from typing import Any, Iterable


# ============================================================
# JALWE V4 PATH
# ============================================================

DEFAULT_JALWE_ROOT = Path(
    r"C:\Users\18bad\Desktop"
    r"\JALWE-AI-TRADER-V4-main"
    r"\JALWE-AI-TRADER-V4-main"
)

JALWE_ROOT = Path(
    os.getenv(
        "JALWE_V4_ROOT",
        str(DEFAULT_JALWE_ROOT),
    )
).resolve()


# ============================================================
# VALIDATE PATH
# ============================================================

BRIDGE_FILE = (
    JALWE_ROOT
    / "intelligence"
    / "external_research_bridge.py"
)

DATABASE_PATH = (
    JALWE_ROOT
    / "data"
    / "apex_jalwe_bridge.db"
)


if not BRIDGE_FILE.exists():

    raise RuntimeError(
        "JALWE external_research_bridge.py "
        f"not found: {BRIDGE_FILE}"
    )


# ============================================================
# IMPORT JALWE
# ============================================================

if str(JALWE_ROOT) not in sys.path:

    sys.path.insert(
        0,
        str(JALWE_ROOT),
    )


from intelligence.external_research_bridge import (
    ExternalResearchBridge,
)


# ============================================================
# APEX -> JALWE BRIDGE CLIENT
# ============================================================

class JalweBridgeClient:
    """
    APEX -> JALWE V4 RESEARCH BRIDGE

    RESEARCH ONLY.

    This class NEVER:
        - buys
        - sells
        - submits broker orders
        - manages positions

    It only publishes Apex research packets
    into JALWE's research database.
    """

    VERSION = "1.0"

    def __init__(
        self,
    ) -> None:

        self.bridge = (
            ExternalResearchBridge(
                DATABASE_PATH
            )
        )


    # ========================================================
    # GET VALUE
    # ========================================================

    @staticmethod
    def _get(
        packet: Any,
        name: str,
        default: Any = None,
    ) -> Any:

        if isinstance(
            packet,
            dict,
        ):

            return packet.get(
                name,
                default,
            )

        return getattr(
            packet,
            name,
            default,
        )


    # ========================================================
    # PACKET -> DICT
    # ========================================================

    @staticmethod
    def _packet_dict(
        packet: Any,
    ) -> dict:

        if isinstance(
            packet,
            dict,
        ):

            return dict(
                packet
            )

        method = getattr(
            packet,
            "to_dict",
            None,
        )

        if callable(
            method
        ):

            return dict(
                method()
            )

        if hasattr(
            packet,
            "__dict__",
        ):

            return dict(
                packet.__dict__
            )

        return {}


    # ========================================================
    # PUBLISH ONE PACKET
    # ========================================================

    def publish_packet(
        self,
        packet: Any,
    ):

        symbol = str(
            self._get(
                packet,
                "symbol",
                "",
            )
            or
            ""
        ).strip().upper()

        if not symbol:

            raise ValueError(
                "Research packet symbol is empty."
            )

        # ----------------------------------------------------
        # Apex confidence is 0-100.
        # JALWE bridge requires 0-1.
        # ----------------------------------------------------

        apex_confidence = float(
            self._get(
                packet,
                "confidence",
                0.0,
            )
            or
            0.0
        )

        confidence = max(
            0.0,
            min(
                apex_confidence / 100.0,
                1.0,
            ),
        )

        news_score = self._get(
            packet,
            "news_score",
            None,
        )

        news_sentiment = str(
            self._get(
                packet,
                "news_sentiment",
                "UNKNOWN",
            )
            or
            "UNKNOWN"
        ).upper()

        bias = str(
            self._get(
                packet,
                "bias",
                "MIXED",
            )
            or
            "MIXED"
        ).upper()

        verdict = str(
            self._get(
                packet,
                "verdict",
                "WATCH",
            )
            or
            "WATCH"
        ).upper()

        research_score = float(
            self._get(
                packet,
                "research_score",
                0.0,
            )
            or
            0.0
        )

        catalysts = list(
            self._get(
                packet,
                "catalysts",
                [],
            )
            or
            []
        )

        catalyst = (
            str(
                catalysts[0]
            )
            if catalysts
            else None
        )

        evidence = list(
            self._get(
                packet,
                "evidence",
                [],
            )
            or
            []
        )

        conflicts = list(
            self._get(
                packet,
                "conflicts",
                [],
            )
            or
            []
        )

        risk_flags = list(
            self._get(
                packet,
                "risk_flags",
                [],
            )
            or
            []
        )

        headlines = list(
            self._get(
                packet,
                "headlines",
                [],
            )
            or
            []
        )

        # ----------------------------------------------------
        # Conflicts are research warnings too.
        # ----------------------------------------------------

        combined_risks = []

        for item in (
            risk_flags
            +
            conflicts
        ):

            text = str(
                item
            ).strip()

            if (
                text
                and
                text not in combined_risks
            ):

                combined_risks.append(
                    text
                )

        summary = (
            f"APEX {verdict} | "
            f"Research Score {research_score:.2f}/100 | "
            f"Confidence {apex_confidence:.2f}% | "
            f"Bias {bias}"
        )

        metadata = (
            self._packet_dict(
                packet
            )
        )

        metadata[
            "apex_research_score"
        ] = research_score

        metadata[
            "apex_verdict"
        ] = verdict

        metadata[
            "apex_confidence_pct"
        ] = apex_confidence

        metadata[
            "transport"
        ] = "LOCAL_SQLITE"

        metadata[
            "execution_authority"
        ] = False

        return (
            self.bridge.publish_research(

                symbol=symbol,

                news_score=(
                    news_score
                ),

                sentiment=(
                    news_sentiment
                ),

                catalyst=(
                    catalyst
                ),

                confidence=(
                    confidence
                ),

                summary=(
                    summary
                ),

                market_bias=(
                    bias
                ),

                technical_notes=(
                    evidence
                    +
                    conflicts
                ),

                headlines=(
                    headlines
                ),

                risk_flags=(
                    combined_risks
                ),

                metadata=(
                    metadata
                ),

                source="APEX",
            )
        )


    # ========================================================
    # PUBLISH SHORTLIST
    # ========================================================

    def publish_shortlist(
        self,
        packets: Iterable[Any],
    ) -> list:

        published = []

        for packet in (
            packets
            or []
        ):

            verdict = str(
                self._get(
                    packet,
                    "verdict",
                    "REJECT",
                )
            ).upper()

            critical_risk = bool(
                self._get(
                    packet,
                    "critical_risk",
                    False,
                )
            )

            # -----------------------------------------------
            # Do not forward rejected / critical packets.
            # -----------------------------------------------

            if verdict == "REJECT":

                continue

            if critical_risk:

                continue

            published.append(
                self.publish_packet(
                    packet
                )
            )

        return published


    # ========================================================
    # HEALTH
    # ========================================================

    def health_check(
        self,
    ) -> dict:

        bridge_health = (
            self.bridge.health_check()
        )

        return {

            "version":
                self.VERSION,

            "jalwe_root":
                str(
                    JALWE_ROOT
                ),

            "bridge_file_exists":
                BRIDGE_FILE.exists(),

            "database":
                str(
                    DATABASE_PATH
                ),

            "bridge_ok":
                bridge_health.get(
                    "ok",
                    False,
                ),

            "research_only":
                True,

            "order_execution_enabled":
                False,
        }


# ============================================================
# STANDALONE
# ============================================================

if __name__ == "__main__":

    client = (
        JalweBridgeClient()
    )

    print(
        client.health_check()
    )
