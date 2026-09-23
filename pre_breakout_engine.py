from __future__ import annotations

import logging
import os

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestClassifier


logger = logging.getLogger(__name__)


# ============================================================
# CUSTOM MARKET DATA ERROR
# ============================================================

class PreBreakoutDataError(RuntimeError):

    def __init__(
        self,
        message: str,
        *,
        status: str = "DATA_ERROR",
        diagnostics: Optional[list[str]] = None,
    ) -> None:

        super().__init__(message)

        self.status = status

        self.diagnostics = list(
            diagnostics
            or []
        )


# ============================================================
# RESULT MODEL
# ============================================================

@dataclass
class PreBreakoutResult:

    symbol: str

    score: float = 0.0

    status: str = "WATCH"

    ready: bool = False

    model_source: str = "RULES_ONLY"

    ml_probability: Optional[float] = None

    # --------------------------------------------------------
    # DATA QUALITY
    # --------------------------------------------------------

    data_status: str = "UNKNOWN"

    timeframe_used: Optional[str] = None

    bars_used: int = 0

    # --------------------------------------------------------
    # MARKET METRICS
    # --------------------------------------------------------

    rvol: Optional[float] = None

    compression: int = 0

    compression_ratio: Optional[float] = None

    vwap: Optional[float] = None

    above_vwap: bool = False

    vwap_reclaimed: int = 0

    resistance: Optional[float] = None

    distance_to_resistance: Optional[float] = None

    distance_to_resistance_pct: Optional[float] = None

    volume_speed: str = "UNKNOWN"

    volume_speed_ratio: Optional[float] = None

    current_price: Optional[float] = None

    # --------------------------------------------------------
    # EXPLANATION
    # --------------------------------------------------------

    reasons: list[str] = field(
        default_factory=list
    )

    warnings: list[str] = field(
        default_factory=list
    )

    metrics: dict[str, Any] = field(
        default_factory=dict
    )

    diagnostics: list[str] = field(
        default_factory=list
    )

    error: Optional[str] = None


# ============================================================
# PRE-BREAKOUT ENGINE
# ============================================================

