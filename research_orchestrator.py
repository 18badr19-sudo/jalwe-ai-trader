from __future__ import annotations

import logging

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional


from scanner_engine import ScannerEngine
from pre_breakout_engine import PreBreakoutEngine
from news_engine import NewsEngine
from liquidity_engine import LiquidityEngine
from ai_engine import AIEngine


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger(__name__)


# ============================================================
# RESEARCH PACKET
# ============================================================

@dataclass
class ResearchPacket:

    symbol: str

    source: str = "APEX"

    research_score: float = 0.0
    confidence: float = 0.0

    bias: str = "MIXED"
    verdict: str = "REJECT"

    # --------------------------------------------------------
    # RADAR
    # --------------------------------------------------------

    radar_score: Optional[float] = None
    radar_rvol: Optional[float] = None
    radar_change_pct: Optional[float] = None
    radar_price: Optional[float] = None

    # --------------------------------------------------------
    # PREBREAKOUT
    # --------------------------------------------------------

    prebreakout_score: Optional[float] = None
    prebreakout_confidence: Optional[float] = None
    prebreakout_status: Optional[str] = None

    score_5m: Optional[float] = None
    score_30m: Optional[float] = None
    score_1h: Optional[float] = None
    score_1d: Optional[float] = None

    # --------------------------------------------------------
    # NEWS
    # --------------------------------------------------------

    news_score: Optional[float] = None
    news_confidence: Optional[float] = None
    news_sentiment: str = "UNKNOWN"
    news_status: str = "UNKNOWN"

    catalysts: list[str] = field(
        default_factory=list
    )

    headlines: list[str] = field(
        default_factory=list
    )

    # --------------------------------------------------------
    # LIQUIDITY
    # --------------------------------------------------------

    liquidity_score: Optional[float] = None
    liquidity_confidence: Optional[float] = None
    liquidity_bias: str = "UNKNOWN"

    buy_pressure: Optional[float] = None
    sell_pressure: Optional[float] = None

    money_flow: Optional[float] = None
    volume_acceleration: Optional[float] = None

    price_volume_confirmation: bool = False

    absorption: bool = False
    distribution: bool = False

    # --------------------------------------------------------
    # AI RESEARCH
    # --------------------------------------------------------

    evidence: list[str] = field(
        default_factory=list
    )

    conflicts: list[str] = field(
        default_factory=list
    )

    risk_flags: list[str] = field(
        default_factory=list
    )

    alignment_bonus: float = 0.0
    risk_penalty: float = 0.0
    prebreakout_penalty: float = 0.0

    critical_risk: bool = False

    # --------------------------------------------------------
    # METADATA
    # --------------------------------------------------------

    created_at: str = field(
        default_factory=lambda: (
            datetime.now(
                timezone.utc
            ).isoformat()
        )
    )

    order_execution_enabled: bool = False


    def to_dict(
        self,
    ) -> dict[str, Any]:

        return asdict(
            self
        )


# ============================================================
# RESEARCH CYCLE RESULT
# ============================================================

@dataclass
class ResearchCycleResult:

    status: str

    radar_count: int = 0

    valid_prebreakout_count: int = 0

    deep_research_count: int = 0

    packet_count: int = 0

    shortlisted_count: int = 0

    packets: list[
        ResearchPacket
    ] = field(
        default_factory=list
    )

    shortlist: list[
        ResearchPacket
    ] = field(
        default_factory=list
    )

    errors: list[str] = field(
        default_factory=list
    )

    started_at: Optional[str] = None
    finished_at: Optional[str] = None


# ============================================================
# RESEARCH ORCHESTRATOR
# ============================================================

