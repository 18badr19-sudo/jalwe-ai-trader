# Early surge research priority

`early_surge_radar.py` adds `early-surge-priority-v1` to the full-market APEX
research pipeline. It never places orders or overrides research verdicts,
confidence, risk, JALWE entry/exit gates or broker tradability. It is explicitly
opt-in with `APEX_EARLY_SURGE_ENABLED=true` and the exact PAPER broker URL.

After a complete all-universe snapshot scan, current tradable candidates whose
snapshot hints at a 0.5–8% minute move with at least $5,000 of observed minute
activity nominate at most forty probes. A snapshot can contain an unfinished
minute; nomination alone confers no priority. One extra batched GET retrieves
up to twenty minutes of 1Min bars from the same entitled `iex` or `sip` feed.
There are no HTTP retries, paid-feed substitutions or pagination assumptions:
a next-page token makes the probe read unavailable rather than publishing a
partial symbol-biased batch. The added request times out after eight seconds.

Confirmation requires exactly nine consecutive, unique, valid completed minute
bars in the current regular session. Six baseline minutes precede three surge
minutes. The three-minute close/open rise must be 1–6%, average volume at least
twice the six-minute baseline, and close-times-volume activity at least $25,000.
The last completed close must exceed the baseline highs and remain within 2%
of the recent highs. A fresh observed trade must still be above the range and
within -1%/+2% of the latest completed close. These are fixed research sampling
rules, not validated profitable parameters, market-wide volume, or buy signals.
The first nine regular minutes must finish before confirmation is possible.

The query boundary is frozen before the request. Inclusive end/current-minute
rows, future rows and earlier rows cannot enter that window even if the request
crosses a minute boundary. Gaps, duplicate minutes, malformed OHLCV, nonfinite
values, stale/future trades, extended moves and failed breakouts remain
unconfirmed. Rechecking the saved bars and current time at each selection
boundary prevents a fabricated score or expired proof from conferring priority.
The fixed window and trade must be no older than 150 seconds. The regular-hours
filter is a wall-clock research guard; native exchange-calendar/session gates
remain responsible for trading eligibility, holidays and early closes.

Up to eight seats, and no more than a quarter of configured radar capacity,
are reserved for confirmed probes. At most two seats, also no more than a
quarter of configured deep-research capacity, are reserved **after** the existing
pre-analysis confidence gate. Remaining seats preserve the ordinary ranking.
Native scores and final research verdicts are unchanged. News/AI critical-risk
rejections still prevent publication to JALWE. Published packets retain the
bounded minute evidence under `metadata.early_surge` for later outcome study;
it is historical evidence by receipt time, not fresh authority to buy.

`APEX_EARLY_SURGE_RADAR` logs configuration/read state, probe count, reasons and
selected priority symbols. APEX RADAR/DEEP audits mark actual selected symbols
and `early_surge_priority`; rank still means original rank. Missing credentials,
unsupported/delayed feeds, non-PAPER mode, closed sessions, incomplete scans or
optional adapter failures preserve ordinary research. Keys, URLs, exception
messages and provider bodies are not logged.

This module does not create a faster scan loop or guarantee discovery of every
surge. It samples a bounded set on the existing full-market cadence; a sparse
IEX feed may not return the necessary minute coverage. It does not claim a
historical hindsight winner was discoverable or tradable live, and does not
learn from future winners to alter these rules automatically. Live-market
coverage and out-of-sample PAPER outcomes must be measured before claiming an
improvement. Existing JALWE T1/T2 stop management remains its authority.

Provider reference: https://docs.alpaca.markets/us/reference/stockbars
