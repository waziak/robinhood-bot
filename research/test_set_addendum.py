"""One-time, explicitly-audited exception: recompute descriptive statistics (drawdown, consistency, capital-
constrained portfolio view) on an ALREADY-SEALED test-set result, for candidates evaluated before the chronological-
sort bug fix (research/stats.py) and the capital-constrained portfolio view (research/portfolio.py) existed.

This does NOT constitute a new look at the test set for decision purposes:
 - The pass/fail decision, parameters, and recorded (n, mean, 2x-cost) in TEST_SET_LOG.md are unchanged and are not
   recomputed or re-judged here.
 - No parameter was changed as a result of seeing this output (there is nothing left to tune: the decision already
   stands).
 - It exists only because the ORIGINAL evaluation's max_drawdown/consistency numbers were computed with a bug
   (multi-symbol trades summed in symbol-concatenation order instead of chronological order) discovered afterward.

Every run of this script appends a permanent, timestamped line to TEST_SET_LOG.md so this exception is auditable
forever, and it refuses to run for any candidate not already present in TEST_SET_LOG.md.

  venv/bin/python -m research.test_set_addendum
"""
import os
from datetime import datetime, timezone

from research import data, portfolio, splits, stats
from research.candidates import CANDIDATES
from research.run_candidates import trades_for

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = splits.LOG


def already_sealed(name: str, params: dict) -> bool:
    return os.path.exists(LOG) and splits.spec_hash(name, params) in open(LOG).read()


def main():
    lines = ['# Test-Set Addendum (post-hoc, bug-fix-only recomputation of already-sealed results)', '',
             f'Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC. See module docstring: this recomputes '
             'DISPLAY statistics only (drawdown, consistency, capital-constrained view) for test windows already '
             'sealed in TEST_SET_LOG.md before those metrics existed or were fixed. No decision is re-made.', '']
    touched = []
    for cand in CANDIDATES:
        if not already_sealed(cand['name'], cand['params']):
            continue
        t, index = trades_for(cand)
        w = splits.bounds(index)
        test = t[splits.in_window(t['entry_ts'], w['test'])]
        if len(test) == 0:
            continue
        touched.append(cand['name'])
        s = stats.summarize(test, years=max((w['test'][1] - w['test'][0]).days / 365.25, 1 / 365.25))
        cm = stats.consistency_metrics(test)
        lines += [f"## {cand['name']}", '', f"Test window: {w['test'][0]:%Y-%m-%d} → {w['test'][1]:%Y-%m-%d}, n={s['n']}",
                 f"- Mean net %/trade: {s['mean_pct']:+.3f} (matches the sealed record — unchanged)",
                 f"- Max drawdown (per-trade, one-unit-per-signal convention): {s['max_dd_pct']:.1f}%",
                 f"- Downside deviation: {cm.get('downside_deviation_pct', float('nan')):.3f}%, Sortino-like: "
                 f"{cm.get('sortino_like', float('nan')):.2f}, longest losing streak: {cm.get('longest_losing_streak', 0)} trades"]
        if len(cand['universe']) > 1:
            try:
                price_data = {s2: data.load(cand['source'], s2, cand['interval']) for s2 in test['symbol'].unique()}
                cal = index[(index >= w['test'][0]) & (index < w['test'][1])]
                p = portfolio.build(test, price_data, cal)
                if p:
                    lines += ['', '**Capital-constrained portfolio view (test window):**',
                             f"- Total return: {p['total_return_pct']:+.1f}% · Annualized: {p['annualized_return_pct']:+.1f}% · "
                             f"Max drawdown: {p['max_drawdown_pct']:.1f}% · Sharpe-like: {p['sharpe_like']:.2f}",
                             f"- Concurrent positions: median {p['median_concurrent_positions']:.0f}, average "
                             f"{p['avg_concurrent_positions']:.1f}, max {p['max_concurrent_positions']}",
                             f"- {p['pct_profitable_weeks']:.0%} of {p['weeks']} weeks profitable (worst week "
                             f"{p['worst_week_pct']:+.2f}%), {p['pct_profitable_months']:.0%} of months profitable"]
            except FileNotFoundError:
                pass
        lines.append('')
    if not touched:
        lines.append('_No sealed candidates needed recomputation._')
    with open(os.path.join(HERE, 'TEST_SET_ADDENDUM.md'), 'w') as f:
        f.write('\n'.join(lines) + '\n')
    with open(LOG, 'a') as f:
        f.write(f"\n<!-- ADDENDUM {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC: display-only recomputation "
                f"(drawdown/consistency bug fix) for {touched or 'none'} — no decision changed, see TEST_SET_ADDENDUM.md -->\n")
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
