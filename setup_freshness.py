"""Saved-setup alerts require source-dated, completed five-minute evidence."""
import math
from datetime import datetime, timezone

from full_market_scan import timestamp

MAX_AGE_MINUTES = 15.


def inspect_setup(pre, now=None):
    now = now or datetime.now(timezone.utc)
    frame = getattr(pre,'timeframe_5m',None)
    feed = getattr(frame,'source_feed',None)
    at = timestamp(getattr(frame,'last_bar_at',None))
    proof = dict(state='MISSING_5M_EVIDENCE',source_feed=feed,
                 bar_at=at.isoformat() if at else None,max_age_minutes=MAX_AGE_MINUTES)
    if (frame is None or getattr(frame,'available',False) is not True
            or feed not in {'iex','sip'} or at is None):
        return proof
    age = (now-at).total_seconds()/60
    proof['age_minutes'] = age
    if at.second or at.microsecond or at.minute%5 or age < 5:
        proof['state']='INCOMPLETE_OR_INVALID_5M_BAR'
    elif age > MAX_AGE_MINUTES:
        proof['state']='STALE_5M_BAR'
    else:
        price, bar_price = getattr(pre,'current_price',None),getattr(frame,'current_price',None)
        if (type(price) not in (int,float) or type(bar_price) not in (int,float)
                or not math.isfinite(price) or not math.isfinite(bar_price) or min(price,bar_price)<=0
                or not math.isclose(price,bar_price,rel_tol=1e-9)):
            proof['state']='PRICE_SOURCE_MISMATCH'
        else:
            proof['state']='FRESH_COMPLETED_5M'
    return proof
