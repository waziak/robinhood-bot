import os
import sys
import time
from dataclasses import replace
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trader.accounts import AccountVerificationError  # noqa: E402
from trader.broker import Broker, BrokerError, BrokerRefused  # noqa: E402
from trader.events import EventLog  # noqa: E402
from trader.execution import ExecutionEngine  # noqa: E402
from trader.market_data import BrokerTimeout, DataError  # noqa: E402
from trader.models import BrokerOrderStatus, Candle, OrderState, Proposal, Quote  # noqa: E402
from trader.risk_config import WEEK_1_VALIDATION_MODE  # noqa: E402
from trader.risk_engine import RiskEngine  # noqa: E402
from trader.store import Store  # noqa: E402

ACCOUNTS = [
    {'account_number': '705601441', 'type': 'margin', 'deactivated': False},
    {'account_number': '768435059', 'type': 'cash', 'deactivated': False},
    {'account_number': '554664508', 'type': 'cash', 'deactivated': False},
]


class FakeClock:
    def __init__(self):
        self.t = time.time()

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


def make_candles(n=120, price=100.0, end_ts=None, volume=100_000, step=0.0):
    end_ts = end_ts or time.time()
    return [Candle(end_ts - (n - i) * 300, price + step * (i - n), price + step * (i - n) + 0.2,
                   price + step * (i - n) - 0.2, price + step * (i - n), volume) for i in range(n)]


class FakeData:
    def __init__(self, clock):
        self.clock = clock
        self.quotes, self.candles, self.fail = {}, {}, set()

    def set(self, sym, bid, ask, candles=None):
        self.quotes[sym] = (bid, ask)
        self.candles[sym] = candles or make_candles(price=(bid + ask) / 2, end_ts=self.clock.now())

    def get_quote(self, sym):
        if sym in self.fail or sym not in self.quotes:
            raise DataError(f'no quote {sym}')
        bid, ask = self.quotes[sym]
        return Quote(sym, bid, ask, (bid + ask) / 2, self.clock.now())

    def get_candles(self, sym):
        if sym in self.fail or sym not in self.candles:
            raise DataError(f'no candles {sym}')
        return self.candles[sym]


class FakeBroker(Broker):
    """Scriptable broker. behavior[side] in: fill, refuse, reject_after_ack, rest, partial,
    timeout_before_receipt, timeout_after_receipt, account_error."""
    mode = 'paper'

    def __init__(self, data, clock, cash=26.86):
        self.data, self.clock, self.cash = data, clock, cash
        self.positions, self.orders, self.behavior = {}, {}, {}
        self.status_error = self.positions_error = self.account_error = self.history_error = False
        self.cancel_confirms = True
        self.stale_reports = 0
        self.submits = 0

    def get_account(self):
        if self.account_error:
            raise BrokerError('account down')
        eq = self.cash + sum(q * self.data.get_quote(s).bid for s, q in self.positions.items() if q > 1e-12)
        return {'equity': eq, 'cash': self.cash, 'buying_power': self.cash}

    def get_positions(self):
        if self.positions_error:
            raise BrokerError('positions down')
        return {s: q for s, q in self.positions.items() if q > 1e-12}

    def get_open_orders(self):
        return [replace(o) for o in self.orders.values() if o.state not in OrderState.TERMINAL]

    def _fill(self, st, qty):
        st.filled_qty += qty
        st.avg_fill_price = st.limit
        sign = 1 if st.side == 'buy' else -1
        self.positions[st.symbol] = self.positions.get(st.symbol, 0) + sign * qty
        self.cash -= sign * qty * st.limit

    def submit_limit_order(self, client_id, symbol, side, qty, limit):
        self.submits += 1
        b = self.behavior.get(side, 'fill')
        if b == 'refuse':
            raise BrokerRefused('refused')
        if b == 'account_error':
            raise AccountVerificationError('account mismatch')
        if b == 'timeout_before_receipt':
            raise BrokerTimeout('timeout')
        st = BrokerOrderStatus(f'b{len(self.orders) + 1}', OrderState.ACKNOWLEDGED, 0.0, 0.0, 0.0, 'confirmed', symbol,
                               side, qty, client_id, 'acct', self.clock.now(), self.clock.now())
        st.limit = limit
        self.orders[st.broker_id] = st
        if b in ('fill', 'timeout_after_receipt'):
            self._fill(st, qty)
            st.state = OrderState.FILLED
        elif b == 'partial':
            self._fill(st, qty / 2)
            st.state = OrderState.PARTIALLY_FILLED
        elif b == 'reject_after_ack':
            st.state = OrderState.REJECTED
        if b == 'timeout_after_receipt':
            raise BrokerTimeout('timeout after send')
        return replace(st)

    def get_order_status(self, broker_id):
        if self.status_error:
            raise BrokerError('status down')
        st = self.orders[broker_id]
        if self.stale_reports:
            self.stale_reports -= 1
            return replace(st, state=OrderState.ACKNOWLEDGED, filled_qty=0.0, updated_at=st.updated_at - 60)
        return replace(st)

    def find_order_by_ref(self, ref_id, symbol, side, since):
        if self.history_error:
            raise BrokerError('history down')
        return next((replace(s) for s in self.orders.values() if s.ref_id == ref_id), None)

    def cancel_order(self, broker_id):
        st = self.orders[broker_id]
        if self.cancel_confirms and st.state not in OrderState.TERMINAL:
            st.state, st.updated_at = OrderState.CANCELLED, self.clock.now() + 1


