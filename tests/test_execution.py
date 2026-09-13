from dataclasses import replace

from conftest import make_proposal
from trader.execution import ExecutionEngine
from trader.models import BrokerOrderStatus, Order, OrderState, Position
from trader.risk_engine import EMERGENCY_HALT, STOP_NEW_TRADES


def approve(env, p=None):
    p = p or make_proposal()
    d = env.risk.evaluate(p, env.data.get_quote(p.symbol), env.data.get_candles(p.symbol), env.account(), [], True,
                          0.0, env.clock.now())
    assert d.approved, d.reason
    return p, d


def opened(env):
    p, d = approve(env)
    pos = env.execution.open_position(p, d)
    assert pos is not None and pos.status == 'open'
    return pos


def halted(env):
    return env.store.get_flag(EMERGENCY_HALT)[0]


def paused(env):
    return env.store.get_flag(STOP_NEW_TRADES)[0]


# ── entries ────────────────────────────────────────────────────────────────
def test_fill_opens_position_with_actual_fill(env):
    p, d = approve(env)
    pos = env.execution.open_position(p, d)
    assert pos.status == 'open' and pos.quantity == d.quantity and pos.entry_price == d.limit_price
    assert env.broker.positions['SPY'] == d.quantity and pos.entry_order_id


def test_refused_or_rejected_entry_creates_no_position(env):
    for behavior in ('refuse', 'reject_after_ack'):
        env.broker.behavior['buy'] = behavior
        p, d = approve(env)
        assert env.execution.open_position(p, d) is None
        assert env.store.open_positions() == []


def test_entry_timeout_after_receipt_is_located_not_resubmitted(env):
    env.broker.behavior['buy'] = 'timeout_after_receipt'
    p, d = approve(env)
    pos = env.execution.open_position(p, d)
    assert env.broker.submits == 1 and pos.status == 'open' and pos.quantity == d.quantity
    assert not paused(env) and not halted(env)


def test_entry_timeout_before_receipt_stays_unknown_then_resolves_after_grace(env):
    env.broker.behavior['buy'] = 'timeout_before_receipt'
    p, d = approve(env)
    assert env.execution.open_position(p, d) is None
    [pos] = env.store.open_positions()
    assert pos.status == 'pending_entry' and env.store.get_order(pos.entry_order_id).state == OrderState.UNKNOWN
    assert paused(env) and not halted(env) and env.broker.submits == 1
    env.clock.sleep(env.cfg.unknown_order_grace_seconds + 1)
    assert env.execution.resolve_entry(env.store.open_positions()[0]) is None
    assert env.store.open_positions() == [] and env.broker.submits == 1
    assert env.store.get_order(pos.entry_order_id).state == OrderState.REJECTED


def test_partial_entry_cancels_remainder(env):
    env.broker.behavior['buy'] = 'partial'
    p, d = approve(env)
    pos = env.execution.open_position(p, d)
    assert abs(pos.quantity - d.quantity / 2) < 1e-9 and env.store.open_orders() == []


def test_unconfirmed_cancel_is_unknown_and_pauses_entries(env):
    env.broker.behavior['buy'] = 'rest'
    env.broker.cancel_confirms = False
    p, d = approve(env)
    assert env.execution.open_position(p, d) is None
    assert paused(env) and not halted(env)
    assert env.store.open_positions()[0].status == 'pending_entry'


def test_duplicate_entry_and_blocked_entry_prevented(env):
    p, d = approve(env)
    env.execution.open_position(p, d)
    assert env.execution.open_position(p, d) is None and env.broker.submits == 1
    env.risk.stop_new_trades('test')
    btc = make_proposal(symbol='BTC', entry=60000, stop=59000, target=62500)
    assert env.execution.open_position(btc, d) is None and env.broker.submits == 1


def test_account_verification_failure_at_order_time_halts(env):
    env.broker.behavior['buy'] = 'account_error'
    p, d = approve(env)
    assert env.execution.open_position(p, d) is None
    assert halted(env)


