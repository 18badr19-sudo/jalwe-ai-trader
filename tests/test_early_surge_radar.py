import copy
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from early_surge_radar import enrich, inspect_bars, proof_valid, reserve, PROTOCOL
from full_market_scan import ScanResult
from scanner_engine import ScannerEngine, RankedCandidate
import test_research_audit as research_fixtures

NOW = datetime(2026,10,13,14,0,30,tzinfo=timezone.utc)


def bars():
    boundary = NOW.replace(second=0)
    result = [dict(t=(boundary-timedelta(minutes=i)).isoformat(),o=10.,h=10.01,l=9.99,c=10.,v=100.)
              for i in range(9,0,-1)]
    for i in range(6,9):
        opening=10.+(i-6)*.1
        result[i].update(o=opening,h=opening+.11,l=opening-.01,c=opening+.1,v=1000.)
    return result


def candidate(symbol='PUBLISH', *, confirmed=True):
    item=dict(symbol=symbol,price=10.3,tradable=True,rank_score=80.,
        raw=dict(feed='iex',latest_trade_at=(NOW-timedelta(seconds=10)).isoformat(),
                 minute_bar=dict(t=NOW.isoformat(),o=10.,h=10.3,l=10.,c=10.3,v=1000.)))
    if confirmed:
        item['raw']['early_surge']=inspect_bars(symbol,bars(),price=10.3,
            trade_at=item['raw']['latest_trade_at'],feed='iex',now=NOW)[0]
    return item


class EarlySurgeEvidenceTests(unittest.TestCase):
    def inspect(self, data, **kwargs):
        return inspect_bars('PUBLISH',data,price=kwargs.pop('price',10.3),
            trade_at=kwargs.pop('trade_at',(NOW-timedelta(seconds=10)).isoformat()),
            feed=kwargs.pop('feed','iex'),now=kwargs.pop('now',NOW),**kwargs)

    def test_real_completed_breakout_keeps_baseline_and_recent_evidence_separate(self):
        proof,reason=self.inspect(bars())
        self.assertEqual(reason,'CONFIRMED')
        self.assertAlmostEqual(proof['rise_3m_pct'],3.)
        self.assertEqual(proof['volume_acceleration'],10.)
        self.assertEqual(len(proof['bars']),9)
        self.assertFalse(proof['execution_authority'])
        self.assertEqual(proof['range_high'],10.01)

    def test_unfinished_future_and_old_rows_cannot_influence_the_fixed_window(self):
        original=self.inspect(bars())[0]
        current=dict(t=NOW.replace(second=0).isoformat(),o=10.,h=100.,l=1.,c=100.,v=100000.)
        future=dict(current,t=(NOW+timedelta(minutes=5)).isoformat())
        old=dict(current,t=(NOW-timedelta(minutes=30)).isoformat())
        self.assertEqual(self.inspect(bars()+[current,future,old])[0],original)

    def test_gaps_duplicate_invalid_ohlcv_and_nonfinite_rows_cannot_confirm(self):
        for kind in ('gap','duplicate','geometry','nan','zero','naive'):
            data=bars()
            if kind=='gap': data.pop(4)
            elif kind=='duplicate': data.append(copy.deepcopy(data[4]))
            elif kind=='geometry': data[4]['h']=9.
            elif kind=='nan': data[4]['v']=float('nan')
            elif kind=='zero': data[4]['v']=0
            else: data[4]['t']=data[4]['t'].replace('+00:00','')
            with self.subTest(kind=kind): self.assertIsNone(self.inspect(data)[0])

    def test_flat_low_activity_false_breakout_and_extended_move_do_not_qualify(self):
        variants=[]
        flat=bars()
        for row in flat: row.update(o=10.,h=10.01,l=9.99,c=10.,v=100.)
        variants.append(flat)
        quiet=bars()
        for row in quiet: row['v']=100.
        variants.append(quiet)
        failed=bars(); failed[-1].update(o=10.2,h=10.8,l=10.1,c=10.3);variants.append(failed)
        late=bars();late[-1].update(o=10.2,h=11.,l=10.1,c=11.);variants.append(late)
        for data in variants: self.assertIsNone(self.inspect(data)[0])
        for price in (10.,10.8): self.assertIsNone(self.inspect(bars(),price=price)[0])

    def test_trade_feed_session_and_window_timing_are_required(self):
        for kw in (dict(feed='delayed_sip'),dict(trade_at=(NOW-timedelta(minutes=3)).isoformat()),
                   dict(trade_at=(NOW+timedelta(seconds=1)).isoformat()),dict(now=NOW.replace(tzinfo=None)),
                   dict(now=NOW.replace(hour=12)),dict(window_end=(NOW+timedelta(minutes=1)).isoformat())):
            self.assertIsNone(self.inspect(bars(),**kw)[0])
        early=NOW.replace(hour=13,minute=35)
        self.assertEqual(self.inspect(bars(),now=early,trade_at=early.isoformat())[1],'WAITING_NINE_REGULAR_MINUTES')

    def test_read_crossing_minute_boundary_cannot_promote_inclusive_partial_bar(self):
        item=candidate(confirmed=False)
        payload={'bars':{'PUBLISH':bars()+[dict(t=NOW.replace(second=0).isoformat(),o=10.,h=50.,l=1.,c=50.,v=1e5)]}}
        session=Mock(); session.get.return_value=Mock(status_code=200)
        session.get.return_value.json.return_value=payload
        later=NOW+timedelta(seconds=35)
        output,audit=enrich([item],enabled=True,paper=True,feed='iex',api_key='fake',api_secret='private',
            session=session,now=Mock(side_effect=[NOW,later]))
        self.assertEqual(audit['confirmed'],1)
        proof=output[0]['raw']['early_surge']
        self.assertEqual(proof['window_end'],NOW.replace(second=0).isoformat())
        self.assertLess(proof['latest_close'],50.)
        self.assertTrue(proof_valid(output[0],later))
        self.assertFalse(proof_valid(output[0],NOW+timedelta(minutes=3)))


