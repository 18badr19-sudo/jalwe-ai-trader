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

    reasons: list[str] = field(
        default_factory=list
    )

    warnings: list[str] = field(
        default_factory=list
    )

    metrics: dict[str, Any] = field(
        default_factory=dict
    )

    error: Optional[str] = None


# ============================================================
# PRE BREAKOUT ENGINE
# ============================================================

class PreBreakoutEngine:
    """
    APEX Pre-Breakout Engine V2

    ROLE:
        Detect stocks that are approaching a possible breakout.

    IMPORTANT:
        RESEARCH ONLY.

        This engine DOES NOT:
        - buy
        - sell
        - submit orders
        - manage positions

    Pipeline:

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

    MACHINE LEARNING:

        The RandomForest model is trained ONLY when
        enough real historical outcomes are available.

        No fake/dummy training data is used.

        Until enough real samples exist:
            RULE-BASED scoring is used.
    """

    # ========================================================
    # FEATURE ORDER
    # ========================================================

    FEATURE_NAMES = [
        "rvol",
        "compression",
        "vwap_reclaimed",
        "distance_to_resistance",
        "volume_speed_high",
    ]

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

        self.alpaca = (
            alpaca_api
        )

        self.learning_engine = (
            learning_engine
        )

        if min_training_samples is None:

            min_training_samples = int(
                os.getenv(
                    "PREBREAKOUT_MIN_TRAINING_SAMPLES",
                    os.getenv(
                        "MIN_TRAINING_SAMPLES",
                        "40",
                    ),
                )
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
    # LEARNING DATA
    # ========================================================

    def _fetch_training_data(
        self,
    ) -> tuple[list, list]:

        if (
            self.learning_engine
            is None
        ):

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

            result = (
                fetch_method()
            )

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

        X_data, y_data = (
            result
        )

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
    # VALIDATE TRAINING DATA
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

        (
            X,
            y,
        ) = (
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

            self._training_samples = (
                len(
                    X_data
                )
            )

            logger.info(
                "PreBreakout ML waiting for "
                "real training data: %s/%s samples.",
                self._training_samples,
                self.min_training_samples,
            )

            return

        self.ai_model.fit(
            X,
            y,
        )

        self._is_trained = True

        self._training_samples = (
            len(
                X
            )
        )

        logger.info(
            "PreBreakout ML trained with "
            "%s real samples.",
            self._training_samples,
        )

    # ========================================================
    # RETRAIN WITH REAL DATA
    # ========================================================

    def update_model_with_real_data(
        self,
    ) -> bool:

        X_data, y_data = (
            self._fetch_training_data()
        )

        (
            X,
            y,
        ) = (
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

            self._training_samples = (
                len(
                    X_data
                )
            )

            return False

        self.ai_model.fit(
            X,
            y,
        )

        self._is_trained = True

        self._training_samples = (
            len(
                X
            )
        )

        logger.info(
            "PreBreakout ML retrained "
            "with %s real outcomes.",
            self._training_samples,
        )

        return True

    # ========================================================
    # GET BARS
    # ========================================================

    def _get_bars(
        self,
        symbol: str,
        *,
        timeframe: str = "5Min",
        limit: int = 100,
    ) -> pd.DataFrame:

        if self.alpaca is None:

            raise RuntimeError(
                "Alpaca API is not available."
            )

        symbol = str(
            symbol
            or ""
        ).strip().upper()

        if not symbol:

            raise ValueError(
                "Symbol cannot be empty."
            )

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

            # Compatibility with older SDK versions.
            bars = (
                self.alpaca.get_bars(
                    symbol,
                    timeframe,
                    limit=int(
                        limit
                    ),
                )
            )

        dataframe = getattr(
            bars,
            "df",
            None,
        )

        if dataframe is None:

            raise RuntimeError(
                "Alpaca returned no dataframe."
            )

        dataframe = (
            dataframe.copy()
        )

        if isinstance(
            dataframe.index,
            pd.MultiIndex,
        ):

            try:

                dataframe = (
                    dataframe.xs(
                        symbol,
                        level=0,
                    )
                )

            except Exception:

                dataframe = (
                    dataframe.reset_index()
                )

        required_columns = {
            "open",
            "high",
            "low",
            "close",
            "volume",
        }

        missing_columns = (
            required_columns
            -
            set(
                dataframe.columns
            )
        )

        if missing_columns:

            raise RuntimeError(
                "Missing market data columns: "
                + ", ".join(
                    sorted(
                        missing_columns
                    )
                )
            )

        for column in (
            required_columns
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

        if (
            len(
                dataframe
            )
            < 25
        ):

            raise RuntimeError(
                "Not enough bars for "
                "PreBreakout analysis."
            )

        return dataframe

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

        vwap = (
            (
                typical_price
                *
                dataframe["volume"]
            )
            .cumsum()
            /
            cumulative_volume
        )

        return vwap

    # ========================================================
    # LIVE METRICS
    # ========================================================

    def calculate_metrics(
        self,
        symbol: str,
    ) -> dict[str, Any]:

        symbol = str(
            symbol
            or ""
        ).strip().upper()

        dataframe = (
            self._get_bars(
                symbol,
                timeframe="5Min",
                limit=100,
            )
        )

        close = (
            dataframe["close"]
        )

        high = (
            dataframe["high"]
        )

        low = (
            dataframe["low"]
        )

        volume = (
            dataframe["volume"]
        )

        current_price = float(
            close.iloc[-1]
        )

        # ====================================================
        # RVOL
        # ====================================================

        prior_volume = (
            volume.iloc[-21:-1]
        )

        average_volume = float(
            prior_volume.mean()
        )

        latest_volume = float(
            volume.iloc[-1]
        )

        if average_volume > 0:

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

        resistance = float(
            high
            .iloc[-21:-1]
            .max()
        )

        if resistance > 0:

            distance_to_resistance = (
                resistance
                -
                current_price
            ) / resistance

        else:

            distance_to_resistance = (
                1.0
            )

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
            .iloc[-5:]
            .max()
        )

        recent_low = float(
            low
            .iloc[-5:]
            .min()
        )

        recent_range = (
            recent_high
            -
            recent_low
        )

        historical_ranges = (
            high.iloc[-25:-5]
            -
            low.iloc[-25:-5]
        )

        baseline_range = float(
            historical_ranges.mean()
        )

        if baseline_range > 0:

            compression_ratio = (
                recent_range
                /
                baseline_range
            )

        else:

            compression_ratio = (
                999.0
            )

        compression = int(
            compression_ratio
            <= 0.70
        )

        # ====================================================
        # VWAP / RECLAIM
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
            current_price
            >
            current_vwap
        )

        vwap_reclaimed = int(
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

        recent_volume_baseline = float(
            volume
            .iloc[-6:-1]
            .mean()
        )

        if recent_volume_baseline > 0:

            volume_speed_ratio = (
                latest_volume
                /
                recent_volume_baseline
            )

        else:

            volume_speed_ratio = (
                0.0
            )

        if volume_speed_ratio >= 1.50:

            volume_speed = (
                "HIGH"
            )

        elif volume_speed_ratio >= 1.10:

            volume_speed = (
                "RISING"
            )

        else:

            volume_speed = (
                "NORMAL"
            )

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

            "current_price": (
                round(
                    current_price,
                    4,
                )
            ),

            "rvol": (
                round(
                    float(
                        rvol
                    ),
                    4,
                )
            ),

            "compression": (
                compression
            ),

            "compression_ratio": (
                round(
                    float(
                        compression_ratio
                    ),
                    4,
                )
            ),

            "vwap": (
                round(
                    current_vwap,
                    4,
                )
            ),

            "above_vwap": (
                above_vwap
            ),

            "vwap_reclaimed": (
                vwap_reclaimed
            ),

            "resistance": (
                round(
                    resistance,
                    4,
                )
            ),

            "distance_to_resistance": (
                round(
                    float(
                        distance_to_resistance
                    ),
                    6,
                )
            ),

            "distance_to_resistance_pct": (
                round(
                    float(
                        distance_to_resistance_pct
                    ),
                    3,
                )
            ),

            "volume_speed": (
                volume_speed
            ),

            "volume_speed_ratio": (
                round(
                    float(
                        volume_speed_ratio
                    ),
                    4,
                )
            ),

            "momentum_3_pct": (
                round(
                    float(
                        momentum_3
                    ),
                    3,
                )
            ),

            "near_resistance": (
                near_resistance
            ),

            "already_broken_out": (
                already_broken_out
            ),

            "bars_used": (
                len(
                    dataframe
                )
            ),

            "status": (
                "SUCCESS"
            ),
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

        rvol = float(
            data.get(
                "rvol",
                0.0,
            )
            or 0.0
        )

        # ----------------------------------------------------
        # RVOL = 25 points
        # ----------------------------------------------------

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

        else:

            warnings.append(
                "Weak relative volume"
            )

        # ----------------------------------------------------
        # Compression = 20 points
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # VWAP = 15 points
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Distance to resistance = 25 points
        # ----------------------------------------------------

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
                "Resistance already being tested/broken"
            )

        else:

            warnings.append(
                "Too far from resistance"
            )

        # ----------------------------------------------------
        # Volume acceleration = 15 points
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Momentum bonus
        # ----------------------------------------------------

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
    # BUILD MODEL FEATURES
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
    # EVALUATE METRICS
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

        # ----------------------------------------------------
        # No trained ML yet:
        # Trust deterministic live-market rules.
        # ----------------------------------------------------

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

            # Real market structure remains majority.
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

        # ----------------------------------------------------
        # Research status.
        #
        # Deliberately NOT named ENTRY.
        # JALWE makes the final trade decision.
        # ----------------------------------------------------

        status = "WATCH"

        if final_score >= 82:

            status = (
                "READY_FOR_JALWE_RESEARCH"
            )

        elif final_score >= 70:

            status = (
                "CONFIRMED"
            )

        elif final_score >= 55:

            status = (
                "SETUP"
            )

        ready = bool(
            final_score >= 70
        )

        return {
            "score": (
                final_score
            ),

            "status": (
                status
            ),

            "ready": (
                ready
            ),

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

            "reasons": (
                reasons
            ),

            "warnings": (
                warnings
            ),
        }

    # ========================================================
    # ANALYZE SYMBOL
    # ========================================================

    def analyze_symbol(
        self,
        symbol: str,
    ) -> PreBreakoutResult:

        symbol = str(
            symbol
            or ""
        ).strip().upper()

        if not symbol:

            return PreBreakoutResult(
                symbol="",
                status="ERROR",
                error=(
                    "Symbol cannot be empty."
                ),
            )

        try:

            metrics = (
                self.calculate_metrics(
                    symbol
                )
            )

        except Exception as exc:

            logger.warning(
                "PreBreakout metrics failed "
                "for %s: %s",
                symbol,
                exc,
            )

            return PreBreakoutResult(
                symbol=symbol,
                status="DATA_ERROR",
                ready=False,
                warnings=[
                    "MARKET_DATA_UNAVAILABLE"
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

            error=None,
        )

    # ========================================================
    # BATCH ANALYSIS
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

        for symbol in (
            symbols
            or []
        ):

            symbol = str(
                symbol
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
                item.score
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

            "feature_count": (
                len(
                    self.FEATURE_NAMES
                )
            ),

            "role": (
                "PRE_BREAKOUT_RESEARCH_ONLY"
            ),

            "order_execution_enabled": (
                False
            ),
        }