# ── exits: a position stays open until broker fills prove otherwise ─────────
def test_sell_timeout_before_receipt(env):
    pos = opened(env)
    env.broker.behavior['sell'] = 'timeout_before_receipt'
    assert env.execution.request_exit(pos, 'stop', 99.0) == 'pending'
    [p] = env.store.open_positions()
    assert p.status == 'exit_pending' and p.quantity == pos.quantity
    assert env.store.get_order(p.exit_order_id).state == OrderState.UNKNOWN
    for _ in range(3):  # repeated exit requests must not create duplicate sells
        assert env.execution.request_exit(env.store.open_positions()[0], 'stop', 99.0) == 'pending'
    assert env.broker.submits == 2
    env.clock.sleep(env.cfg.unknown_order_grace_seconds + 1)
    assert env.execution.request_exit(env.store.open_positions()[0], 'stop', 99.0) == 'retained'
    p = env.store.open_positions()[0]
    assert p.status == 'open' and env.broker.positions['SPY'] == pos.quantity
    env.broker.behavior['sell'] = 'fill'
    assert env.execution.request_exit(p, 'stop', 99.0) == 'closed'
    assert env.broker.submits == 3 and env.broker.get_positions() == {}


def test_sell_timeout_after_receipt_is_located_and_closed_once(env):
    pos = opened(env)
    env.broker.behavior['sell'] = 'timeout_after_receipt'
    assert env.execution.request_exit(pos, 'stop', 99.0) == 'closed'
    assert env.broker.submits == 2 and env.broker.get_positions() == {}
    assert env.store.closed_positions_since(0)[0].exit_reason == 'stop'


def test_partial_sell_keeps_remainder_open(env):
    pos = opened(env)
    original_qty = pos.quantity
    env.broker.behavior['sell'] = 'partial'
    assert env.execution.request_exit(pos, 'target', 102.0) == 'partial'
    [p] = env.store.open_positions()
    assert p.status == 'open' and abs(p.quantity - original_qty / 2) < 1e-9
    assert abs(env.broker.positions['SPY'] - p.quantity) < 1e-9 and p.realized_pnl != 0


def test_rejected_sell_retains_position_and_pauses_after_repeats(env):
    pos = opened(env)
    for behavior in ('refuse', 'reject_after_ack', 'refuse'):
        env.broker.behavior['sell'] = behavior
        assert env.execution.request_exit(env.store.open_positions()[0], 'stop', 99.0) == 'retained'
        p = env.store.open_positions()[0]
        assert p.status == 'open' and p.quantity == pos.quantity
    assert paused(env) and not halted(env)


def test_process_crash_during_exit_order_reached_broker(env):
    pos = opened(env)
    o = Order(Order.new_client_id(), 'SPY', 'sell', pos.quantity, 99.7, purpose='exit:stop', position_id=pos.position_id,
              created_at=env.clock.now(), state=OrderState.SUBMITTING, submitted_at=env.clock.now())
    pos.status, pos.exit_order_id = 'exit_pending', o.client_id
    env.store.upsert_order(o)
    env.store.upsert_position(pos)
    env.broker.submit_limit_order(o.client_id, 'SPY', 'sell', pos.quantity, 99.7)  # it did reach the broker
    restarted = ExecutionEngine(env.broker, env.store, env.events, env.risk, env.cfg, sleep=env.clock.sleep, clock=env.clock.now)
    assert restarted.reconcile_exit(env.store.open_positions()[0]) == 'closed'
    assert env.store.open_positions() == []


def test_process_crash_before_exit_was_sent(env):
    pos = opened(env)
    o = Order(Order.new_client_id(), 'SPY', 'sell', pos.quantity, 99.7, purpose='exit:stop', position_id=pos.position_id,
              created_at=env.clock.now())
    pos.status, pos.exit_order_id = 'exit_pending', o.client_id
    env.store.upsert_order(o)
    env.store.upsert_position(pos)
    assert env.execution.reconcile_exit(env.store.open_positions()[0]) == 'retained'
    p = env.store.open_positions()[0]
    assert p.status == 'open' and env.store.get_order(o.client_id).state == OrderState.CANCELLED


