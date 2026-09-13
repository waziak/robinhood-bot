"""Supervised single-order broker integration test. Tests infrastructure, not profitability.

  venv/bin/python -m trader.broker_test --symbol SPY --side buy --dollars 1.00

Places AT MOST one order, of AT MOST $1, only after typed confirmation, then reconciles and exits.
The live broker object is created with order_budget=1, so a second order is refused even by accident.
"""
import argparse
import math
import time
import uuid

from trader import events as ev
from trader.agent import regular_session_open
from trader.broker import RobinhoodBroker
from trader.execution import WORKING, ExecutionEngine
from trader.models import Order, Position

MAX_DOLLARS = 1.00
CONFIRM_PHRASE = 'SUBMIT ONE ORDER'
PRICE_COLLAR = 0.002


class BrokerTestRefused(Exception):
    pass


def run_broker_test(symbol, side, dollars, *, cfg, store, events, risk, guard, api, data, auth_ok: bool,
                    clock=time.time, sleep=time.sleep, input_fn=input, print_fn=print, session_open=regular_session_open):
    symbol, side = symbol.upper().strip(), side.lower().strip()

    def refuse(msg):
        events.emit(ev.LIFECYCLE, 'broker-test refused', reason=msg, symbol=symbol, side=side, dollars=dollars)
        raise BrokerTestRefused(msg)

    if not (0 < dollars <= MAX_DOLLARS):
        refuse(f'dollar amount must be > 0 and <= ${MAX_DOLLARS:.2f}')
    if side not in ('buy', 'sell'):
        refuse('side must be buy or sell')
    if cfg.is_crypto(symbol):
        refuse('crypto is UNSUPPORTED_FOR_LIVE_AUTOMATION (cannot be pinned to the trading account)')
    if not auth_ok:
        refuse('credentials not verified — run `python -m trader.credentials login` first')
    halted, why = risk.is_emergency_halted()
    if halted:
        refuse(f'emergency halt engaged: {why}')
    if store.get_meta('broker_test').get('submitted'):
        refuse('a broker test order has already been recorded in this database; review it before running another')
    account = guard.verify()
    if not session_open(clock()):
        refuse('US regular trading session is not open')
    inst = api.instrument(symbol)
    if not isinstance(inst, dict) or inst.get('symbol') != symbol or not inst.get('tradeable') or inst.get('state') != 'active':
        refuse(f'{symbol} is not an active tradeable instrument')
    q = data.get_quote(symbol)
    if q.age(clock()) > cfg.stale_quote_seconds or q.spread_pct > cfg.maximum_spread:
        refuse(f'quote not usable (age {q.age(clock()):.0f}s, spread {q.spread_pct:.3%})')
    limit = round(q.ask * (1 + PRICE_COLLAR), 2) if side == 'buy' else round(q.bid * (1 - PRICE_COLLAR), 2)
    qty = math.floor(dollars / limit * 1e6) / 1e6
    if qty <= 0 or qty * limit > MAX_DOLLARS + 1e-9:
        refuse('computed quantity is zero or exceeds the $1 cap')
    broker = RobinhoodBroker(data, cfg, guard, api, order_budget=1)
    if side == 'sell' and broker.get_positions().get(symbol, 0.0) + 1e-9 < qty:
        refuse('not enough shares held in the trading account to sell')

    print_fn('\n'.join([
        '──────── SUPERVISED BROKER TEST ────────',
        f'Account:        ••••{account.last4} ({account.type})',
        f'Instrument:     {symbol} ({inst.get("simple_name") or inst.get("name") or ""})',
        f'Side:           {side.upper()}',
        f'Dollar amount:  ${dollars:.2f} (hard cap ${MAX_DOLLARS:.2f})',
        f'Est. quantity:  {qty:.6f} shares',
        f'Limit price:    ${limit:.2f} (bid {q.bid:.2f} / ask {q.ask:.2f}); order type LIMIT, good-for-day',
        f'Est. notional:  ${qty * limit:.4f}',
        'Emergency halt: off | Credentials: verified | Market: regular session open',
        'This submits EXACTLY ONE real order. Nothing else will be sent automatically.',
        '────────────────────────────────────────']))
    if input_fn(f'Type "{CONFIRM_PHRASE}" to proceed, anything else to abort: ').strip() != CONFIRM_PHRASE:
        events.emit(ev.LIFECYCLE, 'broker-test aborted by user', symbol=symbol)
        print_fn('Aborted. No order was sent.')
        return {'submitted': False}

    execution = ExecutionEngine(broker, store, events, risk, cfg, sleep=sleep, clock=clock)
    pos = None
    o = Order(Order.new_client_id(), symbol, side, qty, limit, purpose='broker_test', created_at=clock())
    if side == 'buy':
        pos = Position(str(uuid.uuid4()), symbol, 'broker_test', 0.0, 0.0, 0.0, 0.0, clock(), 'supervised broker test',
                       status='pending_entry', intended_entry=limit, entry_order_id=o.client_id)
        o.position_id = pos.position_id
        store.upsert_position(pos)
    store.upsert_order(o)
    store.set_meta('broker_test', {'submitted': True, 'client_id': o.client_id, 'symbol': symbol, 'side': side})
    o = execution._send(o)
    if o.state in WORKING:
        o = execution._track(o, cfg.order_ack_timeout_seconds)
    if pos is not None:
        execution.settle_entry(pos, o)

    try:
        broker_qty = broker.get_positions().get(symbol, 0.0)
        working = [w for w in broker.get_open_orders() if w.ref_id == o.client_id or w.broker_id == o.broker_id]
        recon = {'broker_position_qty': broker_qty, 'working_orders_for_this_test': len(working)}
    except Exception as x:
        recon = {'error': f'{type(x).__name__}: {str(x)[:120]}'}
    result = {'submitted': True, 'state': o.state, 'filled_qty': o.filled_qty, 'avg_fill_price': o.avg_fill_price,
              'broker_order_id_present': bool(o.broker_id), 'error': o.error, **recon}
    store.set_meta('broker_test', {**result, 'client_id': o.client_id, 'symbol': symbol, 'side': side})
    events.emit(ev.LIFECYCLE, 'broker-test complete', **result)
    print_fn(f'Result: {result}')
    if o.state == 'unknown':
        print_fn('ORDER STATE UNKNOWN — check the Robinhood app for this order before doing anything else.')
    return result


