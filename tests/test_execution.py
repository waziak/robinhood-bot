from conftest import make_proposal
from trader.models import OrderState
from trader.risk_engine import EMERGENCY_HALT


def approve(env, p=None):
    p = p or make_proposal()
    d = env.risk.evaluate(p, env.data.get_quote(p.symbol), env.data.get_candles(p.symbol), env.account(), [], True,
                          0.0, env.clock.now())
    assert d.approved, d.reason
    return p, d


def test_fill_opens_position_with_actual_fill(env):
    p, d = approve(env)
    pos = env.execution.open_position(p, d)
    assert pos.status == 'open' and pos.quantity == d.quantity and pos.entry_price == d.limit_price
    assert env.broker.positions['SPY'] == d.quantity


def test_refused_order_creates_no_position(env):
    env.broker.behavior['buy'] = 'refuse'
    p, d = approve(env)
    assert env.execution.open_position(p, d) is None
    assert env.store.open_positions() == []


def test_rejected_after_ack_creates_no_position(env):
    env.broker.behavior['buy'] = 'reject_after_ack'
    p, d = approve(env)
    assert env.execution.open_position(p, d) is None and env.store.open_positions() == []


def test_timeout_but_filled_is_located_not_resubmitted(env):
    env.broker.behavior['buy'] = 'timeout_filled'
    p, d = approve(env)
    pos = env.execution.open_position(p, d)
    assert env.broker.submits == 1
    assert pos is not None and pos.quantity == d.quantity
    assert not env.store.get_flag(EMERGENCY_HALT)[0]


def test_timeout_unverifiable_halts_and_never_retries(env):
    env.broker.behavior['buy'] = 'timeout_missing'
    p, d = approve(env)
    assert env.execution.open_position(p, d) is None
    assert env.broker.submits == 1
    assert env.store.get_flag(EMERGENCY_HALT)[0]
    assert [x.status for x in env.store.open_positions()] == ['pending_entry']


def test_partial_fill_cancels_remainder_and_tracks_filled_qty(env):
    env.broker.behavior['buy'] = 'partial'
    p, d = approve(env)
    pos = env.execution.open_position(p, d)
    assert abs(pos.quantity - d.quantity / 2) < 1e-9
    assert env.store.open_orders() == []


def test_resting_order_cancelled_without_position(env):
    env.broker.behavior['buy'] = 'rest'
    p, d = approve(env)
    assert env.execution.open_position(p, d) is None
    assert all(o.state == OrderState.CANCELLED for o in env.broker.orders.values())


def test_unconfirmed_cancel_halts(env):
    env.broker.behavior['buy'] = 'rest'
    env.broker.cancel_confirms = False
    p, d = approve(env)
    env.execution.open_position(p, d)
    assert env.store.get_flag(EMERGENCY_HALT)[0]


def test_duplicate_entry_prevented(env):
    p, d = approve(env)
    env.execution.open_position(p, d)
    assert env.execution.open_position(p, d) is None
    assert env.broker.submits == 1


def test_rejected_exit_keeps_position_and_halts_after_repeats(env):
    p, d = approve(env)
    pos = env.execution.open_position(p, d)
    env.broker.behavior['sell'] = 'refuse'
    for _ in range(3):
        assert env.execution.close_position(pos, 'stop', 99.0) is False
        pos = env.store.open_positions()[0]
        assert pos.status == 'open' and pos.quantity == d.quantity
    assert env.store.get_flag(EMERGENCY_HALT)[0]


def test_successful_exit_books_realized_pnl(env):
    p, d = approve(env)
    pos = env.execution.open_position(p, d)
    assert env.execution.close_position(pos, 'target', 102.0)
    done = env.store.closed_positions_since(0)[0]
    expected_exit = round(102.0 * (1 - env.cfg.max_order_price_deviation), 2)
    assert abs(done.realized_pnl - (expected_exit - pos.entry_price) * d.quantity) < 1e-9
    assert env.broker.get_positions() == {}


def test_emergency_halt_blocks_all_orders(env):
    p, d = approve(env)
    pos = env.execution.open_position(p, d)
    env.risk.emergency_halt('manual')
    n = env.broker.submits
    assert env.execution.close_position(pos, 'stop', 99.0) is False
    assert env.execution.open_position(make_proposal(symbol='BTC', entry=60000, stop=59000, target=62500), d) is None
    assert env.broker.submits == n


def test_status_outage_during_wait_does_not_fabricate_fill(env):
    env.broker.behavior['buy'] = 'rest'
    env.broker.status_error = True
    env.broker.cancel_confirms = False
    p, d = approve(env)
    assert env.execution.open_position(p, d) is None
    assert env.store.get_flag(EMERGENCY_HALT)[0]
