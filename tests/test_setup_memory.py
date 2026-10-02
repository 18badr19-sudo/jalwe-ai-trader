from __future__ import annotations

import tempfile
import unittest

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from research_orchestrator import (
    ResearchOrchestrator,
    ResearchPacket,
)
from setup_memory import (
    SetupMemoryStore,
    SetupMemoryWatcher,
)


def frame(
    *,
    resistance=None,
    vwap=None,
    ma10=None,
    ma20=None,
):
    return SimpleNamespace(
        resistance=resistance,
        vwap=vwap,
        ma10=ma10,
        ma20=ma20,
    )


class ApexSetupMemoryTests(
    unittest.TestCase
):

    def test_setup_context_builds_structure_references(
        self,
    ) -> None:
        pre = SimpleNamespace(
            current_price=10.0,
            timeframe_5m=frame(
                resistance=10.20,
                vwap=9.92,
                ma10=9.90,
                ma20=9.80,
            ),
            timeframe_30m=frame(
                resistance=10.50,
                vwap=9.85,
                ma10=9.88,
                ma20=9.70,
            ),
            timeframe_1h=frame(
                resistance=11.00,
                vwap=9.60,
                ma10=9.75,
                ma20=9.50,
            ),
            timeframe_1d=frame(
                resistance=12.00,
                vwap=None,
                ma10=9.40,
                ma20=9.20,
            ),
            reasons=[
                "5M: COMPRESSION",
                "30M: NEAR_RESISTANCE",
            ],
        )

        context = (
            ResearchOrchestrator
            ._setup_context(
                pre
            )
        )

        self.assertAlmostEqual(
            context[
                "activation_price"
            ],
            10.20,
        )
        self.assertAlmostEqual(
            context[
                "support_reference"
            ],
            9.92,
        )
        self.assertAlmostEqual(
            context[
                "entry_zone_low"
            ],
            10.149,
        )
        self.assertAlmostEqual(
            context[
                "entry_zone_high"
            ],
            10.251,
        )
        self.assertGreater(
            context[
                "target_1_reference"
            ],
            context[
                "activation_price"
            ],
        )
        self.assertGreater(
            context[
                "target_2_reference"
            ],
            context[
                "target_1_reference"
            ],
        )
        self.assertGreater(
            context[
                "target_3_reference"
            ],
            context[
                "target_2_reference"
            ],
        )
        self.assertTrue(
            context[
                "research_only"
            ]
        )

    def test_score_history_survives_store_restart(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = str(
                Path(temp_dir)
                / "setup_memory.db"
            )

            store = SetupMemoryStore(
                database_url="",
                sqlite_path=path,
            )

            orchestrator = SimpleNamespace()

            watcher = SetupMemoryWatcher(
                orchestrator,
                store=store,
                minimum_memory_score=55,
                max_refresh_per_cycle=1,
            )

            packet_1 = ResearchPacket(
                symbol="TEST",
                research_score=60.0,
                confidence=85.0,
                verdict="WATCH",
                radar_score=70.0,
                radar_rvol=2.0,
                metadata={
                    "setup_context": {
                        "current_price": 9.80,
                        "activation_price": 10.0,
                        "entry_zone_low": 9.95,
                        "entry_zone_high": 10.05,
                        "support_reference": 9.50,
                        "resistance_5m": 10.0,
                        "target_1_reference": 10.5,
                        "target_2_reference": 11.0,
                        "target_3_reference": 11.5,
                        "reason": "setup forming",
                    }
                },
            )

            first = watcher.observe_cycle(
                SimpleNamespace(
                    packets=[
                        packet_1
                    ]
                )
            )

            self.assertEqual(
                first[
                    "remembered"
                ],
                1,
            )

            packet_2 = ResearchPacket(
                symbol="TEST",
                research_score=72.0,
                confidence=90.0,
                verdict="RESEARCH_CANDIDATE",
                radar_score=75.0,
                radar_rvol=2.5,
                metadata={
                    "setup_context": {
                        "current_price": 9.90,
                        "activation_price": 10.0,
                        "entry_zone_low": 9.95,
                        "entry_zone_high": 10.05,
                        "support_reference": 9.55,
                        "resistance_5m": 10.0,
                        "target_1_reference": 10.45,
                        "target_2_reference": 10.90,
                        "target_3_reference": 11.35,
                        "reason": "score improving",
                    }
                },
            )

            second = watcher.observe_cycle(
                SimpleNamespace(
                    packets=[
                        packet_2
                    ]
                )
            )

            self.assertEqual(
                second[
                    "remembered"
                ],
                1,
            )

            row = store.get(
                "TEST"
            )

            self.assertEqual(
                row[
                    "observation_count"
                ],
                2,
            )
            self.assertAlmostEqual(
                row[
                    "first_score"
                ],
                60.0,
            )
            self.assertAlmostEqual(
                row[
                    "previous_score"
                ],
                60.0,
            )
            self.assertAlmostEqual(
                row[
                    "latest_score"
                ],
                72.0,
            )
            self.assertAlmostEqual(
                row[
                    "best_score"
                ],
                72.0,
            )
            self.assertAlmostEqual(
                row[
                    "score_delta"
                ],
                12.0,
            )

            store.close()

            restored_store = SetupMemoryStore(
                database_url="",
                sqlite_path=path,
            )

            restored = (
                restored_store
                .get(
                    "TEST"
                )
            )

            self.assertIsNotNone(
                restored
            )
            self.assertEqual(
                restored[
                    "observation_count"
                ],
                2,
            )
            self.assertAlmostEqual(
                restored[
                    "latest_score"
                ],
                72.0,
            )
            self.assertAlmostEqual(
                restored[
                    "activation_price"
                ],
                10.0,
            )

            restored_store.close()

    def test_saved_setup_wakes_jalwe_near_activation_with_cooldown(
        self,
    ) -> None:
        store = SetupMemoryStore(
            database_url="",
            sqlite_path=":memory:",
        )

        store.observe(
            {
                "symbol": "TEST",
                "status": "ACTIVE",
                "score": 70.0,
                "confidence": 90.0,
                "verdict": "RESEARCH_CANDIDATE",
                "current_price": 9.70,
                "activation_price": 10.0,
                "entry_zone_low": 9.95,
                "entry_zone_high": 10.05,
                "support_reference": 9.50,
                "resistance_5m": 10.0,
                "target_1_reference": 10.5,
                "target_2_reference": 11.0,
                "target_3_reference": 11.5,
                "reason": "stored setup",
                "radar_score": 75.0,
                "radar_rvol": 2.0,
                "radar_change_pct": 3.0,
            }
        )

        pre = SimpleNamespace(
            symbol="TEST",
            score=76.0,
            data_confidence=100.0,
            status="CONFIRMED",
            ready=True,
            current_price=9.92,
            score_5m=78.0,
            score_30m=75.0,
            score_1h=73.0,
            score_1d=70.0,
            timeframe_5m=frame(
                resistance=10.0,
                vwap=9.85,
                ma10=9.82,
                ma20=9.75,
            ),
            timeframe_30m=frame(
                resistance=10.30,
                vwap=9.70,
                ma10=9.72,
                ma20=9.60,
            ),
            timeframe_1h=frame(
                resistance=10.80,
                vwap=9.50,
                ma10=9.65,
                ma20=9.40,
            ),
            timeframe_1d=frame(
                resistance=11.50,
                vwap=None,
                ma10=9.30,
                ma20=9.10,
            ),
            reasons=[
                "5M: NEAR_RESISTANCE",
                "30M: COMPRESSION",
            ],
            warnings=[],
        )

        liquidity = SimpleNamespace(
            liquidity_score=80.0,
            confidence=0.95,
            liquidity_bias="BULLISH",
            buy_pressure=65.0,
            sell_pressure=35.0,
            money_flow=100000.0,
            volume_acceleration=2.0,
            price_volume_confirmation=True,
            absorption=False,
            distribution=False,
        )

        news_result = {
            "symbol": "TEST",
            "news_score": 70.0,
            "confidence": 0.90,
            "sentiment": "POSITIVE",
            "status": "SUCCESS",
            "catalysts": [
                "CATALYST"
            ],
            "headlines": [
                "Fresh headline"
            ],
            "risk_flags": [],
        }

        ai_result = {
            "status": "SUCCESS",
            "symbol": "TEST",
            "research_score": 84.0,
            "confidence": 96.0,
            "bias": "BULLISH",
            "verdict":
                "HIGH_PRIORITY_RESEARCH",
            "evidence": [
                "fresh breakout alignment"
            ],
            "conflicts": [],
            "risk_flags": [],
            "alignment_bonus": 5.0,
            "risk_penalty": 0.0,
            "prebreakout_penalty": 0.0,
            "critical_risk": False,
        }

        builder = (
            ResearchOrchestrator
            .__new__(
                ResearchOrchestrator
            )
        )

        bridge = SimpleNamespace(
            publish_shortlist=Mock(
                return_value=[
                    "TEST"
                ]
            )
        )

        orchestrator = SimpleNamespace(
            prebreakout=SimpleNamespace(
                analyze_symbol=Mock(
                    return_value=pre
                )
            ),
            news=SimpleNamespace(
                fetch_symbol_news=Mock(
                    return_value=news_result
                )
            ),
            liquidity=SimpleNamespace(
                analyze_symbol=Mock(
                    return_value=liquidity
                )
            ),
            ai=SimpleNamespace(
                evaluate_research=Mock(
                    return_value=ai_result
                )
            ),
            jalwe_bridge=bridge,
            _build_packet=(
                builder._build_packet
            ),
        )

        watcher = SetupMemoryWatcher(
            orchestrator,
            store=store,
            max_refresh_per_cycle=1,
            max_age_days=30,
            wake_distance_pct=1.5,
            wake_cooldown_minutes=30,
            minimum_pre_score=55,
            minimum_pre_confidence=65,
        )

        first = (
            watcher
            .refresh_saved_setups()
        )

        self.assertEqual(
            first[
                "published"
            ],
            [
                "TEST"
            ],
        )

        bridge.publish_shortlist.assert_called_once()

        published_packet = (
            bridge
            .publish_shortlist
            .call_args[0][0][0]
        )

        self.assertEqual(
            published_packet
            .metadata[
                "watch_lane"
            ],
            "LONG_TERM_REACTIVATION",
        )

        self.assertEqual(
            published_packet
            .metadata[
                "setup_memory"
            ][
                "wake_reason"
            ],
            "NEAR_ACTIVATION",
        )

        row = store.get(
            "TEST"
        )

        self.assertTrue(
            bool(
                row[
                    "last_wake_at"
                ]
            )
        )

        second = (
            watcher
            .refresh_saved_setups()
        )

        self.assertEqual(
            second[
                "published"
            ],
            [],
        )

        bridge.publish_shortlist.assert_called_once()

        store.close()


if __name__ == "__main__":
    unittest.main()
