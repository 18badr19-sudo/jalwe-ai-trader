import copy
from datetime import timedelta
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch,Mock

import prior_day_apex_priority as priority
from scanner_engine import ScannerEngine,RankedCandidate
from full_market_scan import ScanResult
from test_prior_day_bus import packet,NOW
import test_research_audit as fixtures


def candidate(symbol):
    return dict(symbol=symbol,price=10.,tradable=True,rank_score=1.,raw=dict(feed='iex',latest_trade_at=NOW.isoformat()))


class PriorDayApexTests(unittest.TestCase):
    def test_reservations_are_bounded_and_keep_native_scores_and_early_seats(self):
        p=packet(tuple('P'+str(i) for i in range(8)))
        items=[candidate('N'+str(i)) for i in range(40)]+[candidate(s['symbol']) for s in p['signals']]
        original=copy.deepcopy(items)
        with patch.object(priority,'load',return_value=(p,{'state':'READY'})),patch.object(priority,'events'):
            selected,audit=priority.reserve(items,items[:40],limit=40,slots=4,now=NOW,paper=True,trace_key='scan')
        self.assertEqual(len(selected),40); self.assertEqual(len(audit['priority_symbols']),4)
        self.assertEqual([s['symbol'] for s in selected[4:12]],[s['symbol'] for s in items[:8]])
        self.assertTrue(all(s['rank_score']==1 for s in selected))
        self.assertEqual(items,original)
        self.assertTrue(all(s['raw']['prior_day_signal']['signal']['signal_id'] for s in selected[:4]))

    def test_rotation_gives_more_than_the_same_first_candidates_a_turn(self):
        p=packet(tuple('P'+str(i) for i in range(8))); items=[candidate(s['symbol']) for s in p['signals']]
        with patch.object(priority,'load',return_value=(p,{})),patch.object(priority,'events'):
            first,a=priority.reserve(items,items[:8],limit=40,slots=4,now=NOW,paper=True)
            for c in items: c['raw']['latest_trade_at']=(NOW+timedelta(minutes=5)).isoformat()
            second,b=priority.reserve(items,items[:8],limit=40,slots=4,now=NOW+timedelta(minutes=5),paper=True)
        self.assertFalse(set(a['priority_symbols'])&set(b['priority_symbols']))

    def test_incomplete_scan_stale_trade_or_nontradable_cannot_receive_priority(self):
        p=packet(); items=[candidate('N'),candidate('MATCH')]; items[1]['raw']['latest_trade_at']=(NOW-timedelta(seconds=151)).isoformat()
        with patch.object(priority,'load',return_value=(p,{})),patch.object(priority,'events'):
            selected,a=priority.reserve(items,items[:1],limit=4,slots=1,now=NOW,paper=True)
            self.assertEqual(selected,items[:1]); self.assertEqual(a['priority_symbols'],[])
            items[1]['raw']['latest_trade_at']=NOW.isoformat(); items[1]['tradable']=False
            self.assertEqual(priority.reserve(items,items[:1],limit=4,slots=1,now=NOW,paper=True)[0],items[:1])
        with patch.object(priority,'load') as load:
            priority.reserve(items,items[:1],limit=4,slots=1,now=NOW,paper=True,complete=False)
            load.assert_not_called()

    def test_deep_reservation_only_permutates_preapproved_candidates(self):
        p=packet(); items=[(NS(**candidate('N'+str(i))),NS(score=99.)) for i in range(8)]
        items.append((NS(**candidate('MATCH')),NS(score=1.)))
        with patch.object(priority,'load',return_value=(p,{})),patch.object(priority,'events'):
            out,a=priority.reserve(items,items[:8],limit=8,slots=1,now=NOW,paper=True,stage='DEEP',
                candidate_of=lambda row:vars(row[0]))
        self.assertEqual(out[0][0].symbol,'MATCH'); self.assertEqual(out[0][1].score,1.)
        self.assertEqual(len(out),8)

    def test_native_quality_rejections_cannot_be_overridden_by_priority(self):
        engine=fixtures.ResearchAuditTests().engine()
        # The confidence/critical-quality filters still run normally when the
        # optional priority transport is unavailable or PAPER is not configured.
        result,rows=fixtures.ResearchAuditTests().run_and_rows(engine)
        self.assertIn(('LOWCONF','PRE_CONFIDENCE_BELOW_MIN'),{(r['symbol'],r['reason']) for r in rows})
        self.assertIn(('CRITICAL','CRITICAL_RESEARCH_RISK'),{(r['symbol'],r['reason']) for r in rows})
        self.assertEqual(result.published_count,1)

    def test_real_orchestrator_path_preserves_confidence_risk_and_correlated_trace(self):
        engine=fixtures.ResearchAuditTests().engine()
        engine.scanner.base_url='https://paper-api.alpaca.markets'
        p=packet(('LOWCONF','CRITICAL','OUTSIDE'))
        signals={s['symbol']:s for s in p['signals']}
        for c in engine.scanner.run_radar.return_value.ranked_candidates:
            c.tradable=True; c.raw={'latest_trade_at':NOW.isoformat()}
            if c.symbol in signals:
                c.raw['prior_day_signal']=dict(protocol=p['protocol'],session=p['session'],signal=signals[c.symbol])
        with patch.object(priority,'load',return_value=(p,{'state':'READY'})), \
             patch.object(priority,'events') as events, \
             patch('research_orchestrator.datetime',Mock(now=Mock(return_value=NOW))):
            result=engine.run_cycle(deep_research_top_n=8)
        self.assertEqual(result.published_count,1)
        traced=[row for call in events.call_args_list for row in call.args[0]]
        self.assertTrue(any(r['symbol']=='LOWCONF' and r['reason']=='PRE_CONFIDENCE_BELOW_MIN' for r in traced))
        self.assertTrue(any(r['symbol']=='CRITICAL' and r['reason']=='CRITICAL_RESEARCH_RISK' for r in traced))
