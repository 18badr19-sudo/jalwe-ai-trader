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
from uuid import uuid4
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


def audit_row(symbol, snapshot, now, reason):
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    minute = snapshot.get("minuteBar")
    minute = minute if isinstance(minute, dict) else {}
    trade = snapshot.get("latestTrade")
    trade = trade if isinstance(trade, dict) else {}
    stamp = timestamp(minute.get("t"))
    trade_stamp = timestamp(trade.get("t"))
    return {"symbol": symbol, "stage": "DATA", "reason": reason,
            "observed_price": number(trade.get("p")) if fresh(trade, now) else number(minute.get("c")),
            "bar_at": stamp.isoformat() if stamp else None,
            "bar_age_s": round((now - stamp).total_seconds(), 2) if stamp else None,
            "trade_at": trade_stamp.isoformat() if trade_stamp else None}


def snapshot_candidate(symbol, snapshot, now, min_price, max_price, ranker, rejections=None, audit=None):
    def reject(reason):
        if rejections is not None:
            rejections[reason] = rejections.get(reason, 0) + 1
        if audit is not None:
            audit[symbol] = audit_row(symbol, snapshot, now, reason)
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
    trade = trade if isinstance(trade, dict) else {}
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
    if audit is not None:
        audit[symbol] = {**audit_row(symbol, snapshot, now, "FRESH_ELIGIBLE"),
                         "rank_score": score, "volume_basis": "current_daily_bar" if current_day else "latest_minute_bar"}
    return dict(symbol=symbol, rank_score=score, relative_volume=pace,
        volume=volume, average_volume=None, price=price, change_pct=change,
        float_shares=None, dollar_volume=price * volume, tradable=True,
        reasons=reasons, warnings=warnings + ["VOLUME_PACE_PROXY_NOT_HISTORICAL_RVOL"],
        raw={"source": "ALPACA_SNAPSHOT", "latest_bar_at": minute["t"],
             "volume_basis": "current_daily_bar" if current_day else "latest_minute_bar",
             "previous_day_volume": previous_volume, "session_fraction": fraction})


@dataclass
class ScanResult:
    scan_id: str = field(default_factory=lambda: uuid4().hex)
    candidates: list[dict] = field(default_factory=list)
    universe_count: int = 0
    scanned_count: int = 0
    snapshot_count: int = 0
    failed_batches: int = 0
    rejection_counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    complete: bool = False
    audit: dict[str, dict] = field(default_factory=dict)
    refresh_requested: int = 0
    refresh_recovered: int = 0
    refresh_failed_batches: int = 0


