import json
import logging
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from ai_engine import AIEngine
from research_orchestrator import ResearchOrchestrator
from scanner_engine import RadarResult, RankedCandidate


class ResearchAuditTests(unittest.TestCase):
    def engine(self):
        engine = ResearchOrchestrator.__new__(ResearchOrchestrator)
        symbols = ["LOWCONF", "YMT", "CRITICAL", "PUBLISH", "OUTSIDE"]
        radar = RadarResult(status="SUCCESS", source="ALPACA_FULL_MARKET", scan_id="scan-test",
            filters={"feed": "iex"}, ranked_candidates=[RankedCandidate(s, price=2) for s in symbols])
        engine.scanner = Mock()
        engine.scanner.run_radar.return_value = radar
        engine.prebreakout = Mock()
        scores = {"LOWCONF": 100, "YMT": 90, "CRITICAL": 95, "PUBLISH": 85, "OUTSIDE": 80}
        engine.prebreakout.analyze_symbol.side_effect = lambda symbol, **kw: SimpleNamespace(
            symbol=symbol, score=scores[symbol], data_confidence=50 if symbol == "LOWCONF" else 90)
        engine.news = Mock()
        engine.news.fetch_symbol_news.return_value = {"news_score": 58.76, "status": "SUCCESS"}
        engine.liquidity = Mock()
        engine.liquidity.analyze_symbol.return_value = SimpleNamespace(liquidity_score=50, confidence=0.9)
        engine.ai = Mock(watch_threshold=AIEngine.WATCH_THRESHOLD)
        def ai_result(symbol, **kw):
            return dict(symbol=symbol, status="SUCCESS", research_score=39.79 if symbol == "YMT" else 90,
                confidence=93.25, verdict="WATCH" if symbol == "PUBLISH" else "REJECT",
                critical_risk=symbol == "CRITICAL",
                risk_flags=["DISTRIBUTION_PROXY_DETECTED"] if symbol == "CRITICAL" else [])
        engine.ai.evaluate_research.side_effect = ai_result
        engine.jalwe_bridge = Mock()
        engine.jalwe_bridge.publish_shortlist.return_value = ["PUBLISH"]
        engine.jalwe_bridge_error = None
        return engine

    def run_and_rows(self, engine, **kwargs):
        with self.assertLogs("apex.audit", logging.INFO) as logs, patch("research_orchestrator.logger.exception"):
            result = engine.run_cycle(deep_research_top_n=3, **kwargs)
        rows = []
        for message in logs.output:
            if "APEX AUDIT " in message:
                payload = json.loads(message.split("APEX AUDIT ", 1)[1])
                self.assertEqual(payload["scan_id"], "scan-test")
                self.assertEqual(payload["feed"], "iex")
                rows.extend(payload["rows"])
        return result, rows

    def test_actual_cycle_records_each_gate_and_only_publishes_allowed_packet(self):
        engine = self.engine()
        result, rows = self.run_and_rows(engine)
        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.published_count, 1)
        reasons = {(r["symbol"], r["reason"]) for r in rows}
        self.assertIn(("LOWCONF", "PRE_CONFIDENCE_BELOW_MIN"), reasons)
        self.assertIn(("OUTSIDE", "OUTSIDE_DEEP_TOP_N"), reasons)
        self.assertIn(("YMT", "SCORE_BELOW_WATCH_THRESHOLD"), reasons)
        self.assertIn(("CRITICAL", "CRITICAL_RESEARCH_RISK"), reasons)
        self.assertIn(("PUBLISH", "PUBLISHED_TO_JALWE"), reasons)
        sent = engine.jalwe_bridge.publish_shortlist.call_args.args[0]
        self.assertEqual([p.symbol for p in sent], ["PUBLISH"])
        self.assertFalse(sent[0].order_execution_enabled)
        ymt = next(r for r in rows if r["symbol"] == "YMT" and r["stage"] == "RESEARCH")
        self.assertEqual(ymt["score"], 39.79)
        self.assertEqual(ymt["watch_threshold"], 45)

    def test_no_publication_claim_without_bridge_acknowledgment(self):
        engine = self.engine()
        engine.jalwe_bridge.publish_shortlist.return_value = []
        result, rows = self.run_and_rows(engine)
        self.assertEqual(result.published_count, 0)
        self.assertTrue(any(r["reason"] == "PUBLISH_NOT_ACKNOWLEDGED" for r in rows))
        self.assertFalse(any(r["reason"] == "PUBLISHED_TO_JALWE" for r in rows))

    def test_liquidity_error_logged_without_submitting_candidate(self):
        engine = self.engine()
        engine.liquidity.analyze_symbol.side_effect = RuntimeError("test failure")
        result, rows = self.run_and_rows(engine)
        self.assertEqual(result.shortlist, [])
        self.assertTrue(any(r["reason"] == "LIQUIDITY_ANALYSIS_ERROR" for r in rows))
        engine.jalwe_bridge.publish_shortlist.assert_not_called()

    def test_disabled_publication_and_missing_bridge_are_explicit(self):
        engine = self.engine()
        _, rows = self.run_and_rows(engine, publish_to_jalwe=False)
        self.assertTrue(any(r["reason"] == "PUBLISH_DISABLED" for r in rows))
        engine.jalwe_bridge.publish_shortlist.assert_not_called()
        engine = self.engine()
        engine.jalwe_bridge = None
        _, rows = self.run_and_rows(engine)
        self.assertTrue(any(r["reason"] == "BRIDGE_UNAVAILABLE" for r in rows))