class EarlySurgeTransportPriorityTests(unittest.TestCase):
    def call(self,items,**kwargs):
        return enrich(items,enabled=kwargs.pop('enabled',True),paper=kwargs.pop('paper',True),
            feed=kwargs.pop('feed','iex'),api_key=kwargs.pop('api_key','fake'),api_secret='private',
            now=kwargs.pop('now',lambda:NOW),**kwargs)

    def test_disabled_nonpaper_delayed_feed_missing_credentials_and_closed_make_no_request(self):
        session=Mock()
        for kw in (dict(enabled=False),dict(paper=False),dict(feed='delayed_sip'),dict(api_key=''),
                   dict(now=lambda:NOW.replace(hour=22))):
            original=[candidate(confirmed=False)]
            result,audit=self.call(original,session=session,**kw)
            self.assertEqual(result,original)
        session.get.assert_not_called()

    def test_one_bounded_request_same_feed_no_pagination_or_secret_output(self):
        session=Mock();session.get.return_value=Mock(status_code=200)
        items=[candidate('S'+str(i),confirmed=False) for i in range(60)]
        session.get.return_value.json.return_value={'bars':{i['symbol']:bars() for i in sorted(items,key=lambda x:x['symbol'])[:40]}}
        result,audit=self.call(items,session=session)
        self.assertEqual(session.get.call_count,1)
        request=session.get.call_args
        self.assertEqual(request.args[0],'https://data.alpaca.markets/v2/stocks/bars')
        self.assertEqual(len(request.kwargs['params']['symbols'].split(',')),40)
        self.assertEqual(request.kwargs['params']['feed'],'iex')
        self.assertEqual(request.kwargs['timeout'],8)
        self.assertNotIn('private',str(audit))
        session.get.return_value.json.return_value={'bars':{},'next_page_token':'more'}
        output,audit=self.call(items,session=session)
        self.assertEqual(output,items)
        self.assertEqual(audit['state'],'READ_UNAVAILABLE')

    def test_missing_symbols_and_http_failure_keep_baseline_without_retry_or_feed_switch(self):
        session=Mock();session.get.return_value=Mock(status_code=200)
        session.get.return_value.json.return_value={'bars':{}}
        output,audit=self.call([candidate(confirmed=False)],session=session)
        self.assertEqual(audit['reasons'],{'MISSING_COMPLETED_MINUTES':1})
        self.assertIsNone(output[0]['raw']['early_surge'])
        session.get.reset_mock()
        import requests
        session.get.return_value=Mock(status_code=429)
        session.get.return_value.raise_for_status.side_effect=requests.HTTPError('secret key private')
        original=[candidate(confirmed=False)]
        output,audit=self.call(original,session=session)
        self.assertEqual(output,original)
        self.assertEqual(audit['http_status'],429)
        self.assertNotIn('secret',str(audit))
        session.get.assert_called_once()

    def test_bounded_seats_reach_beyond_old_top_n_and_do_not_change_scores(self):
        items=[candidate('BASE'+str(i),confirmed=False) for i in range(12)]
        items += [candidate('SURGE'+str(i)) for i in range(5)]
        original=copy.deepcopy(items)
        chosen,priority=reserve(items,limit=8,slot_cap=8,enabled=True,paper=True,now=NOW)
        self.assertEqual(len(chosen),8);self.assertEqual(len(priority),2)
        self.assertTrue(all(s.startswith('SURGE') for s in priority))
        self.assertEqual([x['symbol'] for x in chosen[2:]],[x['symbol'] for x in items[:6]])
        self.assertEqual(items,original)
        stale,_=reserve(items,limit=8,slot_cap=8,enabled=True,paper=True,now=NOW+timedelta(minutes=3))
        self.assertEqual(stale,items[:8])

    def test_nontradable_and_fabricated_metrics_cannot_override_recomputed_evidence(self):
        honest=candidate('AAA');fake=candidate('ZZZ')
        fake['raw']['early_surge']['volume_acceleration']=1e9
        blocked=candidate('BLOCKED');blocked['tradable']=False
        chosen,priority=reserve([fake,honest,blocked],limit=4,slot_cap=8,enabled=True,paper=True,now=NOW)
        self.assertEqual(priority,['AAA'])
        self.assertFalse(proof_valid(blocked,NOW))
        self.assertEqual(len(chosen),3)

    def test_incomplete_full_scan_never_requests_surge_bars(self):
        engine=ScannerEngine.__new__(ScannerEngine)
        engine._get_tradable_symbols=Mock(return_value={'PUBLISH'})
        engine.api_key='fake';engine.api_secret='private';engine.data_feed='iex'
        engine.base_url='https://paper-api.alpaca.markets';engine.scan_min_price=.5;engine.scan_max_price=100.
        scan=ScanResult(universe_count=1,failed_batches=1)
        with patch.dict('os.environ',{'APEX_EARLY_SURGE_ENABLED':'true'}), \
             patch('scanner_engine.scan_market',return_value=scan),patch('early_surge_radar.requests.Session') as session:
            result=engine._run_full_market_radar(40)
        self.assertEqual(result.status,'INCOMPLETE');session.assert_not_called()

    def test_scanner_reserved_seat_reaches_candidate_outside_old_ranking(self):
        engine=ScannerEngine.__new__(ScannerEngine)
        engine._get_tradable_symbols=Mock(return_value={'PUBLISH'})
        engine.api_key='fake';engine.api_secret='private';engine.data_feed='iex'
        engine.base_url='https://paper-api.alpaca.markets';engine.scan_min_price=.5;engine.scan_max_price=100.
        items=[candidate('BASE'+str(i),confirmed=False) for i in range(40)]+[candidate()]
        scan=ScanResult(universe_count=41,scanned_count=41,snapshot_count=41,complete=True,candidates=items)
        scan.audit={item['symbol']:{'symbol':item['symbol']} for item in items}
        with patch.dict('os.environ',{'APEX_EARLY_SURGE_ENABLED':'true'}), \
             patch('scanner_engine.scan_market',return_value=scan), \
             patch('early_surge_radar.enrich',return_value=(items,{'state':'OBSERVED','confirmed':1})), \
             patch('scanner_engine.datetime') as clock:
            clock.now.return_value=NOW
            result=engine._run_full_market_radar(40)
        self.assertEqual(result.symbols[0],'PUBLISH')
        self.assertEqual(len(result.symbols),40)
        self.assertEqual(scan.audit['PUBLISH']['reason'],'SELECTED_RADAR')
        self.assertTrue(scan.audit['PUBLISH']['early_surge_priority'])
        self.assertEqual(scan.audit['BASE39']['reason'],'OUTSIDE_RADAR_TOP_N')

    def test_deep_seats_preserve_confidence_risk_and_publication_gates(self):
        fixture=research_fixtures.ResearchAuditTests()
        engine=fixture.engine();engine.scanner.base_url='https://paper-api.alpaca.markets'
        radar=engine.scanner.run_radar.return_value
        extra=[RankedCandidate('SLOW1',price=2.),RankedCandidate('SLOW2',price=2.)]
        radar.ranked_candidates += extra
        scores=dict(LOWCONF=100,CRITICAL=95,YMT=90,SLOW1=88,SLOW2=86,PUBLISH=85,OUTSIDE=80)
        engine.prebreakout.analyze_symbol.side_effect=lambda symbol,**kw:SimpleNamespace(
            symbol=symbol,score=scores[symbol],data_confidence=50 if symbol=='LOWCONF' else 90)
        for c in radar.ranked_candidates:
            if c.symbol in ('PUBLISH','LOWCONF'):
                real=candidate(c.symbol);c.price=real['price'];c.tradable=True;c.raw=real['raw']
        with patch.dict('os.environ',{'APEX_EARLY_SURGE_ENABLED':'true'}), \
             patch('research_orchestrator.datetime') as clock:
            clock.now.return_value=NOW
            with self.assertLogs('apex.audit',level='INFO') as logs:
                result=engine.run_cycle(deep_research_top_n=4)
        rows=[]
        for message in logs.output:
            if 'APEX AUDIT ' in message:
                rows.extend(json.loads(message.split('APEX AUDIT ',1)[1])['rows'])
        self.assertEqual(result.deep_research_count,4)
        self.assertEqual(result.published_count,1)
        self.assertEqual([p.symbol for p in engine.jalwe_bridge.publish_shortlist.call_args.args[0]],['PUBLISH'])
        self.assertFalse(result.shortlist[0].order_execution_enabled)
        self.assertEqual(result.shortlist[0].metadata['early_surge']['protocol'],PROTOCOL)
        self.assertTrue(any(r['symbol']=='PUBLISH' and r.get('early_surge_priority') for r in rows))
        self.assertTrue(any(r['symbol']=='LOWCONF' and r['reason']=='PRE_CONFIDENCE_BELOW_MIN' for r in rows))
        self.assertTrue(any(r['symbol']=='CRITICAL' and r['reason']=='CRITICAL_RESEARCH_RISK' for r in rows))


if __name__=='__main__':
    unittest.main()
