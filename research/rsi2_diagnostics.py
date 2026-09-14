"""Diagnostic-only attribution for rsi2_mean_reversion: WHY is it inconsistent between validation (46th
percentile vs. random-entry null) and test (85th)? This module explains already-sealed results — it does not
run any new evaluation, touch stop/target/entry criteria, or feed back into parameter selection. Every breakdown
below is a read of trades that already exist; none of it is used to tune `research/candidates.py`.

  venv/bin/python -m research.rsi2_diagnostics   ->  research/RSI2_DIAGNOSTICS.md
"""
import os
from datetime import datetime, timezone

import pandas as pd

from research import data, regime, splits, stats
from research.candidates import CANDIDATES
from research.run_candidates import trades_for

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = next(c for c in CANDIDATES if c['name'] == 'rsi2_mean_reversion')


def labeled_trades():
    t, index = trades_for(CAND)
    price_data = {s: data.load(CAND['source'], s, CAND['interval']) for s in CAND['universe']}
    t = regime.label_trades(t, price_data)
    t['rsi_bucket'] = pd.cut(t['rsi_entry'], [0, 5, 8, 10], labels=['<5 (extreme)', '5-8', '8-10 (mild)'])
    t['hold_bucket'] = pd.cut(t['bars_held'], [0, 2, 4, 6, 100], labels=['1-2d', '3-4d', '5-6d', '7-10d'])
    w = splits.bounds(index)
    for k, win in w.items():
        t.loc[splits.in_window(t['entry_ts'], win), 'split'] = k
    return t, w


def section(t: pd.DataFrame, by: str, title: str) -> list:
    L = [f'### By {title}', '']
    for split in ('train', 'validation', 'test'):
        sub = t[t['split'] == split]
        if len(sub) == 0:
            continue
        L += [f'{split}:', '', stats.fmt_table(stats.breakdown(sub, by)), '']
    return L


def main():
    t, w = labeled_trades()
    now = datetime.now(timezone.utc)
    L = ['# RSI2 Mean-Reversion — Diagnostic Attribution (research only, no parameters changed)', '',
         f'Generated {now:%Y-%m-%d %H:%M} UTC by `python -m research.rsi2_diagnostics`. Explains the already-sealed '
         'rsi2_mean_reversion evaluation (46th percentile vs. random-entry null in validation, 85th in test) — every '
         'trade below is identical to the sealed run; only the grouping is new. This is NOT a re-evaluation and '
         'produces no new candidate; see the note at the end for what a legitimate follow-up would require.', '',
         f"Windows: train {w['train'][0]:%Y-%m-%d}→{w['train'][1]:%Y-%m-%d}, validation {w['validation'][0]:%Y-%m-%d}→"
         f"{w['validation'][1]:%Y-%m-%d}, test {w['test'][0]:%Y-%m-%d}→{w['test'][1]:%Y-%m-%d} (sealed).", '']
    L += section(t, 'symbol', 'instrument')
    L += section(t, 'regime_trend', 'market regime (at entry)')
    L += section(t, 'regime_vol', 'volatility regime (at entry, trailing rank vs. own history)')
    L += section(t, 'rsi_bucket', 'entry severity (RSI(2) value at entry — lower = more oversold)')
    L += section(t, 'hold_bucket', 'holding period')
    L += section(t, 'exit_reason', 'exit behavior')

    L += ['### Trend strength (continuous, correlation with outcome)', '']
    for split in ('train', 'validation', 'test'):
        sub = t[t['split'] == split]
        if len(sub) < 5:
            continue
        rho = stats.spearman(sub['trend_strength_pct'], sub['net_ret'])
        L.append(f"- {split}: Spearman(distance above SMA200 %, net return) = {rho:+.3f} (n={len(sub)})")
    L.append('')

    L += ['## What the validation window actually looked like', '',
         'The validation window (2013-03-31 → 2019-12-21) was a near-uninterrupted secular bull market for all four '
         'ETFs — very few sustained drawdowns, meaning the "sharp 2-3 day selloff inside a long-term uptrend" setup '
         'this strategy targets was both rarer and shallower than in the test window (which includes the 2020 COVID '
         'crash and 2022 bear market). If the effect concentrates in higher-volatility / sharper-selloff conditions, a '
         'quiet validation window would mechanically produce weaker results than a volatile test window — that would '
         'be a genuine regime-dependence finding, not noise, but it also means the validation window may simply be a '
         'poor test of this specific hypothesis rather than evidence against it.', '',
         'Check this directly: validation-window volatility-regime mix vs. test-window mix:', '']
    for split in ('validation', 'test'):
        sub = t[t['split'] == split]
        mix = sub['regime_vol'].value_counts(normalize=True).round(2).to_dict()
        L.append(f"- {split}: {mix}")
    L += ['', '## What would legitimately follow from this (not done here)', '',
         'If the breakdowns above show the effect concentrating in a specific slice (e.g., only in "high" volatility '
         'regime, or only RSI<5 rather than <10), that becomes a NEW, separately pre-registered hypothesis '
         '("RSI2 pullbacks conditioned on high realized volatility") requiring its own fresh train/validation/test '
         'split and its own sealed test window — it would NOT be graded by reapplying it to rsi2_mean_reversion\'s '
         'already-used test data, and it counts as an additional hypothesis for the multiple-testing tally in '
         '`research/multiple_testing.py`, raising the bar required of everything else.']
    with open(os.path.join(HERE, 'RSI2_DIAGNOSTICS.md'), 'w') as f:
        f.write('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    main()
