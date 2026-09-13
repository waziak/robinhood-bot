import time
import uuid
from dataclasses import replace

import pytest

from conftest import make_proposal
from trader.models import Position, Quote
from trader.risk_config import WEEK_1_VALIDATION_MODE, load_risk_config
from trader.risk_engine import EMERGENCY_HALT, STOP_NEW_TRADES, floor_to


def evaluate(e, p=None, quote=None, market_open=True, positions=None, account='default', unrealized=0.0):
    p = p or make_proposal()
    quote = quote or e.data.get_quote(p.symbol)
    acct = e.account() if account == 'default' else account
    return e.risk.evaluate(p, quote, e.data.get_candles(p.symbol), acct, positions or [], market_open, unrealized,
                           e.clock.now())


def closed(symbol, pnl, exit_time=None):
    t = exit_time or time.time()
    return Position(str(uuid.uuid4()), symbol, 'trend_pullback', 1, 100, 99, 102, t - 60, 'x', status='closed',
                    realized_pnl=pnl, exit_time=t)


def test_approved_trade_respects_all_size_limits(env):
    d = evaluate(env)
    assert d.approved, d.reason
    cfg = env.cfg
    assert d.max_loss <= cfg.max_risk_per_trade_dollars + 1e-9
    assert d.notional <= min(cfg.max_dollar_position, cfg.max_position_percent * env.account()['equity']) + 1e-9
    assert d.quantity == floor_to(d.quantity, 6)


def test_position_too_small_is_skipped(env):
    env.data.set('SPY', 99.99, 100.0)
    d = evaluate(env, make_proposal(stop=60.0, target=190.0, atr=20.0))
    assert not d.approved and 'too small' in d.reason


@pytest.mark.parametrize('kwargs,reason', [
    ({'score': 50}, 'score'),
    ({'target': 100.5}, 'reward/risk'),
    ({'stop': 100.5}, 'stop not below entry'),
    ({'symbol': 'TQQQ'}, 'universe'),
])
def test_bad_proposals_rejected(env, kwargs, reason):
    if kwargs.get('symbol') == 'TQQQ':
        env.data.set('TQQQ', 49.99, 50.0)
    d = evaluate(env, make_proposal(**kwargs))
    assert not d.approved and reason in d.reason


def test_stale_quote_rejected(env):
    q = Quote('SPY', 99.99, 100.0, 100.0, env.clock.now() - 120)
    assert 'stale' in evaluate(env, quote=q).reason


def test_wide_spread_rejected(env):
    q = Quote('SPY', 99.0, 100.0, 99.5, env.clock.now())
    assert 'spread' in evaluate(env, quote=q).reason


def test_stock_rejected_when_market_closed(env):
    assert 'market closed' in evaluate(env, market_open=False).reason


def test_unverified_account_rejected(env):
    assert 'not verified' in evaluate(env, account=None).reason


def test_no_averaging_down_and_max_positions(env):
    pos = Position('p1', 'SPY', 's', 0.05, 100, 99, 102, time.time(), 'x')
    assert 'already open' in evaluate(env, positions=[pos]).reason
    others = [Position(f'p{i}', f'X{i}', 's', 0.01, 100, 99, 102, time.time(), 'x') for i in range(2)]
    assert 'max open positions' in evaluate(env, positions=others).reason


def test_daily_loss_limit_blocks(env):
    from trader.risk_engine import utc_day_start
    exit_t = max(utc_day_start() + 1, time.time() - env.cfg.cooldown_after_loss_seconds - 60)
    env.store.upsert_position(closed('SPY', -1.05, exit_t))
    d = evaluate(env)
    assert not d.approved and 'daily loss' in d.reason


def test_unrealized_loss_counts_toward_daily_limit(env):
    assert 'daily loss' in evaluate(env, unrealized=-1.0).reason


def test_consecutive_losses_and_cooldown(env):
    env.store.upsert_position(closed('SPY', -0.05, time.time() - 7200))
    env.store.upsert_position(closed('SPY', -0.05, time.time() - 7100))
    env.store.upsert_position(closed('SPY', -0.05, time.time() - 7000))
    assert 'consecutive' in evaluate(env).reason


def test_cooldown_after_single_loss(env):
    env.store.upsert_position(closed('SPY', -0.05, time.time() - 60))
    assert 'cooldown' in evaluate(env).reason


def test_abnormal_volatility_rejected(env):
    candles = env.data.get_candles('SPY')
    candles[-1].high, candles[-1].low = 110.0, 90.0
    assert 'abnormal' in evaluate(env).reason


def test_insufficient_cash_caps_size(env):
    env.broker.cash = 0.5
    assert 'too small' in evaluate(env).reason


def test_emergency_halt_and_stop_new_trades_block(env):
    env.risk.stop_new_trades('test')
    assert 'stop new trades' in evaluate(env).reason
    env.store.set_flag(STOP_NEW_TRADES, False)
    env.risk.emergency_halt('test')
    assert 'emergency' in evaluate(env).reason


def test_kill_switches_trip_on_limits(env):
    env.store.record_equity(30.0, 30.0, 't')
    env.risk.check_portfolio_limits({'equity': 26.0, 'cash': 26.0}, unrealized_pnl=-1.2)
    assert env.store.get_flag(STOP_NEW_TRADES)[0]
    assert env.store.get_flag(EMERGENCY_HALT)[0]


def test_api_error_streak_stops_new_trades(env):
    for _ in range(env.cfg.max_api_error_streak):
        env.risk.record_api_result(False, 'x')
    assert env.store.get_flag(STOP_NEW_TRADES)[0]


def test_week1_config_cannot_be_loosened():
    with pytest.raises(ValueError):
        replace(WEEK_1_VALIDATION_MODE, max_daily_loss=50.0).validate()
    with pytest.raises(ValueError):
        replace(WEEK_1_VALIDATION_MODE, allow_margin=True).validate()
    with pytest.raises(ValueError):
        replace(WEEK_1_VALIDATION_MODE, universe=('SPY', 'TQQQ')).validate()


def test_live_requires_explicit_ack(tmp_path, monkeypatch):
    p = tmp_path / 'risk.json'
    p.write_text('{"live_trading_enabled": true}')
    monkeypatch.delenv('LIVE_TRADING_ACK', raising=False)
    assert not load_risk_config(str(p)).live_trading_enabled
    monkeypatch.setenv('LIVE_TRADING_ACK', 'I_ACCEPT_REAL_MONEY_RISK')
    assert load_risk_config(str(p)).live_trading_enabled


def test_unknown_config_keys_rejected(tmp_path):
    p = tmp_path / 'risk.json'
    p.write_text('{"max_dialy_loss": 1}')
    with pytest.raises(ValueError):
        load_risk_config(str(p))
