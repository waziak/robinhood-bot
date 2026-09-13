"""Pre-registered candidate strategies. Each starts from an explicit economic/behavioural hypothesis and has a
small number of FIXED parameters chosen before any result was seen. Parameters are not tuned in this harness.
"""
import numpy as np
import pandas as pd

from research.backtest import Signal
from research.data import CRYPTO, ETFS, STOCKS

INDEX_ETFS = ['SPY', 'QQQ', 'IWM', 'DIA']


def _sessions(df: pd.DataFrame):
    et = df.index.tz_convert('America/New_York')
    day = np.asarray(et.date)
    starts = np.flatnonzero(np.r_[True, day[1:] != day[:-1]])
    ends = np.r_[starts[1:], len(df)]
    return et, list(zip(starts, ends))


def rsi(close: pd.Series, n: int) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


# ── intraday (5-minute) ─────────────────────────────────────────────────────
def orb_continuation(df, p):
    """Opening-range breakout on above-normal opening volume, held to the session close."""
    et, sessions = _sessions(df)
    c, v, h, l = (df[k].to_numpy(float) for k in ('close', 'volume', 'high', 'low'))
    minutes = et.hour * 60 + et.minute
    or_vols, out = [], []
    for s, e in sessions:
        if e - s < p['or_bars'] + 2 or minutes[s] != 570:  # needs a full session starting 09:30
            continue
        or_hi, or_lo, or_vol = h[s:s + p['or_bars']].max(), l[s:s + p['or_bars']].min(), v[s:s + p['or_bars']].sum()
        rvol = or_vol / np.mean(or_vols[-10:]) if len(or_vols) >= 10 and np.mean(or_vols[-10:]) > 0 else None
        or_vols.append(or_vol)
        if rvol is None or rvol < p['rvol_min']:
            continue
        for i in range(s + p['or_bars'], e - 1):
            if minutes[i] >= p['last_entry_minute']:
                break
            if c[i] > or_hi:
                out.append(Signal(i, or_lo, None, e - i, {'rvol': rvol}))
                break
    return out


def vwap_pullback(df, p):
    """In an up-session, a pullback that holds session VWAP resumes toward the session high."""
    et, sessions = _sessions(df)
    o, h, l, c, v = (df[k].to_numpy(float) for k in ('open', 'high', 'low', 'close', 'volume'))
    minutes = et.hour * 60 + et.minute
    out = []
    for s, e in sessions:
        if minutes[s] != 570:
            continue
        tp = (h[s:e] + l[s:e] + c[s:e]) / 3
        cum_v = np.cumsum(v[s:e])
        vwap = np.cumsum(tp * v[s:e]) / np.where(cum_v > 0, cum_v, np.nan)
        for i in range(s, e - 1):
            k = i - s
            if minutes[i] < p['start_minute']:
                continue
            if minutes[i] >= p['end_minute']:
                break
            w = vwap[k]
            if not np.isfinite(w) or c[i] / o[s] - 1 < p['min_session_ret']:
                continue
            if l[i] <= w * (1 + p['touch_tol']) and c[i] > w and c[i] > o[i]:
                session_high = h[s:i + 1].max()
                stop = min(l[i], w) * (1 - p['stop_buffer'])
                if session_high > c[i] * 1.001:
                    out.append(Signal(i, stop, session_high, e - i, {}))
                    break
    return out


# ── hourly ──────────────────────────────────────────────────────────────────
def intraday_momentum_last_hour(df, p):
    """First-hour return predicts the final half-hour return (Gao, Han, Li & Zhou 2018)."""
    et, sessions = _sessions(df)
    o, c = df['open'].to_numpy(float), df['close'].to_numpy(float)
    minutes = et.hour * 60 + et.minute
    out = []
    for s, e in sessions:
        if e - s != 7 or minutes[s] != 570 or minutes[e - 1] != 930:
            continue  # full regular sessions only (09:30 ... 15:30 bars)
        if c[s] / o[s] - 1 > p['min_first_hour_ret']:
            i = e - 2  # decision at the 14:30 bar's close; entry at the 15:30 bar's open; exit at its close
            out.append(Signal(i, c[i] * (1 - p['stop_pct']), None, 1, {}))
    return out


def crypto_tsmom(df, p):
    """Daily-horizon time-series momentum in crypto (Liu & Tsyvinski 2021): long after a positive trailing week."""
    c = df['close']
    ret = c / c.shift(p['lookback_h']) - 1
    sma = c.rolling(p['sma_h']).mean()
    hours = df.index.hour
    out = []
    for i in np.flatnonzero((hours == 0) & (ret > 0).to_numpy() & (c > sma).to_numpy()):
        out.append(Signal(int(i), float(c.iloc[i]) * (1 - p['stop_pct']), None, p['hold_h'], {}))
    return out


# ── daily ───────────────────────────────────────────────────────────────────
def overnight_drift(df, p):
    """Equity returns accrue disproportionately overnight (Cooper, Cliff & Gulen 2008). Buy close, sell next open."""
    c, o = df['close'], df['open']
    mask = pd.Series(True, index=df.index)
    if p.get('trend_filter'):
        mask = c > c.rolling(200).mean()
    rows = []
    idx = df.index
    for i in np.flatnonzero(mask.to_numpy()[:-1]):
        rows.append({'entry_ts': idx[i], 'exit_ts': idx[i + 1], 'entry_raw': float(c.iloc[i]), 'exit_raw': float(o.iloc[i + 1]),
                     'bars_held': 1, 'exit_reason': 'next_open', 'mfe': np.nan, 'mae': np.nan})
    return rows


