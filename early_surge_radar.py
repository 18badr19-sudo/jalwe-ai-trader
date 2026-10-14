"""Bounded early-momentum research priority. No entry or order authority.

Snapshots only nominate probes. Nine consecutive completed regular-session
minute bars must confirm a three-minute breakout against six earlier minutes.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone
import math
from zoneinfo import ZoneInfo

import requests

from full_market_scan import timestamp

PROTOCOL = "early-surge-priority-v1"
NY = ZoneInfo("America/New_York")
PROBE_LIMIT = 40
RADAR_SLOTS = 8
DEEP_SLOTS = 2
MIN_RISE, MAX_RISE = 1.0, 6.0
MIN_ACCELERATION = 2.0
MIN_DOLLARS = 25000.0
MAX_AGE_SECONDS = 150


def positive(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 1e12:
        return None
    return float(value)


def regular_hours(now):
    if not isinstance(now, datetime) or now.tzinfo is None:
        return False
    local = now.astimezone(NY)
    return local.weekday() < 5 and 570 <= local.hour * 60 + local.minute < 960


def inspect_bars(symbol, bars, *, price, trade_at, feed, now, window_end=None):
    """Return an evidence record and a reason; no inference across missing minutes."""
    if feed not in {"iex", "sip"} or not regular_hours(now):
        return None, "OUTSIDE_SUPPORTED_SESSION_OR_FEED"
    price, traded = positive(price), timestamp(trade_at)
    if price is None or traded is None or not 0 <= (now-traded).total_seconds() <= MAX_AGE_SECONDS:
        return None, "STALE_OR_INVALID_TRADE"
    if not isinstance(bars, list):
        return None, "INVALID_BAR_SCHEMA"
    current_boundary = now.astimezone(timezone.utc).replace(second=0, microsecond=0)
    boundary = timestamp(window_end) if window_end is not None else current_boundary
    if (boundary is None or boundary != boundary.replace(second=0,microsecond=0)
            or boundary > current_boundary or not 0 <= (now-boundary).total_seconds() <= MAX_AGE_SECONDS):
        return None, "STALE_OR_INVALID_WINDOW"
    opening = now.astimezone(NY).replace(hour=9, minute=30, second=0, microsecond=0).astimezone(timezone.utc)
    rows = {}
    # Every minute of this fixed recent window is required. Earlier provider
    # rows and the inclusive end/current-minute row cannot change the result.
    expected = [boundary-timedelta(minutes=i) for i in range(9, 0, -1)]
    if expected[0] < opening:
        return None, "WAITING_NINE_REGULAR_MINUTES"
    expected_set = set(expected)
    for raw in bars:
        if not isinstance(raw, dict):
            return None, "INVALID_BAR_SCHEMA"
        at = timestamp(raw.get("t"))
        if at not in expected_set:
            continue
        if at in rows:
            return None, "DUPLICATE_MINUTE"
        values = {key:positive(raw.get(key)) for key in ("o", "h", "l", "c", "v")}
        if any(v is None for v in values.values()):
            return None, "INVALID_OHLCV"
        if values["h"] < max(values["o"], values["l"], values["c"]) or values["l"] > min(values["o"], values["c"]):
            return None, "INVALID_OHLCV"
        rows[at] = {"t":at.isoformat(), **values}
    if set(rows) != expected_set:
        return None, "MISSING_COMPLETED_MINUTES"
    ordered = [rows[t] for t in expected]
    baseline, recent = ordered[:6], ordered[6:]
    rise = 100 * (recent[-1]["c"] / recent[0]["o"] - 1)
    acceleration = (sum(r["v"] for r in recent)/3) / (sum(r["v"] for r in baseline)/6)
    dollars = sum(r["c"] * r["v"] for r in recent)
    trigger = max(r["h"] for r in baseline)
    peak = max(r["h"] for r in recent)
    if not MIN_RISE <= rise <= MAX_RISE:
        return None, "RISE_OUTSIDE_EARLY_WINDOW"
    if acceleration < MIN_ACCELERATION or dollars < MIN_DOLLARS:
        return None, "INSUFFICIENT_VOLUME_ACTIVITY"
    if recent[-1]["c"] <= trigger or recent[-1]["c"] < peak*.98:
        return None, "BREAKOUT_NOT_HELD"
    if not trigger < price <= recent[-1]["c"]*1.02 or price < recent[-1]["c"]*.99:
        return None, "TRADE_REVERSED_OR_EXTENDED"
    return dict(protocol=PROTOCOL, state="CONFIRMED_MINUTE_SURGE", symbol=symbol,
        source_feed=feed, volume_scope="SOURCE_FEED_ONLY_NOT_ALL_MARKET",
        confirmed_at=now.isoformat(), window_end=boundary.isoformat(),
        last_bar_at=ordered[-1]["t"], trade_at=traded.isoformat(),
        rise_3m_pct=rise, volume_acceleration=acceleration, dollar_volume_3m=dollars,
        range_high=trigger, latest_close=recent[-1]["c"], bars=ordered,
        execution_authority=False, scope="RESEARCH_PRIORITY_NOT_BUY_SIGNAL"), "CONFIRMED"


def probe_candidates(candidates, now):
    nominees = []
    for candidate in candidates:
        if candidate.get("tradable") is not True:
            continue
        raw = candidate.get("raw") or {}
        bar = raw.get("minute_bar") or {}
        opened, volume, price = positive(bar.get("o")), positive(bar.get("v")), positive(candidate.get("price"))
        traded = timestamp(raw.get("latest_trade_at"))
        if not opened or not volume or not price or traded is None or not 0 <= (now-traded).total_seconds() <= MAX_AGE_SECONDS:
            continue
        rise = 100*(price/opened-1)
        # A snapshot may describe an unfinished minute. It only decides which
        # symbols deserve a bar request and can never confer priority itself.
        if .5 <= rise <= 8 and price*volume >= 5000:
            nominees.append((rise, price*volume, candidate["symbol"]))
    return [s for _,_,s in sorted(nominees,key=lambda x:(-x[0],-x[1],x[2]))[:PROBE_LIMIT]]


def enrich(candidates, *, enabled, paper, feed, api_key, api_secret, session=None, now=None):
    candidates = list(candidates)
    now = now or (lambda:datetime.now(timezone.utc))
    checked = now()
    audit = dict(protocol=PROTOCOL, state="DISABLED", probe_count=0, confirmed=0,
                 reasons={}, execution_authority=False)
    if not enabled or not paper:
        audit["state"] = "DISABLED" if not enabled else "BLOCKED_NON_PAPER"
        return candidates, audit
    if feed not in {"iex", "sip"} or not regular_hours(checked):
        audit["state"] = "OUTSIDE_SUPPORTED_SESSION_OR_FEED"
        return candidates, audit
    if not api_key or not api_secret:
        audit["state"] = "WAITING_CREDENTIALS"
        return candidates, audit
    nominees = probe_candidates(candidates, checked)
    audit.update(state="NO_PROBES", probe_count=len(nominees))
    if not nominees:
        return candidates, audit
    boundary = checked.astimezone(timezone.utc).replace(second=0, microsecond=0)
    opening = checked.astimezone(NY).replace(hour=9,minute=30,second=0,microsecond=0).astimezone(timezone.utc)
    if boundary-opening < timedelta(minutes=9):
        audit["state"] = "WAITING_NINE_REGULAR_MINUTES"
        return candidates, audit
    client = session or requests.Session()
    status = None
    try:
        # One bounded read per complete full-market scan. No retries or feed
        # fallback. 40 symbols * 20 minutes fits within the 10,000-row page.
        response = client.get("https://data.alpaca.markets/v2/stocks/bars",
            params=dict(symbols=",".join(nominees), timeframe="1Min", feed=feed,
                start=max(opening,boundary-timedelta(minutes=20)).isoformat(),
                end=boundary.isoformat(), adjustment="split", sort="asc", limit=10000),
            headers={"APCA-API-KEY-ID":api_key,"APCA-API-SECRET-KEY":api_secret}, timeout=8)
        status = response.status_code
        response.raise_for_status()
        payload = response.json()
        mapping = payload.get("bars") if isinstance(payload, dict) else None
        if (not isinstance(mapping,dict) or payload.get("next_page_token")
                or any(s not in nominees or not isinstance(v,list) for s,v in mapping.items())
                or sum(len(v) for v in mapping.values()) > 1000):
            raise ValueError("INCOMPLETE_OR_INVALID_BAR_RESPONSE")
        checked = now()
        reasons = Counter()
        output = []
        for candidate in candidates:
            if candidate["symbol"] not in nominees:
                output.append(candidate)
                continue
            raw = candidate.get("raw") or {}
            proof, reason = inspect_bars(candidate["symbol"],mapping.get(candidate["symbol"],[]),
                price=candidate.get("price"),trade_at=raw.get("latest_trade_at"),feed=feed,now=checked,
                window_end=boundary.isoformat())
            reasons[reason] += 1
            output.append({**candidate,"raw":{**raw,"early_surge":proof}})
        audit.update(state="OBSERVED",confirmed=reasons["CONFIRMED"],reasons=dict(reasons))
        return output, audit
    except Exception as exc:
        # Do not log URLs, credentials, exception messages or provider bodies.
        audit.update(state="READ_UNAVAILABLE", error_type=type(exc).__name__)
        if type(status) is int and 100 <= status <= 599:
            audit["http_status"] = status
        return candidates, audit
    finally:
        if session is None:
            client.close()


def checked_proof(candidate, now):
    raw = candidate.get("raw") or {}
    proof = raw.get("early_surge")
    if (candidate.get("tradable") is not True or not isinstance(proof,dict)
            or proof.get("protocol")!=PROTOCOL or proof.get("symbol")!=candidate.get("symbol")
            or proof.get("state")!="CONFIRMED_MINUTE_SURGE"
            or proof.get("scope")!="RESEARCH_PRIORITY_NOT_BUY_SIGNAL" or not proof.get("window_end")
            or proof.get("execution_authority") is not False
            or proof.get("source_feed")!=raw.get("feed")):
        return None
    fresh, _ = inspect_bars(candidate["symbol"],proof.get("bars"),price=candidate.get("price"),
        trade_at=raw.get("latest_trade_at"),feed=proof.get("source_feed"),now=now,
        window_end=proof.get("window_end"))
    # Recompute from the saved bars. A stale flag or a fabricated score alone
    # cannot confer priority at the later deep-research boundary.
    return fresh


def proof_valid(candidate, now):
    return checked_proof(candidate,now) is not None


def reserve(items, *, limit, slot_cap, enabled, paper, now, candidate_of=lambda x:x):
    """Bounded replacement/order only; no scores or eligibility flags change."""
    items = list(items)
    limit = max(1,int(limit))
    base = items[:limit]
    if not enabled or not paper or not regular_hours(now):
        return base, []
    slots = min(max(0,int(slot_cap)),limit//4)
    if not slots:
        return base, []
    priority = []
    for item in items:
        c = candidate_of(item)
        proof = checked_proof(c,now)
        if proof is not None:
            priority.append((proof["volume_acceleration"],proof["rise_3m_pct"],c["symbol"],item))
    selected = [x[3] for x in sorted(priority,key=lambda x:(-x[0],-x[1],x[2]))[:slots]]
    symbols = {candidate_of(x)["symbol"] for x in selected}
    rest = [x for x in items if candidate_of(x)["symbol"] not in symbols]
    return (selected+rest)[:limit], [candidate_of(x)["symbol"] for x in selected]
