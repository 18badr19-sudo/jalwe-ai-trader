import copy
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests

from full_market_scan import ScanResult, scan_market, snapshot_candidate, timestamp
from scanner_engine import ScannerEngine

NOW = datetime(2026, 9, 28, 18, 0, tzinfo=timezone.utc)


def snapshot(volume=1000):
    return {"latestTrade": {"p": 10, "t": NOW.isoformat()},
            "minuteBar": {"c": 10, "v": 200, "t": NOW.isoformat()},
            "dailyBar": {"v": volume, "c": 10, "t": "2026-09-28T04:00:00Z"},
            "prevDailyBar": {"v": 500, "c": 9, "t": "2026-09-25T04:00:00Z"}}


def ranker(**values):
    return values["volume"], [], []


class FakeSession:
    def __init__(self, fail_at=None, status=500, wrapped=False):
        self.calls = []
        self.fail_at = fail_at
        self.status = status
        self.wrapped = wrapped

    def get(self, url, **kwargs):
        symbols = kwargs["params"]["symbols"].split(",")
        self.calls.append(symbols)
        if len(self.calls) == self.fail_at:
            response = Mock(status_code=self.status)
            response.raise_for_status.side_effect = requests.HTTPError("provider failure")
            return response
        payload = {s: snapshot(100000 if s == "ZZZZ" else 1000) for s in symbols}
        response = Mock(status_code=200)
        response.json.return_value = {"snapshots": payload} if self.wrapped else payload
        return response


class FullMarketTests(unittest.TestCase):
    def test_alpaca_fractional_timestamps_on_python_310(self):
        for fraction in ("1", "12", "123", "1234", "12345", "123456", "123456789"):
            with self.subTest(fraction=fraction):
                value = "2026-09-28T17:59:00." + fraction + "Z"
                self.assertIsNotNone(timestamp(value))
                item = snapshot()
                item["minuteBar"]["t"] = value
                self.assertIsNotNone(snapshot_candidate("A", item, NOW, 0.5, 100, ranker))

    def test_exclusions_distinguish_stale_missing_invalid_price_and_volume(self):
        items = {"STALE": snapshot(), "BADTIME": snapshot(), "PRICE": snapshot(),
                 "VOLUME": snapshot(0), "GOOD": snapshot(), "MISSING": None}
        items["STALE"]["minuteBar"]["t"] = (NOW - timedelta(minutes=16)).isoformat()
        items["BADTIME"]["minuteBar"]["t"] = "invalid"
        items["PRICE"]["latestTrade"]["p"] = 101
        session = FakeSession()
        response = Mock(status_code=200)
        response.json.return_value = items
        session.get = Mock(return_value=response)
        result = self.scan(list(items), session)
        self.assertEqual(result.rejection_counts, {"STALE_MINUTE_BAR": 1,
            "INVALID_BAR_TIMESTAMP": 1, "PRICE_OUT_OF_RANGE": 1,
            "INVALID_OR_ZERO_VOLUME": 1, "MISSING_SNAPSHOT": 1})
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(sum(result.rejection_counts.values()) + len(result.candidates), result.scanned_count)

    def scan(self, symbols, session=None, **kwargs):
        return scan_market(symbols, api_key="test", api_secret="test", feed="iex",
            min_price=0.5, max_price=100, ranker=ranker, session=session or FakeSession(),
            request_interval=0, now=kwargs.pop("now", lambda: NOW), **kwargs)

    def test_entire_large_universe_is_scanned_before_ranking(self):
        symbols = [f"S{i:05d}" for i in range(13508)] + ["ZZZZ"]
        session = FakeSession()
        result = self.scan(symbols + symbols[:3], session)
        self.assertTrue(result.complete)
        self.assertEqual(result.universe_count, 13509)
        self.assertEqual(result.scanned_count, 13509)
        self.assertEqual(result.snapshot_count, 13509)
        self.assertEqual(len(session.calls), 91)
        self.assertEqual(result.candidates[0]["symbol"], "ZZZZ")
        self.assertEqual(set(sum(session.calls, [])), set(symbols))
        self.assertTrue(all(len(batch) <= 150 for batch in session.calls))

    def test_late_batch_failure_clears_partial_candidates(self):
        result = self.scan([f"S{i}" for i in range(301)], FakeSession(fail_at=3))
        self.assertFalse(result.complete)
        self.assertEqual(result.scanned_count, 300)
        self.assertEqual(result.failed_batches, 1)
        self.assertEqual(result.candidates, [])

    def test_authorization_and_rate_limit_stop_without_retry_storm(self):
        for status in (401, 403, 429):
            with self.subTest(status=status):
                session = FakeSession(fail_at=1, status=status)
                result = self.scan([f"S{i}" for i in range(500)], session)
                self.assertEqual(len(session.calls), 1)
                self.assertFalse(result.complete)
                self.assertEqual(result.candidates, [])

    def test_deadline_does_not_publish_partial_scan(self):
        result = self.scan(["A"], clock=Mock(side_effect=[0, 0, 181]))
        self.assertFalse(result.complete)
        self.assertIn("SNAPSHOT_SCAN_TIME_BUDGET_EXCEEDED", result.warnings)

    def test_wrapped_snapshot_shape(self):
        result = self.scan(["A"], FakeSession(wrapped=True))
        self.assertTrue(result.complete)
        self.assertEqual(result.candidates[0]["symbol"], "A")

    def test_missing_snapshots_are_not_invented(self):
        session = FakeSession()
        response = Mock(status_code=200)
        response.json.return_value = {"A": snapshot(), "B": None}
        session.get = Mock(return_value=response)
        result = self.scan(["A", "B", "C"], session)
        self.assertTrue(result.complete)
        self.assertEqual(result.scanned_count, 3)
        self.assertEqual(result.snapshot_count, 1)
        self.assertEqual([c["symbol"] for c in result.candidates], ["A"])

    def test_stale_future_and_missing_bar_timestamps_are_rejected(self):
        for stamp in (None, "invalid", "2026-09-28T18:00:00",
                      (NOW - timedelta(minutes=16)).isoformat(),
                      (NOW + timedelta(minutes=1)).isoformat()):
            item = snapshot()
            item["minuteBar"]["t"] = stamp
            self.assertIsNone(snapshot_candidate("A", item, NOW, 0.5, 100, ranker))

    def test_freshness_checked_again_when_scan_finishes(self):
        clock_now = Mock(side_effect=[NOW, NOW + timedelta(minutes=16)])
        result = self.scan(["A"], now=clock_now)
        self.assertTrue(result.complete)
        self.assertEqual(result.candidates, [])

    def test_price_bounds_and_invalid_volume(self):
        for price in (0, 0.49, 101):
            item = snapshot()
            item["latestTrade"]["p"] = price
            item["minuteBar"]["c"] = price
            self.assertIsNone(snapshot_candidate("A", item, NOW, 0.5, 100, ranker))
        for volume in (0, -1, "NaN", "Infinity"):
            item = snapshot(volume)
            self.assertIsNone(snapshot_candidate("A", item, NOW, 0.5, 100, ranker))

    def test_previous_day_volume_is_not_labeled_average(self):
        result = snapshot_candidate("A", snapshot(), NOW, 0.5, 100, ranker)
        self.assertIsNone(result["average_volume"])
        self.assertIn("VOLUME_PACE_PROXY_NOT_HISTORICAL_RVOL", result["warnings"])
        item = snapshot()
        item["dailyBar"]["t"] = "2026-09-25T04:00:00Z"
        result = snapshot_candidate("A", item, NOW, 0.5, 100, ranker)
        self.assertIsNone(result["relative_volume"])
        self.assertEqual(result["volume"], 200)

    def test_requests_are_paced(self):
        sleeper = Mock()
        scan_market([f"A{i}" for i in range(151)], api_key="test", api_secret="test",
            feed="iex", min_price=0.5, max_price=100, ranker=ranker,
            session=FakeSession(), clock=lambda: 0, sleep=sleeper, now=lambda: NOW)
        sleeper.assert_called_once_with(0.5)


