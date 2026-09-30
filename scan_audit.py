"""Compact, searchable stage records. Never logs credentials or provider bodies."""
from __future__ import annotations

import json
import math


def _safe(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    return value


def emit_audit(logger, scan_id, feed, rows, max_chars=12000):
    """Batch rows instead of emitting thousands of individual log lines."""
    prefix = {"scan_id": scan_id, "feed": feed}
    chunk = []
    size = len(json.dumps(prefix)) + 30
    for row in rows:
        row = _safe(row)
        row_size = len(json.dumps(row, separators=(",", ":"))) + 1
        if chunk and size + row_size > max_chars:
            logger.info("APEX AUDIT %s", json.dumps({**prefix, "rows": chunk}, separators=(",", ":")))
            chunk = []
            size = len(json.dumps(prefix)) + 30
        chunk.append(row)
        size += row_size
    if chunk:
        logger.info("APEX AUDIT %s", json.dumps({**prefix, "rows": chunk}, separators=(",", ":")))
