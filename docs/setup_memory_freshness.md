# Saved setup reactivation freshness

Long-term setup memory now requires the current five-minute analysis to expose an
aware source bar timestamp, explicit source feed, and the matching analysis price.
A source bar must be complete, aligned to a five-minute boundary and no more than
15 minutes old measured from its start, matching the JALWE age policy. Daily or
longer-frame price fallback cannot wake a saved setup. Confidence from historical
bar counts alone is not freshness evidence.

Check before updating technical levels or performing deeper research, then check
again immediately before publication. Rejected observations only advance the
rotation check timestamp; the historical setup, levels and wake cooldown remain
intact. Logged SETUP_MEMORY_FRESHNESS records disclose the source timestamp and
reason; published setup metadata retains the final freshness proof.

Historical pre-breakout requests explicitly fetch newest bars first with the
same IEX feed. Five-minute analysis excludes unfinished bars. Unsupported clients
fail rather than retrying with an implicit feed. Research ranking remains
advisory; no broker execution authority or trading gate relaxation is introduced.
