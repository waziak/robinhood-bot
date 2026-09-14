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
    """Short-term overreaction inside a long-term uptrend reverts within days (liquidity-provision premium).

    Signal.meta below is diagnostic metadata ONLY (the RSI value and distance-from-average at entry) — it does
    not affect which bars trigger an entry, the stop, the exit rule, or the holding period, so attaching it does
    not alter trade generation or outcomes and does not constitute a new look at any sealed evaluation of this
    strategy; it exists so research/rsi2_diagnostics.py can explain (not tune) already-sealed results."""
    c = df['close']
    r = rsi(c, 2)
    sma200 = c.rolling(200).mean()
    entry = (c > sma200) & (r < p['rsi_max'])
    exit_rule = (c > c.rolling(5).mean()).to_numpy()
    sig = [Signal(int(i), float(c.iloc[i]) * (1 - p['stop_pct']), None, p['max_hold'],
                 {'rsi_entry': round(float(r.iloc[i]), 2), 'dist_above_sma200_pct': round(100 * (c.iloc[i] / sma200.iloc[i] - 1), 3)})
           for i in np.flatnonzero(entry.to_numpy())]
    return sig, exit_rule


# ── Phase 4: robustness cross-checks and new hypotheses (see docs/PHASE_4_READINESS.md) ────────────────────
def rsi2_early_exit(df, p):
    """Same setup as rsi2_mean_reversion (RSI(2)<10 pullback in a long-term uptrend), but exits on a HARD time-stop
    at day `hold_days` instead of waiting up to 10 days for a 5-day-SMA reclaim.

    Pre-registered from a pattern visible independently in the TRAIN split of rsi2_mean_reversion (i.e., before
    ever looking at its validation or test performance): trades held 1-4 days there were strongly and consistently
    profitable across train/validation/test alike, while trades held 7-10 days were consistently a net loss in
    every one of those three splits. Hypothesis: the reversion either resolves within a few days or the setup has
    failed (a stronger, unresolved downtrend or a failed liquidity-provision scenario), so cutting the holding
    period short should keep the profitable part of the effect and remove the decaying tail — an exit-mechanics
    change, not a re-tuned entry threshold, and evaluated on its own fresh train/validation/(new)test split."""
    c = df['close']
    r = rsi(c, 2)
    sma200 = c.rolling(200).mean()
    entry = (c > sma200) & (r < p['rsi_max'])
    sig = [Signal(int(i), float(c.iloc[i]) * (1 - p['stop_pct']), None, p['hold_days'],
                 {'rsi_entry': round(float(r.iloc[i]), 2)}) for i in np.flatnonzero(entry.to_numpy())]
    return sig


def pullback_from_high(df, p):
    """Cross-check of the same broad hypothesis (short-term overreaction inside a long-term uptrend reverts) using
    a DIFFERENT technical construction — a simple % pullback from the trailing high instead of RSI(2) — to test
    whether the effect is specific to the RSI formula or a more general short-term-oversold phenomenon."""
    c = df['close']
    sma200 = c.rolling(200).mean()
    trailing_high = c.rolling(p['high_lookback']).max()
    pullback = c / trailing_high - 1
    entry = (c > sma200) & (pullback < -p['pullback_pct']) & (c > c.shift(1))  # a down-move that has just turned up
    sig = [Signal(int(i), float(c.iloc[i]) * (1 - p['stop_pct']), None, p['max_hold'],
                 {'pullback_pct_at_entry': round(100 * float(pullback.iloc[i]), 2)})
           for i in np.flatnonzero(entry.to_numpy())]
    exit_rule = (c > c.rolling(5).mean()).to_numpy()
    return sig, exit_rule