def test_stale_broker_responses_are_ignored(env):
    o = Order('c1', 'SPY', 'sell', 1.0, 99.0, state=OrderState.FILLED, broker_id='b1', filled_qty=1.0,
              avg_fill_price=99.0, broker_updated_at=1000.0)
    stale = BrokerOrderStatus('b1', OrderState.ACKNOWLEDGED, 0.0, 0.0, updated_at=900.0, symbol='SPY', side='sell')
    assert env.execution._apply(o, stale) is False and o.state == OrderState.FILLED and o.filled_qty == 1.0
    working = Order('c2', 'SPY', 'sell', 1.0, 99.0, state=OrderState.PARTIALLY_FILLED, broker_id='b2', filled_qty=0.5,
                    broker_updated_at=1000.0)
    shrunk = BrokerOrderStatus('b2', OrderState.PARTIALLY_FILLED, 0.2, 99.0, updated_at=1001.0)
    older = BrokerOrderStatus('b2', OrderState.FILLED, 1.0, 99.0, updated_at=999.0)
    assert not env.execution._apply(working, shrunk) and not env.execution._apply(working, older)
    assert working.filled_qty == 0.5


def test_stale_report_during_tracking_does_not_regress_filled_exit(env):
    pos = opened(env)
    env.broker.behavior['sell'] = 'rest'
    env.broker.stale_reports = 2
    outcome = env.execution.request_exit(pos, 'stop', 99.0)
    assert outcome in ('retained', 'pending')
    assert env.store.open_positions()[0].quantity == pos.quantity


def test_broker_holding_less_than_local_freezes_without_selling(env):
    pos = opened(env)
    env.broker.positions['SPY'] = pos.quantity / 3
    submits = env.broker.submits
    assert env.execution.request_exit(pos, 'stop', 99.0) == 'frozen'
    assert env.broker.submits == submits and paused(env)
    assert env.store.open_positions()[0].reconciliation == 'discrepancy'


def test_unverifiable_broker_position_retains_without_selling(env):
    pos = opened(env)
    env.broker.positions_error = True
    submits = env.broker.submits
    assert env.execution.request_exit(pos, 'stop', 99.0) == 'retained'
    assert env.broker.submits == submits and env.store.open_positions()[0].status == 'open'


def test_exits_allowed_when_entries_paused_and_during_halt_by_default(env):
    pos = opened(env)
    env.risk.stop_new_trades('daily loss')
    env.risk.emergency_halt('drawdown')
    assert env.execution.request_exit(pos, 'stop', 99.0) == 'closed'


def test_exits_blocked_during_halt_only_if_protective_exits_disabled(env):
    pos = opened(env)
    env.execution.risk.cfg = env.risk.cfg = replace(env.cfg, allow_protective_exits_during_halt=False)
    env.risk.emergency_halt('manual')
    assert env.execution.request_exit(pos, 'stop', 99.0) == 'blocked'


def test_successful_exit_books_realized_pnl(env):
    pos = opened(env)
    assert env.execution.request_exit(pos, 'target', 102.0) == 'closed'
    done = env.store.closed_positions_since(0)[0]
    expected_exit = round(102.0 * (1 - env.cfg.max_order_price_deviation), 2)
    assert abs(done.realized_pnl - (expected_exit - pos.entry_price) * pos.quantity) < 1e-9


def test_idealized_and_realistic_pnl_are_tracked_separately(env):
    p, d = approve(env)
    p.features['price'] = 99.995  # decision-time mid
    pos = env.execution.open_position(p, d)
    assert env.execution.request_exit(pos, 'target', 101.99, reference_price=102.0) == 'closed'
    done = env.store.closed_positions_since(0)[0]
    assert abs(done.idealized_pnl - (102.0 - 99.995) * d.quantity) < 1e-9
    assert done.realized_pnl < done.idealized_pnl  # fills pay spread + collar; realistic is what counts


def test_frozen_position_never_gets_automated_exit(env):
    pos = opened(env)
    pos.reconciliation = 'discrepancy'
    env.store.upsert_position(pos)
    assert env.execution.request_exit(pos, 'stop', 99.0) == 'frozen'
    assert isinstance(env.store.get_position(pos.position_id), Position)
