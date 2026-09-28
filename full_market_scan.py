"""Batched, read-only Alpaca universe scan. Never submits broker orders.

Coverage of symbols is distinct from coverage of exchanges (IEX vs SIP).
Volume pace against the previous day is a ranking proxy, not historical RVOL.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable
from zoneinfo import ZoneInfo

import requests
from dateutil.parser import isoparse

NY = ZoneInfo("America/New_York")


def number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) and value >= 0 else None
    except (TypeError, ValueError):
        return None


def timestamp(value):
    try:
        # Alpaca timestamps can have nanoseconds. Python 3.10's fromisoformat
        # accepts only 3 or 6 fractional digits; do not mark valid data stale.
        parsed = isoparse(str(value))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (TypeError, ValueError):
        return None


def fresh(section, now):
    stamp = timestamp(section.get("t")) if isinstance(section, dict) else None
    return stamp is not None and 0 <= (now - stamp).total_seconds() <= 900


def snapshot_candidate(symbol, snapshot, now, min_price, max_price, ranker, rejections=None):
    def reject(reason):
        if rejections is not None:
            rejections[reason] = rejections.get(reason, 0) + 1
        return None

    if not isinstance(snapshot, dict):
        return reject("INVALID_SNAPSHOT")
    minute = snapshot.get("minuteBar") or {}
    if not isinstance(minute, dict) or not minute:
        return reject("MISSING_MINUTE_BAR")
    bar_time = timestamp(minute.get("t"))
    if bar_time is None:
        return reject("INVALID_BAR_TIMESTAMP")
    age = (now - bar_time).total_seconds()
    if age < 0:
        return reject("FUTURE_MINUTE_BAR")
    if age > 900:
        return reject("STALE_MINUTE_BAR")
    trade = snapshot.get("latestTrade") or {}
    price = number(trade.get("p")) if fresh(trade, now) else None
    price = price or number(minute.get("c"))
    if price is None or price <= 0:
        return reject("INVALID_PRICE")
    if not min_price <= price <= max_price:
        return reject("PRICE_OUT_OF_RANGE")
    day = snapshot.get("dailyBar") or {}
    previous = snapshot.get("prevDailyBar") or {}
    day = day if isinstance(day, dict) else {}
    previous = previous if isinstance(previous, dict) else {}
    day_time = timestamp(day.get("t"))
    previous_time = timestamp(previous.get("t"))
    local = now.astimezone(NY)
    current_day = day_time is not None and day_time.astimezone(NY).date() == local.date()
    # Before today's daily bar exists, use only actual recent-minute activity.
    volume = number(day.get("v")) if current_day else number(minute.get("v"))
    if volume is None or volume <= 0:
        return reject("INVALID_OR_ZERO_VOLUME")
    previous_volume = number(previous.get("v"))
    previous_close = number(previous.get("c"))
    previous_is_past = previous_time is not None and previous_time.astimezone(NY).date() < local.date()
    fraction = max(0.1, min(1.0, (local.hour * 60 + local.minute - 570) / 390))
    pace = None
    if current_day and previous_is_past and previous_volume and local.hour * 60 + local.minute >= 570:
        pace = volume / (previous_volume * fraction)
    change = (price / previous_close - 1) * 100 if previous_is_past and previous_close else None
    pace = pace if pace is not None and math.isfinite(pace) else None
    change = change if change is not None and math.isfinite(change) else None
    if not math.isfinite(price * volume):
        return reject("INVALID_DOLLAR_VOLUME")
    score, reasons, warnings = ranker(relative_volume=pace, volume=volume,
        average_volume=None, price=price, change_pct=change, float_shares=None)
    return dict(symbol=symbol, rank_score=score, relative_volume=pace,
        volume=volume, average_volume=None, price=price, change_pct=change,
        float_shares=None, dollar_volume=price * volume, tradable=True,
        reasons=reasons, warnings=warnings + ["VOLUME_PACE_PROXY_NOT_HISTORICAL_RVOL"],
        raw={"source": "ALPACA_SNAPSHOT", "latest_bar_at": minute["t"],
             "volume_basis": "current_daily_bar" if current_day else "latest_minute_bar",
             "previous_day_volume": previous_volume, "session_fraction": fraction})


@dataclass
class ScanResult:
    candidates: list[dict] = field(default_factory=list)
    universe_count: int = 0
    scanned_count: int = 0
    snapshot_count: int = 0
    failed_batches: int = 0
    rejection_counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    complete: bool = False


def scan_market(symbols, *, api_key, api_secret, feed, min_price, max_price,
                ranker: Callable, batch_size=150, timeout=15, deadline_seconds=180,
                request_interval=0.5, session=None, clock=time.monotonic,
                sleep=time.sleep, now=lambda: datetime.now(timezone.utc)):
    """Visit every symbol before ranking; do not stop when top_n is filled.

    A failed or timed-out batch makes the entire scan incomplete. Its candidates
    are never published, avoiding silent alphabet-biased partial coverage.
    """
    symbols = sorted(set(symbols))
    result = ScanResult(universe_count=len(symbols))
    if not symbols:
        result.warnings.append("ALPACA_ASSET_UNIVERSE_EMPTY")
        return result
    if feed not in {"iex", "sip"}:
        result.warnings.append("UNSUPPORTED_ALPACA_DATA_FEED")
        return result
    batch_size = max(25, min(150, int(batch_size)))
    client = session or requests.Session()
    started = clock()
    next_request = started
    consecutive_failures = 0
    try:
        for offset in range(0, len(symbols), batch_size):
            delay = max(0, next_request - clock())
            if delay:
                sleep(delay)
            remaining = deadline_seconds - (clock() - started)
            if remaining <= 0:
                result.warnings.append("SNAPSHOT_SCAN_TIME_BUDGET_EXCEEDED")
                break
            batch = symbols[offset:offset + batch_size]
            next_request = clock() + request_interval
            status = None
            try:
                response = client.get("https://data.alpaca.markets/v2/stocks/snapshots",
                    params={"symbols": ",".join(batch), "feed": feed},
                    headers={"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": api_secret},
                    timeout=min(timeout, remaining))
                status = response.status_code
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("invalid snapshot response")
                snapshots = payload.get("snapshots", payload)
                if not isinstance(snapshots, dict):
                    raise ValueError("invalid snapshot map")
            except (requests.RequestException, ValueError):
                result.failed_batches += 1
                consecutive_failures += 1
                # Do not echo headers, credentials, provider payloads or URLs.
                result.warnings.append(f"SNAPSHOT_BATCH_FAILED:{status or 'NETWORK_OR_DATA'}")
                if status in {401, 403, 429} or consecutive_failures >= 3:
                    break
                continue
            consecutive_failures = 0
            result.scanned_count += len(batch)
            for symbol in batch:
                snapshot = snapshots.get(symbol)
                if not isinstance(snapshot, dict) or not snapshot:
                    result.rejection_counts["MISSING_SNAPSHOT"] = result.rejection_counts.get("MISSING_SNAPSHOT", 0) + 1
                    continue
                result.snapshot_count += 1
                candidate = snapshot_candidate(symbol, snapshot, now(), min_price, max_price, ranker, result.rejection_counts)
                if candidate:
                    candidate["raw"]["feed"] = feed
                    result.candidates.append(candidate)
    finally:
        if session is None:
            client.close()
    result.complete = result.scanned_count == len(symbols) and not result.failed_batches
    if not result.complete:
        result.candidates.clear()
    else:
        finished = now()
        previous_count = len(result.candidates)
        result.candidates = [c for c in result.candidates
            if fresh({"t": c["raw"]["latest_bar_at"]}, finished)]
        expired = previous_count - len(result.candidates)
        if expired:
            result.rejection_counts["EXPIRED_DURING_SCAN"] = expired
        result.candidates.sort(key=lambda c: (c["rank_score"], c["relative_volume"] or 0,
                                             c["dollar_volume"], c["symbol"]), reverse=True)
    result.warnings = list(dict.fromkeys(result.warnings))
    return result
