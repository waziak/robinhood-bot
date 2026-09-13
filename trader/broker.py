"""Broker interface. Only trader.execution may call submit/cancel. Strategies never import this module."""
import time
import uuid
from typing import Optional

from trader.market_data import BrokerTimeout, call_with_timeout
from trader.models import BrokerOrderStatus, OrderState


class BrokerError(Exception):
    pass


class BrokerRefused(BrokerError):
    """Deterministic refusal before anything is sent. Safe: no order exists."""


class Broker:
    mode = 'abstract'

    def get_account(self) -> dict: ...                       # {'equity','cash','buying_power'}
    def get_positions(self) -> dict: ...                     # {symbol: qty}
    def get_open_orders(self) -> list: ...                   # [BrokerOrderStatus + .symbol/.side]
    def submit_limit_order(self, client_id: str, symbol: str, side: str, qty: float, limit: float) -> str: ...
    def get_order_status(self, broker_id: str) -> BrokerOrderStatus: ...
    def find_recent_order(self, symbol: str, side: str, qty: float, since: float) -> Optional[BrokerOrderStatus]: ...
    def cancel_order(self, broker_id: str) -> None: ...


class PaperBroker(Broker):
    """Simulated fills against real bid/ask: buys pay ask + slippage, sells receive bid - slippage, fees charged.
    Marketable limit orders fill immediately; others rest until a later quote crosses."""
    mode = 'paper'

    def __init__(self, data, cfg, starting_cash: float):
        self.data, self.cfg = data, cfg
        self.cash = float(starting_cash)
        self.positions = {}
        self.orders = {}

    def get_account(self) -> dict:
        equity = self.cash
        for sym, qty in self.positions.items():
            equity += qty * self.data.get_quote(sym).bid
        return {'equity': round(equity, 6), 'cash': round(self.cash, 6), 'buying_power': round(self.cash, 6)}

    def get_positions(self) -> dict:
        return {s: q for s, q in self.positions.items() if q > 1e-12}

    def get_open_orders(self) -> list:
        return [o for o in self.orders.values() if o.state not in OrderState.TERMINAL]

    def submit_limit_order(self, client_id, symbol, side, qty, limit) -> str:
        if qty <= 0 or limit <= 0:
            raise BrokerRefused('non-positive qty/limit')
        if side == 'buy' and qty * limit * (1 + self.cfg.fee_rate) > self.cash + 1e-9:
            raise BrokerRefused('insufficient paper cash')
        if side == 'sell' and qty > self.positions.get(symbol, 0) + 1e-9:
            raise BrokerRefused('selling more than held')
        bid = f'paper-{uuid.uuid4()}'
        st = BrokerOrderStatus(bid, OrderState.ACKNOWLEDGED, 0.0, 0.0, 0.0, 'confirmed')
        st.symbol, st.side, st.qty, st.limit, st.created = symbol, side, qty, limit, time.time()
        self.orders[bid] = st
        self._try_fill(st)
        return bid

    def _try_fill(self, st):
        if st.state in OrderState.TERMINAL:
            return
        q = self.data.get_quote(st.symbol)
        slip = self.cfg.slippage_rate
        if st.side == 'buy':
            px = q.ask * (1 + slip)
            if px > st.limit:
                return
            notional = st.qty * px
            fee = notional * self.cfg.fee_rate
            if notional + fee > self.cash + 1e-9:
                st.state, st.raw_state = OrderState.REJECTED, 'insufficient_cash'
                return
            self.cash -= notional + fee
            self.positions[st.symbol] = self.positions.get(st.symbol, 0) + st.qty
        else:
            px = q.bid * (1 - slip)
            if px < st.limit:
                return
            if st.qty > self.positions.get(st.symbol, 0) + 1e-9:
                st.state, st.raw_state = OrderState.REJECTED, 'insufficient_position'
                return
            fee = st.qty * px * self.cfg.fee_rate
            self.cash += st.qty * px - fee
            self.positions[st.symbol] -= st.qty
        st.state, st.filled_qty, st.avg_fill_price, st.fees, st.raw_state = OrderState.FILLED, st.qty, px, fee, 'filled'

    def get_order_status(self, broker_id) -> BrokerOrderStatus:
        st = self.orders.get(broker_id)
        if st is None:
            raise BrokerError(f'unknown order {broker_id}')
        self._try_fill(st)
        return st

    def find_recent_order(self, symbol, side, qty, since):
        for st in self.orders.values():
            if st.symbol == symbol and st.side == side and abs(st.qty - qty) < 1e-9 and st.created >= since:
                return st
        return None

    def cancel_order(self, broker_id):
        st = self.orders.get(broker_id)
        if st and st.state not in OrderState.TERMINAL:
            st.state, st.raw_state = OrderState.CANCELLED, 'cancelled'


_RH_STATE = {
    'queued': OrderState.SUBMITTED, 'unconfirmed': OrderState.SUBMITTED, 'new': OrderState.SUBMITTED,
    'confirmed': OrderState.ACKNOWLEDGED, 'partially_filled': OrderState.PARTIALLY_FILLED,
    'filled': OrderState.FILLED, 'cancelled': OrderState.CANCELLED, 'canceled': OrderState.CANCELLED,
    'rejected': OrderState.REJECTED, 'failed': OrderState.REJECTED, 'voided': OrderState.CANCELLED,
    'expired': OrderState.EXPIRED,
}


