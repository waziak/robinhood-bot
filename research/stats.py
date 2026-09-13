"""Trade statistics, bootstrap confidence, score calibration. All on per-trade NET returns unless stated."""
import numpy as np
import pandas as pd


def max_drawdown(returns) -> float:
    """Drawdown of a fixed-notional equity curve (sum of returns), in return units."""
    eq = np.cumsum(np.asarray(returns, float))
    if len(eq) == 0:
        return 0.0
    peak = np.maximum.accumulate(np.concatenate([[0.0], eq]))[1:]
    return float((peak - eq).max())


def bootstrap_mean(returns, n: int = 5000, seed: int = 7) -> tuple:
    r = np.asarray(returns, float)
    if len(r) < 2:
        return (np.nan, np.nan, np.nan)
    rng = np.random.default_rng(seed)
    means = r[rng.integers(0, len(r), size=(n, len(r)))].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5)), float((means > 0).mean())


def chronological(trades: pd.DataFrame) -> pd.DataFrame:
    """Sort trades by entry time. Required before any sequence-dependent statistic (drawdown, streaks): a
    multi-symbol strategy's trades arrive concatenated symbol-block by symbol-block (all of SPY's trades, then all
    of QQQ's, ...), not in the order they actually occurred — using that row order directly would compute a
    'drawdown' over a fictional timeline that doesn't correspond to any real trading sequence."""
    if trades is None or len(trades) == 0 or 'entry_ts' not in trades:
        return trades
    return trades.sort_values('entry_ts', kind='stable')


def summarize(trades: pd.DataFrame, col: str = 'net_ret', years: float = None) -> dict:
    if trades is None or len(trades) == 0:
        return {'n': 0}
    trades = chronological(trades)
    r = trades[col].to_numpy(float)
    wins, losses = r[r > 0], r[r <= 0]
    lo, hi, p_pos = bootstrap_mean(r)
    std = float(r.std(ddof=1)) if len(r) > 1 else np.nan
    per_year = len(r) / years if years else np.nan
    return {
        'n': int(len(r)), 'mean_pct': 100 * float(r.mean()), 'median_pct': 100 * float(np.median(r)),
        'std_pct': 100 * std, 'win_rate': float(len(wins) / len(r)),
        'avg_win_pct': 100 * float(wins.mean()) if len(wins) else 0.0,
        'avg_loss_pct': 100 * float(losses.mean()) if len(losses) else 0.0,
        'payoff': float(wins.mean() / -losses.mean()) if len(wins) and len(losses) and losses.mean() < 0 else np.nan,
        'profit_factor': float(wins.sum() / -losses.sum()) if len(losses) and losses.sum() < 0 else np.inf,
        'total_pct': 100 * float(r.sum()), 'max_dd_pct': 100 * max_drawdown(r),
        't_stat': float(r.mean() / (std / np.sqrt(len(r)))) if len(r) > 1 and std > 0 else np.nan,
        'sharpe_like': float(r.mean() / std * np.sqrt(per_year)) if std and per_year == per_year else np.nan,
        'ci95_mean_pct': (100 * lo, 100 * hi), 'p_mean_positive': p_pos,
        'gross_mean_pct': 100 * float(trades['gross_ret'].mean()) if 'gross_ret' in trades else np.nan,
        'cost_mean_pct': 100 * float(trades['cost_ret'].mean()) if 'cost_ret' in trades else np.nan,
        'avg_bars_held': float(trades['bars_held'].mean()) if 'bars_held' in trades else np.nan,
        'mfe_pct': 100 * float(trades['mfe'].mean()) if 'mfe' in trades else np.nan,
        'mae_pct': 100 * float(trades['mae'].mean()) if 'mae' in trades else np.nan,
    }


def breakdown(trades: pd.DataFrame, by: str, col: str = 'net_ret') -> pd.DataFrame:
    if len(trades) == 0 or by not in trades:
        return pd.DataFrame()
    g = trades.groupby(by, observed=True)[col]
    return pd.DataFrame({'n': g.size(), 'win_rate': g.apply(lambda x: (x > 0).mean()), 'mean_pct': 100 * g.mean(),
                         'median_pct': 100 * g.median(), 'total_pct': 100 * g.sum()})


def calibration(trades: pd.DataFrame, score_col: str = 'score', bins=(0, 20, 40, 60, 80, 101)) -> pd.DataFrame:
    if len(trades) == 0:
        return pd.DataFrame()
    t = trades.assign(bucket=pd.cut(trades[score_col], bins=list(bins), right=False,
                                    labels=[f'{a}-{min(b, 100)}' for a, b in zip(bins[:-1], bins[1:])]))
    g = t.groupby('bucket', observed=False)
    return pd.DataFrame({'n': g.size(), 'win_rate': g['net_ret'].apply(lambda x: (x > 0).mean() if len(x) else np.nan),
                         'mean_net_pct': 100 * g['net_ret'].mean(), 'median_net_pct': 100 * g['net_ret'].median(),
                         'mean_gross_pct': 100 * g['gross_ret'].mean(), 'mfe_pct': 100 * g['mfe'].mean(),
                         'mae_pct': 100 * g['mae'].mean()})


