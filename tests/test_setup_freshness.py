from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch, Mock

import pandas as pd

from setup_freshness import inspect_setup
from pre_breakout_engine import PreBreakoutEngine, PreBreakoutDataError
import test_setup_refresh_regressions as fixtures


class SetupFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,14,18,28,tzinfo=timezone.utc)
        self.pre=NS(current_price=10.,timeframe_5m=NS(available=True,current_price=10.,
                    last_bar_at='2026-10-14T18:20:00Z',source_feed='iex'))

    def test_rtac_source_age_is_rejected_despite_high_confidence(self):
        self.pre.timeframe_5m.last_bar_at='2026-10-14T17:50:00Z'
        p=inspect_setup(self.pre,self.now)
        self.assertEqual(p['state'],'STALE_5M_BAR');self.assertEqual(p['age_minutes'],38.)

    def test_missing_future_unfinished_wrong_source_and_fallback_price_are_not_fresh(self):
        for at in (None,'2026-10-14T18:20:00','2026-10-14T18:30:00Z','2026-10-14T18:25:00Z',
                   '2026-10-14T18:21:00Z'):
            self.pre.timeframe_5m.last_bar_at=at
            self.assertNotEqual(inspect_setup(self.pre,self.now)['state'],'FRESH_COMPLETED_5M')
        self.pre.timeframe_5m.last_bar_at='2026-10-14T18:20:00Z'
        self.pre.timeframe_5m.source_feed='unknown'
        self.assertEqual(inspect_setup(self.pre,self.now)['state'],'MISSING_5M_EVIDENCE')
        self.pre.timeframe_5m.source_feed='iex';self.pre.current_price=11.
        self.assertEqual(inspect_setup(self.pre,self.now)['state'],'PRICE_SOURCE_MISMATCH')

    def test_exact_fifteen_minute_start_age_is_allowed_without_relaxing_limit(self):
        self.pre.timeframe_5m.last_bar_at='2026-10-14T18:10:00Z'
        self.assertEqual(inspect_setup(self.pre,self.now.replace(minute=25))['state'],'FRESH_COMPLETED_5M')
        self.assertEqual(inspect_setup(self.pre,self.now.replace(minute=25,second=1))['state'],'STALE_5M_BAR')

    def test_old_memory_cannot_refresh_levels_or_publish_and_remains_in_rotation(self):
        f=fixtures.SetupRefreshRegressions();f.setUp()
        try:
            watcher=f.watcher(19.9,20)
            pre=f.orchestrator.prebreakout.analyze_symbol.return_value
            pre.timeframe_5m.last_bar_at='2026-10-13T17:50:00Z'
            before=f.store.get('TEST')
            result=watcher.refresh_saved_setups()
            self.assertEqual(result['freshness_rejections'],{'STALE_5M_BAR':1})
            self.assertEqual(result['published'],[])
            f.orchestrator.news.fetch_symbol_news.assert_not_called()
            after=f.store.get('TEST')
            for key in ('activation_price','last_seen_at','observation_count','last_wake_at'):
                self.assertEqual(after[key],before[key])
            self.assertIsNotNone(after['last_checked_at'])
        finally:f.doCleanups()

    def test_evidence_that_ages_during_research_cannot_publish(self):
        f=fixtures.SetupRefreshRegressions();f.setUp()
        try:
            watcher=f.watcher(19.9,20)
            with patch('setup_freshness.inspect_setup',side_effect=[dict(state='FRESH_COMPLETED_5M'),dict(state='STALE_5M_BAR')]):
                result=watcher.refresh_saved_setups()
            self.assertEqual(result['published'],[])
            f.orchestrator.jalwe_bridge.publish_shortlist.assert_not_called()
            self.assertIsNone(f.store.get('TEST')['last_wake_at'])
        finally:f.doCleanups()

    def test_fetch_requests_newest_same_feed_and_excludes_unfinished_five_minutes(self):
        engine=PreBreakoutEngine.__new__(PreBreakoutEngine)
        engine.alpaca=Mock()
        index=pd.to_datetime(['2026-10-14T18:25:00Z','2026-10-14T18:20:00Z','2026-10-14T18:15:00Z'])
        frame=pd.DataFrame(dict(open=10.,high=11.,low=9.,close=10.,volume=100.),index=index)
        engine.alpaca.get_bars.return_value=NS(df=frame)
        with patch('pre_breakout_engine.datetime') as clock:
            clock.now.return_value=self.now
            result=engine._fetch_bars('TEST',timeframe='5Min',limit=2,lookback_days=10)
        params=engine.alpaca.get_bars.call_args.kwargs
        self.assertEqual(params['sort'],'desc');self.assertEqual(params['feed'],'iex')
        self.assertEqual(result.index.tolist(),list(index[::-1][:2]))
        self.assertEqual(result.attrs['data_feed'],'iex')

    def test_unsupported_feed_request_never_retries_with_implicit_feed(self):
        engine=PreBreakoutEngine.__new__(PreBreakoutEngine);engine.alpaca=Mock()
        engine.alpaca.get_bars.side_effect=TypeError('unsupported client')
        with self.assertRaises(PreBreakoutDataError):
            engine._fetch_bars('TEST',timeframe='5Min',limit=60,lookback_days=10)
        engine.alpaca.get_bars.assert_called_once()
        for call in engine.alpaca.get_bars.call_args_list:
            self.assertEqual(call.kwargs['feed'],'iex')
            self.assertEqual(call.kwargs['sort'],'desc')
