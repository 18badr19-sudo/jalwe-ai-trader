import unittest
from unittest.mock import Mock, patch
import pandas as pd

from market_data_engine import MarketDataEngine, get_latest_stock_quote
from regime_detector import get_current_market_regime
from ml_predictor import MLPredictor
from options_flow_engine import OptionsFlowEngine


class LegacyDataSafetyTests(unittest.TestCase):
    def test_failed_data_read_does_not_generate_fake_prices(self):
        for response in (Mock(status_code=403), Mock(status_code=200, json=Mock(return_value={'bars': []}))):
            with self.subTest(status=response.status_code), patch('market_data_engine.requests.get', return_value=response):
                self.assertTrue(MarketDataEngine().fetch_latest_bars('TEST').empty)
                self.assertEqual(get_latest_stock_quote('TEST'), {})
        with patch('market_data_engine.requests.get', side_effect=TimeoutError()):
            self.assertTrue(MarketDataEngine().fetch_latest_bars('TEST').empty)

    def test_real_bars_remain_available(self):
        payload = {'bars': [dict(t='2026-10-12T14:00:00Z', o=10, h=11, l=9, c=10.5, v=100)]}
        response = Mock(status_code=200, json=Mock(return_value=payload))
        with patch('market_data_engine.requests.get', return_value=response):
            frame = MarketDataEngine().fetch_latest_bars('TEST')
        self.assertEqual(frame.iloc[0]['close'], 10.5)
        self.assertEqual(len(frame), 1)

    def test_benchmark_without_data_is_unknown(self):
        self.assertEqual(get_current_market_regime(), 'UNKNOWN')
        self.assertNotEqual(get_current_market_regime(pd.DataFrame({'close': range(10, 70)})), 'UNKNOWN')

    def test_no_probability_without_a_validated_model(self):
        with self.assertRaisesRegex(RuntimeError, 'model'):
            MLPredictor().predict_probability('TEST', {'rvol': 2, 'rsi': 60})

    def test_no_contract_metrics_without_real_contract_data(self):
        result = OptionsFlowEngine().evaluate_contract('TEST', 10)
        self.assertEqual(result['status'], 'UNAVAILABLE')
        self.assertIsNone(result.get('contract_score'))
        for field in ('iv', 'delta', 'open_interest', 'spread'):
            self.assertIsNone(result.get(field))

    def test_no_target_levels_from_missing_daily_bars(self):
        from target_risk_engine import TargetRiskEngine
        broker = Mock()
        for outcome in (Mock(df=pd.DataFrame()), TimeoutError()):
            with self.subTest(outcome=type(outcome).__name__):
                broker.get_bars.side_effect = outcome if isinstance(outcome, Exception) else None
                broker.get_bars.return_value = outcome
                result = TargetRiskEngine(broker).calculate_levels('TEST', 10)
                self.assertEqual(result['status'], 'UNAVAILABLE')
                for field in ('entry_zone', 'stop_loss', 'target_1', 'target_2', 'target_3'):
                    self.assertIsNone(result.get(field))