def weekly_rsi2(df, p):
    """Same reversion hypothesis sampled at WEEKLY resolution instead of daily — a structurally lower-turnover
    variant, and a check for whether the effect is a short-horizon (daily) microstructure artifact or genuinely
    present at a coarser, even-lower-intervention timescale."""
    w = df.resample('W').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
    c = w['close']
    r = rsi(c, 2)
    sma = c.rolling(p['sma_weeks']).mean()
    entry = (c > sma) & (r < p['rsi_max'])
    idxs = np.flatnonzero(entry.to_numpy())
    o = w['open'].to_numpy(float)
    rows = []
    for k in idxs:
        if k + 1 >= len(w):
            continue
        end = min(len(w) - 1, k + 1 + p['hold_weeks'])
        entry_ts, exit_ts = w.index[k + 1], w.index[end]
        # bars_held must be in TRADING-DAY units (the convention every other candidate and research/reality_check's
        # random-entry null use), not weeks — using week-counts here previously made the null draw ~4-day random
        # holds against this strategy's real ~4-week holds, a unit mismatch that would fabricate an apparent edge.
        days_held = int(df.index.searchsorted(exit_ts) - df.index.searchsorted(entry_ts))
        rows.append({'entry_ts': entry_ts, 'exit_ts': exit_ts, 'entry_raw': o[k + 1],
                    'exit_raw': o[end] if end < len(w) - 1 else c.iloc[end],
                    'bars_held': max(1, days_held), 'exit_reason': 'time', 'mfe': 0.0, 'mae': 0.0})
    return rows


def combined_trend_vol_rsi2(df, p):
    """Combines three INDEPENDENTLY defensible signals rather than adding indicators for their own sake: (1) the
    existing trend filter (price above its 200-day average), (2) the existing RSI(2) oversold pullback, and (3) a
    volatility filter requiring the instrument NOT be in its own trailing-high-volatility tercile. Hypothesis:
    rsi2_mean_reversion's diagnostic breakdown showed its 'high' realized-volatility bucket was flat-to-negative in
    2 of 3 splits (train -0.04%, test -0.12%) while 'low'/'mid' were consistently positive in all three — excluding
    the high-volatility tercile should remove a specifically weak slice rather than mine for a better one, since the
    other two buckets are kept exactly as before, unfiltered."""
    from research.regime import vol_regime
    c = df['close']
    r = rsi(c, 2)
    sma200 = c.rolling(200).mean()
    vr = vol_regime(c)
    entry = (c > sma200) & (r < p['rsi_max']) & (vr != 'high')
    exit_rule = (c > c.rolling(5).mean()).to_numpy()
    sig = [Signal(int(i), float(c.iloc[i]) * (1 - p['stop_pct']), None, p['max_hold'], {}) for i in np.flatnonzero(entry.to_numpy())]
    return sig, exit_rule


def low_volatility_rotation(data: dict, p) -> list:
    """Low-volatility anomaly (Ang, Hodges, Xing & Zhang 2006; Baker, Bradley & Wurgler 2011): lower-volatility
    assets have historically delivered comparable or better risk-adjusted returns than higher-volatility ones,
    plausibly because leverage-constrained investors bid up higher-beta assets for a given expected return. Monthly,
    equal-weight-hold the `top_n` lowest-trailing-realized-volatility instruments in the universe; no absolute
    filter (always invested, unlike the momentum rotation candidate) since low-vol is a relative-ranking effect."""
    from research.candidates import month_end_flags
    calendar = max(data.values(), key=len).index
    idxs = np.flatnonzero(month_end_flags(pd.DataFrame(index=calendar)))
    closes = {s: df['close'].reindex(calendar, method='ffill') for s, df in data.items()}
    opens = {s: df['open'].reindex(calendar, method='ffill') for s, df in data.items()}
    lb = p['vol_lookback_months'] * 21
    trades, held, entry_i = [], set(), None

    def vol_of(sym, i):
        r = closes[sym].iloc[max(0, i - lb):i].pct_change().dropna()
        return r.std() if len(r) > lb / 2 else np.inf

    def close_out(symbols, exit_i, reason):
        rows = []
        for sym in symbols:
            if entry_i is None or exit_i <= entry_i:
                continue
            entry_px, exit_px = opens[sym].iloc[entry_i], opens[sym].iloc[exit_i]
            path = closes[sym].iloc[entry_i:exit_i + 1]
            rows.append({'entry_ts': calendar[entry_i], 'exit_ts': calendar[exit_i], 'entry_raw': entry_px,
                        'exit_raw': exit_px, 'bars_held': exit_i - entry_i, 'exit_reason': reason, 'symbol': sym,
                        'mfe': path.max() / entry_px - 1, 'mae': path.min() / entry_px - 1})
        return rows

    month_ks = [k for k in range(len(idxs)) if idxs[k] >= lb and idxs[k] + 1 < len(calendar)]
    for k in month_ks:
        i = idxs[k]
        # A shorter-history symbol (e.g. an ETF that launched after `calendar` starts) has np.inf here and must
        # never be selected — ranking would otherwise "pick" it with an undefined (NaN) price at that date.
        vols = {s: v for s, v in ((s, vol_of(s, i)) for s in data) if np.isfinite(v)}
        target = set(sorted(vols, key=vols.get)[:min(p['top_n'], len(vols))])
        if target and target != held:
            trades += close_out(held, i + 1, 'rebalance')
            held, entry_i = target, i + 1
    if held:
        trades += close_out(held, len(calendar) - 1, 'data_end')
    return trades


