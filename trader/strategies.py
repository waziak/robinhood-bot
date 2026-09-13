"""Isolated long-only strategies. Each returns a Proposal or None — never touches a broker.

Feature purposes (nothing is included just because it exists):
- SMA20/SMA50 + slope: trend direction; a pullback or breakout is only traded with the trend.
- ATR(14): volatility unit for stop distance and for rejecting abnormal bars.
- RSI(14): pullback depth (trend_pullback) and exhaustion (mean_reversion).
- Rolling high: breakout level. Bollinger(20,2): stretch from mean for mean_reversion.
- Relative volume: confirmation for breakouts (not available for Robinhood crypto candles — volume reads 0).
"""
from typing import Optional

import numpy as np

from trader.models import Proposal, Quote


def closes(c):
    return np.array([x.close for x in c], dtype=float)


def sma(a, n):
    return float(a[-n:].mean()) if len(a) >= n else None


def ema(a, n):
    if len(a) < n:
        return None
    k, e = 2 / (n + 1), float(a[:n].mean())
    for x in a[n:]:
        e = x * k + e * (1 - k)
    return e


def atr(c, n=14):
    if len(c) < n + 1:
        return None
    trs = [max(c[i].high - c[i].low, abs(c[i].high - c[i - 1].close), abs(c[i].low - c[i - 1].close))
           for i in range(len(c) - n, len(c))]
    return float(np.mean(trs))


def rsi(a, n=14):
    if len(a) < n + 1:
        return None
    d = np.diff(a)
    g, l = np.clip(d, 0, None), np.clip(-d, 0, None)
    ag, al = g[:n].mean(), l[:n].mean()
    for i in range(n, len(d)):
        ag, al = (ag * (n - 1) + g[i]) / n, (al * (n - 1) + l[i]) / n
    return 100.0 if al == 0 else float(100 - 100 / (1 + ag / al))


def rel_volume(c, n=20) -> Optional[float]:
    v = np.array([x.volume for x in c[-(n + 1):]], dtype=float)
    if len(v) < n + 1 or v[:-1].mean() <= 0:
        return None
    return float(v[-1] / v[:-1].mean())


def features(c, quote: Quote) -> dict:
    a = closes(c)
    s50_prev = float(a[-60:-10].mean()) if len(a) >= 60 else None
    s50 = sma(a, 50)
    f = {'price': quote.last, 'sma20': sma(a, 20), 'sma50': s50, 'ema20': ema(a, 20), 'atr': atr(c), 'rsi': rsi(a),
         'rel_volume': rel_volume(c), 'spread_pct': quote.spread_pct,
         'sma50_slope': (s50 - s50_prev) / s50_prev if s50 and s50_prev else None}
    f['atr_pct'] = f['atr'] / a[-1] if f['atr'] else None
    return f


MIN_BARS = 80


def trend_pullback(symbol, c, quote: Quote, f: dict) -> Optional[Proposal]:
    if len(c) < MIN_BARS or None in (f['sma20'], f['sma50'], f['ema20'], f['atr'], f['rsi'], f['sma50_slope']):
        return None
    last = c[-1]
    if not (f['sma20'] > f['sma50'] and f['sma50_slope'] > 0 and last.close > f['sma50']):
        return None
    if abs(last.low - f['ema20']) > 0.5 * f['atr'] or not 40 <= f['rsi'] <= 55 or last.close <= last.open:
        return None
    entry = quote.ask
    swing_low = min(x.low for x in c[-6:])
    stop = min(swing_low - 0.25 * f['atr'], entry - 1.0 * f['atr'])
    stop = max(stop, entry - 3.0 * f['atr'])
    risk = entry - stop
    if risk <= 0:
        return None
    return Proposal(symbol, 'trend_pullback', 'long', entry, stop, entry + 2.0 * risk,
                    confidence=0.6 + 0.2 * (f['sma50_slope'] > 0.002),
                    reasoning=f"uptrend (SMA20>SMA50, slope {f['sma50_slope']:.4f}); pullback to EMA20; RSI {f['rsi']:.0f}; up-close resumption bar",
                    invalidation=f'close below swing low {swing_low:.4f}', features=f)


def breakout(symbol, c, quote: Quote, f: dict) -> Optional[Proposal]:
    if len(c) < MIN_BARS or None in (f['sma50'], f['atr'], f['sma50_slope']):
        return None
    last, prior = c[-1], c[-25:-1]
    level = max(x.high for x in prior)
    rng = last.high - last.low
    if not (last.close > level and f['sma50_slope'] > 0 and rng > 1.2 * f['atr']):
        return None
    if last.close - level > 1.0 * f['atr']:
        return None  # already extended; chasing
    rv = f['rel_volume']
    if rv is not None and rv < 1.5:
        return None
    entry = quote.ask
    stop = level - 0.5 * f['atr']
    risk = entry - stop
    if risk <= 0:
        return None
    return Proposal(symbol, 'breakout', 'long', entry, stop, entry + 2.0 * risk,
                    confidence=0.65 if rv is not None else 0.45,
                    reasoning=f'close {last.close:.4f} above 2h high {level:.4f} on range expansion; rel vol {rv}',
                    invalidation=f'close back below {level:.4f}', features=f)


def mean_reversion(symbol, c, quote: Quote, f: dict) -> Optional[Proposal]:
    if len(c) < MIN_BARS or None in (f['sma20'], f['atr'], f['rsi'], f['sma50_slope']):
        return None
    if abs(f['sma50_slope']) > 0.0015:
        return None  # only in a flat regime; fading a trend is excluded
    a = closes(c)
    sd = float(a[-20:].std())
    lower = f['sma20'] - 2 * sd
    prev, last = c[-2], c[-1]
    if not (prev.close < lower and f['rsi'] < 35 and last.close > last.open):
        return None
    entry = quote.ask
    stop = min(x.low for x in c[-3:]) - 0.25 * f['atr']
    target = f['sma20']
    if entry - stop <= 0 or target <= entry:
        return None
    return Proposal(symbol, 'mean_reversion', 'long', entry, stop, target, confidence=0.5,
                    reasoning=f"flat regime; close below lower band {lower:.4f}; RSI {f['rsi']:.0f}; reversal bar",
                    invalidation=f'new low below {stop:.4f}', features=f)


STRATEGIES = (trend_pullback, breakout, mean_reversion)


def generate(symbol, candles, quote: Quote, enabled=None) -> list:
    f = features(candles, quote)
    out = []
    for strat in STRATEGIES:
        if enabled and strat.__name__ not in enabled:
            continue
        p = strat(symbol, candles, quote, f)
        if p:
            out.append(p)
    return out


def regime(candles) -> str:
    if len(candles) < 60:
        return 'unknown'
    a = closes(candles)
    s50, prev = sma(a, 50), float(a[-60:-10].mean())
    slope = (s50 - prev) / prev
    if a[-1] > s50 and slope > 0.0005:
        return 'up'
    if a[-1] < s50 and slope < -0.0005:
        return 'down'
    return 'range'