def _status_from_rh(o: dict) -> BrokerOrderStatus:
    raw = str(o.get('state', ''))
    fills = o.get('executions') or []
    fees = sum(float(e.get('fees') or 0) for e in fills) if fills else float(o.get('fees') or 0)
    st = BrokerOrderStatus(str(o['id']), _RH_STATE.get(raw, OrderState.UNKNOWN),
                           float(o.get('cumulative_quantity') or 0), float(o.get('average_price') or 0), fees, raw)
    st.side = o.get('side')
    return st


class RobinhoodBroker(Broker):
    """Live equities only, pinned to one account, limit orders only.
    Crypto is refused: robin_stocks crypto order functions have no account parameter and would execute in the
    login's default (margin) account rather than the authorised cash account."""
    mode = 'live'

    def __init__(self, data, cfg, account_number: str, rh=None):
        if rh is None:
            import robin_stocks.robinhood as rh
        if not account_number:
            raise BrokerRefused('account_number is required for live trading')
        self.rh, self.data, self.cfg, self.account = rh, data, cfg, account_number

    def get_account(self) -> dict:
        prof = call_with_timeout(self.rh.load_account_profile, account_number=self.account, timeout=10)
        port = call_with_timeout(self.rh.load_portfolio_profile, account_number=self.account, timeout=10)
        if not isinstance(prof, dict) or not isinstance(port, dict):
            raise BrokerError('account profile unavailable')
        if prof.get('account_number') != self.account:
            raise BrokerError('broker returned a different account than configured')
        if prof.get('type') != 'cash' and not self.cfg.allow_margin:
            raise BrokerRefused('configured account is not a cash account and margin is not allowed')
        equity = port.get('equity') or port.get('extended_hours_equity')
        if equity in (None, ''):
            raise BrokerError('equity unavailable')
        return {'equity': float(equity), 'cash': float(prof.get('cash') or 0),
                'buying_power': float(prof.get('buying_power') or 0)}

    def get_positions(self) -> dict:
        rows = call_with_timeout(self.rh.get_open_stock_positions, account_number=self.account, timeout=15)
        if rows is None:
            raise BrokerError('positions unavailable')
        out = {}
        for r in rows:
            qty = float(r.get('quantity') or 0)
            if qty > 0:
                sym = call_with_timeout(self.rh.get_symbol_by_url, r['instrument'], timeout=8)
                out[sym] = out.get(sym, 0) + qty
        return out

    def get_open_orders(self) -> list:
        rows = call_with_timeout(self.rh.get_all_open_stock_orders, account_number=self.account, timeout=15)
        if rows is None:
            raise BrokerError('open orders unavailable')
        out = []
        for o in rows:
            st = _status_from_rh(o)
            st.symbol = call_with_timeout(self.rh.get_symbol_by_url, o['instrument'], timeout=8)
            out.append(st)
        return out

    def submit_limit_order(self, client_id, symbol, side, qty, limit) -> str:
        if self.cfg.is_crypto(symbol):
            raise BrokerRefused('live crypto orders cannot be pinned to the authorised account')
        if not self.cfg.live_trading_enabled:
            raise BrokerRefused('live trading disabled')
        fn = self.rh.order_buy_limit if side == 'buy' else self.rh.order_sell_limit
        try:
            resp = call_with_timeout(fn, symbol, round(qty, 6), round(limit, 2), account_number=self.account,
                                     timeInForce='gfd', timeout=self.cfg.order_ack_timeout_seconds)
        except BrokerTimeout:
            raise
        if not isinstance(resp, dict) or not resp.get('id'):
            raise BrokerRefused(f'order not accepted: {str(resp)[:200]}')
        return str(resp['id'])

    def get_order_status(self, broker_id) -> BrokerOrderStatus:
        o = call_with_timeout(self.rh.get_stock_order_info, broker_id, timeout=10)
        if not isinstance(o, dict) or 'state' not in o:
            raise BrokerError(f'order {broker_id} status unavailable')
        return _status_from_rh(o)

    def find_recent_order(self, symbol, side, qty, since):
        from datetime import datetime, timezone
        start = datetime.fromtimestamp(since - 60, tz=timezone.utc).strftime('%Y-%m-%d')
        rows = call_with_timeout(self.rh.get_all_stock_orders, account_number=self.account, start_date=start, timeout=20)
        if rows is None:
            raise BrokerError('order history unavailable')
        from trader.market_data import _parse_ts
        for o in rows:
            if o.get('side') != side or _parse_ts(o.get('created_at')) < since - 60:
                continue
            if abs(float(o.get('quantity') or 0) - round(qty, 6)) > 1e-6:
                continue
            if call_with_timeout(self.rh.get_symbol_by_url, o['instrument'], timeout=8) == symbol:
                return _status_from_rh(o)
        return None

    def cancel_order(self, broker_id):
        call_with_timeout(self.rh.cancel_stock_order, broker_id, timeout=10)
