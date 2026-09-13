"""Baselines every candidate must beat: buy-and-hold, random entries (matched holding-period distribution),
a simple trend filter, and cash/no-trade. A strategy that cannot clear these after costs is rejected regardless
of how good its raw numbers look in isolation.
"""
import numpy as np
import pandas as pd

from research import stats
from research.costs import CostModel


def _as_trades(entry_ts, exit_ts, entry_px, exit_px, cost: CostModel, bars_held=None, extra: dict = None) -> pd.DataFrame:
    entry_ts, exit_ts = np.asarray(entry_ts), np.asarray(exit_ts)
    entry_px, exit_px = np.asarray(entry_px, float), np.asarray(exit_px, float)
    entry_fill, exit_fill = cost.buy_fill(1.0) / 1.0 * entry_px, cost.sell_fill(1.0) / 1.0 * exit_px
    net = np.array([cost.net_return(a, b) for a, b in zip(entry_px, exit_px)])
    df = pd.DataFrame({'entry_ts': entry_ts, 'exit_ts': exit_ts, 'entry_raw': entry_px, 'exit_raw': exit_px,
                       'entry_fill': entry_fill, 'exit_fill': exit_fill, 'gross_ret': exit_px / entry_px - 1,
                       'net_ret': net, 'cost_ret': (exit_px / entry_px - 1) - net,
                       'bars_held': bars_held if bars_held is not None else 1})
    for k, v in (extra or {}).items():
        df[k] = v
    return df


def buy_and_hold(df: pd.DataFrame, window: tuple, cost: CostModel) -> pd.DataFrame:
    """Daily-return series recast as one 'trade' per day, so it plugs directly into stats.summarize /
    consistency_metrics — buy once at window start, hold, no further costs (cost applied once at entry only
    to keep the comparison apples-to-apples with a single buy-and-hold position, not daily round trips)."""
    w = df[(df.index >= window[0]) & (df.index < window[1])]
    if len(w) < 2:
        return pd.DataFrame()
    px = w['close'].to_numpy(float)
    entry_fill = cost.buy_fill(px[0])
    rets = np.diff(px) / px[:-1]
    rets[0] = px[1] / entry_fill - 1  # first day's cost is the entry spread/slippage; no further trading costs
    return pd.DataFrame({'entry_ts': w.index[:-1], 'exit_ts': w.index[1:], 'entry_raw': px[:-1], 'exit_raw': px[1:],
                         'gross_ret': np.diff(px) / px[:-1], 'net_ret': rets, 'cost_ret': np.r_[rets[0] - (px[1] / px[0] - 1), np.zeros(len(rets) - 1)],
                         'bars_held': 1})


def random_entries(df: pd.DataFrame, window: tuple, n_trades: int, hold_days: np.ndarray, cost: CostModel,
                   rng: np.random.Generator) -> pd.DataFrame:
    """n_trades independent random long entries inside window, holding periods resampled (with replacement) from
    the candidate's own realized holding-period distribution — a fair 'same amount of market exposure' null."""
    w = df[(df.index >= window[0]) & (df.index < window[1])]
    o = w['open'].to_numpy(float)
    if len(w) < 5 or n_trades == 0:
        return pd.DataFrame()
    holds = rng.choice(hold_days, size=n_trades) if len(hold_days) else np.ones(n_trades, dtype=int)
    holds = np.clip(holds.astype(int), 1, len(o) - 2)
    starts = rng.integers(0, np.maximum(1, len(o) - holds - 1))
    ends = starts + holds
    return _as_trades(w.index[starts], w.index[ends], o[starts], o[ends], cost, bars_held=holds)


def trend_filter(df: pd.DataFrame, window: tuple, cost: CostModel, sma_days: int = 200, stop_pct: float = 0.30):
    """The simplest possible trend rule: long while price is above its `sma_days` average, flat otherwise."""
    from research.candidates import trend_sma200
    from research.backtest import run as bt_run
    sigs, rule = trend_sma200(df, {'stop_pct': stop_pct})
    t = bt_run(df, sigs, cost, exit_rule=rule)
    return t[(t['entry_ts'] >= window[0]) & (t['entry_ts'] < window[1])] if len(t) else t


def cash() -> dict:
    return {'n': 0, 'mean_pct': 0.0, 'median_pct': 0.0, 'std_pct': 0.0, 'win_rate': np.nan, 'max_dd_pct': 0.0,
            'profit_factor': np.nan, 'total_pct': 0.0}


def compare_table(candidate_trades: pd.DataFrame, df: pd.DataFrame, window: tuple, cost: CostModel,
                  n_sims: int = 300, seed: int = 13, years: float = None) -> dict:
    rng = np.random.default_rng(seed)
    hold_days = candidate_trades['bars_held'].to_numpy() if len(candidate_trades) else np.array([1])
    n = len(candidate_trades)
    sims = [random_entries(df, window, n, hold_days, cost, rng) for _ in range(n_sims)]
    sim_stats = [stats.summarize(s, years=years) for s in sims if len(s)]
    avg_random = {k: float(np.nanmean([s.get(k, np.nan) for s in sim_stats])) for k in
                 ('mean_pct', 'median_pct', 'win_rate', 'profit_factor', 'max_dd_pct', 'total_pct')} if sim_stats else {}
    bh, tf = buy_and_hold(df, window, cost), trend_filter(df, window, cost)
    return {
        'candidate': stats.summarize(candidate_trades, years=years),
        'buy_and_hold': {**stats.summarize(bh, years=years), **stats.consistency_metrics(bh, years=years)},
        'random_entry_avg_of_sims': avg_random, 'random_entry_n_sims': len(sim_stats),
        'trend_filter_200d': {**stats.summarize(tf, years=years), **stats.consistency_metrics(tf, years=years)},
        'cash': cash(),
    }
