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

Validation: `python -m unittest discover -s tests -v`. Tests use synthetic
market-data responses and never contact a broker or submit orders.