def trend_sma200(df, p):
    """Time-series momentum / trend persistence (Faber 2007; Moskowitz, Ooi & Pedersen 2012)."""
    c = df['close']
    above = (c > c.rolling(200).mean()).to_numpy()
    cross_up = np.r_[False, above[1:] & ~above[:-1]]
    sig = [Signal(int(i), float(c.iloc[i]) * (1 - p['stop_pct']), None, 10_000, {}) for i in np.flatnonzero(cross_up)]
    return sig, ~above


def rsi2_mean_reversion(df, p):
    """Short-term overreaction inside a long-term uptrend reverts within days (liquidity-provision premium)."""
    c = df['close']
    r = rsi(c, 2)
    entry = (c > c.rolling(200).mean()) & (r < p['rsi_max'])
    exit_rule = (c > c.rolling(5).mean()).to_numpy()
    sig = [Signal(int(i), float(c.iloc[i]) * (1 - p['stop_pct']), None, p['max_hold'], {}) for i in np.flatnonzero(entry.to_numpy())]
    return sig, exit_rule


CANDIDATES = [
    {'name': 'orb_continuation', 'fn': orb_continuation, 'source': 'yf', 'interval': '5m', 'universe': ETFS + STOCKS,
     'flatten_daily': True, 'params': {'or_bars': 6, 'rvol_min': 1.2, 'last_entry_minute': 690},
     'hypothesis': 'Early breakouts above the 30-minute opening range on above-normal opening volume reflect persistent order flow and continue into the close.',
     'regime': 'trending / high-volume sessions'},
    {'name': 'vwap_pullback', 'fn': vwap_pullback, 'source': 'yf', 'interval': '5m', 'universe': ETFS + STOCKS,
     'flatten_daily': True, 'params': {'min_session_ret': 0.003, 'start_minute': 630, 'end_minute': 870, 'touch_tol': 0.0005, 'stop_buffer': 0.001},
     'hypothesis': 'In sessions already up >0.3%, a pullback that holds VWAP (the institutional execution benchmark) attracts buyers and resumes toward the session high.',
     'regime': 'intraday uptrend'},
    {'name': 'intraday_momentum_last_hour', 'fn': intraday_momentum_last_hour, 'source': 'yf', 'interval': '1h', 'universe': INDEX_ETFS,
     'flatten_daily': True, 'params': {'min_first_hour_ret': 0.0, 'stop_pct': 0.02},
     'hypothesis': 'A positive first-hour return predicts a positive final half-hour return because late-informed traders and hedgers trade in the same direction near the close.',
     'regime': 'any; strongest on high-volatility days in the literature'},
    {'name': 'crypto_tsmom', 'fn': crypto_tsmom, 'source': 'cb', 'interval': '1h', 'universe': CRYPTO, 'flatten_daily': False,
     'params': {'lookback_h': 168, 'sma_h': 480, 'stop_pct': 0.08, 'hold_h': 24},
     'hypothesis': 'Crypto returns show time-series momentum at daily-to-weekly horizons; being long only after a positive trailing week captures it.',
     'regime': 'trending crypto'},
    {'name': 'overnight_drift', 'fn': overnight_drift, 'source': 'yf', 'interval': '1d', 'universe': INDEX_ETFS, 'kind': 'trades',
     'params': {'trend_filter': False},
     'hypothesis': 'Most of the equity risk premium is earned overnight (close-to-open) rather than intraday.',
     'regime': 'all'},
    {'name': 'overnight_drift_trend', 'fn': overnight_drift, 'source': 'yf', 'interval': '1d', 'universe': INDEX_ETFS, 'kind': 'trades',
     'params': {'trend_filter': True},
     'hypothesis': 'Pre-registered variant: the overnight premium is concentrated when the index is above its 200-day average.',
     'regime': 'long-term uptrend'},
    {'name': 'trend_sma200', 'fn': trend_sma200, 'source': 'yf', 'interval': '1d', 'universe': INDEX_ETFS + ['XLK', 'XLF', 'XLE', 'XLV', 'TLT', 'GLD'],
     'kind': 'exit_rule', 'params': {'stop_pct': 0.30},
     'hypothesis': 'Trends persist; holding only above the 200-day average keeps most upside while avoiding prolonged bear markets.',
     'regime': 'long trends'},
    {'name': 'rsi2_mean_reversion', 'fn': rsi2_mean_reversion, 'source': 'yf', 'interval': '1d', 'universe': INDEX_ETFS,
     'kind': 'exit_rule', 'params': {'rsi_max': 10, 'stop_pct': 0.10, 'max_hold': 10},
     'hypothesis': 'Sharp 2-3 day selloffs inside a long-term uptrend overshoot and revert within days as liquidity providers are paid to absorb flow.',
     'regime': 'long-term uptrend, short-term oversold'},
]
