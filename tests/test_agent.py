import time

import pytest

from conftest import make_proposal
from trader.agent import Agent
from trader.broker import BrokerRefused, PaperBroker, RobinhoodBroker
from trader.events import redact
from trader.market_data import DataError, RobinhoodMarketData, StaleDataError, check_freshness
from trader.models import Order, OrderState, Position, Quote
from trader.reporting import classify, collect, daily_report
from trader.risk_engine import EMERGENCY_HALT, STOP_NEW_TRADES


def agent(env, mode='paper'):
    return Agent(env.cfg, env.store, env.events, env.data, env.broker, env.risk, env.execution, mode,
                 clock=env.clock.now, sleep=env.clock.sleep)


def test_startup_halts_on_unknown_broker_position(env):
    env.broker.positions['AAPL'] = 1.0
    env.data.set('AAPL', 199.9, 200.0)
    a = agent(env)
    assert a.startup()
    assert env.store.get_flag(EMERGENCY_HALT)[0] and not a.trading_enabled


def test_restart_recovers_filled_pending_entry_without_new_order(env):
    pos = Position('p1', 'SPY', 'trend_pullback', 0.0, 0.0, 99, 102.5, time.time(), 'x', status='pending_entry')
    env.store.upsert_position(pos)
    o = Order('c1', 'SPY', 'buy', 0.05, 100.3, state=OrderState.SUBMITTED, broker_id='b1', purpose='entry', position_id='p1')
    env.store.upsert_order(o)
    env.broker.behavior['buy'] = 'fill'
    env.broker.submit_limit_order('c1', 'SPY', 'buy', 0.05, 100.3)
    submits = env.broker.submits
    a = agent(env)
    assert a.startup()
    [p] = env.store.open_positions()
    assert p.status == 'open' and p.quantity == 0.05
    assert env.broker.submits == submits
    assert not env.store.get_flag(EMERGENCY_HALT)[0]


def test_restart_with_exit_in_flight_reverts_to_open_and_pauses(env):
    env.store.upsert_position(Position('p1', 'SPY', 's', 0.05, 100, 99, 102, time.time(), 'x', status='closing'))
    env.broker.positions['SPY'] = 0.05
    agent(env).startup()
    assert env.store.open_positions()[0].status == 'open'
    assert env.store.get_flag(STOP_NEW_TRADES)[0]


def test_untracked_open_order_at_broker_halts(env):
    env.broker.behavior['buy'] = 'rest'
    env.broker.submit_limit_order('x', 'SPY', 'buy', 0.01, 90.0)
    agent(env).startup()
    assert env.store.get_flag(EMERGENCY_HALT)[0]


def test_startup_with_stock_only_universe_does_not_block_trading(env):
    from dataclasses import replace
    a = agent(env)
    a.cfg = replace(env.cfg, universe=('SPY',), crypto_symbols=())
    assert a.startup()
    assert not env.store.get_flag(STOP_NEW_TRADES)[0] and a.trading_enabled


def test_duplicate_instance_refused(env):
    assert env.store.acquire_lock('other-instance')
    assert agent(env).startup() is False


def test_monitor_exits_on_stop(env):
    env.store.upsert_position(Position('p1', 'SPY', 's', 0.05, 100, 99.5, 102, env.clock.now(), 'x'))
    env.broker.positions['SPY'] = 0.05
    env.data.set('SPY', 99.0, 99.02)
    a = agent(env)
    a.startup()
    a.monitor_positions()
    assert env.store.closed_positions_since(0)[0].exit_reason == 'stop'


def test_unpriceable_position_pauses_new_trades(env):
    env.store.upsert_position(Position('p1', 'BTC', 's', 0.0001, 60000, 59000, 62000, env.clock.now(), 'x'))
    env.data.fail.add('BTC')
    a = agent(env)
    for _ in range(7):
        a.monitor_positions()
        env.clock.sleep(60)
    assert env.store.get_flag(STOP_NEW_TRADES)[0]


def test_unverified_account_means_no_trade(env):
    a = agent(env)
    a.startup()
    env.broker.account_error = True
    a.cycle()
    last = env.store.last_event('LIFECYCLE')
    assert last['decision'] == 'NO_TRADE' and 'account' in last['reason']


def test_stale_candles_detected(env):
    q = Quote('BTC', 1, 1.01, 1, env.clock.now())
    old = env.data.get_candles('BTC')
    for c in old:
        c.ts -= 7200
    with pytest.raises(StaleDataError):
        check_freshness(q, old, env.cfg, True, env.clock.now())


class BadRH:
    def get_quotes(self, s, info=None):
        return {'AAPL': [None], 'HALT': [{'trading_halted': True, 'bid_price': '1', 'ask_price': '1', 'last_trade_price': '1'}],
                'BAD': [{'bid_price': 'nan?', 'ask_price': None}]}.get(s, [None])

    def get_crypto_quote(self, s, info=None):
        return 'error string'


@pytest.mark.parametrize('sym', ['NOSUCHTICKER', 'HALT', 'BTC'])
def test_malformed_invalid_or_halted_quotes_raise(env, sym):
    md = RobinhoodMarketData(env.cfg, BadRH())
    with pytest.raises(DataError):
        md.get_quote(sym)


def test_malformed_numeric_quote_raises(env):
    with pytest.raises((DataError, ValueError)):
        RobinhoodMarketData(env.cfg, BadRH()).get_quote('BAD')


def test_live_broker_refuses_crypto_and_disabled_live(env):
    b = RobinhoodBroker(env.data, env.cfg, '554664508', rh=object())
    with pytest.raises(BrokerRefused):
        b.submit_limit_order('c', 'BTC', 'buy', 0.001, 60000)
    with pytest.raises(BrokerRefused):
        b.submit_limit_order('c', 'SPY', 'buy', 0.01, 100)


def test_paper_broker_models_costs_and_refuses_overspend(env):
    pb = PaperBroker(env.data, env.cfg, 10.0)
    with pytest.raises(BrokerRefused):
        pb.submit_limit_order('c', 'SPY', 'buy', 1.0, 101.0)
    oid = pb.submit_limit_order('c', 'SPY', 'buy', 0.05, 101.0)
    st = pb.get_order_status(oid)
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
    text = daily_report(env.store, env.cfg, 0)
    assert 'ACCOUNT' in text and 'LESSONS' in text
    assert classify(collect(env.store, 0, time.time() + 10), env.cfg)[0] == 'B'
