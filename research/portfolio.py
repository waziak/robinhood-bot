"""Capital-constrained equity curve for multi-symbol, independently-timed strategies.

The per-trade convention used elsewhere (each signal gets one fresh, full unit of capital) silently assumes
unlimited capital — fine for judging whether a RULE has edge on average, wrong for judging whether it is
deployable on a small account, which must split its one pool of capital across however many signals are open
at once. This module builds the real equal-weight, capital-constrained curve: on any day with N open positions,
each gets 1/N of total equity, rebalanced daily; days with zero open positions sit in cash (flat).
"""
import numpy as np
import pandas as pd


def build(trades: pd.DataFrame, price_data: dict, calendar: pd.DatetimeIndex) -> dict:
    if trades is None or len(trades) == 0:
        return {}
    symbols = sorted(trades['symbol'].unique())
    daily_ret = {s: price_data[s]['close'].reindex(calendar, method='ffill').pct_change().fillna(0.0)
                for s in symbols if s in price_data}
    open_mask = pd.DataFrame(0.0, index=calendar, columns=symbols)
    for _, tr in trades.iterrows():
        sym = tr['symbol']
        if sym not in open_mask:
            continue
        # Return accrues the day after entry (bought at that day's open) through the exit day inclusive.
        open_mask.loc[(calendar > tr['entry_ts']) & (calendar <= tr['exit_ts']), sym] = 1.0
    n_open = open_mask.sum(axis=1)
    weight = open_mask.div(n_open.replace(0, np.nan), axis=0).fillna(0.0)
    port_ret = sum((weight[s] * daily_ret[s]) for s in symbols if s in daily_ret) if symbols else pd.Series(0.0, index=calendar)
    if isinstance(port_ret, int):
        port_ret = pd.Series(0.0, index=calendar)
    equity = (1 + port_ret).cumprod()
    peak = equity.cummax()
    dd = ((peak - equity) / peak).fillna(0.0)
    weekly = equity.resample('W').last().pct_change().dropna()
    monthly = equity.resample('ME').last().pct_change().dropna()
    years = max((calendar[-1] - calendar[0]).days / 365.25, 1 / 365.25)
    ann_ret = equity.iloc[-1] ** (1 / years) - 1 if equity.iloc[-1] > 0 else -1.0
    return {
        'total_return_pct': 100 * (equity.iloc[-1] - 1), 'annualized_return_pct': 100 * ann_ret,
        'max_drawdown_pct': 100 * float(dd.max()), 'sharpe_like': float(port_ret.mean() / port_ret.std() * np.sqrt(252))
        if port_ret.std() > 0 else np.nan,
        'pct_days_invested': float((n_open > 0).mean()), 'avg_concurrent_positions': float(n_open[n_open > 0].mean()) if (n_open > 0).any() else 0.0,
        'max_concurrent_positions': int(n_open.max()), 'median_concurrent_positions': float(n_open[n_open > 0].median()) if (n_open > 0).any() else 0.0,
        'pct_profitable_weeks': float((weekly > 0).mean()) if len(weekly) else np.nan,
        'pct_profitable_months': float((monthly > 0).mean()) if len(monthly) else np.nan,
        'weeks': int(len(weekly)), 'worst_week_pct': 100 * float(weekly.min()) if len(weekly) else np.nan,
        'equity_curve': equity, 'n_open': n_open,
    }


def per_position_dollars(avg_concurrent: float, max_concurrent: int, account_equity: float) -> dict:
    return {'typical_dollars_per_position': account_equity / max(1.0, avg_concurrent),
            'worst_case_dollars_per_position': account_equity / max(1, max_concurrent)}
