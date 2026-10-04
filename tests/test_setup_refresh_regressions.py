import os
import unittest
from datetime import timedelta
from types import SimpleNamespace as NS
from unittest.mock import Mock
from uuid import uuid4

from research_orchestrator import ResearchOrchestrator, ResearchPacket
from setup_memory import SetupMemoryStore, SetupMemoryWatcher, utc_iso, utc_now


class SetupRefreshRegressions(unittest.TestCase):
    def setUp(self):
        self.store = SetupMemoryStore(database_url="", sqlite_path=":memory:")
        self.addCleanup(self.store.close)
        self.store.observe({
            "symbol": "TEST", "status": "ACTIVE", "score": 80, "confidence": 95,
            "activation_price": 10, "current_price": 9.9,
            "observed_at": utc_iso(utc_now() - timedelta(days=60)),
        })

    def watcher(self, price, activation, *, confidence=100, verdict="HIGH_PRIORITY_RESEARCH",
                critical=False):
        pre = NS(score=90, data_confidence=confidence, current_price=price, ready=False,
                 timeframe_5m=NS(resistance=activation, vwap=None, ma10=None, ma20=None))
        builder = ResearchOrchestrator._setup_context

        def packet(**kwargs):
            return ResearchPacket(
                symbol="TEST", research_score=85, confidence=95, verdict=verdict,
                critical_risk=critical, metadata={"setup_context": builder(kwargs["pre_result"])},
            )

        self.orchestrator = NS(
            prebreakout=NS(analyze_symbol=Mock(return_value=pre)),
            news=NS(fetch_symbol_news=Mock(return_value={"status": "SUCCESS"})),
            liquidity=NS(analyze_symbol=Mock(return_value=NS())),
            ai=NS(evaluate_research=Mock(return_value={"status": "SUCCESS"})),
            jalwe_bridge=NS(publish_shortlist=Mock(return_value=["TEST"])),
            _setup_context=builder, _build_packet=Mock(side_effect=packet),
        )
        return SetupMemoryWatcher(self.orchestrator, store=self.store)

    def test_new_activation_wakes_even_when_old_level_is_far_away(self):
        result = self.watcher(19.9, 20).refresh_saved_setups()
        self.assertEqual(result["published"], ["TEST"])
        self.orchestrator.news.fetch_symbol_news.assert_called_once_with("TEST")
        self.orchestrator.liquidity.analyze_symbol.assert_called_once_with("TEST")
        self.orchestrator.ai.evaluate_research.assert_called_once()
        packet = self.orchestrator.jalwe_bridge.publish_shortlist.call_args.args[0][0]
        self.assertEqual(packet.metadata["setup_context"]["activation_price"], 20)
        self.assertEqual(packet.metadata["setup_memory"]["distance_to_activation_pct"], 0.5)
        self.assertEqual(self.store.get("TEST")["activation_price"], 20)

    def test_price_near_old_level_does_not_wake_far_from_new_level(self):
        result = self.watcher(9.95, 12).refresh_saved_setups()
        self.assertEqual(result["near_activation"], 0)
        self.assertEqual(result["published"], [])
        self.orchestrator.news.fetch_symbol_news.assert_not_called()
        self.assertEqual(self.store.get("TEST")["activation_price"], 12)

    def test_far_structure_refresh_preserves_research_history_and_rotation(self):
        before = self.store.get("TEST")
        result = self.watcher(50, 60).refresh_saved_setups()
        after = self.store.get("TEST")
        self.assertEqual(result["published"], [])
        self.assertEqual(after["current_price"], 50)
        self.assertEqual(after["snapshot"]["activation_price"], 60)
        for key in ("first_seen_at", "last_seen_at", "observation_count", "first_score",
                    "previous_score", "latest_score", "best_score", "score_delta", "last_wake_at"):
            self.assertEqual(after[key], before[key], key)
        self.assertIsNotNone(after["last_checked_at"])
        conn = self.store._connect_sqlite()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM apex_setup_history").fetchone()[0], 1)

    def test_cooldown_still_blocks_wake_but_updates_structure(self):
        self.store.mark_wake("TEST")
        before_wake = self.store.get("TEST")["last_wake_at"]
        result = self.watcher(19.9, 20).refresh_saved_setups()
        self.assertEqual(result["near_activation"], 1)
        self.assertEqual(result["published"], [])
        self.orchestrator.jalwe_bridge.publish_shortlist.assert_not_called()
        row = self.store.get("TEST")
        self.assertEqual(row["activation_price"], 20)
        self.assertEqual(row["last_wake_at"], before_wake)

    def test_low_confidence_cannot_replace_levels_or_publish(self):
        result = self.watcher(19.9, 20, confidence=20).refresh_saved_setups()
        self.assertEqual(result["published"], [])
        self.assertEqual(self.store.get("TEST")["activation_price"], 10)
        self.orchestrator.ai.evaluate_research.assert_not_called()

    def test_missing_current_level_does_not_reuse_old_level(self):
        result = self.watcher(9.95, None).refresh_saved_setups()
        self.assertEqual(result["published"], [])
        self.assertIsNone(self.store.get("TEST")["activation_price"])

    def test_fresh_verdict_and_critical_risk_still_gate_publication(self):
        for verdict, critical in (("REJECT", False), ("HIGH_PRIORITY_RESEARCH", True)):
            with self.subTest(verdict=verdict, critical=critical):
                result = self.watcher(19.9, 20, verdict=verdict, critical=critical).refresh_saved_setups()
                self.assertEqual(result["published"], [])
                self.orchestrator.jalwe_bridge.publish_shortlist.assert_not_called()

    def test_exclusion_precedes_limit_and_preserves_rotation(self):
        for index in range(24):
            self.store.observe({"symbol": f"S{index:02}", "score": 100-index, "status": "ACTIVE"})
        excluded = {f" s{index:02} " for index in range(20)} | {"TEST"}
        due = self.store.list_due(limit=4, max_age_days=0, exclude_symbols=excluded)
        self.assertEqual([row["symbol"] for row in due], ["S20", "S21", "S22", "S23"])
        self.store.mark_checked("S20")
        due = self.store.list_due(limit=1, max_age_days=0, exclude_symbols=excluded)
        self.assertEqual([row["symbol"] for row in due], ["S21"])