def downside_deviation(returns, mar: float = 0.0) -> float:
    """Std dev of returns below a minimum acceptable return (0 by default) — the 'bad half' of volatility."""
    r = np.asarray(returns, float)
    below = np.minimum(r - mar, 0.0)
    return float(np.sqrt((below ** 2).mean())) if len(r) else np.nan


def longest_losing_streak(returns) -> int:
    r = np.asarray(returns, float)
    longest = cur = 0
    for x in r:
        cur = cur + 1 if x <= 0 else 0
        longest = max(longest, cur)
    return int(longest)


def longest_winning_streak(returns) -> int:
    r = np.asarray(returns, float)
    longest = cur = 0
    for x in r:
        cur = cur + 1 if x > 0 else 0
        longest = max(longest, cur)
    return int(longest)


def period_returns(trades: pd.DataFrame, freq: str = 'W', col: str = 'net_ret') -> pd.Series:
    """Realized return summed by the calendar period each trade EXITED in — a practical proxy for 'P&L that week'
    for a one-position-at-a-time system. Periods with zero exits are not included (see period_hit_rate for how
    those are handled: as flat, not counted against the strategy)."""
    if trades is None or len(trades) == 0 or 'exit_ts' not in trades:
        return pd.Series(dtype=float)
    t = trades.sort_values('exit_ts', kind='stable')
    return t.set_index(pd.DatetimeIndex(t['exit_ts']))[col].resample(freq).sum().dropna()


def period_hit_rate(trades: pd.DataFrame, freq: str = 'W', col: str = 'net_ret') -> dict:
    """% of periods (that actually had activity) that were net profitable, plus the full flat-inclusive rate
    (flat periods — no trade exited — counted as non-losing, matching 'no trade' being an acceptable outcome)."""
    p = period_returns(trades, freq, col)
    if len(p) == 0:
        return {'n_active_periods': 0, 'active_win_rate': np.nan, 'mean_period_pct': np.nan, 'std_period_pct': np.nan}
    return {'n_active_periods': int(len(p)), 'active_win_rate': float((p > 0).mean()),
            'mean_period_pct': 100 * float(p.mean()), 'std_period_pct': 100 * float(p.std(ddof=1)) if len(p) > 1 else np.nan,
            'worst_period_pct': 100 * float(p.min()), 'best_period_pct': 100 * float(p.max())}


def consistency_metrics(trades: pd.DataFrame, years: float = None) -> dict:
    """Metrics oriented at 'smooth', not maximal, returns."""
    if trades is None or len(trades) == 0:
        return {}
    trades = chronological(trades)
    r = trades['net_ret'].to_numpy(float)
    dd = downside_deviation(r)
    mdd = max_drawdown(r)
    per_year = len(r) / years if years else np.nan
    weekly, monthly = period_hit_rate(trades, 'W'), period_hit_rate(trades, 'ME')
    return {
        'downside_deviation_pct': 100 * dd, 'sortino_like': float(r.mean() / dd * np.sqrt(per_year)) if dd and per_year == per_year else np.nan,
        'calmar_like': float(r.sum() / mdd) if mdd > 0 else np.inf,
        'longest_losing_streak': longest_losing_streak(r), 'longest_winning_streak': longest_winning_streak(r),
        'pct_profitable_weeks': weekly['active_win_rate'], 'weeks_active': weekly['n_active_periods'],
        'weekly_return_std_pct': weekly['std_period_pct'], 'worst_week_pct': weekly.get('worst_period_pct'),
        'pct_profitable_months': monthly['active_win_rate'], 'months_active': monthly['n_active_periods'],
    }


def spearman(x, y) -> float:
    x, y = pd.Series(x, dtype=float), pd.Series(y, dtype=float)
    ok = x.notna() & y.notna()
    if ok.sum() < 5:
        return np.nan
    return float(x[ok].rank().corr(y[ok].rank()))


def fmt_table(df: pd.DataFrame, floatfmt: str = '{:.3f}') -> str:
    if df is None or len(df) == 0:
        return '_no data_'
    cols = [str(c) for c in df.columns]
    lines = ['| ' + ' | '.join([str(df.index.name or '')] + cols) + ' |', '|' + '---|' * (len(cols) + 1)]
    for i, row in df.iterrows():
        cells = [floatfmt.format(v) if isinstance(v, (float, np.floating)) and v == v else str(v) for v in row]
        lines.append('| ' + ' | '.join([str(i)] + cells) + ' |')
    return '\n'.join(lines)
