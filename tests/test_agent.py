import time
import uuid
from dataclasses import replace

import pytest

from conftest import ACCOUNTS, make_proposal
from trader.accounts import AccountGuard
from trader.agent import Agent
from trader.broker import BrokerRefused, PaperBroker
from trader.events import redact
from trader.market_data import DataError, RobinhoodMarketData, StaleDataError, check_freshness
from trader.models import Order, OrderState, Position, Quote
from trader.reporting import classify, collect, daily_report
from trader.risk_engine import EMERGENCY_HALT, STOP_NEW_TRADES


def agent(env, guard=None, cfg=None):
    return Agent(cfg or env.cfg, env.store, env.events, env.data, env.broker, env.risk, env.execution, 'paper',
                 clock=env.clock.now, sleep=env.clock.sleep, guard=guard)


def paused(env):
    return env.store.get_flag(STOP_NEW_TRADES)[0]


def halted(env):
    return env.store.get_flag(EMERGENCY_HALT)[0]


def local_open(env, symbol='SPY', qty=0.05, entry=100.0, stop=99.5, target=102.0, on_broker=True, **kw):
    p = Position(str(uuid.uuid4()), symbol, 'trend_pullback', qty, entry, stop, target, env.clock.now(), 'x', **kw)
    env.store.upsert_position(p)
    if on_broker:
        env.broker.positions[symbol] = env.broker.positions.get(symbol, 0) + qty
    return p


# ── reconciliation categories ──────────────────────────────────────────────
def test_clean_reconciliation_enables_trading(env):
    local_open(env)
    a = agent(env)
    assert a.startup() and a.trading_enabled
    assert env.store.get_meta('last_reconciliation')['clean'] and not paused(env)


def test_broker_position_without_local_record(env):
    env.broker.positions['AAPL'] = 1.0
    env.data.set('AAPL', 199.9, 200.0)
    agent(env).startup()
    [p] = env.store.open_positions()
    assert p.strategy == 'unmanaged' and p.reconciliation == 'discrepancy' and p.quantity == 1.0
    assert paused(env) and not halted(env)
    assert 'BROKER_POSITION_NO_LOCAL_POSITION' in env.store.get_meta('last_reconciliation')['summary']


def test_local_position_without_broker_position(env):
    local_open(env, on_broker=False)
    agent(env).startup()
    assert env.store.open_positions() == []
    [p] = env.store.closed_positions_since(0)
    assert p.pnl_verified == 0 and 'absent at broker' in p.exit_reason and paused(env)


def test_quantity_mismatch_adopts_broker_quantity_and_freezes(env):
    local_open(env, qty=0.05, on_broker=False)
    env.broker.positions['SPY'] = 0.03
    agent(env).startup()
    [p] = env.store.open_positions()
    assert p.quantity == 0.03 and p.reconciliation == 'discrepancy' and paused(env)


def test_unknown_order_pauses_entries(env):
    env.store.upsert_order(Order('lost-1', 'SPY', 'buy', 0.05, 100.3, state=OrderState.UNKNOWN,
                                 created_at=env.clock.now(), submitted_at=env.clock.now()))
    agent(env).startup()
    assert paused(env) and 'UNKNOWN_ORDER' in env.store.get_meta('last_reconciliation')['summary']


def test_unexpected_open_order_is_flagged_not_cancelled(env):
    env.broker.behavior['buy'] = 'rest'
    st = env.broker.submit_limit_order('someone-else', 'SPY', 'buy', 0.01, 90.0)
    agent(env).startup()
    assert paused(env) and env.broker.orders[st.broker_id].state == OrderState.ACKNOWLEDGED
    assert 'UNEXPECTED_OPEN_ORDER' in env.store.get_meta('last_reconciliation')['summary']


# ── restart recovery ───────────────────────────────────────────────────────
def test_restart_recovers_filled_pending_entry_without_new_order(env):
    pos = Position('p1', 'SPY', 'trend_pullback', 0.0, 0.0, 99, 102.5, env.clock.now(), 'x', status='pending_entry',
                   entry_order_id='c1')
    env.store.upsert_position(pos)
    env.store.upsert_order(Order('c1', 'SPY', 'buy', 0.05, 100.3, state=OrderState.SUBMITTING, purpose='entry',
                                 position_id='p1', created_at=env.clock.now(), submitted_at=env.clock.now()))
    env.broker.submit_limit_order('c1', 'SPY', 'buy', 0.05, 100.3)
    submits = env.broker.submits
    a = agent(env)
    assert a.startup()
    [p] = env.store.open_positions()
    assert p.status == 'open' and p.quantity == 0.05 and env.broker.submits == submits and not paused(env)


def test_restart_with_filled_exit_in_flight_closes(env):
    pos = local_open(env, status='exit_pending', exit_order_id='x1')
    env.store.upsert_order(Order('x1', 'SPY', 'sell', 0.05, 99.0, state=OrderState.SUBMITTING, purpose='exit:stop',
                                 position_id=pos.position_id, created_at=env.clock.now(), submitted_at=env.clock.now()))
    env.broker.submit_limit_order('x1', 'SPY', 'sell', 0.05, 99.0)
    agent(env).startup()
    assert env.store.open_positions() == [] and env.store.closed_positions_since(0)[0].exit_reason == 'stop'


def test_account_verification_failure_at_startup_halts(env):
    guard = AccountGuard(lambda: [a for a in ACCOUNTS if not a['account_number'].endswith('4508')], last4='4508')
    a = agent(env, guard=guard)
    assert a.startup() and not a.trading_enabled and halted(env)
    assert env.store.get_meta('account')['verified'] is False