# ── monthly / cross-sectional (low turnover, "smooth returns" family) ───────
def month_end_flags(df: pd.DataFrame) -> np.ndarray:
    d = df.index.tz_convert('America/New_York') if df.index.tz else df.index
    month = np.asarray([(t.year, t.month) for t in d])
    flags = np.zeros(len(df), dtype=bool)
    if len(df):
        flags[:-1] = np.any(month[:-1] != month[1:], axis=1)
        flags[-1] = True
    return flags


def monthly_sma_timing(df, p):
    """Faber (2007) timing model: long an index only while its month-end close is above a trailing N-month
    average; flat (cash) otherwise. Decision at each month's last close, executed at the next trading day's open."""
    c = df['close'].to_numpy(float)
    idxs = np.flatnonzero(month_end_flags(df))
    monthly_c = c[idxs]
    sma = pd.Series(monthly_c).rolling(p['sma_months']).mean().to_numpy()
    above = monthly_c > sma
    rows, in_pos, entry_i = [], False, None
    for k in range(len(idxs)):
        i = idxs[k]
        if i + 1 >= len(df) or not np.isfinite(sma[k]):
            continue
        if not in_pos and above[k]:
            entry_i, in_pos = i + 1, True
        elif in_pos and not above[k]:
            rows.append(_monthly_row(df, entry_i, i + 1, 'flat_signal'))
            in_pos = False
    if in_pos and entry_i < len(df) - 1:
        rows.append(_monthly_row(df, entry_i, len(df) - 1, 'data_end'))
    return rows


def _monthly_row(df, entry_i, exit_i, reason):
    o, c = df['open'].to_numpy(float), df['close'].to_numpy(float)
    entry_px = o[entry_i]
    exit_px = o[exit_i] if exit_i < len(df) - 1 or reason != 'data_end' else c[exit_i]
    path = c[entry_i:exit_i + 1]
    return {'entry_ts': df.index[entry_i], 'exit_ts': df.index[exit_i], 'entry_raw': entry_px, 'exit_raw': exit_px,
           'bars_held': exit_i - entry_i, 'exit_reason': reason,
           'mfe': path.max() / entry_px - 1 if len(path) else 0.0, 'mae': path.min() / entry_px - 1 if len(path) else 0.0}


