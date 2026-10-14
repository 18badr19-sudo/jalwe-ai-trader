# Pre-breakout bar integrity

Intraday 5-minute, 30-minute and 1-hour analyses now exclude unfinished source
bars before retaining the newest requested history. The timestamp must be aware
and undisputed. Daily analysis retains its existing behavior.

OHLCV evidence must be finite, positive and geometrically consistent. Boolean
values and duplicate timestamps fail the timeframe rather than being used or
silently dropped from its history. The analysis reports unavailable evidence;
confidence cannot be based on a repaired or disputed row sequence. Validation
applies to the completed analysis window; excluded unfinished or unrelated older
rows do not veto it. A disputed timestamp at the trim boundary remains rejected.

Session VWAP resets at the latest New York trading date, even when that date has
only one bar. Previously that first bar inherited volume weighting from previous
sessions. A one-bar session cannot claim an intraday VWAP reclaim. Displaying the
same timestamp index in another timezone does not change the result.

These are research evidence corrections. Trading entry thresholds, stops, risk
limits, broker authority and the saved-setup 15-minute age policy are unchanged.
