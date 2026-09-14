"""Daily regime classifiers, shared across candidates and diagnostics. Pure functions of trailing data only —
each array's value at position i depends only on data up to and including i (verified by truncation tests)."""
import numpy as np
import pandas as pd


def trend_regime(close: pd.Series, fast: int = 50, slow: int = 200, slope_lookback: int = 20) -> pd.Series:
    """'up' if price > slow SMA and that SMA has risen over slope_lookback bars; 'down' if the mirror; else 'range'."""
    sma = close.rolling(slow).mean()
    slope = sma - sma.shift(slope_lookback)
    up = (close > sma) & (slope > 0)
    down = (close < sma) & (slope < 0)
    out = np.where(up, 'up', np.where(down, 'down', 'range'))
    out[: slow + slope_lookback] = 'unknown'
    return pd.Series(out, index=close.index)


def trend_strength(close: pd.Series, window: int = 200) -> pd.Series:
    """% distance of price from its long SMA — a continuous measure of how strong the prevailing trend is."""
    sma = close.rolling(window).mean()
    return (close - sma) / sma


def realized_vol(close: pd.Series, window: int = 20, annualize: bool = True) -> pd.Series:
    r = close.pct_change()
    vol = r.rolling(window).std()
    return vol * np.sqrt(252) if annualize else vol


def vol_regime(close: pd.Series, window: int = 20, lookback: int = 252) -> pd.Series:
    """'low'/'mid'/'high' by trailing rank of realized vol within its own trailing `lookback`-bar history —
    adaptive per-instrument, not a fixed cutoff, and never uses data past the current bar."""
    vol = realized_vol(close, window, annualize=False)
    pct_rank = vol.rolling(lookback).apply(lambda x: (x[-1] > x[:-1]).mean() if len(x) > 1 else np.nan, raw=True)
    bucket = pd.cut(pct_rank, [-0.01, 1 / 3, 2 / 3, 1.01], labels=['low', 'mid', 'high'])
    return bucket.astype(object).where(pct_rank.notna(), 'unknown')


def label_trades(trades: pd.DataFrame, price_data: dict, at: str = 'entry_ts') -> pd.DataFrame:
    """Attach trend_regime/vol_regime/trend_strength — evaluated using only data through the bar BEFORE `at`
    (the decision point), never the entry bar's own close — to each trade, per its own symbol's price series."""
    if len(trades) == 0:
        return trades
    out = trades.copy()
    for col in ('regime_trend', 'regime_vol', 'trend_strength_pct'):
        out[col] = None
    for sym, df in price_data.items():
        mask = out['symbol'] == sym
        if not mask.any():
            continue
        c = df['close']
        tr, vr, ts = trend_regime(c), vol_regime(c), trend_strength(c)
        idx = df.index.searchsorted(out.loc[mask, at]) - 1
        idx = np.clip(idx, 0, len(df) - 1)
        out.loc[mask, 'regime_trend'] = tr.to_numpy()[idx]
        out.loc[mask, 'regime_vol'] = vr.to_numpy()[idx]
        out.loc[mask, 'trend_strength_pct'] = 100 * ts.to_numpy()[idx]
    return out