class ResearchOrchestrator:
    """
    APEX RESEARCH ORCHESTRATOR V1

    PIPELINE:

        ScannerEngine V3
            ↓
        Top Ranked Candidates
            ↓
        PreBreakout
        5M + 30M + 1H + 1D
            ↓
        Data Confidence Filter
            ↓
        Top Deep Research Candidates
            ↓
        NewsEngine V3
            ↓
        LiquidityEngine V2
            ↓
        AIEngine V3
            ↓
        ResearchPacket
            ↓
        JALWE

    IMPORTANT:

        APEX is research-only.

        This module NEVER:
            - buys
            - sells
            - submits orders
            - manages positions

        JALWE remains the final decision-maker.
    """

    VERSION = "1.0"

    DEFAULT_RADAR_TOP_N = 20

    DEFAULT_DEEP_RESEARCH_TOP_N = 5

    DEFAULT_MIN_PRE_CONFIDENCE = 75.0


    # ========================================================
    # INIT
    # ========================================================

    def __init__(
        self,
        *,
        scanner: Optional[
            ScannerEngine
        ] = None,
        prebreakout: Optional[
            PreBreakoutEngine
        ] = None,
        news: Optional[
            NewsEngine
        ] = None,
        liquidity: Optional[
            LiquidityEngine
        ] = None,
        ai: Optional[
            AIEngine
        ] = None,
    ) -> None:

        self.scanner = (
            scanner
            or
            ScannerEngine()
        )

        self.prebreakout = (
            prebreakout
            or
            PreBreakoutEngine(
                self.scanner.alpaca,
                None,
            )
        )

        self.news = (
            news
            or
            NewsEngine()
        )

        self.liquidity = (
            liquidity
            or
            LiquidityEngine(
                self.scanner.alpaca
            )
        )

        self.ai = (
            ai
            or
            AIEngine()
        )


    # ========================================================
    # RADAR MAP
    # ========================================================

    @staticmethod
    def _radar_map(
        radar_result: Any,
    ) -> dict[
        str,
        Any,
    ]:

        output = {}

        candidates = getattr(
            radar_result,
            "ranked_candidates",
            [],
        )

        for candidate in candidates:

            symbol = str(
                getattr(
                    candidate,
                    "symbol",
                    "",
                )
                or
                ""
            ).strip().upper()

            if symbol:

                output[
                    symbol
                ] = candidate

        return output


    # ========================================================
    # BUILD PACKET
    # ========================================================

    def _build_packet(
        self,
        *,
        candidate: Any,
        pre_result: Any,
        news_result: dict[str, Any],
        liquidity_result: Any,
        ai_result: dict[str, Any],
    ) -> ResearchPacket:

        symbol = str(
            ai_result.get(
                "symbol",
                "",
            )
        ).strip().upper()

        return ResearchPacket(

            symbol=symbol,

            source="APEX",

            # ------------------------------------------------
            # AI
            # ------------------------------------------------

            research_score=float(
                ai_result.get(
                    "research_score",
                    0.0,
                )
                or
                0.0
            ),

            confidence=float(
                ai_result.get(
                    "confidence",
                    0.0,
                )
                or
                0.0
            ),

            bias=str(
                ai_result.get(
                    "bias",
                    "MIXED",
                )
            ),

            verdict=str(
                ai_result.get(
                    "verdict",
                    "REJECT",
                )
            ),

            # ------------------------------------------------
            # RADAR
            # ------------------------------------------------

            radar_score=getattr(
                candidate,
                "rank_score",
                None,
            ),

            radar_rvol=getattr(
                candidate,
                "relative_volume",
                None,
            ),

            radar_change_pct=getattr(
                candidate,
                "change_pct",
                None,
            ),

            radar_price=getattr(
                candidate,
                "price",
                None,
            ),

            # ------------------------------------------------
            # PREBREAKOUT
            # ------------------------------------------------

            prebreakout_score=getattr(
                pre_result,
                "score",
                None,
            ),

            prebreakout_confidence=getattr(
                pre_result,
                "data_confidence",
                None,
            ),

            prebreakout_status=getattr(
                pre_result,
                "status",
                None,
            ),

            score_5m=getattr(
                pre_result,
                "score_5m",
                None,
            ),

            score_30m=getattr(
                pre_result,
                "score_30m",
                None,
            ),

            score_1h=getattr(
                pre_result,
                "score_1h",
                None,
            ),

            score_1d=getattr(
                pre_result,
                "score_1d",
                None,
            ),

            # ------------------------------------------------
            # NEWS
            # ------------------------------------------------

            news_score=(
                news_result.get(
                    "news_score"
                )
            ),

            news_confidence=(
                (
                    float(
                        news_result.get(
                            "confidence",
                            0.0,
                        )
                        or
                        0.0
                    )
                    *
                    100.0
                )
            ),

            news_sentiment=str(
                news_result.get(
                    "sentiment",
                    "UNKNOWN",
                )
            ),

            news_status=str(
                news_result.get(
                    "status",
                    "UNKNOWN",
                )
            ),

            catalysts=list(
                news_result.get(
                    "catalysts",
                    [],
                )
                or
                []
            ),

            headlines=list(
                news_result.get(
                    "headlines",
                    [],
                )
                or
                []
            )[:5],

            # ------------------------------------------------
            # LIQUIDITY
            # ------------------------------------------------

            liquidity_score=getattr(
                liquidity_result,
                "liquidity_score",
                None,
            ),

            liquidity_confidence=(
                float(
                    getattr(
                        liquidity_result,
                        "confidence",
                        0.0,
                    )
                    or
                    0.0
                )
                *
                100.0
            ),

            liquidity_bias=str(
                getattr(
                    liquidity_result,
                    "liquidity_bias",
                    "UNKNOWN",
                )
            ),

            buy_pressure=getattr(
                liquidity_result,
                "buy_pressure",
                None,
            ),

            sell_pressure=getattr(
                liquidity_result,
                "sell_pressure",
                None,
            ),

            money_flow=getattr(
                liquidity_result,
                "money_flow",
                None,
            ),

            volume_acceleration=getattr(
                liquidity_result,
                "volume_acceleration",
                None,
            ),

            price_volume_confirmation=bool(
                getattr(
                    liquidity_result,
                    "price_volume_confirmation",
                    False,
                )
            ),

            absorption=bool(
                getattr(
                    liquidity_result,
                    "absorption",
                    False,
                )
            ),

            distribution=bool(
                getattr(
                    liquidity_result,
                    "distribution",
                    False,
                )
            ),

            # ------------------------------------------------
            # AI DETAILS
            # ------------------------------------------------

            evidence=list(
                ai_result.get(
                    "evidence",
                    [],
                )
                or
                []
            ),

            conflicts=list(
                ai_result.get(
                    "conflicts",
                    [],
                )
                or
                []
            ),

            risk_flags=list(
                ai_result.get(
                    "risk_flags",
                    [],
                )
                or
                []
            ),

            alignment_bonus=float(
                ai_result.get(
                    "alignment_bonus",
                    0.0,
                )
                or
                0.0
            ),

            risk_penalty=float(
                ai_result.get(
                    "risk_penalty",
                    0.0,
                )
                or
                0.0
            ),

            prebreakout_penalty=float(
                ai_result.get(
                    "prebreakout_penalty",
                    0.0,
                )
                or
                0.0
            ),

            critical_risk=bool(
                ai_result.get(
                    "critical_risk",
                    False,
                )
            ),

            order_execution_enabled=False,
        )


    # ========================================================
    # RUN CYCLE
    # ========================================================

    def run_cycle(
        self,
        *,
        radar_top_n: int = (
            DEFAULT_RADAR_TOP_N
        ),
        deep_research_top_n: int = (
            DEFAULT_DEEP_RESEARCH_TOP_N
        ),
        min_pre_confidence: float = (
            DEFAULT_MIN_PRE_CONFIDENCE
        ),
    ) -> ResearchCycleResult:

        started_at = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        result = ResearchCycleResult(

            status="STARTED",

            started_at=started_at,
        )

        # ====================================================
        # 1. SCANNER
        # ====================================================

        try:

            radar = (
                self.scanner
                .run_radar(
                    top_n=(
                        radar_top_n
                    )
                )
            )

        except Exception as exc:

            result.status = (
                "SCANNER_ERROR"
            )

            result.errors.append(
                str(
                    exc
                )
            )

            result.finished_at = (
                datetime.now(
                    timezone.utc
                ).isoformat()
            )

            return result

        if (
            getattr(
                radar,
                "status",
                None,
            )
            !=
            "SUCCESS"
        ):

            result.status = (
                "NO_RADAR_RESULTS"
            )

            radar_error = getattr(
                radar,
                "error",
                None,
            )

            if radar_error:

                result.errors.append(
                    str(
                        radar_error
                    )
                )

            result.finished_at = (
                datetime.now(
                    timezone.utc
                ).isoformat()
            )

            return result

        radar_candidates = list(
            getattr(
                radar,
                "ranked_candidates",
                [],
            )
            or
            []
        )

        result.radar_count = len(
            radar_candidates
        )

        if not radar_candidates:

            result.status = (
                "NO_RADAR_RESULTS"
            )

            result.finished_at = (
                datetime.now(
                    timezone.utc
                ).isoformat()
            )

            return result

        # ====================================================
        # 2. PREBREAKOUT
        # ====================================================

        pre_results = []

        for candidate in (
            radar_candidates
        ):

            symbol = str(
                getattr(
                    candidate,
                    "symbol",
                    "",
                )
            ).strip().upper()

            if not symbol:

                continue

            try:

                pre = (
                    self.prebreakout
                    .analyze_symbol(

                        symbol,

                        radar_context=(
                            candidate
                        ),
                    )
                )

            except Exception as exc:

                result.errors.append(

                    f"{symbol}:PRE:"
                    f"{str(exc)}"
                )

                continue

            confidence = float(
                getattr(
                    pre,
                    "data_confidence",
                    0.0,
                )
                or
                0.0
            )

            if (
                confidence
                <
                float(
                    min_pre_confidence
                )
            ):

                continue

            pre_results.append(
                (
                    candidate,
                    pre,
                )
            )

        result.valid_prebreakout_count = (
            len(
                pre_results
            )
        )

        # ----------------------------------------------------
        # Best technical research first
        # ----------------------------------------------------

        pre_results.sort(

            key=lambda item: (

                float(
                    getattr(
                        item[1],
                        "score",
                        0.0,
                    )
                    or
                    0.0
                ),

                float(
                    getattr(
                        item[1],
                        "data_confidence",
                        0.0,
                    )
                    or
                    0.0
                ),

                float(
                    getattr(
                        item[0],
                        "rank_score",
                        0.0,
                    )
                    or
                    0.0
                ),
            ),

            reverse=True,
        )

        deep_candidates = (
            pre_results[
                :max(
                    1,
                    int(
                        deep_research_top_n
                    ),
                )
            ]
        )

        result.deep_research_count = (
            len(
                deep_candidates
            )
        )

        if not deep_candidates:

            result.status = (
                "NO_DEEP_RESEARCH_CANDIDATES"
            )

            result.finished_at = (
                datetime.now(
                    timezone.utc
                ).isoformat()
            )

            return result

        # ====================================================
        # 3. NEWS
        # 4. LIQUIDITY
        # 5. AI
        # ====================================================

        packets: list[
            ResearchPacket
        ] = []

        for (
            candidate,
            pre,
        ) in deep_candidates:

            symbol = str(
                getattr(
                    candidate,
                    "symbol",
                    "",
                )
            ).strip().upper()

            # ------------------------------------------------
            # NEWS
            # ------------------------------------------------

            try:

                news = (
                    self.news
                    .fetch_symbol_news(
                        symbol
                    )
                )

            except Exception as exc:

                logger.exception(
                    "News failure for %s",
                    symbol,
                )

                news = {

                    "symbol":
                        symbol,

                    "news_score":
                        None,

                    "confidence":
                        0.0,

                    "sentiment":
                        "UNKNOWN",

                    "status":
                        "ERROR",

                    "catalysts":
                        [],

                    "headlines":
                        [],

                    "risk_flags":
                        [
                            "NEWS_ENGINE_ERROR"
                        ],
                }

                result.errors.append(

                    f"{symbol}:NEWS:"
                    f"{str(exc)}"
                )

            # ------------------------------------------------
            # LIQUIDITY
            # ------------------------------------------------

            try:

                liquidity = (
                    self.liquidity
                    .analyze_symbol(
                        symbol
                    )
                )

            except Exception as exc:

                logger.exception(
                    "Liquidity failure for %s",
                    symbol,
                )

                result.errors.append(

                    f"{symbol}:LIQUIDITY:"
                    f"{str(exc)}"
                )

                continue

            # ------------------------------------------------
            # AI
            # ------------------------------------------------

            try:

                ai_result = (
                    self.ai
                    .evaluate_research(

                        symbol,

                        prebreakout_result=(
                            pre
                        ),

                        news_result=(
                            news
                        ),

                        liquidity_result=(
                            liquidity
                        ),
                    )
                )

            except Exception as exc:

                logger.exception(
                    "AI failure for %s",
                    symbol,
                )

                result.errors.append(

                    f"{symbol}:AI:"
                    f"{str(exc)}"
                )

                continue

            if (
                ai_result.get(
                    "status"
                )
                !=
                "SUCCESS"
            ):

                result.errors.append(

                    f"{symbol}:AI_STATUS:"
                    f"{ai_result.get('status')}"
                )

                continue

            # ------------------------------------------------
            # PACKET
            # ------------------------------------------------

            packet = (
                self._build_packet(

                    candidate=(
                        candidate
                    ),

                    pre_result=(
                        pre
                    ),

                    news_result=(
                        news
                    ),

                    liquidity_result=(
                        liquidity
                    ),

                    ai_result=(
                        ai_result
                    ),
                )
            )

            packets.append(
                packet
            )

        # ====================================================
        # FINAL SORT
        # ====================================================

        packets.sort(

            key=lambda packet: (

                packet.research_score,

                packet.confidence,

                packet.prebreakout_score
                or
                0.0,
            ),

            reverse=True,
        )

        result.packets = (
            packets
        )

        result.packet_count = (
            len(
                packets
            )
        )

        # ====================================================
        # SHORTLIST
        #
        # REJECT is NOT forwarded as a positive candidate.
        # WATCH can still be forwarded for monitoring.
        # ====================================================

        allowed_verdicts = {

            "WATCH",

            "RESEARCH_CANDIDATE",

            "HIGH_PRIORITY_RESEARCH",
        }

        shortlist = [

            packet

            for packet
            in packets

            if (
                packet.verdict
                in
                allowed_verdicts

                and

                not packet.critical_risk
            )
        ]

        result.shortlist = (
            shortlist
        )

        result.shortlisted_count = (
            len(
                shortlist
            )
        )

        result.status = (
            "SUCCESS"
        )

        result.finished_at = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        return result


    # ========================================================
    # SIMPLE RUN
    # ========================================================

    def run_once(
        self,
    ) -> ResearchCycleResult:

        return (
            self.run_cycle()
        )


    # ========================================================
    # HEALTH CHECK
    # ========================================================

    def health_check(
        self,
    ) -> dict[str, Any]:

        return {

            "version":
                self.VERSION,

            "role":
                "APEX_RESEARCH_ORCHESTRATOR",

            "scanner":
                self.scanner.health_check(),

            "prebreakout":
                self.prebreakout.health_check(),

            "news":
                self.news.health_check(),

            "liquidity":
                self.liquidity.health_check(),

            "ai":
                self.ai.health_check(),

            "pipeline": [

                "SCANNER",

                "PREBREAKOUT",

                "NEWS",

                "LIQUIDITY",

                "AI",

                "RESEARCH_PACKET",
            ],

            "order_execution_enabled":
                False,
        }


# ============================================================
# STANDALONE TEST
# ============================================================

if __name__ == "__main__":

    engine = (
        ResearchOrchestrator()
    )

    cycle = (
        engine.run_cycle()
    )

    print(
        "======================================"
    )

    print(
        "APEX RESEARCH ORCHESTRATOR V1"
    )

    print(
        "======================================"
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

    print()

    for (
        index,
        packet,
    ) in enumerate(
        cycle.packets,
        start=1,
    ):

        print(

            index,

            packet.symbol,

            "| SCORE:",
            packet.research_score,

            "| CONF:",
            packet.confidence,

            "| BIAS:",
            packet.bias,

            "| VERDICT:",
            packet.verdict,

            "| PRE:",
            packet.prebreakout_score,

            "| NEWS:",
            packet.news_score,

            "| LIQ:",
            packet.liquidity_score,
        )

    if cycle.errors:

        print()

        print(
            "ERRORS:"
        )

        for error in (
            cycle.errors
        ):

            print(
                "-",
                error,
            )
