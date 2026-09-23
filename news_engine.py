from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

import requests


logger = logging.getLogger(__name__)


# ============================================================
# NEWS ENGINE
# APEX -> RESEARCH PROVIDER FOR JALWE
# ============================================================

class NewsEngine:
    """
    APEX News Engine V2

    ROLE:
        Collect and analyze news only.

    It does NOT:
        - buy
        - sell
        - submit broker orders
        - tell JALWE to execute

    Output can later be consumed by JALWE as one
    research input among many.
    """

    NEWS_URL = (
        "https://data.alpaca.markets/v1beta1/news"
    )

    # ========================================================
    # KEYWORD GROUPS
    # ========================================================

    POSITIVE_KEYWORDS = {
        "growth": 0.15,
        "beat": 0.20,
        "beats": 0.20,
        "upgrade": 0.20,
        "upgraded": 0.20,
        "partnership": 0.20,
        "approval": 0.25,
        "approved": 0.25,
        "record": 0.15,
        "profit": 0.15,
        "profits": 0.15,
        "surge": 0.15,
        "strong": 0.10,
        "contract": 0.15,
        "acquisition": 0.15,
        "launch": 0.10,
        "expansion": 0.10,
        "raises guidance": 0.30,
        "raised guidance": 0.30,
    }

    NEGATIVE_KEYWORDS = {
        "miss": -0.20,
        "misses": -0.20,
        "lawsuit": -0.25,
        "downgrade": -0.20,
        "downgraded": -0.20,
        "investigation": -0.25,
        "loss": -0.15,
        "losses": -0.15,
        "recall": -0.25,
        "fraud": -0.35,
        "bankruptcy": -0.50,
        "offering": -0.20,
        "dilution": -0.30,
        "cuts guidance": -0.30,
        "cut guidance": -0.30,
        "warning": -0.15,
        "weak": -0.10,
    }

    HIGH_IMPACT_KEYWORDS = {
        "fda": "FDA",
        "approval": "APPROVAL",
        "earnings": "EARNINGS",
        "guidance": "GUIDANCE",
        "acquisition": "M&A",
        "acquire": "M&A",
        "merger": "M&A",
        "contract": "CONTRACT",
        "partnership": "PARTNERSHIP",
        "lawsuit": "LEGAL",
        "investigation": "LEGAL",
        "offering": "OFFERING",
        "bankruptcy": "BANKRUPTCY",
        "recall": "RECALL",
    }

    # ========================================================
    # INIT
    # ========================================================

    def __init__(self) -> None:

        # ----------------------------------------------------
        # Compatibility:
        # old APEX env names + new JALWE env names
        # ----------------------------------------------------

        self.api_key = (
            os.getenv("APCA_API_KEY_ID")
            or
            os.getenv("ALPACA_API_KEY")
            or
            ""
        ).strip()

        self.api_secret = (
            os.getenv("APCA_API_SECRET_KEY")
            or
            os.getenv("ALPACA_SECRET_KEY")
            or
            ""
        ).strip()

        self.base_url = (
            os.getenv(
                "APCA_API_BASE_URL"
            )
            or
            os.getenv(
                "ALPACA_BASE_URL"
            )
            or
            "https://paper-api.alpaca.markets"
        ).strip()

        self.news_url = (
            self.NEWS_URL
        )

    # ========================================================
    # CREDENTIAL STATUS
    # ========================================================

    def credentials_ready(
        self,
    ) -> bool:

        return bool(
            self.api_key
            and
            self.api_secret
        )

    # ========================================================
    # HEADERS
    # ========================================================

    def _headers(
        self,
    ) -> dict[str, str]:

        return {
            "APCA-API-KEY-ID": (
                self.api_key
            ),
            "APCA-API-SECRET-KEY": (
                self.api_secret
            ),
        }

    # ========================================================
    # NORMALIZE SYMBOL
    # ========================================================

    @staticmethod
    def _normalize_symbol(
        symbol: str,
    ) -> str:

        value = str(
            symbol or ""
        ).strip().upper()

        if not value:
            raise ValueError(
                "Symbol cannot be empty."
            )

        return value

    # ========================================================
    # PARSE TIME
    # ========================================================

    @staticmethod
    def _parse_time(
        value: Any,
    ) -> Optional[datetime]:

        if not value:
            return None

        try:

            text = str(
                value
            ).strip()

            if text.endswith("Z"):
                text = (
                    text[:-1]
                    + "+00:00"
                )

            dt = (
                datetime.fromisoformat(
                    text
                )
            )

            if dt.tzinfo is None:
                dt = dt.replace(
                    tzinfo=timezone.utc
                )

            return dt

        except Exception:
            return None

    # ========================================================
    # SENTIMENT FOR ONE HEADLINE
    # ========================================================

    def _score_text(
        self,
        text: str,
    ) -> float:

        text = str(
            text or ""
        ).lower()

        score = 0.0

        for (
            keyword,
            weight,
        ) in (
            self.POSITIVE_KEYWORDS
            .items()
        ):

            if keyword in text:
                score += weight

        for (
            keyword,
            weight,
        ) in (
            self.NEGATIVE_KEYWORDS
            .items()
        ):

            if keyword in text:
                score += weight

        return max(
            -1.0,
            min(
                score,
                1.0,
            ),
        )

    # ========================================================
    # CATALYST DETECTION
    # ========================================================

    def _detect_catalysts(
        self,
        text: str,
    ) -> list[str]:

        text = str(
            text or ""
        ).lower()

        catalysts: list[str] = []

        for (
            keyword,
            catalyst,
        ) in (
            self.HIGH_IMPACT_KEYWORDS
            .items()
        ):

            if (
                keyword in text
                and
                catalyst not in catalysts
            ):
                catalysts.append(
                    catalyst
                )

        return catalysts

    # ========================================================
    # SENTIMENT LABEL
    # ========================================================

    @staticmethod
    def _sentiment_label(
        score: float,
    ) -> str:

        if score >= 0.20:
            return "BULLISH"

        if score <= -0.20:
            return "BEARISH"

        if (
            -0.20
            < score
            < 0.20
        ):
            return "NEUTRAL"

        return "UNKNOWN"

    # ========================================================
    # NEWS SCORE 0 -> 100
    # ========================================================

    @staticmethod
    def _news_score(
        sentiment_score: float,
        news_count: int,
        catalyst_count: int,
    ) -> float:

        # Neutral baseline = 50
        score = (
            50.0
            +
            sentiment_score
            * 35.0
        )

        # Activity bonus
        score += min(
            news_count * 2.0,
            8.0,
        )

        # Catalyst bonus
        score += min(
            catalyst_count * 3.0,
            12.0,
        )

        return round(
            max(
                0.0,
                min(
                    score,
                    100.0,
                ),
            ),
            2,
        )

    # ========================================================
    # CONFIDENCE
    # ========================================================

    @staticmethod
    def _confidence(
        *,
        news_count: int,
        scored_items: int,
        catalyst_count: int,
    ) -> float:

        if news_count <= 0:
            return 0.0

        coverage = (
            scored_items
            /
            news_count
        )

        confidence = (
            0.30
            +
            min(
                news_count,
                5,
            )
            * 0.08
            +
            coverage
            * 0.20
            +
            min(
                catalyst_count,
                3,
            )
            * 0.05
        )

        return round(
            min(
                confidence,
                0.95,
            ),
            3,
        )

    # ========================================================
    # FETCH SYMBOL NEWS
    # ========================================================

    def fetch_symbol_news(
        self,
        symbol: str,
        *,
        limit: int = 10,
    ) -> dict[str, Any]:

        symbol = (
            self._normalize_symbol(
                symbol
            )
        )

        # ----------------------------------------------------
        # Missing credentials
        # ----------------------------------------------------

        if not self.credentials_ready():

            return {
                "symbol": symbol,
                "sentiment_score": None,
                "sentiment": "UNKNOWN",
                "news_score": None,
                "confidence": 0.0,
                "catalyst_detected": False,
                "catalysts": [],
                "news_count": 0,
                "headlines": [],
                "risk_flags": [
                    "NEWS_CREDENTIALS_MISSING"
                ],
                "latest_news_at": None,
                "status": (
                    "CREDENTIALS_MISSING"
                ),
            }

        params = {
            "symbols": symbol,
            "limit": max(
                1,
                min(
                    int(limit),
                    50,
                ),
            ),
            "sort": "desc",
        }

        try:

            response = requests.get(
                self.news_url,
                headers=self._headers(),
                params=params,
                timeout=8,
            )

        except requests.RequestException as exc:

            logger.warning(
                "News request failed for %s: %s",
                symbol,
                exc,
            )

            return {
                "symbol": symbol,
                "sentiment_score": None,
                "sentiment": "UNKNOWN",
                "news_score": None,
                "confidence": 0.0,
                "catalyst_detected": False,
                "catalysts": [],
                "news_count": 0,
                "headlines": [],
                "risk_flags": [
                    "NEWS_API_UNAVAILABLE"
                ],
                "latest_news_at": None,
                "status": (
                    "API_ERROR"
                ),
            }

        # ----------------------------------------------------
        # HTTP error
        # ----------------------------------------------------

        if response.status_code != 200:

            logger.warning(
                "News API returned HTTP %s "
                "for %s",
                response.status_code,
                symbol,
            )

            return {
                "symbol": symbol,
                "sentiment_score": None,
                "sentiment": "UNKNOWN",
                "news_score": None,
                "confidence": 0.0,
                "catalyst_detected": False,
                "catalysts": [],
                "news_count": 0,
                "headlines": [],
                "risk_flags": [
                    (
                        "NEWS_HTTP_"
                        + str(
                            response.status_code
                        )
                    )
                ],
                "latest_news_at": None,
                "status": "HTTP_ERROR",
            }

        # ----------------------------------------------------
        # JSON
        # ----------------------------------------------------

        try:

            data = response.json()

        except ValueError:

            return {
                "symbol": symbol,
                "sentiment_score": None,
                "sentiment": "UNKNOWN",
                "news_score": None,
                "confidence": 0.0,
                "catalyst_detected": False,
                "catalysts": [],
                "news_count": 0,
                "headlines": [],
                "risk_flags": [
                    "NEWS_INVALID_JSON"
                ],
                "latest_news_at": None,
                "status": "INVALID_JSON",
            }

        news_items = (
            data.get(
                "news",
                []
            )
            or []
        )

        # ----------------------------------------------------
        # Valid API response, but no news
        # ----------------------------------------------------

        if not news_items:

            return {
                "symbol": symbol,
                "sentiment_score": 0.0,
                "sentiment": "NEUTRAL",
                "news_score": 50.0,
                "confidence": 0.0,
                "catalyst_detected": False,
                "catalysts": [],
                "news_count": 0,
                "headlines": [],
                "risk_flags": [],
                "latest_news_at": None,
                "status": "NO_NEWS",
            }

        # ----------------------------------------------------
        # Analyze items
        # ----------------------------------------------------

        scores: list[float] = []

        headlines: list[str] = []

        catalysts: list[str] = []

        latest_news_time: Optional[
            datetime
        ] = None

        positive_items = 0
        negative_items = 0
        scored_items = 0

        for item in news_items:

            headline = str(
                item.get(
                    "headline",
                    "",
                )
                or ""
            ).strip()

            summary = str(
                item.get(
                    "summary",
                    "",
                )
                or ""
            ).strip()

            combined_text = (
                headline
                + " "
                + summary
            )

            if headline:
                headlines.append(
                    headline
                )

            item_score = (
                self._score_text(
                    combined_text
                )
            )

            scores.append(
                item_score
            )

            if item_score > 0:
                positive_items += 1
                scored_items += 1

            elif item_score < 0:
                negative_items += 1
                scored_items += 1

            item_catalysts = (
                self._detect_catalysts(
                    combined_text
                )
            )

            for catalyst in (
                item_catalysts
            ):

                if catalyst not in catalysts:
                    catalysts.append(
                        catalyst
                    )

            created_at = (
                self._parse_time(
                    item.get(
                        "created_at"
                    )
                    or
                    item.get(
                        "updated_at"
                    )
                )
            )

            if created_at is not None:

                if (
                    latest_news_time
                    is None
                    or
                    created_at
                    >
                    latest_news_time
                ):
                    latest_news_time = (
                        created_at
                    )

        # ----------------------------------------------------
        # Aggregate sentiment
        # ----------------------------------------------------

        if scores:

            sentiment_score = (
                sum(scores)
                /
                len(scores)
            )

        else:
            sentiment_score = 0.0

        sentiment_score = round(
            max(
                -1.0,
                min(
                    sentiment_score,
                    1.0,
                ),
            ),
            4,
        )

        sentiment = (
            self._sentiment_label(
                sentiment_score
            )
        )

        news_count = len(
            news_items
        )

        news_score = (
            self._news_score(
                sentiment_score,
                news_count,
                len(catalysts),
            )
        )

        confidence = (
            self._confidence(
                news_count=news_count,
                scored_items=scored_items,
                catalyst_count=(
                    len(catalysts)
                ),
            )
        )

        # ----------------------------------------------------
        # Risk flags
        # ----------------------------------------------------

        risk_flags: list[str] = []

        if negative_items > positive_items:
            risk_flags.append(
                "NEGATIVE_NEWS_DOMINANCE"
            )

        if "LEGAL" in catalysts:
            risk_flags.append(
                "LEGAL_CATALYST"
            )

        if "OFFERING" in catalysts:
            risk_flags.append(
                "DILUTION_OR_OFFERING_RISK"
            )

        if "BANKRUPTCY" in catalysts:
            risk_flags.append(
                "BANKRUPTCY_RISK"
            )

        if "RECALL" in catalysts:
            risk_flags.append(
                "RECALL_RISK"
            )

        latest_news_at = (
            latest_news_time
            .isoformat()
            if latest_news_time
            is not None
            else None
        )

        return {
            "symbol": symbol,

            "sentiment_score": (
                float(
                    sentiment_score
                )
            ),

            "sentiment": sentiment,

            "news_score": (
                float(
                    news_score
                )
            ),

            "confidence": (
                float(
                    confidence
                )
            ),

            "catalyst_detected": (
                bool(catalysts)
            ),

            "catalysts": catalysts,

            "news_count": (
                news_count
            ),

            "headlines": (
                headlines[:10]
            ),

            "positive_items": (
                positive_items
            ),

            "negative_items": (
                negative_items
            ),

            "risk_flags": (
                risk_flags
            ),

            "latest_news_at": (
                latest_news_at
            ),

            "status": "SUCCESS",
        }


# ============================================================
# COMPATIBILITY HELPER
# ============================================================

def analyze_news_catalyst(
    symbol: str,
) -> dict[str, Any]:

    try:

        engine = (
            NewsEngine()
        )

        return (
            engine
            .fetch_symbol_news(
                symbol
            )
        )

    except Exception as exc:

        logger.exception(
            "Error in analyze_news_catalyst "
            "for %s",
            symbol,
        )

        return {
            "symbol": str(
                symbol or ""
            ).upper(),

            "sentiment_score": None,

            "sentiment": "UNKNOWN",

            "news_score": None,

            "confidence": 0.0,

            "catalyst_detected": False,

            "catalysts": [],

            "news_count": 0,

            "headlines": [],

            "risk_flags": [
                "NEWS_ENGINE_ERROR"
            ],

            "latest_news_at": None,

            "status": "ERROR",

            "error": str(
                exc
            ),
        }
