"""Execution engine: persisted intents, monotonic order state machine, reconcile-before-retry.

Invariants:
- Every order is persisted as CREATED, then SUBMITTING, before any network call.
- A timeout or unexpected error produces UNKNOWN — never FILLED, never "failed". UNKNOWN orders are located at the
  broker by ref_id; they are never resubmitted.
- A position changes quantity only on broker-reported fills, and becomes CLOSED only when fills cover it.
- An exit in flight (exit_pending) blocks any second exit order for that position.
- Stale broker reports (state regressions, shrinking fills, older timestamps) are ignored.
"""
import time
import uuid

from trader import events as ev
from trader.accounts import AccountVerificationError
from trader.broker import BrokerRefused
from trader.models import Order, OrderState, Position

WORKING = (OrderState.SUBMITTED, OrderState.ACKNOWLEDGED, OrderState.PARTIALLY_FILLED)


class ExecutionEngine:
    def __init__(self, broker, store, events, risk, cfg, sleep=time.sleep, clock=time.time):
        self.broker, self.store, self.events, self.risk, self.cfg = broker, store, events, risk, cfg
        self.sleep, self.clock = sleep, clock

    # ── order plumbing ─────────────────────────────────────────────────────
    def _save(self, o: Order, msg: str = ''):
        self.store.upsert_order(o)
        self.events.emit(ev.ORDER_UPDATE, msg or o.state, client_id=o.client_id, broker_id=o.broker_id, symbol=o.symbol,
                         side=o.side, state=o.state, qty=o.quantity, filled=o.filled_qty, avg=o.avg_fill_price,
                         purpose=o.purpose, error=o.error)

    def _apply(self, o: Order, st) -> bool:
        if (st.symbol and st.symbol != o.symbol) or (st.side and st.side != o.side) or (
                st.ref_id and st.ref_id != o.client_id and (not o.broker_id or st.broker_id != o.broker_id)):
            self.events.emit(ev.SYSTEM_ERROR, 'broker report does not match order — ignored', client_id=o.client_id)
            return False
        stale = (OrderState.is_regression(o.state, st.state) or st.filled_qty + 1e-12 < o.filled_qty
                 or (st.updated_at and o.broker_updated_at and st.updated_at < o.broker_updated_at))
        if stale:
            self.events.emit(ev.ORDER_UPDATE, 'stale broker report ignored', client_id=o.client_id, have=o.state,
                             reported=st.state, have_filled=o.filled_qty, reported_filled=st.filled_qty)
            return False
        if st.filled_qty > o.quantity + 1e-9:
            self.risk.stop_new_trades(f'broker reports overfill on {o.symbol}: {st.filled_qty} > {o.quantity}')
        o.broker_id = o.broker_id or st.broker_id
        o.state, o.filled_qty, o.avg_fill_price, o.fees = st.state, st.filled_qty, st.avg_fill_price, st.fees
        o.broker_updated_at = st.updated_at or o.broker_updated_at
        return True

    def _send(self, o: Order) -> Order:
        o.state, o.submitted_at = OrderState.SUBMITTING, self.clock()
        self.store.upsert_order(o)
        self.events.emit(ev.ORDER_SUBMITTED, 'submitting', client_id=o.client_id, symbol=o.symbol, side=o.side,
                         qty=o.quantity, limit=o.limit_price, purpose=o.purpose, mode=self.broker.mode)
        try:
            st = self.broker.submit_limit_order(o.client_id, o.symbol, o.side, o.quantity, o.limit_price)
            self.risk.record_api_result(True)
        except BrokerRefused as e:
            o.state, o.error = OrderState.REJECTED, str(e)[:300]
            self._save(o, 'refused before reaching broker')
            return o
        except AccountVerificationError as e:
            o.state, o.error = OrderState.UNKNOWN if 'response' in str(e) else OrderState.REJECTED, str(e)[:300]
            self._save(o, 'account verification failed')
            self.risk.emergency_halt(f'account verification failed at order time: {e}')
            return o
        except Exception as e:
            o.state, o.error = OrderState.UNKNOWN, f'{type(e).__name__}: {str(e)[:200]}'
            self.risk.record_api_result(False, 'submit')
            self._save(o, 'submission outcome unknown — locating at broker, not retrying')
            o = self.resolve_unknown(o)
            if o.state == OrderState.UNKNOWN:
                self.risk.stop_new_trades(f'order {o.client_id[:8]} ({o.side} {o.symbol}) outcome unknown')
            return o
        o.broker_id, o.state = st.broker_id, OrderState.SUBMITTED
        self._apply(o, st)
        self._save(o)
        return o

    def resolve_unknown(self, o: Order, attempts: int = 3) -> Order:
        lookup_ok = False
        for i in range(attempts):
            try:
                st = (self.broker.get_order_status(o.broker_id) if o.broker_id
                      else self.broker.find_order_by_ref(o.client_id, o.symbol, o.side, o.created_at))
                lookup_ok = True
            except Exception as e:
                st, o.error = None, f'lookup failed: {type(e).__name__}'
            if st is not None:
                if o.state == OrderState.SUBMITTING:
                    o.state = OrderState.UNKNOWN
                self._apply(o, st)
                self._save(o, 'located at broker')
                return o
            if i < attempts - 1:
                self.sleep(2)
        age = self.clock() - (o.submitted_at or o.created_at)
        if lookup_ok and age >= self.cfg.unknown_order_grace_seconds and self._broker_position_unchanged(o):
            o.state = OrderState.REJECTED
            o.error = 'not received by broker: absent from order history after grace period, no working order, position unchanged'
            self._save(o, 'resolved as never received')
            return o
        o.state = OrderState.UNKNOWN
        self._save(o, 'order state still unknown')
        return o

    def _broker_position_unchanged(self, o: Order) -> bool:
        try:
            broker_qty = self.broker.get_positions().get(o.symbol, 0.0)
            working = self.broker.get_open_orders()
        except Exception:
            return False
        if any(w.ref_id == o.client_id or (o.broker_id and w.broker_id == o.broker_id) for w in working):
            return False
        local = sum(p.quantity for p in self.store.open_positions() if p.symbol == o.symbol and p.status in ('open', 'exit_pending'))
        return abs(broker_qty - local) <= 1e-6

    def _track(self, o: Order, timeout: float) -> Order:
        deadline = self.clock() + timeout
        while o.state in WORKING:
            try:
                self._apply(o, self.broker.get_order_status(o.broker_id))
                self.risk.record_api_result(True)
                self.store.upsert_order(o)
            except Exception as e:
                self.risk.record_api_result(False, 'order status')
                o.error = f'status: {type(e).__name__}'
            if o.state not in WORKING or self.clock() >= deadline:
                break
            self.sleep(1)
        if o.state in WORKING:
            o = self._cancel_and_confirm(o)
        self._save(o)
        return o

    def _cancel_and_confirm(self, o: Order) -> Order:
        try:
            self.broker.cancel_order(o.broker_id)
        except Exception as e:
            o.error = f'cancel failed: {type(e).__name__}'
        for _ in range(5):
            try:
                self._apply(o, self.broker.get_order_status(o.broker_id))
                if o.state in OrderState.TERMINAL:
                    return o
            except Exception as e:
                o.error = f'post-cancel status: {type(e).__name__}'
            self.sleep(1)
        o.state = OrderState.UNKNOWN
        self._save(o, 'cancel not confirmed')
        self.risk.stop_new_trades(f'order {o.client_id[:8]} on {o.symbol}: cancel not confirmed')
        return o

    def refresh_order(self, o: Order) -> Order:
        """Bring a persisted non-terminal order up to date. Used by reconciliation and pending exits/entries."""
        if o.state == OrderState.CREATED:
            o.state, o.error = OrderState.CANCELLED, 'never submitted (process stopped before send)'
            self._save(o)
        elif o.state in (OrderState.SUBMITTING, OrderState.UNKNOWN):
            o = self.resolve_unknown(o)
        elif o.state in WORKING:
            try:
                self._apply(o, self.broker.get_order_status(o.broker_id))
                self.store.upsert_order(o)
            except Exception as e:
                o.error = f'status: {type(e).__name__}'
                return o
            if o.state in WORKING and self.clock() - (o.submitted_at or o.created_at) > self.cfg.order_ack_timeout_seconds:
                o = self._cancel_and_confirm(o)
            self._save(o)
        return o

    # ── entries ────────────────────────────────────────────────────────────
    def open_position(self, proposal, decision, candidate_id=None):
        ok, why = self.risk.entries_allowed(self.clock())
        if not ok:
            self.events.emit(ev.RISK_DECISION, 'entry blocked at execution', symbol=proposal.symbol, reason=why)
            return None
        sym = proposal.symbol
        if any(p.symbol == sym for p in self.store.open_positions()) or any(o.symbol == sym for o in self.store.open_orders()):
            self.events.emit(ev.RISK_DECISION, 'duplicate entry prevented', symbol=sym)
            return None
        pos = Position(str(uuid.uuid4()), sym, proposal.strategy, 0.0, 0.0, proposal.stop, proposal.target, self.clock(),
                       proposal.reasoning, status='pending_entry', candidate_id=candidate_id,
                       intended_entry=proposal.entry, initial_stop=proposal.stop,
                       entry_reference=float(proposal.features.get('price') or proposal.entry))
        o = Order(Order.new_client_id(), sym, 'buy', decision.quantity, decision.limit_price, purpose='entry',
                  position_id=pos.position_id, created_at=self.clock())
        pos.entry_order_id = o.client_id
        self.store.upsert_position(pos)
        self.store.upsert_order(o)
        o = self._send(o)
        if o.state in WORKING:
            o = self._track(o, self.cfg.order_ack_timeout_seconds)
        return self.settle_entry(pos, o)

    def settle_entry(self, pos: Position, o: Order):
        if o.state in OrderState.TERMINAL and o.filled_qty > 0:
            pos.quantity, pos.entry_price, pos.fees, pos.status = o.filled_qty, o.avg_fill_price, o.fees, 'open'
            self.store.upsert_position(pos)
            self.events.emit(ev.POSITION_UPDATE, 'opened', position_id=pos.position_id, symbol=pos.symbol,
                             qty=pos.quantity, entry=pos.entry_price, stop=pos.stop, target=pos.target,
                             partial=o.state != OrderState.FILLED, slippage=round(pos.entry_price - pos.intended_entry, 6))
            return pos
        if o.state in OrderState.TERMINAL:
            pos.status, pos.exit_reason = 'cancelled', f'entry {o.state}: {o.error}'[:300]
        self.store.upsert_position(pos)
        return None

    def resolve_entry(self, pos: Position):
        o = self.store.get_order(pos.entry_order_id) if pos.entry_order_id else None
        if o is None:
            pos.status, pos.exit_reason = 'cancelled', 'no entry order on record'
            self.store.upsert_position(pos)
            return None
        return self.settle_entry(pos, self.refresh_order(o))

    # ── exits ──────────────────────────────────────────────────────────────
    def request_exit(self, pos: Position, reason: str, bid: float, reference_price: float = None) -> str:
        """Returns closed | partial | pending | retained | blocked | frozen. Never reports closed without fills."""
        if pos.status == 'open':
            pos.exit_reference = float(reference_price or bid)
        if pos.status == 'exit_pending':
            return self.reconcile_exit(pos)
        if pos.status != 'open':
            return 'blocked'
        if pos.reconciliation != 'ok':
            self.events.emit(ev.SYSTEM_ERROR, 'automated exit refused: position frozen by reconciliation discrepancy',
                             symbol=pos.symbol, position_id=pos.position_id)
            return 'frozen'
        ok, why = self.risk.exits_allowed()
        if not ok:
            self.events.emit(ev.RISK_DECISION, 'exit blocked', symbol=pos.symbol, reason=why)
            return 'blocked'
        try:
            broker_qty = self.broker.get_positions().get(pos.symbol, 0.0)
        except Exception as e:
            self.risk.record_api_result(False, 'positions before exit')
            self.events.emit(ev.SYSTEM_ERROR, 'cannot verify broker position before exit — will retry next cycle',
                             symbol=pos.symbol, error=type(e).__name__)
            return 'retained'
        if broker_qty + 1e-9 < pos.quantity:
            pos.reconciliation = 'discrepancy'
            self.store.upsert_position(pos)
            self.risk.stop_new_trades(f'{pos.symbol}: broker holds {broker_qty}, local expects {pos.quantity}')
            return 'frozen'
        o = Order(Order.new_client_id(), pos.symbol, 'sell', pos.quantity,
                  round(bid * (1 - self.cfg.max_order_price_deviation), 2), purpose=f'exit:{reason}',
                  position_id=pos.position_id, created_at=self.clock())
        pos.status, pos.exit_order_id, pos.exit_attempts = 'exit_pending', o.client_id, pos.exit_attempts + 1
        self.store.upsert_order(o)
        self.store.upsert_position(pos)
        o = self._send(o)
        if o.state in WORKING:
            o = self._track(o, self.cfg.order_ack_timeout_seconds)
        return self._finalize_exit(pos, o)

    def reconcile_exit(self, pos: Position) -> str:
        o = self.store.get_order(pos.exit_order_id) if pos.exit_order_id else None
        if o is None:
            pos.status, pos.exit_order_id = 'open', None
            self.store.upsert_position(pos)
            self.events.emit(ev.SYSTEM_ERROR, 'exit_pending position had no exit order; reverted to open', symbol=pos.symbol)
            return 'retained'
        return self._finalize_exit(pos, self.refresh_order(o))

    def _finalize_exit(self, pos: Position, o: Order) -> str:
        if o.state not in OrderState.TERMINAL:
            self.store.upsert_position(pos)
            return 'pending'
        reason = o.purpose.split(':', 1)[-1] if ':' in o.purpose else 'exit'
        filled = min(o.filled_qty, pos.quantity)
        if filled > 0:
            share = filled / pos.quantity
            entry_fee_share = pos.fees * share
            pos.realized_pnl += (o.avg_fill_price - pos.entry_price) * filled - o.fees - entry_fee_share
            if pos.entry_reference and pos.exit_reference:
                pos.idealized_pnl += (pos.exit_reference - pos.entry_reference) * filled
            pos.fees -= entry_fee_share
            pos.quantity = round(pos.quantity - filled, 10)
        pos.exit_order_id = None
        if pos.quantity <= 1e-9:
            pos.status, pos.quantity = 'closed', filled
            pos.exit_price, pos.exit_time, pos.exit_reason = o.avg_fill_price, self.clock(), reason
            self.store.upsert_position(pos)
            self.events.emit(ev.TRADE_EXIT, reason, position_id=pos.position_id, symbol=pos.symbol, strategy=pos.strategy,
                             exit=o.avg_fill_price, entry=pos.entry_price, pnl=round(pos.realized_pnl, 4), mfe=pos.mfe,
                             mae=pos.mae, held_s=round(pos.exit_time - pos.entry_time))
            return 'closed'
        pos.status = 'open'
        self.store.upsert_position(pos)
        if filled > 0:
            self.events.emit(ev.POSITION_UPDATE, 'partial exit; remainder stays open', symbol=pos.symbol,
                             sold=filled, remaining=pos.quantity)
            return 'partial'
        self.events.emit(ev.SYSTEM_ERROR, 'exit not filled; position remains open', symbol=pos.symbol,
                         order_state=o.state, error=o.error, attempt=pos.exit_attempts)
        if pos.exit_attempts >= self.cfg.max_exit_attempts_before_alert:
            self.risk.stop_new_trades(f'{pos.exit_attempts} unfilled exit attempts on {pos.symbol}')
        return 'retained'
