import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from datetime import datetime, timezone

import pandas as pd

from pre_breakout_engine import PreBreakoutEngine, PreBreakoutDataError


class PrebreakoutIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.engine=PreBreakoutEngine.__new__(PreBreakoutEngine)

    def frame(self):
        index=pd.date_range('2026-10-13T18:30:00Z',periods=20,freq='5min')
        previous=pd.DataFrame(dict(open=100.,high=101.,low=99.,close=100.,volume=10000.),index=index)
        today=pd.DataFrame(dict(open=[10.],high=[11.],low=[9.],close=[10.],volume=[100.]),
                           index=pd.to_datetime(['2026-10-14T13:30:00Z']))
        return pd.concat([previous,today])

    def test_first_bar_of_new_session_has_no_previous_day_vwap_weight(self):
        result=self.engine._session_vwap(self.frame())
        self.assertEqual(len(result),1)
        self.assertEqual(result.iloc[-1],10.)

    def test_session_vwap_is_invariant_to_the_index_display_timezone(self):
        frame=self.frame(); result=self.engine._session_vwap(frame.tz_convert('Asia/Tokyo'))
        self.assertEqual(len(result),1);self.assertEqual(result.iloc[-1],10.)

    def test_first_bar_cannot_claim_a_same_session_vwap_reclaim(self):
        metrics=self.engine._calculate_metrics(self.frame(),intraday=True)
        self.assertEqual(metrics['vwap'],10.)
        self.assertFalse(metrics['vwap_reclaimed'])

    def test_bad_ohlcv_cannot_be_silently_used_or_dropped_from_evidence(self):
        for column,value in (('close',float('inf')),('low',-1.),('volume',0.),
                             ('high',1.),('close',float('nan')),('volume',True)):
            frame=self.frame().astype(object);frame.iloc[-1,frame.columns.get_loc(column)]=value
            with self.subTest(column=column,value=value), self.assertRaises(PreBreakoutDataError):
                self.engine._normalize_dataframe(frame,'TEST')

    def test_same_timestamp_disputes_are_rejected_for_every_timeframe(self):
        frame=self.frame(); frame=pd.concat([frame,frame.iloc[[-1]]])
        with self.assertRaises(PreBreakoutDataError):
            self.engine._normalize_dataframe(frame,'TEST')

    def test_all_intraday_timeframes_exclude_unfinished_source_bars(self):
        now=datetime(2026,10,14,18,28,tzinfo=timezone.utc)
        for timeframe,minutes,last in (('5Min',5,'18:20'),('30Min',30,'17:30'),('1Hour',60,'17:00')):
            completed=pd.Timestamp('2026-10-14T'+last+':00Z')
            index=pd.DatetimeIndex([completed-pd.Timedelta(minutes=minutes),completed,
                                   completed+pd.Timedelta(minutes=minutes)])
            frame=pd.DataFrame(dict(open=10.,high=11.,low=9.,close=10.,volume=100.),index=index)
            self.engine.alpaca=Mock();self.engine.alpaca.get_bars.return_value=SimpleNamespace(df=frame)
            with self.subTest(timeframe=timeframe),patch('pre_breakout_engine.datetime') as clock:
                clock.now.return_value=now
                result=self.engine._fetch_bars('TEST',timeframe=timeframe,limit=60,lookback_days=10)
            self.assertEqual(result.index[-1],completed)

    def test_unzoned_intraday_timestamps_cannot_establish_completion(self):
        frame=self.frame().tz_localize(None)
        self.engine.alpaca=Mock();self.engine.alpaca.get_bars.return_value=SimpleNamespace(df=frame)
        with self.assertRaises(PreBreakoutDataError):
            self.engine._fetch_bars('TEST',timeframe='30Min',limit=60,lookback_days=10)

    def test_excluded_old_and_unfinished_rows_cannot_contaminate_completed_window(self):
        index=pd.to_datetime(['2026-10-14T17:00:00Z','2026-10-14T18:15:00Z',
                              '2026-10-14T18:20:00Z','2026-10-14T18:25:00Z'])
        frame=pd.DataFrame(dict(open=10.,high=11.,low=9.,close=10.,volume=100.),index=index)
        frame.loc[index[0],'volume']=float('nan');frame.loc[index[-1],'volume']=0.
        self.engine.alpaca=Mock();self.engine.alpaca.get_bars.return_value=SimpleNamespace(df=frame)
        with patch('pre_breakout_engine.datetime') as clock:
            clock.now.return_value=datetime(2026,10,14,18,28,tzinfo=timezone.utc)
            result=self.engine._fetch_bars('TEST',timeframe='5Min',limit=2,lookback_days=10)
        self.assertEqual(result.index.tolist(),list(index[1:3]))

    def test_duplicate_at_trim_boundary_cannot_be_hidden_by_limit(self):
        frame=self.frame();frame=pd.concat([frame,frame.iloc[[-1]]])
        self.engine.alpaca=Mock();self.engine.alpaca.get_bars.return_value=SimpleNamespace(df=frame)
        with self.assertRaises(PreBreakoutDataError):
            self.engine._fetch_bars('TEST',timeframe='5Min',limit=1,lookback_days=10)
