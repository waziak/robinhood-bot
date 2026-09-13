"""Broker interface. Only trader.execution may call submit/cancel. Strategies never import this module."""
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from trader.accounts import ASSET_CLASS_SUPPORT, SUPPORTED, AccountGuard, AccountVerificationError
from trader.market_data import _parse_ts, call_with_timeout
from trader.models import BrokerOrderStatus, OrderState

ORDERS_URL = 'https://api.robinhood.com/orders/'


class BrokerError(Exception):
    pass


class BrokerRefused(BrokerError):
    """Deterministic refusal before anything reached the broker. Safe: no order exists."""


class Broker:
    mode = 'abstract'

    def get_account(self) -> dict: ...                       # {'equity','cash','buying_power'}
    def get_positions(self) -> dict: ...                     # {symbol: qty}
    def get_open_orders(self) -> list: ...                   # [BrokerOrderStatus]
    def submit_limit_order(self, client_id, symbol, side, qty, limit) -> BrokerOrderStatus: ...
    def get_order_status(self, broker_id) -> BrokerOrderStatus: ...
    def find_order_by_ref(self, ref_id, symbol, side, since) -> Optional[BrokerOrderStatus]: ...
    def cancel_order(self, broker_id) -> None: ...


class PaperBroker(Broker):
    """Simulated fills against real bid/ask: buys pay ask + slippage, sells receive bid - slippage, fees charged.
    Marketable limit orders fill immediately; others rest until a later quote crosses."""
    mode = 'paper'

    def __init__(self, data, cfg, starting_cash: float, clock=time.time):
        self.data, self.cfg, self.clock = data, cfg, clock
        self.cash = float(starting_cash)
        self.positions = {}
        self.orders = {}

    def get_account(self) -> dict:
        equity = self.cash
        for sym, qty in self.positions.items():
            if qty > 1e-12:
                equity += qty * self.data.get_quote(sym).bid
        return {'equity': round(equity, 6), 'cash': round(self.cash, 6), 'buying_power': round(self.cash, 6)}

    def get_positions(self) -> dict:
        return {s: q for s, q in self.positions.items() if q > 1e-12}

    def get_open_orders(self) -> list:
        return [o for o in self.orders.values() if o.state not in OrderState.TERMINAL]

    def submit_limit_order(self, client_id, symbol, side, qty, limit) -> BrokerOrderStatus:
        if qty <= 0 or limit <= 0 or side not in ('buy', 'sell'):
            raise BrokerRefused('invalid order parameters')
        if side == 'buy' and qty * limit * (1 + self.cfg.fee_rate) > self.cash + 1e-9:
            raise BrokerRefused('insufficient paper cash')
        if side == 'sell' and qty > self.positions.get(symbol, 0) + 1e-9:
            raise BrokerRefused('selling more than held')
        st = BrokerOrderStatus(f'paper-{uuid.uuid4()}', OrderState.ACKNOWLEDGED, 0.0, 0.0, 0.0, 'confirmed', symbol, side,
                               qty, client_id, 'paper', self.clock(), self.clock())
        st.limit = limit
        self.orders[st.broker_id] = st
        self._try_fill(st)
        return st

    def _try_fill(self, st):
        if st.state in OrderState.TERMINAL:
            return
        q = self.data.get_quote(st.symbol)
        slip = self.cfg.slippage_rate
        if st.side == 'buy':
            px = q.ask * (1 + slip)
            if px > st.limit:
                return
            fee = st.quantity * px * self.cfg.fee_rate
            if st.quantity * px + fee > self.cash + 1e-9:
                st.state, st.raw_state = OrderState.REJECTED, 'insufficient_cash'
                return
            self.cash -= st.quantity * px + fee
            self.positions[st.symbol] = self.positions.get(st.symbol, 0) + st.quantity
        else:
            px = q.bid * (1 - slip)
            if px < st.limit:
                return
            if st.quantity > self.positions.get(st.symbol, 0) + 1e-9:
                st.state, st.raw_state = OrderState.REJECTED, 'insufficient_position'
                return
            fee = st.quantity * px * self.cfg.fee_rate
            self.cash += st.quantity * px - fee
            self.positions[st.symbol] -= st.quantity
        st.state, st.filled_qty, st.avg_fill_price, st.fees, st.raw_state = OrderState.FILLED, st.quantity, px, fee, 'filled'
        st.updated_at = self.clock()

    def get_order_status(self, broker_id) -> BrokerOrderStatus:
        st = self.orders.get(broker_id)
        if st is None:
            raise BrokerError('unknown order id')
        self._try_fill(st)
        return st

    def find_order_by_ref(self, ref_id, symbol, side, since):
        return next((st for st in self.orders.values() if st.ref_id == ref_id), None)

    def cancel_order(self, broker_id):
        st = self.orders.get(broker_id)
        if st and st.state not in OrderState.TERMINAL:
            st.state, st.raw_state, st.updated_at = OrderState.CANCELLED, 'cancelled', self.clock()


