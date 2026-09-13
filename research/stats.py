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


def summarize(trades: pd.DataFrame, col: str = 'net_ret', years: float = None) -> dict:
    if trades is None or len(trades) == 0:
        return {'n': 0}
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