class PreBreakoutEngine:
    """
    APEX PRE-BREAKOUT ENGINE V2.2

    PURPOSE:
        Research-only detector for possible pre-breakout setups.

    FLOW:

        ScannerEngine
            ↓
        PreBreakoutEngine
            ↓
        strongest candidates
            ↓
        News / Liquidity / AI
            ↓
        Research Packet
            ↓
        JALWE V4

    DATA FALLBACK:

        Try 5Min
            ↓
        if unavailable / insufficient
            ↓
        Try 15Min
            ↓
        if unavailable / insufficient
            ↓
        Try 30Min
            ↓
        if still insufficient
            ↓
        DATA_UNAVAILABLE

    SAFETY:

        - no synthetic market data
        - no dummy ML training data
        - no broker order execution
        - no BUY/SELL decision
        - missing data cannot create a fake score
    """

    # ========================================================
    # ML SETTINGS
    # ========================================================

    DEFAULT_MIN_TRAINING_SAMPLES = 40

    FEATURE_NAMES = [
        "rvol",
        "compression",
        "vwap_reclaimed",
        "distance_to_resistance",
        "volume_speed_high",
    ]

    # ========================================================
    # MARKET DATA FALLBACK
    # ========================================================

    TIMEFRAME_CANDIDATES = [
        {
            "timeframe": "5Min",
            "limit": 100,
            "minimum_bars": 25,
        },
        {
            "timeframe": "15Min",
            "limit": 80,
            "minimum_bars": 20,
        },
        {
            "timeframe": "30Min",
            "limit": 60,
            "minimum_bars": 15,
        },
    ]

    REQUIRED_COLUMNS = {
        "open",
        "high",
        "low",
        "close",
        "volume",
    }

    # ========================================================
    # INIT
    # ========================================================

    def __init__(
        self,
        alpaca_api,
        learning_engine=None,
        *,
        min_training_samples: Optional[int] = None,
    ) -> None:

        self.alpaca = alpaca_api

        self.learning_engine = learning_engine

        if min_training_samples is None:

            try:

                min_training_samples = int(
                    os.getenv(
                        "PREBREAKOUT_MIN_TRAINING_SAMPLES",
                        str(
                            self.DEFAULT_MIN_TRAINING_SAMPLES
                        ),
                    )
                )

            except (
                TypeError,
                ValueError,
            ):

                min_training_samples = (
                    self.DEFAULT_MIN_TRAINING_SAMPLES
                )

        self.min_training_samples = max(
            10,
            int(
                min_training_samples
            ),
        )

        self.ai_model = (
            RandomForestClassifier(
                n_estimators=150,
                max_depth=6,
                min_samples_leaf=2,
                random_state=42,
                class_weight="balanced",
            )
        )

        self._is_trained = False

        self._training_samples = 0

        self._initial_train()

    # ========================================================
    # TRAINING DATA
    # ========================================================

    def _fetch_training_data(
        self,
    ) -> tuple[list, list]:

        if self.learning_engine is None:

            return (
                [],
                [],
            )

        fetch_method = getattr(
            self.learning_engine,
            "fetch_training_data",
            None,
        )

        if not callable(
            fetch_method
        ):

            return (
                [],
                [],
            )

        try:

            result = fetch_method()

        except Exception as exc:

            logger.warning(
                "Could not fetch PreBreakout "
                "training data: %s",
                exc,
            )

            return (
                [],
                [],
            )

        if (
            not isinstance(
                result,
                tuple,
            )
            or
            len(result) != 2
        ):

            return (
                [],
                [],
            )

        X_data, y_data = result

        return (
            list(
                X_data
                or []
            ),
            list(
                y_data
                or []
            ),
        )

    # ========================================================
    # PREPARE TRAINING DATA
    # ========================================================

    def _prepare_training_data(
        self,
        X_data: list,
        y_data: list,
    ) -> tuple[
        Optional[np.ndarray],
        Optional[np.ndarray],
    ]:

        if (
            len(X_data)
            != len(y_data)
        ):

            return (
                None,
                None,
            )

        if (
            len(X_data)
            <
            self.min_training_samples
        ):

            return (
                None,
                None,
            )

        try:

            X = np.asarray(
                X_data,
                dtype=float,
            )

            y = np.asarray(
                y_data,
                dtype=int,
            )

        except Exception:

            return (
                None,
                None,
            )

        if (
            X.ndim != 2
            or
            X.shape[1]
            != len(
                self.FEATURE_NAMES
            )
        ):

            return (
                None,
                None,
            )

        if (
            len(
                np.unique(
                    y
                )
            )
            < 2
        ):

            return (
                None,
                None,
            )

        if not (
            np.isfinite(
                X
            ).all()
        ):

            return (
                None,
                None,
            )

        return (
            X,
            y,
        )

    # ========================================================
    # INITIAL TRAIN
    # ========================================================

    def _initial_train(
        self,
    ) -> None:

        X_data, y_data = (
            self._fetch_training_data()
        )

        self._training_samples = (
            len(
                X_data
            )
        )

        X, y = (
            self._prepare_training_data(
                X_data,
                y_data,
            )
        )

        if (
            X is None
            or
            y is None
        ):

            self._is_trained = False

            logger.info(
                "PreBreakout ML waiting "
                "for real data: %s/%s",
                self._training_samples,
                self.min_training_samples,
            )

            return

        self.ai_model.fit(
            X,
            y,
        )

        self._is_trained = True

        self._training_samples = len(
            X
        )

    # ========================================================
    # RETRAIN
    # ========================================================

    def update_model_with_real_data(
        self,
    ) -> bool:

        X_data, y_data = (
            self._fetch_training_data()
        )

        self._training_samples = len(
            X_data
        )

        X, y = (
            self._prepare_training_data(
                X_data,
                y_data,
            )
        )

        if (
            X is None
            or
            y is None
        ):

            return False

        self.ai_model.fit(
            X,
            y,
        )

        self._is_trained = True

        self._training_samples = len(
            X
        )

        logger.info(
            "PreBreakout ML retrained "
            "with %s real outcomes.",
            self._training_samples,
        )

        return True

    # ========================================================
    # SYMBOL
    # ========================================================

    @staticmethod
    def _normalize_symbol(
        symbol: str,
    ) -> str:

        symbol = str(
            symbol
            or ""
        ).strip().upper()

        if not symbol:

            raise ValueError(
                "Symbol cannot be empty."
            )

        return symbol

    # ========================================================
    # NORMALIZE DATAFRAME
    # ========================================================

    def _normalize_dataframe(
        self,
        dataframe: Any,
        symbol: str,
    ) -> pd.DataFrame:

        if dataframe is None:

            raise PreBreakoutDataError(
                "Market data dataframe is None.",
                status="EMPTY_DATA",
            )

        if not isinstance(
            dataframe,
            pd.DataFrame,
        ):

            try:

                dataframe = pd.DataFrame(
                    dataframe
                )

            except Exception as exc:

                raise PreBreakoutDataError(
                    "Could not convert market data "
                    "to dataframe.",
                    status="INVALID_DATAFRAME",
                ) from exc

        dataframe = dataframe.copy()

        if dataframe.empty:

            raise PreBreakoutDataError(
                "Market data dataframe is empty.",
                status="EMPTY_DATA",
            )

        # ----------------------------------------------------
        # Alpaca can return MultiIndex.
        # ----------------------------------------------------

        if isinstance(
            dataframe.index,
            pd.MultiIndex,
        ):

            extracted = False

            for level in range(
                dataframe.index.nlevels
            ):

                try:

                    values = (
                        dataframe.index
                        .get_level_values(
                            level
                        )
                        .astype(str)
                        .str.upper()
                    )

                    if symbol in set(
                        values
                    ):

                        dataframe = (
                            dataframe.xs(
                                symbol,
                                level=level,
                            )
                        )

                        extracted = True
                        break

                except Exception:
                    continue

            if not extracted:

                try:

                    dataframe = (
                        dataframe.reset_index()
                    )

                except Exception:
                    pass

        # ----------------------------------------------------
        # Normalize column names.
        # ----------------------------------------------------

        dataframe.columns = [
            str(column)
            .strip()
            .lower()
            for column
            in dataframe.columns
        ]

        # ----------------------------------------------------
        # If symbol column exists because of reset_index,
        # keep only requested symbol.
        # ----------------------------------------------------

        if (
            "symbol"
            in dataframe.columns
        ):

            try:

                mask = (
                    dataframe["symbol"]
                    .astype(str)
                    .str.upper()
                    ==
                    symbol
                )

                filtered = (
                    dataframe.loc[
                        mask
                    ]
                    .copy()
                )

                if not filtered.empty:

                    dataframe = filtered

            except Exception:
                pass

        if dataframe.empty:

            raise PreBreakoutDataError(
                "No rows exist for requested symbol.",
                status="EMPTY_DATA",
            )

        # ----------------------------------------------------
        # Required OHLCV columns.
        # ----------------------------------------------------

        missing_columns = (
            self.REQUIRED_COLUMNS
            -
            set(
                dataframe.columns
            )
        )

        if missing_columns:

            raise PreBreakoutDataError(
                "Missing market data columns: "
                + ", ".join(
                    sorted(
                        missing_columns
                    )
                ),
                status="INVALID_COLUMNS",
            )

        # ----------------------------------------------------
        # Convert numbers safely.
        # ----------------------------------------------------

        for column in (
            self.REQUIRED_COLUMNS
        ):

            dataframe[column] = (
                pd.to_numeric(
                    dataframe[column],
                    errors="coerce",
                )
            )

        dataframe = (
            dataframe.dropna(
                subset=[
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                ]
            )
        )

        if dataframe.empty:

            raise PreBreakoutDataError(
                "OHLCV rows became empty "
                "after numeric cleaning.",
                status="EMPTY_DATA",
            )

        return dataframe

    # ========================================================
    # FETCH ONE TIMEFRAME
    # ========================================================

    def _get_bars_for_timeframe(
        self,
        symbol: str,
        *,
        timeframe: str,
        limit: int,
    ) -> pd.DataFrame:

        if self.alpaca is None:

            raise PreBreakoutDataError(
                "Alpaca API is not available.",
                status="API_UNAVAILABLE",
            )

        try:

            try:

                bars = (
                    self.alpaca.get_bars(
                        symbol,
                        timeframe,
                        limit=int(
                            limit
                        ),
                        feed="iex",
                    )
                )

            except TypeError:

                bars = (
                    self.alpaca.get_bars(
                        symbol,
                        timeframe,
                        limit=int(
                            limit
                        ),
                    )
                )

        except Exception as exc:

            raise PreBreakoutDataError(
                f"Alpaca request failed "
                f"for {timeframe}: {exc}",
                status="API_ERROR",
            ) from exc

        dataframe = getattr(
            bars,
            "df",
            None,
        )

        if dataframe is None:

            # Some SDK responses may already
            # behave like a dataframe/list.
            dataframe = bars

        return (
            self._normalize_dataframe(
                dataframe,
                symbol,
            )
        )

    # ========================================================
    # FALLBACK MARKET DATA
    # ========================================================

    def _get_best_bars(
        self,
        symbol: str,
    ) -> tuple[
        pd.DataFrame,
        str,
        list[str],
    ]:

        diagnostics: list[str] = []

        best_partial: Optional[
            tuple[
                pd.DataFrame,
                str,
                int,
            ]
        ] = None

        for candidate in (
            self.TIMEFRAME_CANDIDATES
        ):

            timeframe = str(
                candidate[
                    "timeframe"
                ]
            )

            limit = int(
                candidate[
                    "limit"
                ]
            )

            minimum_bars = int(
                candidate[
                    "minimum_bars"
                ]
            )

            try:

                dataframe = (
                    self._get_bars_for_timeframe(
                        symbol,
                        timeframe=timeframe,
                        limit=limit,
                    )
                )

            except PreBreakoutDataError as exc:

                diagnostics.append(
                    f"{timeframe}:"
                    f"{exc.status}:"
                    f"{exc}"
                )

                continue

            bar_count = len(
                dataframe
            )

            diagnostics.append(
                f"{timeframe}:"
                f"BARS={bar_count}"
            )

            if (
                best_partial
                is None
                or
                bar_count
                >
                best_partial[2]
            ):

                best_partial = (
                    dataframe,
                    timeframe,
                    bar_count,
                )

            if (
                bar_count
                >= minimum_bars
            ):

                return (
                    dataframe,
                    timeframe,
                    diagnostics,
                )

            diagnostics.append(
                f"{timeframe}:"
                f"INSUFFICIENT_BARS="
                f"{bar_count}/"
                f"{minimum_bars}"
            )

        # ----------------------------------------------------
        # We intentionally DO NOT score partial data.
        # ----------------------------------------------------

        if best_partial is not None:

            raise PreBreakoutDataError(
                "Market data exists but "
                "there are not enough bars "
                "for reliable analysis.",
                status="INSUFFICIENT_BARS",
                diagnostics=diagnostics,
            )

        raise PreBreakoutDataError(
            "No usable market data was "
            "available in 5Min, 15Min or 30Min.",
            status="DATA_UNAVAILABLE",
            diagnostics=diagnostics,
        )

    # ========================================================
    # VWAP
    # ========================================================

    @staticmethod
    def _calculate_vwap(
        dataframe: pd.DataFrame,
    ) -> pd.Series:

        typical_price = (
            dataframe["high"]
            +
            dataframe["low"]
            +
            dataframe["close"]
        ) / 3.0

        cumulative_volume = (
            dataframe["volume"]
            .cumsum()
            .replace(
                0,
                np.nan,
            )
        )

        return (
            (
                typical_price
                *
                dataframe["volume"]
            )
            .cumsum()
            /
            cumulative_volume
        )

    # ========================================================
    # LIVE METRICS
    # ========================================================

    def calculate_metrics(
        self,
        symbol: str,
    ) -> dict[str, Any]:

        symbol = (
            self._normalize_symbol(
                symbol
            )
        )

        (
            dataframe,
            timeframe_used,
            diagnostics,
        ) = (
            self._get_best_bars(
                symbol
            )
        )

        close = dataframe[
            "close"
        ]

        high = dataframe[
            "high"
        ]

        low = dataframe[
            "low"
        ]

        volume = dataframe[
            "volume"
        ]

        current_price = float(
            close.iloc[-1]
        )

        # ====================================================
        # DYNAMIC LOOKBACK
        # ====================================================

        available_bars = len(
            dataframe
        )

        main_lookback = min(
            20,
            max(
                10,
                available_bars - 1,
            ),
        )

        compression_window = min(
            5,
            max(
                3,
                available_bars // 4,
            ),
        )

        # ====================================================
        # RVOL
        # ====================================================

        prior_volume = (
            volume.iloc[
                -(
                    main_lookback
                    + 1
                ):-1
            ]
        )

        average_volume = float(
            prior_volume.mean()
        )

        latest_volume = float(
            volume.iloc[-1]
        )

        if (
            np.isfinite(
                average_volume
            )
            and
            average_volume > 0
        ):

            rvol = (
                latest_volume
                /
                average_volume
            )

        else:

            rvol = 0.0

        # ====================================================
        # RESISTANCE
        # ====================================================

        previous_highs = (
            high.iloc[
                -(
                    main_lookback
                    + 1
                ):-1
            ]
        )

        resistance = float(
            previous_highs.max()
        )

        if (
            np.isfinite(
                resistance
            )
            and
            resistance > 0
        ):

            distance_to_resistance = (
                resistance
                -
                current_price
            ) / resistance

        else:

            distance_to_resistance = 1.0

        distance_to_resistance_pct = (
            distance_to_resistance
            *
            100.0
        )

        # ====================================================
        # COMPRESSION
        # ====================================================

        recent_high = float(
            high
            .iloc[
                -compression_window:
            ]
            .max()
        )

        recent_low = float(
            low
            .iloc[
                -compression_window:
            ]
            .min()
        )

        recent_range = (
            recent_high
            -
            recent_low
        )

        historical_end = (
            -compression_window
        )

        historical_start = max(
            0,
            available_bars
            -
            (
                compression_window
                +
                main_lookback
            ),
        )

        historical_ranges = (
            high.iloc[
                historical_start:
                historical_end
            ]
            -
            low.iloc[
                historical_start:
                historical_end
            ]
        )

        baseline_range = float(
            historical_ranges.mean()
        )

        if (
            np.isfinite(
                baseline_range
            )
            and
            baseline_range > 0
        ):

            compression_ratio = (
                recent_range
                /
                baseline_range
            )

        else:

            compression_ratio = 999.0

        compression = int(
            compression_ratio
            <= 0.70
        )

        # ====================================================
        # VWAP
        # ====================================================

        vwap_series = (
            self._calculate_vwap(
                dataframe
            )
        )

        current_vwap = float(
            vwap_series.iloc[-1]
        )

        previous_vwap = float(
            vwap_series.iloc[-2]
        )

        previous_close = float(
            close.iloc[-2]
        )

        above_vwap = bool(
            np.isfinite(
                current_vwap
            )
            and
            current_price
            >
            current_vwap
        )

        vwap_reclaimed = int(
            np.isfinite(
                previous_vwap
            )
            and
            previous_close
            <= previous_vwap
            and
            current_price
            >
            current_vwap
        )

        # ====================================================
        # VOLUME SPEED
        # ====================================================

        volume_window = min(
            5,
            max(
                2,
                available_bars - 1,
            ),
        )

        recent_volume_baseline = float(
            volume
            .iloc[
                -(
                    volume_window
                    + 1
                ):-1
            ]
            .mean()
        )

        if (
            np.isfinite(
                recent_volume_baseline
            )
            and
            recent_volume_baseline > 0
        ):

            volume_speed_ratio = (
                latest_volume
                /
                recent_volume_baseline
            )

        else:

            volume_speed_ratio = 0.0

        if volume_speed_ratio >= 1.50:

            volume_speed = "HIGH"

        elif volume_speed_ratio >= 1.10:

            volume_speed = "RISING"

        else:

            volume_speed = "NORMAL"

        # ====================================================
        # SHORT MOMENTUM
        # ====================================================

        momentum_3 = 0.0

        if (
            len(
                close
            )
            >= 4
            and
            float(
                close.iloc[-4]
            )
            > 0
        ):

            momentum_3 = (
                (
                    current_price
                    /
                    float(
                        close.iloc[-4]
                    )
                )
                -
                1.0
            ) * 100.0

        # ====================================================
        # BREAKOUT STATE
        # ====================================================

        already_broken_out = bool(
            current_price
            >
            resistance
        )

        near_resistance = bool(
            -0.01
            <=
            distance_to_resistance
            <=
            0.03
        )

        return {
            "symbol": symbol,

            "data_status": (
                "SUCCESS"
            ),

            "timeframe_used": (
                timeframe_used
            ),

            "bars_used": (
                available_bars
            ),

            "diagnostics": (
                diagnostics
            ),

            "current_price": round(
                current_price,
                4,
            ),

            "rvol": round(
                float(
                    rvol
                ),
                4,
            ),

            "compression": (
                compression
            ),

            "compression_ratio": round(
                float(
                    compression_ratio
                ),
                4,
            ),

            "vwap": round(
                current_vwap,
                4,
            )
            if np.isfinite(
                current_vwap
            )
            else None,

            "above_vwap": (
                above_vwap
            ),

            "vwap_reclaimed": (
                vwap_reclaimed
            ),

            "resistance": round(
                resistance,
                4,
            ),

            "distance_to_resistance": round(
                float(
                    distance_to_resistance
                ),
                6,
            ),

            "distance_to_resistance_pct": round(
                float(
                    distance_to_resistance_pct
                ),
                3,
            ),

            "volume_speed": (
                volume_speed
            ),

            "volume_speed_ratio": round(
                float(
                    volume_speed_ratio
                ),
                4,
            ),

            "momentum_3_pct": round(
                float(
                    momentum_3
                ),
                3,
            ),

            "near_resistance": (
                near_resistance
            ),

            "already_broken_out": (
                already_broken_out
            ),

            "status": "SUCCESS",
        }

    # ========================================================
    # RULE SCORE
    # ========================================================

    @staticmethod
    def _rule_score(
        data: dict[str, Any],
    ) -> tuple[
        float,
        list[str],
        list[str],
    ]:

        score = 0.0

        reasons: list[str] = []

        warnings: list[str] = []

        # ====================================================
        # RVOL
        # ====================================================

        rvol = float(
            data.get(
                "rvol",
                0.0,
            )
            or 0.0
        )

        if rvol >= 3.0:

            score += 25.0

            reasons.append(
                "Exceptional RVOL"
            )

        elif rvol >= 2.0:

            score += 22.0

            reasons.append(
                "Strong RVOL"
            )

        elif rvol >= 1.5:

            score += 16.0

            reasons.append(
                "Elevated RVOL"
            )

        elif rvol >= 1.2:

            score += 8.0

            reasons.append(
                "RVOL improving"
            )

        else:

            warnings.append(
                "Weak relative volume"
            )

        # ====================================================
        # COMPRESSION
        # ====================================================

        if int(
            data.get(
                "compression",
                0,
            )
        ) == 1:

            score += 20.0

            reasons.append(
                "Price compression near resistance"
            )

        # ====================================================
        # VWAP
        # ====================================================

        if int(
            data.get(
                "vwap_reclaimed",
                0,
            )
        ) == 1:

            score += 15.0

            reasons.append(
                "VWAP reclaimed"
            )

        elif bool(
            data.get(
                "above_vwap",
                False,
            )
        ):

            score += 10.0

            reasons.append(
                "Price holding above VWAP"
            )

        else:

            warnings.append(
                "Price below VWAP"
            )

        # ====================================================
        # RESISTANCE
        # ====================================================

        distance = float(
            data.get(
                "distance_to_resistance",
                1.0,
            )
            or 1.0
        )

        if (
            0.0
            <= distance
            <= 0.01
        ):

            score += 25.0

            reasons.append(
                "Within 1% of resistance"
            )

        elif (
            0.01
            <
            distance
            <= 0.02
        ):

            score += 20.0

            reasons.append(
                "Within 2% of resistance"
            )

        elif (
            0.02
            <
            distance
            <= 0.03
        ):

            score += 12.0

            reasons.append(
                "Approaching resistance"
            )

        elif distance < 0:

            score += 10.0

            reasons.append(
                "Resistance is being tested/broken"
            )

        else:

            warnings.append(
                "Too far from resistance"
            )

        # ====================================================
        # VOLUME SPEED
        # ====================================================

        volume_speed = str(
            data.get(
                "volume_speed",
                "UNKNOWN",
            )
        ).upper()

        if volume_speed == "HIGH":

            score += 15.0

            reasons.append(
                "High volume acceleration"
            )

        elif volume_speed == "RISING":

            score += 8.0

            reasons.append(
                "Volume is accelerating"
            )

        # ====================================================
        # MOMENTUM
        # ====================================================

        momentum = float(
            data.get(
                "momentum_3_pct",
                0.0,
            )
            or 0.0
        )

        if (
            0.25
            <= momentum
            <= 5.0
        ):

            score += 5.0

            reasons.append(
                "Positive short-term momentum"
            )

        elif momentum < -1.0:

            warnings.append(
                "Short-term momentum is negative"
            )

        return (
            round(
                min(
                    score,
                    100.0,
                ),
                2,
            ),
            reasons,
            warnings,
        )

    # ========================================================
    # BUILD ML FEATURES
    # ========================================================

    @staticmethod
    def _build_features(
        data: dict[str, Any],
    ) -> np.ndarray:

        return np.asarray(
            [[
                float(
                    data.get(
                        "rvol",
                        0.0,
                    )
                    or 0.0
                ),

                float(
                    int(
                        data.get(
                            "compression",
                            0,
                        )
                    )
                ),

                float(
                    int(
                        data.get(
                            "vwap_reclaimed",
                            0,
                        )
                    )
                ),

                float(
                    data.get(
                        "distance_to_resistance",
                        1.0,
                    )
                    or 1.0
                ),

                1.0
                if str(
                    data.get(
                        "volume_speed",
                        "",
                    )
                ).upper()
                == "HIGH"
                else 0.0,
            ]],
            dtype=float,
        )

    # ========================================================
    # ML PROBABILITY
    # ========================================================

    def _ml_probability(
        self,
        data: dict[str, Any],
    ) -> Optional[float]:

        if not self._is_trained:

            return None

        try:

            features = (
                self._build_features(
                    data
                )
            )

            probabilities = (
                self.ai_model
                .predict_proba(
                    features
                )[0]
            )

            classes = list(
                self.ai_model.classes_
            )

            if 1 not in classes:

                return None

            positive_index = (
                classes.index(
                    1
                )
            )

            return float(
                probabilities[
                    positive_index
                ]
            )

        except Exception as exc:

            logger.warning(
                "PreBreakout ML inference "
                "failed: %s",
                exc,
            )

            return None

    # ========================================================
    # EVALUATE
    # ========================================================

    def evaluate_pre_breakout(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]:

        (
            rule_score,
            reasons,
            warnings,
        ) = (
            self._rule_score(
                data
            )
        )

        ml_probability = (
            self._ml_probability(
                data
            )
        )

        if ml_probability is None:

            final_score = (
                rule_score
            )

            model_source = (
                "RULES_ONLY"
            )

        else:

            ml_score = (
                ml_probability
                *
                100.0
            )

            final_score = (
                rule_score
                *
                0.65
                +
                ml_score
                *
                0.35
            )

            model_source = (
                "RULES_REAL_ML_BLEND"
            )

            reasons.append(
                "Real ML probability available"
            )

        final_score = round(
            max(
                0.0,
                min(
                    final_score,
                    100.0,
                ),
            ),
            2,
        )

        status = "WATCH"

        if final_score >= 82:

            status = (
                "READY_FOR_JALWE_RESEARCH"
            )

        elif final_score >= 70:

            status = "CONFIRMED"

        elif final_score >= 55:

            status = "SETUP"

        ready = bool(
            final_score >= 70
        )

        return {
            "score": final_score,

            "status": status,

            "ready": ready,

            "model_source": (
                model_source
            ),

            "ml_probability": (
                round(
                    ml_probability,
                    4,
                )
                if ml_probability
                is not None
                else None
            ),

            "reasons": reasons,

            "warnings": warnings,
        }

    # ========================================================
    # ANALYZE SYMBOL
    # ========================================================

    def analyze_symbol(
        self,
        symbol: str,
    ) -> PreBreakoutResult:

        try:

            symbol = (
                self._normalize_symbol(
                    symbol
                )
            )

        except Exception as exc:

            return PreBreakoutResult(
                symbol="",
                status="ERROR",
                data_status="INVALID_SYMBOL",
                error=str(
                    exc
                ),
            )

        try:

            metrics = (
                self.calculate_metrics(
                    symbol
                )
            )

        except PreBreakoutDataError as exc:

            logger.info(
                "PreBreakout data unavailable "
                "for %s: %s",
                symbol,
                exc,
            )

            return PreBreakoutResult(
                symbol=symbol,

                status=exc.status,

                data_status=exc.status,

                ready=False,

                warnings=[
                    "MARKET_DATA_UNAVAILABLE"
                ],

                diagnostics=list(
                    exc.diagnostics
                ),

                error=str(
                    exc
                ),
            )

        except Exception as exc:

            logger.exception(
                "Unexpected PreBreakout error "
                "for %s",
                symbol,
            )

            return PreBreakoutResult(
                symbol=symbol,

                status="DATA_ERROR",

                data_status="DATA_ERROR",

                ready=False,

                warnings=[
                    "MARKET_DATA_ERROR"
                ],

                error=str(
                    exc
                ),
            )

        evaluation = (
            self.evaluate_pre_breakout(
                metrics
            )
        )

        return PreBreakoutResult(
            symbol=symbol,

            score=float(
                evaluation[
                    "score"
                ]
            ),

            status=str(
                evaluation[
                    "status"
                ]
            ),

            ready=bool(
                evaluation[
                    "ready"
                ]
            ),

            model_source=str(
                evaluation[
                    "model_source"
                ]
            ),

            ml_probability=(
                evaluation[
                    "ml_probability"
                ]
            ),

            data_status=str(
                metrics.get(
                    "data_status",
                    "SUCCESS",
                )
            ),

            timeframe_used=(
                metrics.get(
                    "timeframe_used"
                )
            ),

            bars_used=int(
                metrics.get(
                    "bars_used",
                    0,
                )
                or 0
            ),

            rvol=metrics.get(
                "rvol"
            ),

            compression=int(
                metrics.get(
                    "compression",
                    0,
                )
            ),

            compression_ratio=(
                metrics.get(
                    "compression_ratio"
                )
            ),

            vwap=metrics.get(
                "vwap"
            ),

            above_vwap=bool(
                metrics.get(
                    "above_vwap",
                    False,
                )
            ),

            vwap_reclaimed=int(
                metrics.get(
                    "vwap_reclaimed",
                    0,
                )
            ),

            resistance=metrics.get(
                "resistance"
            ),

            distance_to_resistance=(
                metrics.get(
                    "distance_to_resistance"
                )
            ),

            distance_to_resistance_pct=(
                metrics.get(
                    "distance_to_resistance_pct"
                )
            ),

            volume_speed=str(
                metrics.get(
                    "volume_speed",
                    "UNKNOWN",
                )
            ),

            volume_speed_ratio=(
                metrics.get(
                    "volume_speed_ratio"
                )
            ),

            current_price=(
                metrics.get(
                    "current_price"
                )
            ),

            reasons=list(
                evaluation.get(
                    "reasons",
                    [],
                )
            ),

            warnings=list(
                evaluation.get(
                    "warnings",
                    [],
                )
            ),

            metrics=dict(
                metrics
            ),

            diagnostics=list(
                metrics.get(
                    "diagnostics",
                    [],
                )
            ),

            error=None,
        )

    # ========================================================
    # ANALYZE MANY
    # ========================================================

    def analyze_symbols(
        self,
        symbols: list[str],
        *,
        minimum_score: float = 55.0,
        max_results: int = 30,
    ) -> list[PreBreakoutResult]:

        results: list[
            PreBreakoutResult
        ] = []

        seen: set[str] = set()

        for raw_symbol in (
            symbols
            or []
        ):

            symbol = str(
                raw_symbol
                or ""
            ).strip().upper()

            if (
                not symbol
                or
                symbol in seen
            ):

                continue

            seen.add(
                symbol
            )

            result = (
                self.analyze_symbol(
                    symbol
                )
            )

            # ------------------------------------------------
            # Only genuine valid market-data results
            # can enter ranking.
            # ------------------------------------------------

            if (
                result.data_status
                != "SUCCESS"
            ):

                continue

            if (
                result.error
                is not None
            ):

                continue

            if (
                result.score
                <
                float(
                    minimum_score
                )
            ):

                continue

            results.append(
                result
            )

        results.sort(
            key=lambda item: (
                item.score,
                item.rvol
                if item.rvol
                is not None
                else 0.0,
            ),
            reverse=True,
        )

        return results[
            :max(
                1,
                int(
                    max_results
                ),
            )
        ]

    # ========================================================
    # DATA AVAILABILITY TEST
    # ========================================================

    def test_data_availability(
        self,
        symbols: list[str],
    ) -> dict[str, Any]:

        summary = {
            "total": 0,
            "success": 0,
            "unavailable": 0,
            "by_status": {},
            "timeframes": {},
        }

        for symbol in (
            symbols
            or []
        ):

            summary[
                "total"
            ] += 1

            result = (
                self.analyze_symbol(
                    symbol
                )
            )

            status = (
                result.data_status
            )

            summary[
                "by_status"
            ][status] = (
                summary[
                    "by_status"
                ].get(
                    status,
                    0,
                )
                +
                1
            )

            if status == "SUCCESS":

                summary[
                    "success"
                ] += 1

                timeframe = (
                    result.timeframe_used
                    or
                    "UNKNOWN"
                )

                summary[
                    "timeframes"
                ][timeframe] = (
                    summary[
                        "timeframes"
                    ].get(
                        timeframe,
                        0,
                    )
                    +
                    1
                )

            else:

                summary[
                    "unavailable"
                ] += 1

        return summary

    # ========================================================
    # HEALTH CHECK
    # ========================================================

    def health_check(
        self,
    ) -> dict[str, Any]:

        return {
            "alpaca_available": (
                self.alpaca
                is not None
            ),

            "learning_engine_available": (
                self.learning_engine
                is not None
            ),

            "ml_trained": (
                self._is_trained
            ),

            "training_samples": (
                self._training_samples
            ),

            "minimum_training_samples": (
                self.min_training_samples
            ),

            "feature_count": len(
                self.FEATURE_NAMES
            ),

            "market_data_fallback": [
                item[
                    "timeframe"
                ]
                for item
                in self.TIMEFRAME_CANDIDATES
            ],

            "role": (
                "PRE_BREAKOUT_RESEARCH_ONLY"
            ),

            "order_execution_enabled": (
                False
            ),
        }
