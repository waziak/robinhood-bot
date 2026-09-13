import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trader.broker import Broker, BrokerError, BrokerRefused  # noqa: E402
from trader.events import EventLog  # noqa: E402
from trader.execution import ExecutionEngine  # noqa: E402
from trader.market_data import BrokerTimeout, DataError  # noqa: E402
from trader.models import BrokerOrderStatus, Candle, OrderState, Proposal, Quote  # noqa: E402
from trader.risk_config import WEEK_1_VALIDATION_MODE  # noqa: E402
from trader.risk_engine import RiskEngine  # noqa: E402
from trader.store import Store  # noqa: E402


class FakeClock:
    def __init__(self):
        self.t = time.time()

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


def make_candles(n=120, price=100.0, end_ts=None, volume=100_000, step=0.0):
    end_ts = end_ts or time.time()
    out = []
    for i in range(n):
        p = price + step * (i - n)
        out.append(Candle(end_ts - (n - i) * 300, p, p + 0.2, p - 0.2, p, volume))
    return out


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
    mode = 'paper'

    def __init__(self, data, cash=26.86):
        self.data, self.cash = data, cash
        self.positions, self.orders = {}, {}
        self.behavior = {}
        self.status_error = False
        self.cancel_confirms = True
        self.submits = 0
        self.account_error = False

    def get_account(self):
        if self.account_error:
            raise BrokerError('account down')
        eq = self.cash + sum(q * self.data.get_quote(s).bid for s, q in self.positions.items())
        return {'equity': eq, 'cash': self.cash, 'buying_power': self.cash}

    def get_positions(self):
        return {s: q for s, q in self.positions.items() if q > 1e-12}

    def get_open_orders(self):
        return [o for o in self.orders.values() if o.state not in OrderState.TERMINAL]

    def _fill(self, st, qty):
        px = st.limit
        st.filled_qty += qty
        st.avg_fill_price = px
        sign = 1 if st.side == 'buy' else -1
        self.positions[st.symbol] = self.positions.get(st.symbol, 0) + sign * qty
        self.cash -= sign * qty * px

    def submit_limit_order(self, client_id, symbol, side, qty, limit):
        self.submits += 1
        b = self.behavior.get(side, 'fill')
        if b == 'refuse':
            raise BrokerRefused('refused')
        if b == 'timeout_missing':
            raise BrokerTimeout('timeout')
        st = BrokerOrderStatus(f'b{len(self.orders) + 1}', OrderState.ACKNOWLEDGED, 0.0, 0.0)
        st.symbol, st.side, st.qty, st.limit, st.created = symbol, side, qty, limit, time.time()
        self.orders[st.broker_id] = st
        if b in ('fill', 'timeout_filled'):
            self._fill(st, qty)
            st.state = OrderState.FILLED
        elif b == 'partial':
            self._fill(st, qty / 2)
            st.state = OrderState.PARTIALLY_FILLED
        elif b == 'reject_after_ack':
            st.state = OrderState.REJECTED
        if b == 'timeout_filled':
            raise BrokerTimeout('timeout after send')
        return st.broker_id

    def get_order_status(self, broker_id):
        if self.status_error:
            raise BrokerError('status down')
        return self.orders[broker_id]

    def find_recent_order(self, symbol, side, qty, since):
        for st in self.orders.values():
            if st.symbol == symbol and st.side == side and abs(st.qty - qty) < 1e-9:
                return st
        return None

    def cancel_order(self, broker_id):
        st = self.orders[broker_id]
        if self.cancel_confirms and st.state not in OrderState.TERMINAL:
            st.state = OrderState.CANCELLED


def make_proposal(symbol='SPY', entry=100.0, stop=99.0, target=102.5, score=80, atr=0.5, strategy='trend_pullback'):
    return Proposal(symbol, strategy, 'long', entry, stop, target, 0.7, 'test', 'test', features={'atr': atr}, score=score)


@pytest.fixture
def env():
    clock = FakeClock()
    cfg = WEEK_1_VALIDATION_MODE
    store = Store(':memory:')
    events = EventLog(store)
    data = FakeData(clock)
    data.set('SPY', 99.99, 100.0)
    data.set('BTC', 59990.0, 60000.0)
    broker = FakeBroker(data)
    risk = RiskEngine(cfg, store, events)
    execution = ExecutionEngine(broker, store, events, risk, cfg, sleep=clock.sleep, clock=clock.now)

    class Env:
        pass

    e = Env()
    e.clock, e.cfg, e.store, e.events, e.data, e.broker, e.risk, e.execution = clock, cfg, store, events, data, broker, risk, execution
    e.account = lambda: broker.get_account()
    return e