def _iso(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace('+00:00', 'Z')


class FakeApi:
    """Stands in for RobinhoodApi (robin_stocks) in live-broker tests."""

    def __init__(self, clock, accounts=None, fill_on_post=False):
        self.clock, self.accounts = clock, accounts if accounts is not None else ACCOUNTS
        self.fill_on_post = fill_on_post
        self.posts, self.account_list_calls, self.orders = [], 0, {}
        self.position_rows, self.response_account, self.post_error = [], None, None
        self.inst_overrides = {}

    def account_list(self):
        self.account_list_calls += 1
        return self.accounts

    def account(self, n):
        return {'account_number': n, 'type': 'cash', 'cash': '26.86', 'buying_power': '26.86'}

    def portfolio(self, n):
        return {'equity': '26.86'}

    def positions(self, n):
        return self.position_rows

    def open_orders(self, n):
        return [o for o in self.orders.values() if o['state'] in ('queued', 'confirmed', 'partially_filled')]

    def orders_since(self, n, start):
        return list(self.orders.values())

    def order_info(self, oid):
        return dict(self.orders[oid])

    def cancel(self, oid):
        if self.orders[oid]['state'] in ('queued', 'confirmed'):
            self.orders[oid].update(state='cancelled', updated_at=_iso(self.clock.now() + 1))

    def instrument(self, symbol):
        base = {'symbol': symbol, 'url': f'https://api.robinhood.com/instruments/{symbol}/', 'tradeable': True, 'state': 'active'}
        return {**base, **self.inst_overrides}

    def symbol_by_url(self, url):
        return url.rstrip('/').split('/')[-1]

    def post_order(self, payload):
        self.posts.append(payload)
        if self.post_error:
            raise self.post_error
        oid = f'o{len(self.posts)}'
        o = {'id': oid, 'state': 'filled' if self.fill_on_post else 'queued', 'side': payload['side'],
             'quantity': payload['quantity'], 'ref_id': payload['ref_id'], 'instrument': payload['instrument'],
             'account': self.response_account or payload['account'],
             'cumulative_quantity': payload['quantity'] if self.fill_on_post else '0',
             'average_price': payload['price'] if self.fill_on_post else None,
             'created_at': _iso(self.clock.now()), 'updated_at': _iso(self.clock.now())}
        self.orders[oid] = o
        if self.fill_on_post:
            self.position_rows = [{'account': payload['account'], 'instrument': payload['instrument'],
                                   'quantity': payload['quantity']}]
        return dict(o)


def make_proposal(symbol='SPY', entry=100.0, stop=99.0, target=102.5, score=80, atr=0.5, strategy='trend_pullback'):
    return Proposal(symbol, strategy, 'long', entry, stop, target, 0.7, 'test', 'test', features={'atr': atr}, score=score)


@pytest.fixture
def env():
    clock = FakeClock()
    # Mechanics tests need a strategy that may trade; the production default approves none.
    cfg = replace(WEEK_1_VALIDATION_MODE, approved_strategies=('trend_pullback', 'breakout', 'mean_reversion'))
    store = Store(':memory:', clock=clock.now)
    events = EventLog(store, clock=clock.now)
    data = FakeData(clock)
    data.set('SPY', 99.99, 100.0)
    data.set('BTC', 59990.0, 60000.0)
    broker = FakeBroker(data, clock)
    risk = RiskEngine(cfg, store, events, clock=clock.now)
    execution = ExecutionEngine(broker, store, events, risk, cfg, sleep=clock.sleep, clock=clock.now)

    class Env:
        pass

    e = Env()
    e.clock, e.cfg, e.store, e.events, e.data, e.broker, e.risk, e.execution = clock, cfg, store, events, data, broker, risk, execution
    e.account = lambda: broker.get_account()
    return e
