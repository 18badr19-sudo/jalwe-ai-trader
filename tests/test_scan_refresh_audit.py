import copy
import json
import logging
import unittest
from datetime import timedelta
from unittest.mock import Mock, patch

import requests

from full_market_scan import scan_market
from scan_audit import emit_audit
import test_full_market_scan as fixtures
from test_full_market_scan import NOW, ranker, snapshot


class RefreshSession:
    def __init__(self, items, bars, refresh_status=200):
        self.items = items
        self.bars = bars
        self.refresh_status = refresh_status
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        symbols = kwargs["params"]["symbols"].split(",")
        refresh = url.endswith("/bars/latest")
        status = self.refresh_status if refresh else 200
        response = Mock(status_code=status)
        if status != 200:
            response.raise_for_status.side_effect = requests.HTTPError("test failure")
        data = {s: copy.deepcopy((self.bars if refresh else self.items).get(s)) for s in symbols}
        response.json.return_value = {"bars": data} if refresh else data
        return response


def stale_snapshot():
    item = snapshot()
    item["minuteBar"]["t"] = (NOW - timedelta(minutes=16)).isoformat()
    return item


def fresh_bar():
    return {"t": (NOW - timedelta(minutes=1)).isoformat(), "c": 10, "v": 250}


class ScanRefreshTests(unittest.TestCase):
    def scan(self, session, **kwargs):
        return scan_market(list(session.items), api_key="SECRET_KEY_TEST", api_secret="SECRET_VALUE_TEST",
            feed="iex", min_price=0.5, max_price=100, ranker=ranker, session=session,
            request_interval=kwargs.pop("request_interval", 0), now=kwargs.pop("now", lambda: NOW), **kwargs)

    def test_stale_snapshot_recovered_only_from_real_bar_same_feed(self):
        item = stale_snapshot()
        session = RefreshSession({"YMT": item}, {"YMT": fresh_bar()})
        result = self.scan(session)
        self.assertTrue(result.complete)
        self.assertEqual(result.refresh_requested, 1)
        self.assertEqual(result.refresh_recovered, 1)
        self.assertEqual(result.rejection_counts, {})
        self.assertEqual(result.candidates[0]["raw"]["latest_bar_source"], "ALPACA_LATEST_BARS")
        self.assertEqual(result.candidates[0]["raw"]["latest_bar_at"], fresh_bar()["t"])
        self.assertEqual(item["minuteBar"]["t"], (NOW - timedelta(minutes=16)).isoformat())
        self.assertTrue(all(kwargs["params"]["feed"] == "iex" for _, kwargs in session.calls))
        self.assertEqual(result.audit["YMT"]["snapshot_bar_at"], item["minuteBar"]["t"])
        self.assertEqual(result.audit["YMT"]["bar_refresh"], "REAL_BAR_UPDATED")

    def test_recovery_never_accepts_stale_future_invalid_or_zero_volume_bar(self):
        bars = [None, {**fresh_bar(), "t": (NOW - timedelta(minutes=16)).isoformat()},
                {**fresh_bar(), "t": (NOW + timedelta(minutes=1)).isoformat()},
                {**fresh_bar(), "t": "invalid"}, {**fresh_bar(), "v": 0},
                {**fresh_bar(), "c": 0}, {**fresh_bar(), "v": "NaN"}]
        for bar in bars:
            with self.subTest(bar=bar):
                result = self.scan(RefreshSession({"YMT": stale_snapshot()}, {"YMT": bar}))
                self.assertEqual(result.candidates, [])
                self.assertEqual(result.refresh_recovered, 0)
                self.assertEqual(result.audit["YMT"]["reason"], "STALE_MINUTE_BAR")

    def test_no_refresh_without_recent_valid_trade_or_with_fresh_snapshot(self):
        items = {"STALE_TRADE": stale_snapshot(), "OUT_OF_RANGE": stale_snapshot(), "FRESH": snapshot()}
        items["STALE_TRADE"]["latestTrade"]["t"] = (NOW - timedelta(minutes=16)).isoformat()
        items["OUT_OF_RANGE"]["latestTrade"]["p"] = 101
        session = RefreshSession(items, {})
        result = self.scan(session)
        self.assertEqual(len(session.calls), 1)
        self.assertEqual([c["symbol"] for c in result.candidates], ["FRESH"])

    def test_refresh_cap_and_shared_request_pacing(self):
        items = {f"A{i:03d}": stale_snapshot() for i in range(26)}
        session = RefreshSession(items, {s: fresh_bar() for s in items})
        sleeper = Mock()
        result = self.scan(session, batch_size=25, refresh_max_batches=1,
                           request_interval=0.5, clock=lambda: 0, sleep=sleeper)
        self.assertEqual(len(session.calls), 3)
        self.assertEqual(sleeper.call_args_list, [unittest.mock.call(0.5), unittest.mock.call(0.5)])
        self.assertEqual(result.refresh_requested, 25)
        self.assertEqual(len(result.candidates), 25)
        self.assertEqual(result.audit["A025"]["bar_refresh"], "LIMIT_REACHED")

    def test_auth_and_rate_limit_failure_abort_without_publishing_partial_data(self):
        for status in (401, 403, 429):
            with self.subTest(status=status):
                items = {f"A{i:03d}": stale_snapshot() for i in range(26)}
                items["A000"] = snapshot()
                session = RefreshSession(items, {}, refresh_status=status)
                result = self.scan(session, batch_size=25)
                self.assertFalse(result.complete)
                self.assertEqual(len(session.calls), 2)
                self.assertEqual(result.candidates, [])
                self.assertEqual(result.audit["A000"]["reason"], "SUPPRESSED_INCOMPLETE_SCAN")
                self.assertEqual(result.audit["A025"]["reason"], "UNSCANNED_SCAN_ABORTED")

    def test_failed_optional_refresh_keeps_original_rejection(self):
        result = self.scan(RefreshSession({"YMT": stale_snapshot()}, {}, refresh_status=500))
        self.assertTrue(result.complete)
        self.assertEqual(result.candidates, [])
        self.assertEqual(result.audit["YMT"]["bar_refresh"], "REQUEST_FAILED")
        self.assertEqual(result.audit["YMT"]["reason"], "STALE_MINUTE_BAR")

    def test_recovered_bar_still_expires_at_scan_finish(self):
        result = self.scan(RefreshSession({"YMT": stale_snapshot()}, {"YMT": fresh_bar()}),
                           now=Mock(side_effect=[NOW, NOW, NOW + timedelta(minutes=16)]))
        self.assertEqual(result.candidates, [])
        self.assertEqual(result.audit["YMT"]["reason"], "EXPIRED_DURING_SCAN")