def sector_rotation_monthly(data: dict, p) -> pd.DataFrame:
    """Cross-sectional momentum (Jegadeesh & Titman 1993): relative strength persists 3-12 months because
    information diffuses slowly and flows chase recent winners. Monthly, rotate into the single best trailing-
    `lookback_months` performer among the universe; move to cash if even the best trailing return is negative
    (absolute-momentum overlay, avoids being long the 'least-bad' asset in a broad selloff)."""
    calendar = max(data.values(), key=len).index
    idxs = np.flatnonzero(month_end_flags(pd.DataFrame(index=calendar)))
    closes = {s: df['close'].reindex(calendar, method='ffill') for s, df in data.items()}
    opens = {s: df['open'].reindex(calendar, method='ffill') for s, df in data.items()}
    lb = p['lookback_months']
    trades, held, entry_i = [], None, None

    def close_out(exit_i, reason):
        if held is None or exit_i <= entry_i:
            return None
        entry_px, exit_px = opens[held].iloc[entry_i], opens[held].iloc[exit_i]
        path = closes[held].iloc[entry_i:exit_i + 1]
        return {'entry_ts': calendar[entry_i], 'exit_ts': calendar[exit_i], 'entry_raw': entry_px, 'exit_raw': exit_px,
               'bars_held': exit_i - entry_i, 'exit_reason': reason, 'symbol': held,
               'mfe': path.max() / entry_px - 1, 'mae': path.min() / entry_px - 1}

    month_ks = [k for k in range(len(idxs)) if idxs[k] >= lb * 21 and idxs[k] + 1 < len(calendar)]
    for k in month_ks:
        i = idxs[k]
        trailing = {s: closes[s].iloc[i] / closes[s].iloc[max(0, i - lb * 21)] - 1 for s in data}
        best = max(trailing, key=trailing.get)
        target = best if trailing[best] > 0 else None
        if target != held:
            row = close_out(i + 1, 'rotate')
            if row:
                trades.append(row)
            held, entry_i = target, (i + 1 if target else None)
    if held is not None:
        row = close_out(len(calendar) - 1, 'data_end')
        if row:
            trades.append(row)
    return trades


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
    {'name': 'monthly_sma10_timing_spy', 'fn': monthly_sma_timing, 'source': 'yf', 'interval': '1d', 'universe': ['SPY'],
     'kind': 'trades', 'params': {'sma_months': 10},
     'hypothesis': "Faber (2007): being long only while price is above its 10-month average sidesteps most of a major bear "
                   "market's depth (investors as a group are trend-followers at long horizons) while capturing most bull-market "
                   "upside, at very low turnover (roughly 4-6 decisions/year).",
     'regime': 'all — designed specifically to reduce drawdown in bear regimes'},
    {'name': 'monthly_sma10_timing_multi', 'fn': monthly_sma_timing, 'source': 'yf', 'interval': '1d',
     'universe': ETFS, 'kind': 'trades', 'params': {'sma_months': 10},
     'hypothesis': 'Same as monthly_sma10_timing_spy, applied per-instrument across a broader liquid-ETF universe to see whether '
                   'the effect is SPY-specific or general.',
     'regime': 'all'},
    {'name': 'sector_rotation_momentum', 'fn': sector_rotation_monthly, 'source': 'yf', 'interval': '1d',
     'universe': [s for s in ETFS if s != 'SHY'], 'kind': 'portfolio', 'params': {'lookback_months': 6},
     'hypothesis': 'Jegadeesh & Titman (1993) cross-sectional momentum: information diffuses slowly and flows chase recent '
                   'winners, so relative strength persists 3-12 months. Monthly, hold only the single best trailing-6-month '
                   'performer across a diversified ETF set; go to cash if even the best is negative (avoids the "least-bad '
                   'asset in a crash" trap).',
     'regime': 'all — cash overlay specifically targets crash regimes'},

    # ── Phase 4 ──────────────────────────────────────────────────────────────
    {'name': 'rsi2_early_exit', 'fn': rsi2_early_exit, 'source': 'yf', 'interval': '1d', 'universe': INDEX_ETFS,
     'params': {'rsi_max': 10, 'stop_pct': 0.10, 'hold_days': 4},
     'hypothesis': rsi2_early_exit.__doc__.strip(),
     'regime': 'long-term uptrend, short-term oversold; hypothesis specifically about EXIT timing'},
    {'name': 'pullback_from_high', 'fn': pullback_from_high, 'source': 'yf', 'interval': '1d', 'universe': INDEX_ETFS,
     'kind': 'exit_rule', 'params': {'high_lookback': 10, 'pullback_pct': 0.03, 'stop_pct': 0.10, 'max_hold': 10},
     'hypothesis': pullback_from_high.__doc__.strip(),
     'regime': 'long-term uptrend, short-term oversold'},
    {'name': 'weekly_rsi2', 'fn': weekly_rsi2, 'source': 'yf', 'interval': '1d', 'universe': INDEX_ETFS,
     'kind': 'trades', 'params': {'rsi_max': 10, 'sma_weeks': 40, 'hold_weeks': 3},
     'hypothesis': weekly_rsi2.__doc__.strip(),
     'regime': 'long-term uptrend, short-term oversold, weekly resolution'},
    {'name': 'combined_trend_vol_rsi2', 'fn': combined_trend_vol_rsi2, 'source': 'yf', 'interval': '1d', 'universe': INDEX_ETFS,
     'kind': 'exit_rule', 'params': {'rsi_max': 10, 'stop_pct': 0.10, 'max_hold': 10},
     'hypothesis': combined_trend_vol_rsi2.__doc__.strip(),
     'regime': 'long-term uptrend, short-term oversold, excluding high-volatility regime'},
    {'name': 'low_volatility_rotation', 'fn': low_volatility_rotation, 'source': 'yf', 'interval': '1d',
     'universe': [s for s in ETFS if s != 'SHY'], 'kind': 'portfolio', 'params': {'vol_lookback_months': 6, 'top_n': 5},
     'hypothesis': low_volatility_rotation.__doc__.strip(),
     'regime': 'all — a relative-ranking effect, not regime-dependent by construction'},
]