_RH_STATE = {
    'queued': OrderState.SUBMITTED, 'unconfirmed': OrderState.SUBMITTED, 'new': OrderState.SUBMITTED,
    'confirmed': OrderState.ACKNOWLEDGED, 'partially_filled': OrderState.PARTIALLY_FILLED,
    'filled': OrderState.FILLED, 'cancelled': OrderState.CANCELLED, 'canceled': OrderState.CANCELLED,
    'rejected': OrderState.REJECTED, 'failed': OrderState.REJECTED, 'voided': OrderState.CANCELLED,
    'expired': OrderState.EXPIRED,
}


def status_from_rh(o: dict, symbol: str = '') -> BrokerOrderStatus:
    execs = o.get('executions') or []
    fees = sum(float(e.get('fees') or 0) for e in execs) if execs else float(o.get('fees') or 0)
    return BrokerOrderStatus(
        str(o['id']), _RH_STATE.get(str(o.get('state', '')), OrderState.UNKNOWN),
        float(o.get('cumulative_quantity') or 0), float(o.get('average_price') or 0), fees, str(o.get('state', '')),
        symbol or str(o.get('symbol') or ''), str(o.get('side') or ''), float(o.get('quantity') or 0),
        str(o.get('ref_id') or ''), str(o.get('account') or ''), _parse_ts(o.get('updated_at')), _parse_ts(o.get('created_at')))


class RobinhoodApi:
    """Thin, timeout-wrapped adapter over robin_stocks. Exists so the live broker can be tested without a network."""

    def __init__(self, rh=None):
        if rh is None:
            import robin_stocks.robinhood as rh
        self.rh = rh

    def account_list(self):
        return call_with_timeout(self.rh.load_account_profile, dataType='results', timeout=10)

    def account(self, n):
        return call_with_timeout(self.rh.load_account_profile, account_number=n, timeout=10)

    def portfolio(self, n):
        return call_with_timeout(self.rh.load_portfolio_profile, account_number=n, timeout=10)

    def positions(self, n):
        return call_with_timeout(self.rh.get_open_stock_positions, account_number=n, timeout=15)

    def open_orders(self, n):
        return call_with_timeout(self.rh.get_all_open_stock_orders, account_number=n, timeout=15)

    def orders_since(self, n, start_date):
        return call_with_timeout(self.rh.get_all_stock_orders, account_number=n, start_date=start_date, timeout=20)

    def order_info(self, order_id):
        return call_with_timeout(self.rh.get_stock_order_info, order_id, timeout=10)

    def cancel(self, order_id):
        return call_with_timeout(self.rh.cancel_stock_order, order_id, timeout=10)

    def instrument(self, symbol):
        rows = call_with_timeout(self.rh.get_instruments_by_symbols, symbol, timeout=10)
        return rows[0] if rows else None

    def symbol_by_url(self, url):
        return call_with_timeout(self.rh.get_symbol_by_url, url, timeout=8)

    def post_order(self, payload):
        from robin_stocks.robinhood.helper import request_post
        return call_with_timeout(request_post, ORDERS_URL, payload, jsonify_data=True, timeout=30)


