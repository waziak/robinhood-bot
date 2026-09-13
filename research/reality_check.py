"""Statistical reality check for candidates that passed validation. Parameters are NOT changed here.

Questions: is the per-trade return a timing edge, or just the market's drift earned while exposed? Does it survive
worse costs and delayed entries? Is it concentrated in one period?

  venv/bin/python -m research.reality_check   ->  research/REALITY_CHECK.md
"""
import os
from dataclasses import replace
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from research import costs, data, splits, stats
from research.candidates import CANDIDATES
from research.run_candidates import net_at, trades_for

HERE = os.path.dirname(os.path.abspath(__file__))
TARGETS = ('trend_sma200', 'rsi2_mean_reversion')
SIMS = 2000


def delayed(cand):
    """Same rules, but every entry fills one bar later (a crude latency/slippage stress)."""
    fn = cand['fn']

    def shifted(df, p):
        out = fn(df, p)
        sigs, rule = out if isinstance(out, tuple) else (out, None)
        sigs = [replace(s, i=s.i + 1) for s in sigs if s.i + 2 < len(df)]
        return (sigs, rule) if rule is not None else sigs
    return {**cand, 'fn': shifted}


def random_null(cand, trades: pd.DataFrame, window: tuple, rng) -> np.ndarray:
    """Mean net return of random long entries on the same symbols, same holding periods, same window."""
    means = np.zeros(SIMS)
    parts = []
    for sym, g in trades.groupby('symbol'):
        df = data.load(cand['source'], sym, cand['interval'])
        o = df['open'].to_numpy(float)
        ts = df.index
        lo, hi = np.searchsorted(ts.asi8, pd.Timestamp(window[0]).value), np.searchsorted(ts.asi8, pd.Timestamp(window[1]).value)
        rt = costs.for_symbol(sym).round_trip_bps() / 1e4
        holds = g['bars_held'].to_numpy(int)
        parts.append((o, lo, hi, holds, rt))
    total = sum(len(p[3]) for p in parts)
    for k in range(SIMS):
        acc = 0.0
        for o, lo, hi, holds, rt in parts:
            upper = np.maximum(lo + 1, hi - holds - 1)
            j = rng.integers(lo, upper)
            j = np.minimum(j, len(o) - 1 - holds)
            gross = o[j + holds] / o[j] - 1
            acc += ((1 + gross) * (1 - rt) - 1).sum()
        means[k] = acc / total
    return means


def buy_and_hold_per_day(cand, symbols, window) -> float:
    rets = []
    for sym in symbols:
        df = data.load(cand['source'], sym, cand['interval'])
        w = df[(df.index >= window[0]) & (df.index < window[1])]
        if len(w) > 1:
            rets.append((w['close'].iloc[-1] / w['open'].iloc[0]) ** (1 / len(w)) - 1)
    return float(np.mean(rets)) if rets else np.nan


def analyse(cand) -> list:
    rng = np.random.default_rng(11)
    t, index = trades_for(cand)
    td, _ = trades_for(delayed(cand))
    w = splits.bounds(index)
    L = [f"## {cand['name']}", '', f"Hypothesis: {cand['hypothesis']}", f"Parameters (unchanged): `{cand['params']}`", '',
         '| split | n | mean net %/trade | t-stat | random-entry null mean % | strategy percentile vs null | excess %/trade | '
         'avg days held | net %/exposure-day | buy&hold %/day | time in market | 1-bar-delayed entry mean % | mean @3x / @5x costs |',
         '|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    verdicts = {}
    for split in ('train', 'validation', 'test'):
        sub = t[splits.in_window(t['entry_ts'], w[split])]
        sd = td[splits.in_window(td['entry_ts'], w[split])] if len(td) else td
        if len(sub) < 2:
            L.append(f'| {split} | {len(sub)} | — |')
            continue
        s = stats.summarize(sub)
        null = random_null(cand, sub, w[split], rng)
        pct = float((null < sub['net_ret'].mean()).mean())
        excess = 100 * (sub['net_ret'].mean() - null.mean())
        days = sub['bars_held'].sum()
        per_exposure_day = 100 * sub['net_ret'].sum() / days
        bh = 100 * buy_and_hold_per_day(cand, sub['symbol'].unique(), w[split])
        span_days = max(1, len(index[(index >= w[split][0]) & (index < w[split][1])]))
        exposure = days / (span_days * sub['symbol'].nunique())
        L.append(f"| {split} | {s['n']} | {s['mean_pct']:+.3f} | {s['t_stat']:.2f} | {100 * null.mean():+.3f} | {100 * pct:.0f}% | "
                 f"{excess:+.3f} | {sub['bars_held'].mean():.1f} | {per_exposure_day:+.4f} | {bh:+.4f} | {100 * exposure:.0f}% | "
                 f"{stats.summarize(sd).get('mean_pct', float('nan')):+.3f} | {net_at(sub, 3):+.3f} / {net_at(sub, 5):+.3f} |")
        verdicts[split] = (pct, excess, per_exposure_day, bh)
    test = t[splits.in_window(t['entry_ts'], w['test'])]
    if len(test):
        by_year = stats.breakdown(test.assign(year=test['entry_ts'].dt.year), 'year')
        L += ['', 'Test window by year:', '', stats.fmt_table(by_year), '', 'Test window by symbol:', '',
              stats.fmt_table(stats.breakdown(test, 'symbol')), '']
    tv = verdicts.get('test')
    if tv:
        pct, excess, ped, bh = tv
        if pct >= 0.95 and excess > 0:
            v = 'Timing edge beyond random entries at the 95% level in the test window.'
        elif pct >= 0.80 and excess > 0:
            v = 'Weak evidence of timing edge beyond random entries (80-95% percentile) — not conclusive.'
        else:
            v = 'Per-trade gains are explained by market drift while exposed; no timing edge beyond random entries.'
        v += (f" Per exposure-day it earned {ped:+.4f}% vs buy-and-hold {bh:+.4f}%/day"
              f" ({'better' if ped > bh else 'worse'} than simply holding while invested).")
        L += [f'**Reality-check verdict:** {v}', '']
    return L


def main():
    L = ['# Reality Check — candidates that passed validation', '',
         f'Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC by `python -m research.reality_check`. '
         f'Random-entry null: {SIMS} simulations of long trades on the same symbols with the same holding periods inside the same '
         'window, charged the same round-trip costs. A strategy whose mean does not beat that null is earning market drift, not timing.', '']
    for cand in CANDIDATES:
        if cand['name'] in TARGETS:
            L += analyse(cand)
    with open(os.path.join(HERE, 'REALITY_CHECK.md'), 'w') as f:
        f.write('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    main()
