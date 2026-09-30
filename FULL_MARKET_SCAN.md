# APEX full-market research scanner

The standalone Railway APEX service now defaults to scanning all active,
tradable US-equity symbols returned by Alpaca, excluding known fund/ETF names
using the existing security-name guard. This name guard is a best-effort filter,
not an authoritative security classification.

Snapshot requests cover the entire eligible symbol list in batches of 150,
paced at no more than 120 requests/minute. Requests have a 15-second timeout;
the scan has a 180-second budget checked between requests. Authentication and
rate-limit failures abort immediately. Other failures abort after three
consecutive batches. Any incomplete scan publishes no new candidates and does
not silently switch to a Finviz subset.

The scanner requires an actual minute bar no older than 15 minutes, rejects
future/missing timestamps, and applies a default price range of $0.50–$100.
The newest usable trade or minute close provides the price. Ranking uses
observed activity; daily volume pace against the previous day is explicitly
labeled as a proxy, not historical average RVOL. Previous-day volume is never
passed off as today's volume or an average. Before today's daily bar exists,
only recent-minute volume is used, without a volume-pace estimate.

After complete coverage, the top 40 candidates go to PreBreakout and up to 8
to deep research. JALWE still independently checks features, freshness,
strategy, session, trigger, and risk before PAPER execution.

Configuration:

- `APEX_FULL_MARKET_SCAN=true` (default). Explicit `false` selects legacy Finviz.
- `ALPACA_DATA_FEED=iex` (default), or `sip` only when the account already has access.
- `APEX_SCAN_MIN_PRICE=0.50`, `APEX_SCAN_MAX_PRICE=100`.

Full symbol coverage does not imply consolidated exchange coverage: IEX data
reflects that exchange only. No subscription or trading account is changed.
Logs show universe, successfully scanned symbols, available snapshots, fresh
eligible candidates, selected radar size, failed batches and coverage status.

## Bounded refresh and per-symbol audit

When a Snapshot has a missing/invalid/stale minute bar but a recent, valid trade
inside the price range, APEX makes a batched `GET /v2/stocks/bars/latest` request
using the same configured feed. It replaces the bar only if the provider returns
a real, fresh bar with positive price and volume. It never builds bars from
quotes or trades, changes feeds, or extends the 15-minute freshness limit.
JALWE's independent closed-bar, strategy and risk checks still apply.

At most eight optional refresh batches run per scan. Primary snapshot and
refresh requests share the existing request pacing and 180-second deadline.
Optional transient failures preserve the original rejection; authentication,
access and rate-limit failures stop further requests and suppress incomplete
scan candidates. Final freshness is checked again after the scan. The refresh
summary's `recovered` count includes only candidates surviving that final check.
This can recover an outdated Snapshot cache, but cannot supply activity absent
from IEX or provide consolidated volume. No new data subscription is enabled.

Search Railway runtime logs for `APEX AUDIT` and a ticker. Compact JSON batches
carry a shared `scan_id` and `feed`, with individual symbol records for:

- Asset universe exclusions (not tradable, fund-name guard).
- Missing, invalid, future, stale and out-of-range market data.
- Refresh attempts, original/current bar timestamps and observed bar age.
- Every eligible symbol's rank, including candidates outside the radar limit.
- Low PreBreakout confidence and candidates outside the deep-research limit.
- Analysis errors, research scores/risks and research-verdict exclusions.
- Bridge acknowledgment per symbol, without claiming broker execution.

Audit records cover symbols returned by Alpaca's active asset listing. A symbol
absent from that listing cannot receive an individual record. Logs begin with
this deployment; they cannot reconstruct prior-day missing stage records and
are available only within Railway's log retention window. Records omit raw
provider bodies, headers, credentials and exception text. Related rows are
batched into at most 3,000-character payloads and sent through an explicit INFO
stdout logger. Large batches are paced below 200 lines/second to stay under
Railway's 500-line/second limit. The ordinary cycle summary also prints bar
refresh counts, independently of the scanner module's logger configuration.

Validation: `python -m unittest discover -s tests -v`. Tests use synthetic
market-data responses and never contact a broker or submit orders.