class RobinhoodBroker(Broker):
    """Live equities only, limit orders only, every call scoped to the verified account.

    The order payload is built here rather than via robin_stocks.order(), because order() resolves the account URL
    with a separate network call that returns None on failure — which would submit an order with no account and let
    Robinhood route it to the login's default account. ref_id is our persisted client id (broker-side idempotency)."""
    mode = 'live'

    def __init__(self, data, cfg, guard: AccountGuard, api: RobinhoodApi, order_budget: Optional[int] = None):
        self.data, self.cfg, self.guard, self.api = data, cfg, guard, api
        self.order_budget = order_budget
        self._symbols = {}

    def _acct(self, max_age: float = 60.0) -> str:
        return self.guard.require('equity', max_age=max_age).account_number

    def _owned(self, record: dict, n: str) -> bool:
        return f'/accounts/{n}/' in str(record.get('account', '')) or str(record.get('account_number', '')) == n

    def _symbol(self, instrument_url: str) -> str:
        if instrument_url not in self._symbols:
            self._symbols[instrument_url] = self.api.symbol_by_url(instrument_url)
        return self._symbols[instrument_url]

    def get_account(self) -> dict:
        n = self._acct()
        prof, port = self.api.account(n), self.api.portfolio(n)
        if not isinstance(prof, dict) or not isinstance(port, dict):
            raise BrokerError('account profile unavailable')
        if str(prof.get('account_number')) != n:
            raise AccountVerificationError('broker returned a different account than verified')
        if prof.get('type') != 'cash':
            raise AccountVerificationError('trading account is not a cash account')
        equity = port.get('equity') or port.get('extended_hours_equity')
        if equity in (None, ''):
            raise BrokerError('equity unavailable')
        return {'equity': float(equity), 'cash': float(prof.get('cash') or 0),
                'buying_power': float(prof.get('buying_power') or 0)}

    def get_positions(self) -> dict:
        n = self._acct()
        rows = self.api.positions(n)
        if not isinstance(rows, list):
            raise BrokerError('positions unavailable')
        out = {}
        for r in rows:
            if not self._owned(r, n):
                raise AccountVerificationError('position row belongs to a different account')
            qty = float(r.get('quantity') or 0)
            if qty > 0:
                sym = self._symbol(r['instrument'])
                out[sym] = out.get(sym, 0.0) + qty
        return out

    def get_open_orders(self) -> list:
        n = self._acct()
        rows = self.api.open_orders(n)
        if not isinstance(rows, list):
            raise BrokerError('open orders unavailable')
        out = []
        for o in rows:
            if not self._owned(o, n):
                raise AccountVerificationError('open order belongs to a different account')
            out.append(status_from_rh(o, self._symbol(o['instrument'])))
        return out

    def submit_limit_order(self, client_id, symbol, side, qty, limit) -> BrokerOrderStatus:
        asset = 'crypto' if self.cfg.is_crypto(symbol) else 'equity'
        support, why = ASSET_CLASS_SUPPORT[asset]
        if support != SUPPORTED:
            raise BrokerRefused(f'{asset}: UNSUPPORTED_FOR_LIVE_AUTOMATION — {why}')
        if self.order_budget is None and not self.cfg.live_trading_enabled:
            raise BrokerRefused('live trading disabled')
        if self.order_budget is not None and self.order_budget <= 0:
            raise BrokerRefused('supervised order budget exhausted — no further orders may be placed by this process')
        if side not in ('buy', 'sell') or qty <= 0 or limit <= 0:
            raise BrokerRefused('invalid order parameters')
        n = self._acct(max_age=0)  # fresh broker round-trip immediately before every live order
        inst = self.api.instrument(symbol)
        if not isinstance(inst, dict) or inst.get('symbol') != symbol or not inst.get('tradeable') or inst.get('state') != 'active':
            raise BrokerRefused(f'{symbol} is not an active tradeable instrument')
        payload = {
            'account': f'https://api.robinhood.com/accounts/{n}/', 'instrument': inst['url'], 'symbol': symbol,
            'price': f'{limit:.2f}', 'quantity': f'{qty:.6f}', 'ref_id': client_id, 'type': 'limit',
            'time_in_force': 'gfd', 'trigger': 'immediate', 'side': side, 'market_hours': 'regular_hours',
            'extended_hours': False, 'order_form_version': 4,
        }
        if self.order_budget is not None:
            self.order_budget -= 1  # consumed even if the call times out: a timed-out order may exist
        resp = self.api.post_order(payload)
        if not isinstance(resp, dict) or not resp.get('id'):
            detail = resp.get('detail') if isinstance(resp, dict) else type(resp).__name__
            raise BrokerRefused(f'order not accepted: {str(detail)[:160]}')
        self.guard.check_order_account(resp)
        return status_from_rh(resp, symbol)

    def get_order_status(self, broker_id) -> BrokerOrderStatus:
        n = self._acct()
        o = self.api.order_info(broker_id)
        if not isinstance(o, dict) or 'state' not in o:
            raise BrokerError('order status unavailable')
        if not self._owned(o, n):
            raise AccountVerificationError('order belongs to a different account')
        return status_from_rh(o)

    def find_order_by_ref(self, ref_id, symbol, side, since):
        n = self._acct()
        start = datetime.fromtimestamp(since - 86400, tz=timezone.utc).strftime('%Y-%m-%d')
        rows = self.api.orders_since(n, start)
        if not isinstance(rows, list):
            raise BrokerError('order history unavailable')
        for o in rows:
            if str(o.get('ref_id')) == ref_id:
                if not self._owned(o, n):
                    raise AccountVerificationError('matched order belongs to a different account')
                return status_from_rh(o, symbol)
        return None

    def cancel_order(self, broker_id):
        self._acct()
        self.api.cancel(broker_id)