class ScannerIntegrationTests(unittest.TestCase):
    def engine(self):
        with patch.dict("os.environ", {"APEX_FULL_MARKET_SCAN": "true"}), \
             patch.object(ScannerEngine, "_initialize_alpaca"):
            engine = ScannerEngine()
        engine.alpaca = Mock()
        return engine

    def test_full_market_routes_without_finviz_and_preserves_top_limit(self):
        engine = self.engine()
        engine.alpaca.list_assets.return_value = [
            SimpleNamespace(symbol=f"A{i:03d}", tradable=True, name="Company") for i in range(300)]
        engine._run_custom_screen = Mock(side_effect=AssertionError("Finviz must not run"))
        import full_market_scan
        def actual_scan(symbols, **kwargs):
            return full_market_scan.scan_market(symbols, **kwargs, session=FakeSession(),
                                               request_interval=0, now=lambda: NOW)
        with patch("scanner_engine.scan_market", side_effect=actual_scan), self.assertLogs("apex.audit"):
            result = engine.run_radar(top_n=40)
        self.assertEqual(result.source, "ALPACA_FULL_MARKET")
        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.scanned_count, 300)
        self.assertEqual(len(result.ranked_candidates), 40)
        self.assertTrue(result.coverage_complete)
        engine._run_custom_screen.assert_not_called()

    def test_incomplete_scan_does_not_fall_back_to_finviz(self):
        engine = self.engine()
        engine._get_tradable_symbols = Mock(return_value={"A"})
        engine._run_custom_screen = Mock()
        with patch("scanner_engine.scan_market", return_value=ScanResult(universe_count=1, failed_batches=1)):
            result = engine.run_radar()
        self.assertEqual(result.status, "INCOMPLETE")
        self.assertEqual(result.symbols, [])
        engine._run_custom_screen.assert_not_called()

    def test_nontradable_and_known_funds_excluded_from_universe(self):
        engine = self.engine()
        engine.alpaca.list_assets.return_value = [
            SimpleNamespace(symbol="AAA", tradable=True, name="Ordinary Company"),
            SimpleNamespace(symbol="ETF", tradable=True, name="Example ETF"),
            SimpleNamespace(symbol="NO", tradable=False, name="Inactive Company")]
        self.assertEqual(engine._get_tradable_symbols(), {"AAA"})


if __name__ == "__main__":
    unittest.main()