@unittest.skipUnless(os.getenv("TEST_POSTGRES_DSN"), "Requires TEST_POSTGRES_DSN")
class PostgresSetupRefreshRegressions(unittest.TestCase):
    def test_structure_refresh_and_exclusion_before_limit_on_postgres(self):
        store = SetupMemoryStore(database_url=os.environ["TEST_POSTGRES_DSN"])
        symbols = ["REG" + uuid4().hex[:12].upper() for _ in range(7)]
        try:
            for index, symbol in enumerate(symbols):
                store.observe({"symbol": symbol, "status": "ACTIVE", "score": 100-index,
                               "activation_price": 10, "current_price": 9.9})
            before = store.get(symbols[-1])
            store.refresh_structure(symbols[-1], {"current_price": 19.9, "activation_price": 20})
            after = store.get(symbols[-1])
            self.assertEqual(after["activation_price"], 20)
            self.assertEqual(after["snapshot"]["current_price"], 19.9)
            self.assertEqual(after["observation_count"], before["observation_count"])
            self.assertEqual(after["last_seen_at"], before["last_seen_at"])
            all_rows = store.list_due(limit=1000, max_age_days=0)
            excluded = {row["symbol"] for row in all_rows} - {symbols[-1]}
            self.assertEqual([row["symbol"] for row in store.list_due(
                limit=1, max_age_days=0, exclude_symbols=excluded)], [symbols[-1]])
        finally:
            conn = store._connect_postgres()
            try:
                with conn:
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM apex_setup_history WHERE symbol = ANY(%s)", (symbols,))
                        cur.execute("DELETE FROM apex_setup_memory WHERE symbol = ANY(%s)", (symbols,))
            finally:
                conn.close()
                store.close()