def scan_market(symbols, *, api_key, api_secret, feed, min_price, max_price,
                ranker: Callable, batch_size=150, timeout=15, deadline_seconds=180,
                request_interval=0.5, session=None, clock=time.monotonic,
                sleep=time.sleep, now=lambda: datetime.now(timezone.utc), refresh_max_batches=8):
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
    refresh_batches = 0
    stop_after_batch = False

    def request_budget():
        nonlocal next_request
        delay = max(0, next_request - clock())
        if delay:
            sleep(delay)
        remaining = deadline_seconds - (clock() - started)
        if remaining > 0:
            next_request = clock() + request_interval
        return remaining

    headers = {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": api_secret}
    try:
        for offset in range(0, len(symbols), batch_size):
            remaining = request_budget()
            if remaining <= 0:
                result.warnings.append("SNAPSHOT_SCAN_TIME_BUDGET_EXCEEDED")
                break
            batch = symbols[offset:offset + batch_size]
            status = None
            try:
                response = client.get("https://data.alpaca.markets/v2/stocks/snapshots",
                    params={"symbols": ",".join(batch), "feed": feed},
                    headers=headers,
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
                for symbol in batch:
                    result.audit[symbol] = {"symbol": symbol, "stage": "DATA", "reason": "SNAPSHOT_BATCH_FAILED",
                                             "http_status": status}
                if status in {401, 403, 429} or consecutive_failures >= 3:
                    break
                continue
            consecutive_failures = 0
            result.scanned_count += len(batch)
            checked_at = now()
            # A recent real trade can coexist with a stale Snapshot minute bar.
            # Confirm activity using real minute bars from the SAME entitled feed.
            refresh_symbols = []
            refresh_details = {}
            for symbol in batch:
                item = snapshots.get(symbol)
                if not isinstance(item, dict) or not item:
                    continue
                trade = item.get("latestTrade")
                if not isinstance(trade, dict):
                    continue
                price = number(trade.get("p"))
                if not fresh(item.get("minuteBar"), checked_at) and fresh(trade, checked_at) and price and min_price <= price <= max_price:
                    refresh_symbols.append(symbol)
                    refresh_details[symbol] = {"snapshot_bar_at": audit_row(symbol, item, checked_at, "")["bar_at"],
                                                "bar_refresh": "LIMIT_REACHED"}
            if refresh_symbols and refresh_batches < max(0, int(refresh_max_batches)):
                remaining = request_budget()
                if remaining <= 0:
                    for symbol in refresh_symbols:
                        refresh_details[symbol]["bar_refresh"] = "TIME_BUDGET_EXCEEDED"
                else:
                    refresh_batches += 1
                    result.refresh_requested += len(refresh_symbols)
                    refresh_status = None
                    try:
                        response = client.get("https://data.alpaca.markets/v2/stocks/bars/latest",
                            params={"symbols": ",".join(refresh_symbols), "feed": feed},
                            headers=headers, timeout=min(timeout, remaining))
                        refresh_status = response.status_code
                        response.raise_for_status()
                        payload = response.json()
                        bars = payload.get("bars") if isinstance(payload, dict) else None
                        if not isinstance(bars, dict):
                            raise ValueError("invalid latest bar map")
                        checked_at = now()
                        for symbol in refresh_symbols:
                            bar = bars.get(symbol)
                            valid_bar = (fresh(bar, checked_at) and number(bar.get("c")) and number(bar.get("v")))
                            refresh_details[symbol]["bar_refresh"] = "REAL_BAR_UPDATED" if valid_bar else "NO_FRESH_VALID_BAR"
                            if valid_bar:
                                snapshots[symbol] = {**snapshots[symbol], "minuteBar": bar}
                    except (requests.RequestException, ValueError):
                        result.refresh_failed_batches += 1
                        result.warnings.append(f"LATEST_BAR_REFRESH_FAILED:{refresh_status or 'NETWORK_OR_DATA'}")
                        for symbol in refresh_symbols:
                            refresh_details[symbol]["bar_refresh"] = "REQUEST_FAILED"
                        # Stop all new requests on auth/rate-limit failures.
                        if refresh_status in {401, 403, 429}:
                            result.failed_batches += 1
                            stop_after_batch = True
            for symbol in batch:
                snapshot = snapshots.get(symbol)
                if not isinstance(snapshot, dict) or not snapshot:
                    result.rejection_counts["MISSING_SNAPSHOT"] = result.rejection_counts.get("MISSING_SNAPSHOT", 0) + 1
                    result.audit[symbol] = audit_row(symbol, snapshot, checked_at, "MISSING_SNAPSHOT")
                    continue
                result.snapshot_count += 1
                candidate = snapshot_candidate(symbol, snapshot, checked_at, min_price, max_price, ranker, result.rejection_counts, result.audit)
                if symbol in refresh_details:
                    result.audit[symbol].update(refresh_details[symbol])
                if candidate:
                    candidate["raw"]["feed"] = feed
                    candidate["raw"]["latest_bar_source"] = "ALPACA_LATEST_BARS" if refresh_details.get(symbol, {}).get("bar_refresh") == "REAL_BAR_UPDATED" else "ALPACA_SNAPSHOT"
                    result.candidates.append(candidate)
            if stop_after_batch:
                break
    finally:
        if session is None:
            client.close()
    result.complete = result.scanned_count == len(symbols) and not result.failed_batches
    for symbol in symbols:
        result.audit.setdefault(symbol, {"symbol": symbol, "stage": "DATA", "reason": "UNSCANNED_SCAN_ABORTED"})
    if not result.complete:
        for candidate in result.candidates:
            result.audit[candidate["symbol"]].update(reason="SUPPRESSED_INCOMPLETE_SCAN")
        result.candidates.clear()
    else:
        finished = now()
        previous_count = len(result.candidates)
        for candidate in result.candidates:
            row = result.audit[candidate["symbol"]]
            row["bar_age_s"] = round((finished - timestamp(candidate["raw"]["latest_bar_at"])).total_seconds(), 2)
            if not fresh({"t": candidate["raw"]["latest_bar_at"]}, finished):
                row["reason"] = "EXPIRED_DURING_SCAN"
        result.candidates = [c for c in result.candidates if fresh({"t": c["raw"]["latest_bar_at"]}, finished)]
        expired = previous_count - len(result.candidates)
        if expired:
            result.rejection_counts["EXPIRED_DURING_SCAN"] = expired
        result.candidates.sort(key=lambda c: (c["rank_score"], c["relative_volume"] or 0,
                                             c["dollar_volume"], c["symbol"]), reverse=True)
    result.refresh_recovered = sum(c["raw"]["latest_bar_source"] == "ALPACA_LATEST_BARS" for c in result.candidates)
    result.warnings = list(dict.fromkeys(result.warnings))
    return result
