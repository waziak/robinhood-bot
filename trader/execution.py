"""Execution engine: persisted intents, order state machine, reconcile-before-retry. Positions change only on
broker-confirmed fills. An order whose state cannot be verified trips EMERGENCY_HALT instead of being guessed."""
import time
import uuid

from trader import events as ev
from trader.broker import BrokerError, BrokerRefused
from trader.market_data import BrokerTimeout
from trader.models import Order, OrderState, Position

MAX_EXIT_FAILURES = 3


class ExecutionEngine:
    def __init__(self, broker, store, events, risk, cfg, sleep=time.sleep, clock=time.time):
        self.broker, self.store, self.events, self.risk, self.cfg = broker, store, events, risk, cfg
        self.sleep, self.clock = sleep, clock
        self.exit_failures = {}

    def _save(self, o: Order, msg: str = ''):
        self.store.upsert_order(o)
        self.events.emit(ev.ORDER_UPDATE, msg or o.state, client_id=o.client_id, broker_id=o.broker_id, symbol=o.symbol,
                         side=o.side, state=o.state, qty=o.quantity, filled=o.filled_qty, avg=o.avg_fill_price,
                         error=o.error)

    def _apply(self, o: Order, st) -> Order:
        o.state, o.filled_qty, o.avg_fill_price, o.fees = st.state, st.filled_qty, st.avg_fill_price, st.fees
        return o

    def _submit(self, o: Order) -> Order:
        """Persist first, then submit once. Never resubmits: on timeout the order is located, not retried."""
        if self.risk.is_emergency_halted()[0]:
            o.state, o.error = OrderState.REJECTED, 'emergency halt'
            self._save(o)
            return o
        self.store.upsert_order(o)
        self.events.emit(ev.ORDER_SUBMITTED, 'submitting', client_id=o.client_id, symbol=o.symbol, side=o.side,
                         qty=o.quantity, limit=o.limit_price, purpose=o.purpose, mode=self.broker.mode)
        try:
            o.broker_id = self.broker.submit_limit_order(o.client_id, o.symbol, o.side, o.quantity, o.limit_price)
            o.state = OrderState.SUBMITTED
            self.risk.record_api_result(True)
        except BrokerRefused as e:
            o.state, o.error = OrderState.REJECTED, str(e)
        except (BrokerTimeout, BrokerError, Exception) as e:
            o.state, o.error = OrderState.UNKNOWN, f'{type(e).__name__}: {e}'
            self.risk.record_api_result(False, 'submit')
            self._save(o, 'submit outcome unknown — reconciling')
            return self._locate_unknown(o)
        self._save(o)
        return o

    def _locate_unknown(self, o: Order) -> Order:
        for _ in range(3):
            self.sleep(2)
            try:
                st = self.broker.find_recent_order(o.symbol, o.side, o.quantity, o.created_at)
            except Exception as e:
                o.error = f'reconcile lookup failed: {e}'
                continue
            if st is None:
                continue
            o.broker_id = st.broker_id
            self._apply(o, st)
            self._save(o, 'located after unknown submit')
            return o
        self._save(o, 'order state unverifiable')
        self.risk.emergency_halt(f'order {o.client_id} ({o.side} {o.symbol}) state unknown after submit')
        return o

    def _await(self, o: Order, timeout: float) -> Order:
        deadline = self.clock() + timeout
        while o.state not in OrderState.TERMINAL and o.state != OrderState.UNKNOWN:
            try:
                st = self.broker.get_order_status(o.broker_id)
                self.risk.record_api_result(True)
                self._apply(o, st)
                self.store.upsert_order(o)
            except Exception as e:
                self.risk.record_api_result(False, 'order status')
                o.error = f'status: {e}'
            if o.state in OrderState.TERMINAL or self.clock() >= deadline:
                break
            self.sleep(1)
        if o.state not in OrderState.TERMINAL:
            o = self._cancel_and_confirm(o)
        self._save(o)
        return o

    def _cancel_and_confirm(self, o: Order) -> Order:
        try:
            self.broker.cancel_order(o.broker_id)
        except Exception as e:
            o.error = f'cancel failed: {e}'
        for _ in range(5):
            try:
                st = self.broker.get_order_status(o.broker_id)
                self._apply(o, st)
                if o.state in OrderState.TERMINAL:
                    return o
            except Exception as e:
                o.error = f'post-cancel status: {e}'
            self.sleep(1)
        o.state = OrderState.UNKNOWN
        self._save(o, 'cancel not confirmed')
        self.risk.emergency_halt(f'order {o.broker_id} could not be confirmed cancelled')
        return o

    # ── entries ────────────────────────────────────────────────────────────
    def open_position(self, proposal, decision, candidate_id=None):
        sym = proposal.symbol
        if any(p.symbol == sym for p in self.store.open_positions()) or any(o.symbol == sym for o in self.store.open_orders()):
            self.events.emit(ev.RISK_DECISION, 'duplicate entry prevented', symbol=sym)
            return None
        pos = Position(str(uuid.uuid4()), sym, proposal.strategy, 0.0, 0.0, proposal.stop, proposal.target, self.clock(),
                       proposal.reasoning, status='pending_entry', candidate_id=candidate_id, intended_entry=proposal.entry)
        self.store.upsert_position(pos)
        o = Order(Order.new_client_id(), sym, 'buy', decision.quantity, decision.limit_price, purpose='entry',
                  position_id=pos.position_id)
        o = self._submit(o)
        if o.state == OrderState.SUBMITTED:
            o = self._await(o, self.cfg.order_ack_timeout_seconds)
        return self._settle_entry(pos, o)

    def _settle_entry(self, pos: Position, o: Order):
        if o.filled_qty > 0 and o.state in (OrderState.FILLED, OrderState.CANCELLED, OrderState.EXPIRED):
            pos.quantity, pos.entry_price, pos.fees, pos.status = o.filled_qty, o.avg_fill_price, o.fees, 'open'
            pos.entry_time = self.clock()
            self.store.upsert_position(pos)
            self.events.emit(ev.POSITION_UPDATE, 'opened', position_id=pos.position_id, symbol=pos.symbol,
                             qty=pos.quantity, entry=pos.entry_price, stop=pos.stop, target=pos.target,
                             partial=o.state != OrderState.FILLED, slippage=pos.entry_price - pos.intended_entry)
            return pos
        if o.state == OrderState.UNKNOWN:
            return None  # stays pending_entry; startup reconciliation resolves it
        pos.status, pos.exit_reason = 'cancelled', f'entry {o.state}: {o.error}'
        self.store.upsert_position(pos)
        return None

    # ── exits ──────────────────────────────────────────────────────────────
    def close_position(self, pos: Position, reason: str, bid: float) -> bool:
        if self.risk.is_emergency_halted()[0]:
            return False
        limit = round(bid * (1 - self.cfg.max_order_price_deviation), 2)
        pos.status = 'closing'
        self.store.upsert_position(pos)
        o = Order(Order.new_client_id(), pos.symbol, 'sell', pos.quantity, limit, purpose=f'exit:{reason}',
                  position_id=pos.position_id)
        o = self._submit(o)
        if o.state == OrderState.SUBMITTED:
            o = self._await(o, self.cfg.order_ack_timeout_seconds)
        if o.state == OrderState.UNKNOWN:
            return False  # emergency halt already engaged; position stays 'closing' and is never forgotten

        filled = o.filled_qty
        if filled > 0:
            pnl = (o.avg_fill_price - pos.entry_price) * filled - o.fees
            entry_fee_share = pos.fees * (filled / pos.quantity) if pos.quantity else 0
            pos.realized_pnl += pnl - entry_fee_share
            pos.fees = pos.fees - entry_fee_share
            pos.quantity = round(pos.quantity - filled, 10)
        if pos.quantity <= 1e-9:
            pos.status, pos.exit_price, pos.exit_time, pos.exit_reason = 'closed', o.avg_fill_price, self.clock(), reason
            pos.quantity = filled
            self.store.upsert_position(pos)
            self.exit_failures.pop(pos.position_id, None)
            self.events.emit(ev.TRADE_EXIT, reason, position_id=pos.position_id, symbol=pos.symbol,
                             strategy=pos.strategy, exit=o.avg_fill_price, entry=pos.entry_price,
                             pnl=round(pos.realized_pnl, 4), mfe=pos.mfe, mae=pos.mae,
                             held_s=round(pos.exit_time - pos.entry_time))
            return True

        pos.status = 'open'
        self.store.upsert_position(pos)
        n = self.exit_failures.get(pos.position_id, 0) + 1
        self.exit_failures[pos.position_id] = n
        self.events.emit(ev.SYSTEM_ERROR, 'exit not completed; position retained', position_id=pos.position_id,
                         symbol=pos.symbol, remaining=pos.quantity, order_state=o.state, error=o.error, attempt=n)
        if n >= MAX_EXIT_FAILURES:
            self.risk.emergency_halt(f'{n} failed exit attempts on {pos.symbol}')
        return False
