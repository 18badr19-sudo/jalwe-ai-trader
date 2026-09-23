from __future__ import annotations

import logging
import os
import time

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import alpaca_trade_api as tradeapi
from dotenv import load_dotenv


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger(__name__)


# ============================================================
# LOAD LOCAL .ENV
# ============================================================

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
)

ENV_FILE = (
    BASE_DIR
    / ".env"
)

load_dotenv(
    ENV_FILE
)


# ============================================================
# SCAN RESULT
# ============================================================

@dataclass
class MarketScanResult:
    symbols: list[str]

    status: str

    source: str

    total_assets_received: int

    total_symbols_accepted: int

    used_fallback: bool

    error: Optional[str] = None


# ============================================================
# MARKET SCANNER
# ============================================================

class MarketScanner:
    """
    APEX MARKET SCANNER V2.1

    ROLE:
        Build the tradable US equity universe
        for Apex research.

    IMPORTANT:
        This scanner DOES NOT:
        - Buy
        - Sell
        - Submit orders
        - Manage positions

    It is research-only.

    Supports both environment naming styles:

        OLD APEX:
            APCA_API_KEY_ID
            APCA_API_SECRET_KEY
            APCA_API_BASE_URL

        NEW JALWE:
            ALPACA_API_KEY
            ALPACA_SECRET_KEY
            ALPACA_BASE_URL
    """

    # ========================================================
    # EXCHANGES
    # ========================================================

    ALLOWED_EXCHANGES = {
        "NASDAQ",
        "NYSE",
        "ARCA",
        "BATS",
        "AMEX",
    }

    # ========================================================
    # FALLBACK
    # ========================================================

    FALLBACK_SYMBOLS = [
        "AAPL",
        "TSLA",
        "NVDA",
        "AMD",
        "MSFT",
        "AMZN",
        "META",
        "GOOGL",
        "NFLX",
        "PLTR",
        "MARA",
        "RIOT",
        "COIN",
        "JPM",
        "BAC",
        "XOM",
        "CVX",
        "DIS",
        "PYPL",
        "INTC",
        "QCOM",
        "BA",
        "IBM",
        "ORCL",
        "CRM",
        "NKE",
        "SHOP",
        "UBER",
        "ABNB",
        "SQ",
    ]

    # ========================================================
    # INIT
    # ========================================================

    def __init__(
        self,
        *,
        cache_seconds: int = 600,
    ) -> None:

        # ----------------------------------------------------
        # Support old APEX variable names
        # AND new JALWE variable names.
        # ----------------------------------------------------

        self.api_key = (
            os.getenv(
                "APCA_API_KEY_ID"
            )
            or
            os.getenv(
                "ALPACA_API_KEY"
            )
            or
            ""
        ).strip()

        self.api_secret = (
            os.getenv(
                "APCA_API_SECRET_KEY"
            )
            or
            os.getenv(
                "ALPACA_SECRET_KEY"
            )
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

        self.cache_seconds = max(
            0,
            int(
                cache_seconds
            ),
        )

        self._cached_result: Optional[
            MarketScanResult
        ] = None

        self._cache_time: float = 0.0

        self.api: Optional[
            tradeapi.REST
        ] = None

        self._initialize_api()

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
    # INITIALIZE ALPACA
    # ========================================================

    def _initialize_api(
        self,
    ) -> None:

        if not self.credentials_ready():

            logger.warning(
                "MarketScanner Alpaca "
                "credentials are missing."
            )

            self.api = None

            return

        # ----------------------------------------------------
        # HARD PAPER CHECK
        # ----------------------------------------------------

        if (
            "paper-api.alpaca.markets"
            not in
            self.base_url.lower()
        ):

            logger.error(
                "MarketScanner blocked because "
                "ALPACA URL is not PAPER."
            )

            self.api = None

            return

        try:

            self.api = (
                tradeapi.REST(
                    self.api_key,
                    self.api_secret,
                    self.base_url,
                    api_version="v2",
                )
            )

        except Exception as exc:

            logger.exception(
                "Failed to initialize Alpaca "
                "REST in MarketScanner: %s",
                exc,
            )

            self.api = None

    # ========================================================
    # NORMALIZE SYMBOL
    # ========================================================

    @staticmethod
    def _normalize_symbol(
        symbol: Any,
    ) -> Optional[str]:

        value = str(
            symbol
            or ""
        ).strip().upper()

        if not value:
            return None

        if len(value) > 15:
            return None

        # ----------------------------------------------------
        # Symbols deliberately excluded for now.
        # ----------------------------------------------------

        blocked_characters = {
            "/",
            ".",
            "^",
            " ",
        }

        if any(
            character
            in value
            for character
            in blocked_characters
        ):

            return None

        allowed_characters = set(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "0123456789-"
        )

        if any(
            character
            not in allowed_characters
            for character
            in value
        ):

            return None

        return value

    # ========================================================
    # NORMALIZE EXCHANGE
    # ========================================================

    @staticmethod
    def _normalize_exchange(
        exchange: Any,
    ) -> str:

        return str(
            exchange
            or ""
        ).strip().upper()

    # ========================================================
    # ASSET FILTER
    # ========================================================

    def _asset_is_allowed(
        self,
        asset: Any,
    ) -> bool:

        if not bool(
            getattr(
                asset,
                "tradable",
                False,
            )
        ):

            return False

        exchange = (
            self._normalize_exchange(
                getattr(
                    asset,
                    "exchange",
                    "",
                )
            )
        )

        if (
            exchange
            not in
            self.ALLOWED_EXCHANGES
        ):

            return False

        symbol = (
            self._normalize_symbol(
                getattr(
                    asset,
                    "symbol",
                    "",
                )
            )
        )

        if symbol is None:
            return False

        return True

    # ========================================================
    # CACHE
    # ========================================================

    def _cache_valid(
        self,
    ) -> bool:

        if (
            self._cached_result
            is None
        ):

            return False

        if (
            self.cache_seconds
            <= 0
        ):

            return False

        age_seconds = (
            time.time()
            -
            self._cache_time
        )

        return bool(
            age_seconds
            <= self.cache_seconds
        )

    def clear_cache(
        self,
    ) -> None:

        self._cached_result = None

        self._cache_time = 0.0

    # ========================================================
    # FALLBACK RESULT
    # ========================================================

    def _fallback_result(
        self,
        *,
        error: str,
        enabled: bool,
        total_assets: int = 0,
    ) -> MarketScanResult:

        # ----------------------------------------------------
        # Fail completely
        # ----------------------------------------------------

        if not enabled:

            return MarketScanResult(
                symbols=[],
                status="ERROR",
                source="NONE",
                total_assets_received=(
                    total_assets
                ),
                total_symbols_accepted=0,
                used_fallback=False,
                error=error,
            )

        # ----------------------------------------------------
        # Controlled fallback
        # ----------------------------------------------------

        symbols = list(
            self.FALLBACK_SYMBOLS
        )

        logger.warning(
            "MarketScanner is using "
            "FALLBACK universe of %s symbols. "
            "This is NOT a full-market scan.",
            len(
                symbols
            ),
        )

        return MarketScanResult(
            symbols=symbols,
            status="FALLBACK",
            source="FALLBACK_STATIC",
            total_assets_received=(
                total_assets
            ),
            total_symbols_accepted=(
                len(
                    symbols
                )
            ),
            used_fallback=True,
            error=error,
        )

    # ========================================================
    # FULL MARKET SCAN
    # ========================================================

    def scan_market(
        self,
        *,
        force_refresh: bool = False,
        allow_fallback: bool = True,
    ) -> MarketScanResult:

        # ----------------------------------------------------
        # Cache
        # ----------------------------------------------------

        if (
            not force_refresh
            and
            self._cache_valid()
        ):

            if (
                self._cached_result
                is not None
            ):

                return (
                    self._cached_result
                )

        # ----------------------------------------------------
        # Alpaca unavailable
        # ----------------------------------------------------

        if self.api is None:

            return self._fallback_result(
                error=(
                    "Alpaca API is not initialized."
                ),
                enabled=(
                    allow_fallback
                ),
            )

        # ----------------------------------------------------
        # Get all active US equities
        # ----------------------------------------------------

        try:

            assets = (
                self.api.list_assets(
                    status="active",
                    asset_class="us_equity",
                )
            )

        except Exception as exc:

            logger.exception(
                "Error fetching market "
                "assets from Alpaca: %s",
                exc,
            )

            return self._fallback_result(
                error=str(
                    exc
                ),
                enabled=(
                    allow_fallback
                ),
            )

        total_assets = len(
            assets
        )

        symbols: list[str] = []

        seen: set[str] = set()

        # ----------------------------------------------------
        # Filter
        # ----------------------------------------------------

        for asset in assets:

            if not self._asset_is_allowed(
                asset
            ):

                continue

            symbol = (
                self._normalize_symbol(
                    getattr(
                        asset,
                        "symbol",
                        "",
                    )
                )
            )

            if symbol is None:
                continue

            if symbol in seen:
                continue

            seen.add(
                symbol
            )

            symbols.append(
                symbol
            )

        symbols.sort()

        # ----------------------------------------------------
        # Suspicious empty result
        # ----------------------------------------------------

        if not symbols:

            return self._fallback_result(
                error=(
                    "Alpaca returned assets "
                    "but no symbols passed "
                    "MarketScanner filters."
                ),
                enabled=(
                    allow_fallback
                ),
                total_assets=(
                    total_assets
                ),
            )

        # ----------------------------------------------------
        # Success
        # ----------------------------------------------------

        result = MarketScanResult(
            symbols=symbols,
            status="SUCCESS",
            source="ALPACA",
            total_assets_received=(
                total_assets
            ),
            total_symbols_accepted=(
                len(
                    symbols
                )
            ),
            used_fallback=False,
            error=None,
        )

        self._cached_result = (
            result
        )

        self._cache_time = (
            time.time()
        )

        logger.info(
            "MarketScanner loaded %s "
            "tradable US equities from "
            "%s total Alpaca assets.",
            len(
                symbols
            ),
            total_assets,
        )

        return result

    # ========================================================
    # OLD COMPATIBILITY METHOD
    # ========================================================

    def quick_scan(
        self,
    ) -> list[str]:

        result = (
            self.scan_market(
                allow_fallback=True,
            )
        )

        return list(
            result.symbols
        )

    # ========================================================
    # HEALTH CHECK
    # ========================================================

    def health_check(
        self,
    ) -> dict[str, Any]:

        return {
            "api_initialized": (
                self.api
                is not None
            ),

            "credentials_present": (
                self.credentials_ready()
            ),

            "paper_url": (
                "paper-api.alpaca.markets"
                in
                self.base_url.lower()
            ),

            "base_url": (
                self.base_url
            ),

            "env_file": (
                str(
                    ENV_FILE
                )
            ),

            "env_file_exists": (
                ENV_FILE.exists()
            ),

            "allowed_exchanges": (
                sorted(
                    self.ALLOWED_EXCHANGES
                )
            ),

            "cache_seconds": (
                self.cache_seconds
            ),

            "role": (
                "MARKET_UNIVERSE_ONLY"
            ),

            # Hard research-only declaration
            "order_execution_enabled": (
                False
            ),
        }


# ============================================================
# COMPATIBILITY HELPER
# ============================================================

def get_top_trending_stocks(
) -> list[str]:
    """
    Compatibility with existing Apex code.

    IMPORTANT:
    Despite the old function name,
    this returns a market universe.
    It does NOT rank trending stocks.
    """

    try:

        scanner = (
            MarketScanner()
        )

        return (
            scanner.quick_scan()
        )

    except Exception as exc:

        logger.exception(
            "Error in "
            "get_top_trending_stocks: %s",
            exc,
        )

        return []