def test_duplicate_instance_refused(env):
    assert env.store.acquire_lock('other-instance')
    assert agent(env).startup() is False


def test_startup_with_stock_only_universe_does_not_block_trading(env):
    a = agent(env, cfg=replace(env.cfg, universe=('SPY',), crypto_symbols=()))
    assert a.startup() and not paused(env) and a.trading_enabled


# ── position management is independent of entry permission ─────────────────
def _stop_hit(env):
    p = local_open(env, stop=99.5)
    env.data.set('SPY', 99.0, 99.02)
    return p


@pytest.mark.parametrize('block', ['stop_new_trades', 'daily_loss', 'losing_streak', 'emergency_halt', 'account_down'])
def test_stop_exit_still_executes_when_entries_are_blocked(env, block):
    a = agent(env)
    a.startup()
    p = _stop_hit(env)
    if block == 'stop_new_trades':
        env.risk.stop_new_trades('test')
    elif block in ('daily_loss', 'losing_streak'):
        n, pnl = (1, -1.5) if block == 'daily_loss' else (3, -0.01)
        for i in range(n):
            env.store.upsert_position(Position(f'l{i}', 'QQQ', 's', 1, 1, 1, 1, env.clock.now() - 90, 'x', status='closed',
                                               realized_pnl=pnl, exit_time=env.clock.now() - 60 + i))
    elif block == 'emergency_halt':
        env.risk.emergency_halt('drawdown')
    elif block == 'account_down':
        env.broker.account_error = True
    a.cycle()
    assert env.store.get_position(p.position_id).status == 'closed'
    assert env.store.last_event('LIFECYCLE')['decision'] == 'NO_TRADE'


def test_monitoring_updates_excursions_while_halted(env):
    a = agent(env)
    a.startup()
    p = local_open(env, stop=90.0, target=150.0)
    env.risk.emergency_halt('manual')
    env.data.set('SPY', 101.0, 101.02)
    a.cycle()
    assert env.store.get_position(p.position_id).mfe > 0


def test_frozen_or_unmanaged_positions_are_watched_but_never_auto_exited(env):
    a = agent(env)
    a.startup()
    p = local_open(env, stop=99.5, reconciliation='discrepancy')
    env.data.set('SPY', 99.0, 99.02)
    submits = env.broker.submits
    a.monitor_positions()
    assert env.store.get_position(p.position_id).status == 'open' and env.broker.submits == submits


def test_unpriceable_position_pauses_new_trades(env):
    local_open(env, symbol='BTC', qty=0.0001, entry=60000, stop=59000, target=62000)
    env.data.fail.add('BTC')
    a = agent(env)
    for _ in range(7):
        a.monitor_positions()
        env.clock.sleep(60)
    assert paused(env)


def test_periodic_reconciliation_catches_mid_session_discrepancy(env):
    a = agent(env)
    a.startup()
    assert not paused(env)
    env.broker.positions['MSFT'] = 2.0
    env.data.set('MSFT', 499.9, 500.0)
    env.clock.sleep(env.cfg.reconcile_interval_seconds + 1)
    a.cycle()
    assert paused(env) and any(p.symbol == 'MSFT' for p in env.store.open_positions())


# ── data / misc ────────────────────────────────────────────────────────────
def test_stale_candles_detected(env):
    q = Quote('BTC', 1, 1.01, 1, env.clock.now())
    old = env.data.get_candles('BTC')
    for c in old:
        c.ts -= 7200
    with pytest.raises(StaleDataError):
        check_freshness(q, old, env.cfg, True, env.clock.now())


class BadRH:
    def get_quotes(self, s, info=None):
        return {'HALT': [{'trading_halted': True, 'bid_price': '1', 'ask_price': '1', 'last_trade_price': '1'}],
                'BAD': [{'bid_price': 'nan?', 'ask_price': None}]}.get(s, [None])

    def get_crypto_quote(self, s, info=None):
        return 'error string'


@pytest.mark.parametrize('sym', ['NOSUCHTICKER', 'HALT', 'BTC'])
def test_malformed_invalid_or_halted_quotes_raise(env, sym):
    with pytest.raises(DataError):
        RobinhoodMarketData(env.cfg, BadRH()).get_quote(sym)


def test_malformed_numeric_quote_raises(env):
    with pytest.raises((DataError, ValueError)):
        RobinhoodMarketData(env.cfg, BadRH()).get_quote('BAD')


def test_paper_broker_models_costs_and_refuses_overspend(env):
    pb = PaperBroker(env.data, env.cfg, 10.0)
    with pytest.raises(BrokerRefused):
        pb.submit_limit_order('c', 'SPY', 'buy', 1.0, 101.0)
    st = pb.submit_limit_order('c', 'SPY', 'buy', 0.05, 101.0)
    assert st.state == OrderState.FILLED and st.avg_fill_price > 100.0
    with pytest.raises(BrokerRefused):
        pb.submit_limit_order('c', 'SPY', 'sell', 1.0, 90.0)


def test_redaction():
    out = redact({'authorization': 'Bearer abc.def', 'msg': 'account 554664508 url /accounts/5QR12345/ Bearer xyz'})
    assert out['authorization'] == '[REDACTED]'
    assert '554664508' not in out['msg'] and 'xyz' not in out['msg'] and '5QR12345' not in out['msg']


def test_reports_render_and_classify_small_sample_as_needs_data(env):
    env.store.record_equity(26.86, 26.86, 't')
    env.store.add_candidate(make_proposal(), 'rejected', 'score 50 < 70', {'regime': 'up'})
    assert 'LESSONS' in daily_report(env.store, env.cfg, 0)
    assert classify(collect(env.store, 0, time.time() + 10), env.cfg)[0] == 'B'