def main():
    from trader import credentials
    from trader.accounts import AccountGuard
    from trader.broker import RobinhoodApi
    from trader.events import EventLog
    from trader.market_data import RobinhoodMarketData
    from trader.risk_config import load_risk_config
    from trader.risk_engine import RiskEngine
    from trader.store import Store

    ap = argparse.ArgumentParser()
    ap.add_argument('--symbol', required=True)
    ap.add_argument('--side', default='buy', choices=('buy', 'sell'))
    ap.add_argument('--dollars', type=float, default=1.00)
    ap.add_argument('--db', default='data/trader.db')
    a = ap.parse_args()
    cfg, store = load_risk_config(), Store(a.db)
    events = EventLog(store)
    risk = RiskEngine(cfg, store, events)
    auth_ok = credentials.resume(credentials.KeychainStore())
    store.set_meta('auth', {'ok': auth_ok, 'source': 'keychain'})
    api = RobinhoodApi()
    try:
        run_broker_test(a.symbol, a.side, a.dollars, cfg=cfg, store=store, events=events, risk=risk,
                        guard=AccountGuard(api.account_list), api=api, data=RobinhoodMarketData(cfg), auth_ok=auth_ok)
    except BrokerTestRefused as e:
        raise SystemExit(f'Refused: {e}')


if __name__ == '__main__':
    main()
