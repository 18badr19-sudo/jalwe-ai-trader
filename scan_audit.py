"""Compact, searchable stage records. Never logs credentials or provider bodies."""
from __future__ import annotations

import json
import logging
import math
import sys
import time


audit_logger = logging.getLogger("apex.audit")
if not audit_logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    audit_logger.addHandler(handler)
audit_logger.setLevel(logging.INFO)
audit_logger.propagate = False


def _safe(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    return value


def emit_audit(scan_id, feed, rows, *, logger=None, max_chars=3000, sleep=time.sleep):
    """Use an explicit stdout handler, bounded lines and at most 200 lines/sec."""
    logger = logger if logger is not None else audit_logger
    prefix = {"scan_id": scan_id, "feed": feed}
    chunk = []
    size = len(json.dumps(prefix)) + 30
    emitted = False

    def write_chunk(items):
        nonlocal emitted
        if emitted:
            sleep(0.005)
        logger.info("APEX AUDIT %s", json.dumps({**prefix, "rows": items}, separators=(",", ":")))
        emitted = True

    for row in rows:
        row = _safe(row)
        row_size = len(json.dumps(row, separators=(",", ":"))) + 1
        if chunk and size + row_size > max_chars:
            write_chunk(chunk)
            chunk = []
            size = len(json.dumps(prefix)) + 30
        chunk.append(row)
        size += row_size
    if chunk:
        write_chunk(chunk)