class AuditTests(unittest.TestCase):
    def test_chunks_preserve_all_symbols_without_secrets_or_invalid_json(self):
        session = RefreshSession({f"S{i:05d}": snapshot() for i in range(13508)}, {})
        result = ScanRefreshTests().scan(session)
        logger = Mock()
        emit_audit(logger, result.scan_id, "iex", result.audit.values())
        rows = []
        self.assertLess(logger.info.call_count, 500)
        for call in logger.info.call_args_list:
            message = call.args[1]
            self.assertLessEqual(len(message), 12000)
            self.assertNotIn("SECRET_", message)
            payload = json.loads(message)
            self.assertEqual(payload["scan_id"], result.scan_id)
            rows.extend(payload["rows"])
        self.assertEqual({r["symbol"] for r in rows}, set(session.items))

    def test_radar_audit_explains_selection_and_universe_exclusions(self):
        engine = fixtures.ScannerIntegrationTests().engine()
        from types import SimpleNamespace
        engine.alpaca.list_assets.return_value = [
            SimpleNamespace(symbol="YMT", tradable=True, name="Company"),
            SimpleNamespace(symbol="SMJF", tradable=True, name="Company"),
            SimpleNamespace(symbol="FUND", tradable=True, name="Example ETF"),
            SimpleNamespace(symbol="HALT", tradable=False, name="Company")]
        session = RefreshSession({"YMT": snapshot(2000), "SMJF": snapshot(1000)}, {})
        def actual_scan(symbols, **kwargs):
            return scan_market(symbols, **kwargs, session=session, now=lambda: NOW, request_interval=0)
        with patch("scanner_engine.scan_market", side_effect=actual_scan), self.assertLogs("scanner_engine", logging.INFO) as logs:
            result = engine.run_radar(top_n=1)
        self.assertEqual(result.symbols, ["YMT"])
        rows = []
        for message in logs.output:
            if "APEX AUDIT " in message:
                rows.extend(json.loads(message.split("APEX AUDIT ", 1)[1])["rows"])
        by_symbol = {r["symbol"]: r for r in rows}
        self.assertEqual(by_symbol["YMT"]["reason"], "SELECTED_RADAR")
        self.assertEqual(by_symbol["SMJF"]["reason"], "OUTSIDE_RADAR_TOP_N")
        self.assertEqual(by_symbol["SMJF"]["rank"], 2)
        self.assertEqual(by_symbol["FUND"]["reason"], "FUND_NAME_GUARD")
        self.assertEqual(by_symbol["HALT"]["reason"], "ASSET_NOT_TRADABLE")
