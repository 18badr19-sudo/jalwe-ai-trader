"""Bounded PAPER-only seats for validated pre-open research packets."""
from datetime import datetime, timezone
import json
import logging

from full_market_scan import timestamp
from prior_day_priority_bus import load, events, valid_signal

logger=logging.getLogger(__name__)
RADAR_SLOTS,DEEP_SLOTS=4,1


def candidate(item):
    return item if isinstance(item,dict) else dict(symbol=item.symbol,price=item.price,
        tradable=item.tradable,raw=item.raw)


def reserve(items,baseline,*,limit,slots,now,paper,complete=True,candidate_of=candidate,stage='RADAR',trace_key=''):
    items=list(items); baseline=list(baseline)
    if not complete: return baseline,dict(state='INCOMPLETE_SCAN',priority_symbols=[])
    packet,audit=load(now,paper=paper)
    if packet is None: return baseline,dict(audit,priority_symbols=[])
    signals={s['symbol']:s for s in packet['signals']}
    eligible=[]; reasons={}
    for item in items:
        c=candidate_of(item); symbol=c['symbol']; signal=signals.get(symbol)
        if signal is None: continue
        trade=timestamp((c.get('raw') or {}).get('latest_trade_at'))
        if c.get('tradable') is not True or trade is None or not 0<=(now-trade).total_seconds()<=150:
            reasons[symbol]='STALE_OR_INELIGIBLE'; continue
        if not valid_signal(signal,packet['session']): continue
        proof=dict(protocol=packet['protocol'],packet_id=packet['packet_id'],session=packet['session'],
            frozen_at=packet['frozen_at'],signal=signal,scan_id=trace_key)
        if isinstance(item,dict):
            item={**item,'raw':{**(item.get('raw') or {}),'prior_day_signal':proof}}
        else:
            cobj=item[0] if isinstance(item,tuple) else item
            cobj.raw={**(cobj.raw or {}),'prior_day_signal':proof}
        eligible.append(item)
    cap=min(max(0,slots),max(0,int(limit)//4))
    offset=(int(now.timestamp())//300*max(1,cap))%len(eligible) if eligible else 0
    selected=(eligible[offset:]+eligible[:offset])[:cap]
    names={candidate_of(item)['symbol'] for item in selected}
    # Preserve existing early-surge reservations and native order behind these seats.
    replacement={candidate_of(item)['symbol']:item for item in eligible}
    ordered=selected+[replacement.get(candidate_of(item)['symbol'],item) for item in baseline
                      if candidate_of(item)['symbol'] not in names]
    ordered=ordered[:limit]
    if stage=='RADAR':
        observed={candidate_of(item)['symbol'] for item in items}
        rows=[]
        for symbol,signal in signals.items():
            reason=('RESERVED' if symbol in names else reasons.get(symbol,
                    'NOT_ELIGIBLE_SCANNER' if symbol not in observed else 'OUTSIDE_RESERVED_SEATS'))
            row=dict(signal_id=signal['signal_id'],symbol=symbol,stage='APEX_RADAR',reason=reason,
                     trace_key=trace_key,at=now.isoformat(),packet_id=packet['packet_id'])
            rows.append(row)
        events(rows)
    else:
        events([dict(signal_id=signals[candidate_of(item)['symbol']]['signal_id'],symbol=candidate_of(item)['symbol'],
            stage='APEX_DEEP',reason='RESERVED' if candidate_of(item)['symbol'] in names else 'NATIVE_OR_WAITING',
            trace_key=trace_key,at=now.isoformat()) for item in eligible])
    return ordered,dict(audit,priority_symbols=sorted(names),eligible=len(eligible),slots=cap,
                        stage=stage,execution_authority=False)


def stage_event(proof,stage,reason,trace_key,**values):
    if not isinstance(proof,dict) or not isinstance(proof.get('signal'),dict): return
    signal=proof['signal']
    if not valid_signal(signal,proof.get('session',{})): return
    row=dict(signal_id=signal['signal_id'],symbol=signal['symbol'],stage='APEX_'+stage,reason=reason,
             trace_key=trace_key,at=datetime.now(timezone.utc).isoformat(),**values)
    logger.info('PRIOR_DAY_SIGNAL_STAGE %s',json.dumps(row,sort_keys=True))
    events([row])
