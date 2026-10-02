from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional


logger = logging.getLogger(__name__)

UTC = timezone.utc
DEFAULT_SQLITE_PATH = (
    Path(__file__).resolve().parent
    / "data"
    / "apex_setup_memory.db"
)

ALLOWED_WAKE_VERDICTS = {
    "WATCH",
    "RESEARCH_CANDIDATE",
    "HIGH_PRIORITY_RESEARCH",
}


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_iso(value: Optional[datetime] = None) -> str:
    dt = value or utc_now()

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    else:
        dt = dt.astimezone(UTC)

    return dt.isoformat()


def _parse_datetime(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()

    if not text:
        return None

    try:
        parsed = datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )
    except (TypeError, ValueError):
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    else:
        parsed = parsed.astimezone(UTC)

    return parsed


def _float(
    value: Any,
    default: Optional[float] = None,
) -> Optional[float]:
    try:
        if value is None:
            return default

        result = float(value)

        if result != result:
            return default

        return result

    except (TypeError, ValueError):
        return default


def _json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )


def _loads(value: Any) -> dict[str, Any]:
    try:
        decoded = json.loads(
            str(value or "{}")
        )

        if isinstance(decoded, dict):
            return decoded

    except Exception:
        pass

    return {}


class SetupMemoryStore:
    """
    Persistent APEX setup memory.

    Railway uses DATABASE_URL/PostgreSQL when available so setup
    memory survives APEX container redeploys. SQLite is a safe
    local/test fallback.

    This store is research-only. It has no broker integration.
    """

    def __init__(
        self,
        database_url: Optional[str] = None,
        sqlite_path: Optional[str] = None,
    ) -> None:
        self.database_url = (
            database_url
            if database_url is not None
            else os.getenv(
                "DATABASE_URL",
                "",
            ).strip()
        )

        self.backend = (
            "POSTGRES"
            if self.database_url
            else "SQLITE"
        )

        self.sqlite_path = (
            sqlite_path
            or os.getenv(
                "APEX_SETUP_MEMORY_DB",
                str(DEFAULT_SQLITE_PATH),
            )
        )

        self._lock = threading.RLock()
        self._sqlite_conn: Optional[
            sqlite3.Connection
        ] = None

        self._initialize()

    def _connect_postgres(self):
        try:
            import psycopg2
        except ImportError as exc:
            raise RuntimeError(
                "psycopg2-binary is required "
                "for PostgreSQL setup memory."
            ) from exc

        return psycopg2.connect(
            self.database_url,
            connect_timeout=10,
        )

    def _connect_sqlite(
        self,
    ) -> sqlite3.Connection:
        with self._lock:
            if self._sqlite_conn is not None:
                return self._sqlite_conn

            if self.sqlite_path != ":memory:":
                path = Path(
                    self.sqlite_path
                )

                path.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

            conn = sqlite3.connect(
                self.sqlite_path,
                timeout=30,
                check_same_thread=False,
            )

            conn.row_factory = sqlite3.Row
            conn.execute(
                "PRAGMA journal_mode=WAL"
            )
            conn.execute(
                "PRAGMA synchronous=NORMAL"
            )

            self._sqlite_conn = conn

            return conn

    def _initialize(self) -> None:
        if self.backend == "POSTGRES":
            conn = self._connect_postgres()

            try:
                with conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            CREATE TABLE IF NOT EXISTS
                            apex_setup_memory (
                                symbol TEXT PRIMARY KEY,
                                status TEXT NOT NULL,
                                first_seen_at TEXT NOT NULL,
                                last_seen_at TEXT NOT NULL,
                                last_checked_at TEXT,
                                last_wake_at TEXT,
                                observation_count INTEGER NOT NULL,
                                first_score DOUBLE PRECISION NOT NULL,
                                previous_score DOUBLE PRECISION NOT NULL,
                                latest_score DOUBLE PRECISION NOT NULL,
                                best_score DOUBLE PRECISION NOT NULL,
                                score_delta DOUBLE PRECISION NOT NULL,
                                confidence DOUBLE PRECISION NOT NULL,
                                verdict TEXT,
                                current_price DOUBLE PRECISION,
                                activation_price DOUBLE PRECISION,
                                entry_zone_low DOUBLE PRECISION,
                                entry_zone_high DOUBLE PRECISION,
                                support_reference DOUBLE PRECISION,
                                resistance_5m DOUBLE PRECISION,
                                resistance_30m DOUBLE PRECISION,
                                resistance_1h DOUBLE PRECISION,
                                resistance_1d DOUBLE PRECISION,
                                target_1_reference DOUBLE PRECISION,
                                target_2_reference DOUBLE PRECISION,
                                target_3_reference DOUBLE PRECISION,
                                reason TEXT NOT NULL,
                                snapshot_json TEXT NOT NULL
                            )
                            """
                        )

                        cur.execute(
                            """
                            CREATE TABLE IF NOT EXISTS
                            apex_setup_history (
                                id BIGSERIAL PRIMARY KEY,
                                symbol TEXT NOT NULL,
                                observed_at TEXT NOT NULL,
                                score DOUBLE PRECISION NOT NULL,
                                confidence DOUBLE PRECISION NOT NULL,
                                verdict TEXT,
                                current_price DOUBLE PRECISION,
                                activation_price DOUBLE PRECISION,
                                score_delta DOUBLE PRECISION NOT NULL,
                                snapshot_json TEXT NOT NULL
                            )
                            """
                        )

                        cur.execute(
                            """
                            CREATE INDEX IF NOT EXISTS
                            idx_apex_setup_memory_due
                            ON apex_setup_memory (
                                status,
                                last_checked_at,
                                best_score DESC
                            )
                            """
                        )

                        cur.execute(
                            """
                            CREATE INDEX IF NOT EXISTS
                            idx_apex_setup_history_symbol
                            ON apex_setup_history (
                                symbol,
                                observed_at DESC
                            )
                            """
                        )

            finally:
                conn.close()

            return

        conn = self._connect_sqlite()

        with self._lock:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS
                apex_setup_memory (
                    symbol TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    last_checked_at TEXT,
                    last_wake_at TEXT,
                    observation_count INTEGER NOT NULL,
                    first_score REAL NOT NULL,
                    previous_score REAL NOT NULL,
                    latest_score REAL NOT NULL,
                    best_score REAL NOT NULL,
                    score_delta REAL NOT NULL,
                    confidence REAL NOT NULL,
                    verdict TEXT,
                    current_price REAL,
                    activation_price REAL,
                    entry_zone_low REAL,
                    entry_zone_high REAL,
                    support_reference REAL,
                    resistance_5m REAL,
                    resistance_30m REAL,
                    resistance_1h REAL,
                    resistance_1d REAL,
                    target_1_reference REAL,
                    target_2_reference REAL,
                    target_3_reference REAL,
                    reason TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS
                apex_setup_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    score REAL NOT NULL,
                    confidence REAL NOT NULL,
                    verdict TEXT,
                    current_price REAL,
                    activation_price REAL,
                    score_delta REAL NOT NULL,
                    snapshot_json TEXT NOT NULL
                )
                """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_apex_setup_memory_due
                ON apex_setup_memory (
                    status,
                    last_checked_at,
                    best_score DESC
                )
                """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_apex_setup_history_symbol
                ON apex_setup_history (
                    symbol,
                    observed_at DESC
                )
                """
            )

            conn.commit()

    @staticmethod
    def _row_dict(row: Any) -> Optional[dict[str, Any]]:
        if row is None:
            return None

        if isinstance(row, dict):
            return dict(row)

        try:
            return dict(row)
        except Exception:
            return None

    def get(
        self,
        symbol: str,
    ) -> Optional[dict[str, Any]]:
        symbol = str(
            symbol or ""
        ).strip().upper()

        if not symbol:
            return None

        if self.backend == "POSTGRES":
            conn = self._connect_postgres()

            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT *
                        FROM apex_setup_memory
                        WHERE symbol = %s
                        """,
                        (symbol,),
                    )

                    row = cur.fetchone()

                    if row is None:
                        return None

                    columns = [
                        item.name
                        if hasattr(item, "name")
                        else item[0]
                        for item in cur.description
                    ]

                    result = dict(
                        zip(columns, row)
                    )

            finally:
                conn.close()

        else:
            conn = self._connect_sqlite()

            with self._lock:
                row = conn.execute(
                    """
                    SELECT *
                    FROM apex_setup_memory
                    WHERE symbol = ?
                    """,
                    (symbol,),
                ).fetchone()

            result = (
                dict(row)
                if row is not None
                else None
            )

        if result is not None:
            result["snapshot"] = _loads(
                result.get(
                    "snapshot_json"
                )
            )

        return result

    def observe(
        self,
        snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        symbol = str(
            snapshot.get(
                "symbol",
                "",
            )
            or ""
        ).strip().upper()

        if not symbol:
            raise ValueError(
                "Setup snapshot requires a symbol."
            )

        observed_at = str(
            snapshot.get(
                "observed_at"
            )
            or utc_iso()
        )

        score = float(
            _float(
                snapshot.get(
                    "score"
                ),
                0.0,
            )
            or 0.0
        )

        confidence = float(
            _float(
                snapshot.get(
                    "confidence"
                ),
                0.0,
            )
            or 0.0
        )

        existing = self.get(
            symbol
        )

        if existing is None:
            first_seen_at = observed_at
            observation_count = 1
            first_score = score
            previous_score = score
            best_score = score
            last_checked_at = None
            last_wake_at = None

        else:
            first_seen_at = str(
                existing.get(
                    "first_seen_at"
                )
                or observed_at
            )

            observation_count = (
                int(
                    existing.get(
                        "observation_count",
                        0,
                    )
                    or 0
                )
                + 1
            )

            first_score = float(
                existing.get(
                    "first_score",
                    score,
                )
                or score
            )

            previous_score = float(
                existing.get(
                    "latest_score",
                    score,
                )
                or score
            )

            best_score = max(
                float(
                    existing.get(
                        "best_score",
                        score,
                    )
                    or score
                ),
                score,
            )

            last_checked_at = (
                existing.get(
                    "last_checked_at"
                )
            )

            last_wake_at = (
                existing.get(
                    "last_wake_at"
                )
            )

        score_delta = round(
            score
            - previous_score,
            4,
        )

        values = {
            "symbol": symbol,
            "status": str(
                snapshot.get(
                    "status",
                    "ACTIVE",
                )
                or "ACTIVE"
            ).upper(),
            "first_seen_at": first_seen_at,
            "last_seen_at": observed_at,
            "last_checked_at": last_checked_at,
            "last_wake_at": last_wake_at,
            "observation_count": observation_count,
            "first_score": first_score,
            "previous_score": previous_score,
            "latest_score": score,
            "best_score": best_score,
            "score_delta": score_delta,
            "confidence": confidence,
            "verdict": snapshot.get(
                "verdict"
            ),
            "current_price": _float(
                snapshot.get(
                    "current_price"
                )
            ),
            "activation_price": _float(
                snapshot.get(
                    "activation_price"
                )
            ),
            "entry_zone_low": _float(
                snapshot.get(
                    "entry_zone_low"
                )
            ),
            "entry_zone_high": _float(
                snapshot.get(
                    "entry_zone_high"
                )
            ),
            "support_reference": _float(
                snapshot.get(
                    "support_reference"
                )
            ),
            "resistance_5m": _float(
                snapshot.get(
                    "resistance_5m"
                )
            ),
            "resistance_30m": _float(
                snapshot.get(
                    "resistance_30m"
                )
            ),
            "resistance_1h": _float(
                snapshot.get(
                    "resistance_1h"
                )
            ),
            "resistance_1d": _float(
                snapshot.get(
                    "resistance_1d"
                )
            ),
            "target_1_reference": _float(
                snapshot.get(
                    "target_1_reference"
                )
            ),
            "target_2_reference": _float(
                snapshot.get(
                    "target_2_reference"
                )
            ),
            "target_3_reference": _float(
                snapshot.get(
                    "target_3_reference"
                )
            ),
            "reason": str(
                snapshot.get(
                    "reason",
                    "",
                )
                or ""
            ),
            "snapshot_json": _json(
                snapshot
            ),
        }

        ordered = (
            values["symbol"],
            values["status"],
            values["first_seen_at"],
            values["last_seen_at"],
            values["last_checked_at"],
            values["last_wake_at"],
            values["observation_count"],
            values["first_score"],
            values["previous_score"],
            values["latest_score"],
            values["best_score"],
            values["score_delta"],
            values["confidence"],
            values["verdict"],
            values["current_price"],
            values["activation_price"],
            values["entry_zone_low"],
            values["entry_zone_high"],
            values["support_reference"],
            values["resistance_5m"],
            values["resistance_30m"],
            values["resistance_1h"],
            values["resistance_1d"],
            values["target_1_reference"],
            values["target_2_reference"],
            values["target_3_reference"],
            values["reason"],
            values["snapshot_json"],
        )

        if self.backend == "POSTGRES":
            conn = self._connect_postgres()

            try:
                with conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO apex_setup_memory (
                                symbol,status,first_seen_at,last_seen_at,
                                last_checked_at,last_wake_at,
                                observation_count,first_score,
                                previous_score,latest_score,best_score,
                                score_delta,confidence,verdict,
                                current_price,activation_price,
                                entry_zone_low,entry_zone_high,
                                support_reference,resistance_5m,
                                resistance_30m,resistance_1h,
                                resistance_1d,target_1_reference,
                                target_2_reference,target_3_reference,
                                reason,snapshot_json
                            )
                            VALUES (
                                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                                %s,%s,%s,%s,%s,%s,%s,%s
                            )
                            ON CONFLICT (symbol)
                            DO UPDATE SET
                                status = EXCLUDED.status,
                                last_seen_at = EXCLUDED.last_seen_at,
                                last_checked_at =
                                    apex_setup_memory.last_checked_at,
                                last_wake_at =
                                    apex_setup_memory.last_wake_at,
                                observation_count =
                                    EXCLUDED.observation_count,
                                first_score =
                                    apex_setup_memory.first_score,
                                previous_score =
                                    EXCLUDED.previous_score,
                                latest_score =
                                    EXCLUDED.latest_score,
                                best_score =
                                    EXCLUDED.best_score,
                                score_delta =
                                    EXCLUDED.score_delta,
                                confidence =
                                    EXCLUDED.confidence,
                                verdict =
                                    EXCLUDED.verdict,
                                current_price =
                                    EXCLUDED.current_price,
                                activation_price =
                                    EXCLUDED.activation_price,
                                entry_zone_low =
                                    EXCLUDED.entry_zone_low,
                                entry_zone_high =
                                    EXCLUDED.entry_zone_high,
                                support_reference =
                                    EXCLUDED.support_reference,
                                resistance_5m =
                                    EXCLUDED.resistance_5m,
                                resistance_30m =
                                    EXCLUDED.resistance_30m,
                                resistance_1h =
                                    EXCLUDED.resistance_1h,
                                resistance_1d =
                                    EXCLUDED.resistance_1d,
                                target_1_reference =
                                    EXCLUDED.target_1_reference,
                                target_2_reference =
                                    EXCLUDED.target_2_reference,
                                target_3_reference =
                                    EXCLUDED.target_3_reference,
                                reason =
                                    EXCLUDED.reason,
                                snapshot_json =
                                    EXCLUDED.snapshot_json
                            """,
                            ordered,
                        )

                        cur.execute(
                            """
                            INSERT INTO apex_setup_history (
                                symbol,observed_at,score,confidence,
                                verdict,current_price,activation_price,
                                score_delta,snapshot_json
                            )
                            VALUES (
                                %s,%s,%s,%s,%s,%s,%s,%s,%s
                            )
                            """,
                            (
                                symbol,
                                observed_at,
                                score,
                                confidence,
                                values["verdict"],
                                values["current_price"],
                                values["activation_price"],
                                score_delta,
                                values["snapshot_json"],
                            ),
                        )

            finally:
                conn.close()

        else:
            conn = self._connect_sqlite()

            with self._lock:
                conn.execute(
                    """
                    INSERT INTO apex_setup_memory (
                        symbol,status,first_seen_at,last_seen_at,
                        last_checked_at,last_wake_at,
                        observation_count,first_score,
                        previous_score,latest_score,best_score,
                        score_delta,confidence,verdict,
                        current_price,activation_price,
                        entry_zone_low,entry_zone_high,
                        support_reference,resistance_5m,
                        resistance_30m,resistance_1h,
                        resistance_1d,target_1_reference,
                        target_2_reference,target_3_reference,
                        reason,snapshot_json
                    )
                    VALUES (
                        ?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                        ?,?,?,?,?,?,?,?,?,?,?,?,?,?
                    )
                    ON CONFLICT(symbol)
                    DO UPDATE SET
                        status = excluded.status,
                        last_seen_at = excluded.last_seen_at,
                        observation_count =
                            excluded.observation_count,
                        previous_score =
                            excluded.previous_score,
                        latest_score =
                            excluded.latest_score,
                        best_score =
                            excluded.best_score,
                        score_delta =
                            excluded.score_delta,
                        confidence =
                            excluded.confidence,
                        verdict =
                            excluded.verdict,
                        current_price =
                            excluded.current_price,
                        activation_price =
                            excluded.activation_price,
                        entry_zone_low =
                            excluded.entry_zone_low,
                        entry_zone_high =
                            excluded.entry_zone_high,
                        support_reference =
                            excluded.support_reference,
                        resistance_5m =
                            excluded.resistance_5m,
                        resistance_30m =
                            excluded.resistance_30m,
                        resistance_1h =
                            excluded.resistance_1h,
                        resistance_1d =
                            excluded.resistance_1d,
                        target_1_reference =
                            excluded.target_1_reference,
                        target_2_reference =
                            excluded.target_2_reference,
                        target_3_reference =
                            excluded.target_3_reference,
                        reason =
                            excluded.reason,
                        snapshot_json =
                            excluded.snapshot_json
                    """,
                    ordered,
                )

                conn.execute(
                    """
                    INSERT INTO apex_setup_history (
                        symbol,observed_at,score,confidence,
                        verdict,current_price,activation_price,
                        score_delta,snapshot_json
                    )
                    VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        symbol,
                        observed_at,
                        score,
                        confidence,
                        values["verdict"],
                        values["current_price"],
                        values["activation_price"],
                        score_delta,
                        values["snapshot_json"],
                    ),
                )

                conn.commit()

        result = self.get(
            symbol
        )

        if result is None:
            raise RuntimeError(
                "Setup memory observation was not persisted."
            )

        return result

    def list_due(
        self,
        *,
        limit: int,
        max_age_days: int,
        exclude_symbols: Optional[set[str]] = None,
    ) -> list[dict[str, Any]]:
        limit = max(
            1,
            int(limit),
        )

        cutoff = utc_iso(
            utc_now()
            - timedelta(
                days=max(
                    1,
                    int(max_age_days),
                )
            )
        )

        if self.backend == "POSTGRES":
            conn = self._connect_postgres()

            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT *
                        FROM apex_setup_memory
                        WHERE status = 'ACTIVE'
                          AND last_seen_at >= %s
                        ORDER BY
                            CASE
                                WHEN last_checked_at IS NULL
                                THEN 0
                                ELSE 1
                            END ASC,
                            last_checked_at ASC,
                            best_score DESC
                        LIMIT %s
                        """,
                        (
                            cutoff,
                            limit * 5,
                        ),
                    )

                    rows = cur.fetchall()

                    columns = [
                        item.name
                        if hasattr(item, "name")
                        else item[0]
                        for item in cur.description
                    ]

                    records = [
                        dict(
                            zip(columns, row)
                        )
                        for row in rows
                    ]

            finally:
                conn.close()

        else:
            conn = self._connect_sqlite()

            with self._lock:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM apex_setup_memory
                    WHERE status = 'ACTIVE'
                      AND last_seen_at >= ?
                    ORDER BY
                        CASE
                            WHEN last_checked_at IS NULL
                            THEN 0
                            ELSE 1
                        END ASC,
                        last_checked_at ASC,
                        best_score DESC
                    LIMIT ?
                    """,
                    (
                        cutoff,
                        limit * 5,
                    ),
                ).fetchall()

            records = [
                dict(row)
                for row in rows
            ]

        excluded = {
            str(symbol).strip().upper()
            for symbol in (
                exclude_symbols
                or set()
            )
            if str(symbol).strip()
        }

        result = []

        for row in records:
            symbol = str(
                row.get(
                    "symbol",
                    "",
                )
                or ""
            ).upper()

            if symbol in excluded:
                continue

            row["snapshot"] = _loads(
                row.get(
                    "snapshot_json"
                )
            )

            result.append(
                row
            )

            if len(result) >= limit:
                break

        return result

    def _mark(
        self,
        symbol: str,
        field: str,
        when: Optional[datetime] = None,
    ) -> None:
        if field not in {
            "last_checked_at",
            "last_wake_at",
        }:
            raise ValueError(
                "Unsupported setup memory timestamp field."
            )

        symbol = str(
            symbol or ""
        ).strip().upper()

        if not symbol:
            return

        value = utc_iso(
            when
        )

        if self.backend == "POSTGRES":
            conn = self._connect_postgres()

            try:
                with conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            f"""
                            UPDATE apex_setup_memory
                            SET {field} = %s
                            WHERE symbol = %s
                            """,
                            (
                                value,
                                symbol,
                            ),
                        )

            finally:
                conn.close()

            return

        conn = self._connect_sqlite()

        with self._lock:
            conn.execute(
                f"""
                UPDATE apex_setup_memory
                SET {field} = ?
                WHERE symbol = ?
                """,
                (
                    value,
                    symbol,
                ),
            )
            conn.commit()

    def mark_checked(
        self,
        symbol: str,
        when: Optional[datetime] = None,
    ) -> None:
        self._mark(
            symbol,
            "last_checked_at",
            when,
        )

    def mark_wake(
        self,
        symbol: str,
        when: Optional[datetime] = None,
    ) -> None:
        self._mark(
            symbol,
            "last_wake_at",
            when,
        )

    def wake_allowed(
        self,
        row: dict[str, Any],
        *,
        cooldown_minutes: int,
        now: Optional[datetime] = None,
    ) -> bool:
        last_wake = _parse_datetime(
            row.get(
                "last_wake_at"
            )
        )

        if last_wake is None:
            return True

        current = now or utc_now()

        return (
            current
            - last_wake
        ) >= timedelta(
            minutes=max(
                1,
                int(cooldown_minutes),
            )
        )

    def close(self) -> None:
        with self._lock:
            if self._sqlite_conn is not None:
                try:
                    self._sqlite_conn.close()
                except Exception:
                    pass

                self._sqlite_conn = None


class SetupMemoryWatcher:
    """
    Two-lane APEX research memory.

    FAST lane:
        Existing ResearchOrchestrator shortlist continues to publish
        immediately to JALWE.

    LONG-TERM lane:
        Strong research packets are remembered for days/weeks.
        A small rotating subset is re-checked each cycle. When a saved
        setup approaches its activation level, APEX performs fresh
        News + Liquidity + AI research and republishes only if the
        current evidence still passes the research gates.

    This class NEVER places or manages broker orders.
    """

    def __init__(
        self,
        orchestrator: Any,
        *,
        store: Optional[
            SetupMemoryStore
        ] = None,
        max_refresh_per_cycle: Optional[int] = None,
        max_age_days: Optional[int] = None,
        wake_distance_pct: Optional[float] = None,
        wake_cooldown_minutes: Optional[int] = None,
        minimum_memory_score: Optional[float] = None,
        minimum_pre_score: Optional[float] = None,
        minimum_pre_confidence: Optional[float] = None,
    ) -> None:
        self.orchestrator = orchestrator

        self.store = (
            store
            or SetupMemoryStore()
        )

        self.max_refresh_per_cycle = max(
            1,
            int(
                max_refresh_per_cycle
                if max_refresh_per_cycle is not None
                else os.getenv(
                    "APEX_SETUP_MEMORY_REFRESH_PER_CYCLE",
                    "4",
                )
            ),
        )

        self.max_age_days = max(
            1,
            int(
                max_age_days
                if max_age_days is not None
                else os.getenv(
                    "APEX_SETUP_MEMORY_MAX_AGE_DAYS",
                    "30",
                )
            ),
        )

        self.wake_distance_pct = max(
            0.1,
            float(
                wake_distance_pct
                if wake_distance_pct is not None
                else os.getenv(
                    "APEX_SETUP_WAKE_DISTANCE_PCT",
                    "1.5",
                )
            ),
        )

        self.wake_cooldown_minutes = max(
            1,
            int(
                wake_cooldown_minutes
                if wake_cooldown_minutes is not None
                else os.getenv(
                    "APEX_SETUP_WAKE_COOLDOWN_MINUTES",
                    "30",
                )
            ),
        )

        self.minimum_memory_score = float(
            minimum_memory_score
            if minimum_memory_score is not None
            else os.getenv(
                "APEX_SETUP_MEMORY_MIN_SCORE",
                "55",
            )
        )

        self.minimum_pre_score = float(
            minimum_pre_score
            if minimum_pre_score is not None
            else os.getenv(
                "APEX_SETUP_WAKE_MIN_PRE_SCORE",
                "55",
            )
        )

        self.minimum_pre_confidence = float(
            minimum_pre_confidence
            if minimum_pre_confidence is not None
            else os.getenv(
                "APEX_SETUP_WAKE_MIN_CONFIDENCE",
                "65",
            )
        )

    @staticmethod
    def _packet_metadata(
        packet: Any,
    ) -> dict[str, Any]:
        metadata = getattr(
            packet,
            "metadata",
            {},
        )

        if isinstance(
            metadata,
            dict,
        ):
            return dict(
                metadata
            )

        return {}

    @staticmethod
    def _snapshot_from_packet(
        packet: Any,
        *,
        lane: str,
    ) -> dict[str, Any]:
        metadata = (
            SetupMemoryWatcher
            ._packet_metadata(
                packet
            )
        )

        context = metadata.get(
            "setup_context",
            {},
        )

        if not isinstance(
            context,
            dict,
        ):
            context = {}

        reason_parts = []

        for value in (
            context.get(
                "reason"
            ),
            ", ".join(
                list(
                    getattr(
                        packet,
                        "evidence",
                        [],
                    )
                    or []
                )[:4]
            ),
        ):
            text = str(
                value or ""
            ).strip()

            if text:
                reason_parts.append(
                    text
                )

        score = float(
            _float(
                getattr(
                    packet,
                    "research_score",
                    0.0,
                ),
                0.0,
            )
            or 0.0
        )

        return {
            "symbol": str(
                getattr(
                    packet,
                    "symbol",
                    "",
                )
                or ""
            ).strip().upper(),
            "status": "ACTIVE",
            "observed_at": str(
                getattr(
                    packet,
                    "created_at",
                    "",
                )
                or utc_iso()
            ),
            "score": score,
            "confidence": float(
                _float(
                    getattr(
                        packet,
                        "confidence",
                        0.0,
                    ),
                    0.0,
                )
                or 0.0
            ),
            "verdict": str(
                getattr(
                    packet,
                    "verdict",
                    "",
                )
                or ""
            ).upper(),
            "current_price": _float(
                context.get(
                    "current_price",
                    getattr(
                        packet,
                        "radar_price",
                        None,
                    ),
                )
            ),
            "activation_price": _float(
                context.get(
                    "activation_price"
                )
            ),
            "entry_zone_low": _float(
                context.get(
                    "entry_zone_low"
                )
            ),
            "entry_zone_high": _float(
                context.get(
                    "entry_zone_high"
                )
            ),
            "support_reference": _float(
                context.get(
                    "support_reference"
                )
            ),
            "resistance_5m": _float(
                context.get(
                    "resistance_5m"
                )
            ),
            "resistance_30m": _float(
                context.get(
                    "resistance_30m"
                )
            ),
            "resistance_1h": _float(
                context.get(
                    "resistance_1h"
                )
            ),
            "resistance_1d": _float(
                context.get(
                    "resistance_1d"
                )
            ),
            "target_1_reference": _float(
                context.get(
                    "target_1_reference"
                )
            ),
            "target_2_reference": _float(
                context.get(
                    "target_2_reference"
                )
            ),
            "target_3_reference": _float(
                context.get(
                    "target_3_reference"
                )
            ),
            "reason": " | ".join(
                reason_parts
            ),
            "watch_lane": lane,
            "radar_score": _float(
                getattr(
                    packet,
                    "radar_score",
                    None,
                )
            ),
            "radar_rvol": _float(
                getattr(
                    packet,
                    "radar_rvol",
                    None,
                )
            ),
            "radar_change_pct": _float(
                getattr(
                    packet,
                    "radar_change_pct",
                    None,
                )
            ),
            "prebreakout_score": _float(
                getattr(
                    packet,
                    "prebreakout_score",
                    None,
                )
            ),
            "score_5m": _float(
                getattr(
                    packet,
                    "score_5m",
                    None,
                )
            ),
            "score_30m": _float(
                getattr(
                    packet,
                    "score_30m",
                    None,
                )
            ),
            "score_1h": _float(
                getattr(
                    packet,
                    "score_1h",
                    None,
                )
            ),
            "score_1d": _float(
                getattr(
                    packet,
                    "score_1d",
                    None,
                )
            ),
        }

    def observe_cycle(
        self,
        cycle: Any,
    ) -> dict[str, Any]:
        remembered = 0
        skipped = 0
        errors: list[str] = []

        packets = list(
            getattr(
                cycle,
                "packets",
                [],
            )
            or []
        )

        for packet in packets:
            try:
                score = float(
                    _float(
                        getattr(
                            packet,
                            "research_score",
                            0.0,
                        ),
                        0.0,
                    )
                    or 0.0
                )

                if (
                    score
                    < self.minimum_memory_score
                    or bool(
                        getattr(
                            packet,
                            "critical_risk",
                            False,
                        )
                    )
                ):
                    skipped += 1
                    continue

                snapshot = (
                    self
                    ._snapshot_from_packet(
                        packet,
                        lane="FAST_OPPORTUNITY",
                    )
                )

                row = self.store.observe(
                    snapshot
                )

                metadata = (
                    self._packet_metadata(
                        packet
                    )
                )

                metadata[
                    "setup_memory"
                ] = {
                    "observation_count":
                        row.get(
                            "observation_count"
                        ),
                    "first_score":
                        row.get(
                            "first_score"
                        ),
                    "previous_score":
                        row.get(
                            "previous_score"
                        ),
                    "latest_score":
                        row.get(
                            "latest_score"
                        ),
                    "best_score":
                        row.get(
                            "best_score"
                        ),
                    "score_delta":
                        row.get(
                            "score_delta"
                        ),
                }

                packet.metadata = metadata
                remembered += 1

            except Exception as exc:
                errors.append(
                    f"{getattr(packet, 'symbol', 'UNKNOWN')}:"
                    f"{type(exc).__name__}:{exc}"
                )

        return {
            "remembered": remembered,
            "skipped": skipped,
            "errors": errors,
        }

    def _near_activation(
        self,
        *,
        current_price: Optional[float],
        activation_price: Optional[float],
        pre_score: float,
        ready: bool,
    ) -> tuple[bool, Optional[float], str]:
        if (
            current_price is None
            or activation_price is None
            or current_price <= 0
            or activation_price <= 0
        ):
            return (
                bool(
                    ready
                    and pre_score >= 78.0
                ),
                None,
                "TECHNICAL_READY"
                if ready
                and pre_score >= 78.0
                else "NO_ACTIVATION_LEVEL",
            )

        distance_pct = (
            (
                activation_price
                - current_price
            )
            / activation_price
            * 100.0
        )

        near = (
            -0.75
            <= distance_pct
            <= self.wake_distance_pct
        )

        if near:
            return (
                True,
                round(
                    distance_pct,
                    4,
                ),
                "NEAR_ACTIVATION",
            )

        if (
            ready
            and pre_score >= 78.0
            and -2.5 <= distance_pct < -0.75
        ):
            return (
                True,
                round(
                    distance_pct,
                    4,
                ),
                "FRESH_BREAKOUT_CONFIRMATION",
            )

        return (
            False,
            round(
                distance_pct,
                4,
            ),
            "NOT_NEAR_ACTIVATION",
        )

    @staticmethod
    def _synthetic_radar_context(
        row: dict[str, Any],
        current_price: Optional[float],
    ) -> Any:
        snapshot = row.get(
            "snapshot",
            {},
        )

        if not isinstance(
            snapshot,
            dict,
        ):
            snapshot = {}

        return SimpleNamespace(
            symbol=row.get(
                "symbol"
            ),
            rank_score=_float(
                snapshot.get(
                    "radar_score"
                )
            ),
            relative_volume=_float(
                snapshot.get(
                    "radar_rvol"
                )
            ),
            change_pct=_float(
                snapshot.get(
                    "radar_change_pct"
                )
            ),
            price=current_price,
        )

    def refresh_saved_setups(
        self,
        *,
        exclude_symbols: Optional[
            set[str]
        ] = None,
    ) -> dict[str, Any]:
        due = self.store.list_due(
            limit=self.max_refresh_per_cycle,
            max_age_days=self.max_age_days,
            exclude_symbols=exclude_symbols,
        )

        checked = 0
        near_count = 0
        published: list[str] = []
        errors: list[str] = []

        for row in due:
            symbol = str(
                row.get(
                    "symbol",
                    "",
                )
                or ""
            ).strip().upper()

            if not symbol:
                continue

            checked += 1

            try:
                pre = (
                    self.orchestrator
                    .prebreakout
                    .analyze_symbol(
                        symbol
                    )
                )

                pre_score = float(
                    _float(
                        getattr(
                            pre,
                            "score",
                            0.0,
                        ),
                        0.0,
                    )
                    or 0.0
                )

                pre_confidence = float(
                    _float(
                        getattr(
                            pre,
                            "data_confidence",
                            0.0,
                        ),
                        0.0,
                    )
                    or 0.0
                )

                current_price = _float(
                    getattr(
                        pre,
                        "current_price",
                        None,
                    )
                )

                activation_price = _float(
                    row.get(
                        "activation_price"
                    )
                )

                if (
                    pre_score
                    < self.minimum_pre_score
                    or pre_confidence
                    < self.minimum_pre_confidence
                ):
                    continue

                (
                    near,
                    distance_pct,
                    wake_reason,
                ) = self._near_activation(
                    current_price=current_price,
                    activation_price=activation_price,
                    pre_score=pre_score,
                    ready=bool(
                        getattr(
                            pre,
                            "ready",
                            False,
                        )
                    ),
                )

                if not near:
                    continue

                near_count += 1

                if not self.store.wake_allowed(
                    row,
                    cooldown_minutes=(
                        self.wake_cooldown_minutes
                    ),
                ):
                    continue

                news = (
                    self.orchestrator
                    .news
                    .fetch_symbol_news(
                        symbol
                    )
                )

                liquidity = (
                    self.orchestrator
                    .liquidity
                    .analyze_symbol(
                        symbol
                    )
                )

                ai_result = (
                    self.orchestrator
                    .ai
                    .evaluate_research(
                        symbol,
                        prebreakout_result=pre,
                        news_result=news,
                        liquidity_result=liquidity,
                    )
                )

                if str(
                    ai_result.get(
                        "status",
                        "",
                    )
                    or ""
                ).upper() != "SUCCESS":
                    continue

                candidate = (
                    self._synthetic_radar_context(
                        row,
                        current_price,
                    )
                )

                packet = (
                    self.orchestrator
                    ._build_packet(
                        candidate=candidate,
                        pre_result=pre,
                        news_result=news,
                        liquidity_result=liquidity,
                        ai_result=ai_result,
                    )
                )

                metadata = (
                    self._packet_metadata(
                        packet
                    )
                )

                metadata[
                    "watch_lane"
                ] = (
                    "LONG_TERM_REACTIVATION"
                )

                metadata[
                    "setup_memory"
                ] = {
                    "first_seen_at":
                        row.get(
                            "first_seen_at"
                        ),
                    "last_seen_at":
                        row.get(
                            "last_seen_at"
                        ),
                    "observation_count":
                        row.get(
                            "observation_count"
                        ),
                    "first_score":
                        row.get(
                            "first_score"
                        ),
                    "previous_score":
                        row.get(
                            "previous_score"
                        ),
                    "latest_score":
                        row.get(
                            "latest_score"
                        ),
                    "best_score":
                        row.get(
                            "best_score"
                        ),
                    "score_delta":
                        row.get(
                            "score_delta"
                        ),
                    "distance_to_activation_pct":
                        distance_pct,
                    "wake_reason":
                        wake_reason,
                }

                packet.metadata = metadata

                verdict = str(
                    getattr(
                        packet,
                        "verdict",
                        "",
                    )
                    or ""
                ).upper()

                if (
                    verdict
                    not in ALLOWED_WAKE_VERDICTS
                    or bool(
                        getattr(
                            packet,
                            "critical_risk",
                            False,
                        )
                    )
                ):
                    self.store.observe(
                        self._snapshot_from_packet(
                            packet,
                            lane=(
                                "LONG_TERM_RECHECK"
                            ),
                        )
                    )
                    continue

                bridge = getattr(
                    self.orchestrator,
                    "jalwe_bridge",
                    None,
                )

                if bridge is None:
                    raise RuntimeError(
                        "JALWE bridge unavailable "
                        "for saved-setup wake."
                    )

                acknowledged = (
                    bridge.publish_shortlist(
                        [
                            packet
                        ]
                    )
                )

                self.store.observe(
                    self._snapshot_from_packet(
                        packet,
                        lane=(
                            "LONG_TERM_REACTIVATION"
                        ),
                    )
                )

                if symbol in set(
                    acknowledged
                    or []
                ):
                    self.store.mark_wake(
                        symbol
                    )

                    published.append(
                        symbol
                    )

            except Exception as exc:
                errors.append(
                    f"{symbol}:"
                    f"{type(exc).__name__}:{exc}"
                )

                logger.exception(
                    "APEX saved setup refresh "
                    "failed for %s",
                    symbol,
                )

            finally:
                try:
                    self.store.mark_checked(
                        symbol
                    )
                except Exception:
                    logger.warning(
                        "Unable to mark saved setup "
                        "as checked: %s",
                        symbol,
                    )

        return {
            "checked": checked,
            "near_activation": near_count,
            "published": published,
            "errors": errors,
        }

    def process_cycle(
        self,
        cycle: Any,
    ) -> dict[str, Any]:
        observed = self.observe_cycle(
            cycle
        )

        current_symbols = {
            str(
                getattr(
                    packet,
                    "symbol",
                    "",
                )
                or ""
            ).strip().upper()
            for packet in list(
                getattr(
                    cycle,
                    "packets",
                    [],
                )
                or []
            )
            if str(
                getattr(
                    packet,
                    "symbol",
                    "",
                )
                or ""
            ).strip()
        }

        refreshed = (
            self.refresh_saved_setups(
                exclude_symbols=current_symbols
            )
        )

        return {
            "observed": observed,
            "refreshed": refreshed,
            "research_only": True,
            "order_execution_enabled": False,
        }
