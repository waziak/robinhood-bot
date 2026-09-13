"""Market data with explicit failure types. Never returns a fabricated or defaulted price."""
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import datetime

from trader.models import Candle, Quote


class DataError(Exception):
    pass


class StaleDataError(DataError):
    pass


class BrokerTimeout(Exception):
    """The call may or may not have taken effect on the broker side."""


_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix='api')


def call_with_timeout(fn, *args, timeout: float = 10, **kwargs):
    fut = _pool.submit(fn, *args, **kwargs)
    try:
        return fut.result(timeout=timeout)
    except FutureTimeout:
        raise BrokerTimeout(f'{getattr(fn, "__name__", "call")} exceeded {timeout}s')


def _parse_ts(value) -> float:
    if not value:
        return 0.0
    return datetime.fromisoformat(str(value).replace('Z', '+00:00')).timestamp()


def _f(d: dict, key: str) -> float:
    v = d.get(key)
    if v in (None, ''):
        raise DataError(f'missing field {key}')
    x = float(v)
    if x <= 0:
        raise DataError(f'non-positive {key}={x}')
    return x


class RobinhoodMarketData:
    def __init__(self, cfg, rh=None):
        if rh is None:
            import robin_stocks.robinhood as rh
        self.rh = rh
        self.cfg = cfg

    def get_quote(self, symbol: str) -> Quote:
        fetched = time.time()
        if self.cfg.is_crypto(symbol):
            q = call_with_timeout(self.rh.get_crypto_quote, symbol, timeout=8)
            if not isinstance(q, dict):
                raise DataError(f'bad crypto quote for {symbol}: {type(q).__name__}')
            # Crypto quotes carry no server timestamp; freshness is enforced via the candle feed instead.
            return Quote(symbol, _f(q, 'bid_price'), _f(q, 'ask_price'), _f(q, 'mark_price'), fetched)
        qs = call_with_timeout(self.rh.get_quotes, symbol, timeout=8)
        if not qs or not isinstance(qs, list) or not qs[0]:
            raise DataError(f'no quote for {symbol}')
        q = qs[0]
        if q.get('trading_halted'):
            raise DataError(f'{symbol} trading halted')
        ts = _parse_ts(q.get('updated_at')) or fetched
        return Quote(symbol, _f(q, 'bid_price'), _f(q, 'ask_price'), _f(q, 'last_trade_price'), ts)

    def get_candles(self, symbol: str, interval: str = '5minute') -> list:
        if self.cfg.is_crypto(symbol):
            raw = call_with_timeout(self.rh.get_crypto_historicals, symbol, interval=interval, span='week',
                                    bounds='24_7', timeout=15)
        else:
            raw = call_with_timeout(self.rh.get_stock_historicals, symbol, interval=interval, span='week',
                                    bounds='regular', timeout=15)
        if not raw or not isinstance(raw, list):
            raise DataError(f'no candles for {symbol}')
        out = []
        for c in raw:
            try:
                out.append(Candle(_parse_ts(c['begins_at']), float(c['open_price']), float(c['high_price']),
                                  float(c['low_price']), float(c['close_price']), float(c.get('volume') or 0)))
            except (KeyError, TypeError, ValueError):
                continue
        if len(out) < 0.9 * len(raw):
            raise DataError(f'{symbol}: {len(raw) - len(out)} malformed candles')
        return out


def check_freshness(quote: Quote, candles: list, cfg, is_market_hours: bool, now: float = None) -> None:
    now = now or time.time()
    if quote.age(now) > cfg.stale_quote_seconds:
        raise StaleDataError(f'{quote.symbol} quote {quote.age(now):.0f}s old')
    if quote.bid > quote.ask:
        raise DataError(f'{quote.symbol} crossed quote bid={quote.bid} ask={quote.ask}')
    if candles and (cfg.is_crypto(quote.symbol) or is_market_hours):
        # a 5-minute bar "begins_at" up to 5 min before it closes
        age = now - candles[-1].ts - 300
        if age > cfg.stale_candle_seconds:
            raise StaleDataError(f'{quote.symbol} last candle {age:.0f}s past close')
