from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

import alpaca_trade_api as tradeapi


logger = logging.getLogger(__name__)


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
# APEX RESEARCH UNIVERSE PROVIDER
# ============================================================

class MarketScanner:
    """
    APEX Market Scanner V2

    ROLE:
        Build the market universe that Apex will research.

    This module DOES NOT:
        - rank opportunities
        - buy
        - sell
        - submit broker orders
        - tell JALWE to execute

    Flow:

        Alpaca assets
            ↓
        Tradable US equities
            ↓
        Clean symbols
            ↓
        Apex ScannerEngine
            ↓
        News / AI / Liquidity / Pre-Breakout
            ↓
        Research packet
            ↓
        JALWE
    """

    ALLOWED_EXCHANGES = {
        "NASDAQ",
        "NYSE",
        "ARCA",
        "BATS",
        "AMEX",
    }

    # --------------------------------------------------------
    # Fallback is deliberately small and clearly marked.
    #
    # It should NEVER be treated as a successful
    # whole-market scan.
    # --------------------------------------------------------

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
        # Support old Apex names and new JALWE names.
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
            os.getenv("APCA_API_BASE_URL")
            or
            os.getenv("ALPACA_BASE_URL")
            or
            "https://paper-api.alpaca.markets"
        ).strip()

        self.cache_seconds = max(
            0,
            int(cache_seconds),
        )

        self._cached_result: Optional[
            MarketScanResult
        ] = None

        self._cache_time: float = 0.0

        self.api = None

        self._initialize_api()

    # ========================================================
    # API INITIALIZATION
    # ========================================================

    def _initialize_api(
        self,
    ) -> None:

        if not (
            self.api_key
            and
            self.api_secret
        ):

            logger.warning(
                "MarketScanner credentials are missing."
            )

            self.api = None
            return

        try:

            self.api = tradeapi.REST(
                self.api_key,
                self.api_secret,
                self.base_url,
                api_version="v2",
            )

        except Exception as exc:

            logger.exception(
                "Failed to initialize Alpaca REST "
                "in MarketScanner: %s",
                exc,
            )

            self.api = None

    # ========================================================
    # SYMBOL NORMALIZATION
    # ========================================================

    @staticmethod
    def _normalize_symbol(
        symbol: Any,
    ) -> Optional[str]:

        value = str(
            symbol or ""
        ).strip().upper()

        if not value:
            return None

        if len(value) > 15:
            return None

        # ----------------------------------------------------
        # Exclude symbols such as:
        #
        # BRK.B
        # crypto pairs
        # special symbols
        #
        # We can support them later deliberately.
        # ----------------------------------------------------

        blocked_characters = {
            "/",
            ".",
            "^",
            " ",
        }

        if any(
            char in value
            for char in blocked_characters
        ):
            return None

        allowed_characters = set(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
        )

        if any(
            char not in allowed_characters
            for char in value
        ):
            return None

        return value

    # ========================================================
    # EXCHANGE NORMALIZATION
    # ========================================================

    @staticmethod
    def _normalize_exchange(
        exchange: Any,
    ) -> str:

        return str(
            exchange or ""
        ).strip().upper()

    # ========================================================
    # ASSET FILTER
    # ========================================================

    def _asset_is_allowed(
        self,
        asset: Any,
    ) -> bool:

        # Must be tradable.
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
            not in self.ALLOWED_EXCHANGES
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

        age = (
            time.time()
            - self._cache_time
        )

        return (
            age
            <= self.cache_seconds
        )

    def clear_cache(
        self,
    ) -> None:

        self._cached_result = None
        self._cache_time = 0.0

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
        # Cached universe
        # ----------------------------------------------------

        if (
            not force_refresh
            and
            self._cache_valid()
        ):

            cached = (
                self._cached_result
            )

            if cached is not None:
                return cached

        # ----------------------------------------------------
        # No API
        # ----------------------------------------------------

        if self.api is None:

            error = (
                "Alpaca API is not initialized."
            )

            logger.warning(
                error
            )

            return self._fallback_result(
                error=error,
                enabled=allow_fallback,
            )

        # ----------------------------------------------------
        # Fetch all active US equities
        # ----------------------------------------------------

        try:

            assets = (
                self.api.list_assets(
                    status="active",
                    asset_class="us_equity",
                )
            )

        except Exception as exc:

            error = (
                "Error fetching market assets "
                f"from Alpaca: {exc}"
            )

            logger.exception(
                error
            )

            return self._fallback_result(
                error=error,
                enabled=allow_fallback,
            )

        total_assets = len(
            assets
        )

        symbols: list[str] = []

        seen: set[str] = set()

        # ----------------------------------------------------
        # Clean whole market universe
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
        # Alpaca responded but nothing survived filtering.
        # Treat that as suspicious instead of pretending
        # that the scan succeeded.
        # ----------------------------------------------------

        if not symbols:

            error = (
                "Alpaca returned assets, but no "
                "symbols passed MarketScanner filters."
            )

            logger.error(
                error
            )

            return self._fallback_result(
                error=error,
                enabled=allow_fallback,
                total_assets=(
                    total_assets
                ),
            )

        result = MarketScanResult(
            symbols=symbols,
            status="SUCCESS",
            source="ALPACA",
            total_assets_received=(
                total_assets
            ),
            total_symbols_accepted=(
                len(symbols)
            ),
            used_fallback=False,
            error=None,
        )

        # ----------------------------------------------------
        # Save cache only for real Alpaca scan.
        # ----------------------------------------------------

        self._cached_result = (
            result
        )

        self._cache_time = (
            time.time()
        )

        logger.info(
            "MarketScanner loaded %s tradable "
            "US equities from %s total assets.",
            len(symbols),
            total_assets,
        )

        return result

    # ========================================================
    # FALLBACK
    # ========================================================

    def _fallback_result(
        self,
        *,
        error: str,
        enabled: bool,
        total_assets: int = 0,
    ) -> MarketScanResult:

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

        symbols = list(
            self.FALLBACK_SYMBOLS
        )

        logger.warning(
            "MarketScanner is using FALLBACK "
            "universe of %s symbols. "
            "This is NOT a full-market scan.",
            len(symbols),
        )

        return MarketScanResult(
            symbols=symbols,
            status="FALLBACK",
            source="FALLBACK_STATIC",
            total_assets_received=(
                total_assets
            ),
            total_symbols_accepted=(
                len(symbols)
            ),
            used_fallback=True,
            error=error,
        )

    # ========================================================
    # COMPATIBILITY METHOD
    # ========================================================

    def quick_scan(
        self,
    ) -> list[str]:
        """
        Compatibility method for the old Apex code.

        Returns only the symbol list.

        New code should prefer scan_market()
        so status/fallback information is not lost.
        """

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

            "credentials_present": bool(
                self.api_key
                and
                self.api_secret
            ),

            "base_url": (
                self.base_url
            ),

            "allowed_exchanges": sorted(
                self.ALLOWED_EXCHANGES
            ),

            "cache_seconds": (
                self.cache_seconds
            ),

            "role": (
                "MARKET_UNIVERSE_ONLY"
            ),

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
    Backwards-compatible name.

    NOTE:
    This does NOT technically return "top trending stocks".
    It returns the current tradable market universe.

    Ranking/trending logic belongs in ScannerEngine.
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
