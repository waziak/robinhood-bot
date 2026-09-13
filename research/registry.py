"""Strategy registry: one row per strategy ever evaluated, with a state and the evidence behind it.

States: IDEA, RESEARCHING, FAILED, SHADOW_CANDIDATE, SHADOW_VALIDATED, LIVE_ELIGIBLE, RETIRED.

Promotion rule to SHADOW_CANDIDATE (the only automatic promotion this module makes) requires ALL of:
 - passed the pre-registered train/validation gate in run_candidates.py
 - reality-check percentile vs. a random-entry null >= 95% in the TEST window, with positive excess return
 - reality-check percentile >= 80% in the VALIDATION window too (not a one-window fluke)
Nothing beyond SHADOW_CANDIDATE is ever assigned automatically — SHADOW_VALIDATED requires an actual completed
shadow-mode run (trader.agent --mode shadow) with its own sample-size bar, and LIVE_ELIGIBLE requires a completed
Week-1 live validation review; neither can be produced by a research script.

  venv/bin/python -m research.registry   ->  research/STRATEGY_REGISTRY.md
"""
import os
from datetime import datetime, timezone

from research.candidates import CANDIDATES
from research.reality_check import main as reality_check_main
from research.run_candidates import evaluate

HERE = os.path.dirname(os.path.abspath(__file__))

LEGACY = [
    ('trend_pullback', 'RETIRED', 'Production strategy (bot.py). No predictive signal after costs on 180d crypto + '
     '60d equity 5-min bars (gross ≈0%, net −0.03% to −0.43%/trade). See research/CURRENT_STRATEGY_POSTMORTEM.md.'),
    ('breakout', 'RETIRED', 'Production strategy (bot.py). Same postmortem: no signal after costs.'),
    ('mean_reversion', 'RETIRED', 'Production strategy (bot.py). Same postmortem: no signal after costs.'),
]


def classify(decision: str, verdicts: dict) -> tuple:
    if decision in ('NO DATA',):
        return 'RESEARCHING', 'no historical data available yet'
    if decision == 'INSUFFICIENT SAMPLE':
        return 'RESEARCHING', 'too few trades in train/validation to evaluate the gate — needs more data or a broader universe'
    if decision in ('REJECTED AT VALIDATION', 'FAILED ON TEST'):
        return 'FAILED', decision.lower().replace('_', ' ')
    if decision.startswith('OUT-OF-SAMPLE POSITIVE') or decision.startswith('PASSED VALIDATION'):
        val_pct = verdicts.get('validation', (None,))[0]
        test = verdicts.get('test') or verdicts.get('validation')
        if test is None:
            return 'RESEARCHING', 'passed the validation gate but produced no out-of-sample trades for a reality check yet'
        test_pct, excess = test[0], test[1]
        if test_pct is not None and test_pct >= 0.95 and excess > 0 and (val_pct or 0) >= 0.80:
            return 'SHADOW_CANDIDATE', (f'beats a random-entry null at ≥95th percentile in the test window '
                                        f'(validation {100 * val_pct:.0f}th, test {100 * test_pct:.0f}th) — ready for a completed shadow-mode run')
        if test_pct is not None and test_pct >= 0.80 and excess > 0:
            return 'RESEARCHING', (f'weak/inconclusive edge vs. random-entry null (test {100 * test_pct:.0f}th percentile, '
                                   f'validation {100 * (val_pct or 0):.0f}th) — passed the formal gate but not the reality check; needs more evidence')
        return 'FAILED', (f'reality check: test-window gains are explained by market drift/exposure '
                          f'({100 * (test_pct or 0):.0f}th percentile vs. random-entry null), not timing skill')
    return 'RESEARCHING', f'unclassified decision: {decision}'


def build():
    results = [evaluate(c) for c in CANDIDATES]
    verdicts_by_name = reality_check_main()  # also (re)writes REALITY_CHECK.md
    rows = []
    for name, status, rationale in LEGACY:
        rows.append({'name': name, 'family': 'legacy production', 'status': status, 'rationale': rationale})
    for r in results:
        c = r['cand']
        family = {'5m': 'intraday', '1h': 'multi-hour', '1d': 'daily/monthly'}.get(c['interval'], c['interval'])
        if c.get('kind') == 'portfolio':
            family += ' (cross-sectional rotation)'
        status, rationale = classify(r['decision'], verdicts_by_name.get(c['name'], {}))
        rows.append({'name': c['name'], 'family': family, 'status': status, 'rationale': rationale,
                     'trades': r.get('trades', 0), 'decision': r['decision']})
    return rows


def main():
    rows = build()
    now = datetime.now(timezone.utc)
    order = {'LIVE_ELIGIBLE': 0, 'SHADOW_VALIDATED': 1, 'SHADOW_CANDIDATE': 2, 'RESEARCHING': 3, 'IDEA': 4, 'FAILED': 5, 'RETIRED': 6}
    rows.sort(key=lambda r: order.get(r['status'], 9))
    counts = {}
    for r in rows:
        counts[r['status']] = counts.get(r['status'], 0) + 1
    L = ['# Strategy Registry', '', f'Generated {now:%Y-%m-%d %H:%M} UTC by `python -m research.registry`. '
         'States: IDEA, RESEARCHING, FAILED, SHADOW_CANDIDATE, SHADOW_VALIDATED, LIVE_ELIGIBLE, RETIRED.', '',
         'Summary: ' + ', '.join(f'{k}={v}' for k, v in sorted(counts.items(), key=lambda kv: order.get(kv[0], 9))), '',
         '| strategy | family | status | trades | rationale |', '|---|---|---|---|---|']
    for r in rows:
        L.append(f"| {r['name']} | {r['family']} | **{r['status']}** | {r.get('trades', '—')} | {r['rationale']} |")
    L += ['', '## Promotion rules', '',
          '- **SHADOW_CANDIDATE** (automatic, this script): passed the pre-registered validation gate AND beats a '
          'random-entry null at ≥95th percentile in the sealed test window (≥80th in validation too, so it is not a '
          'one-window fluke). Nothing currently qualifies.',
          '- **SHADOW_VALIDATED** (manual, requires evidence this script cannot produce): a SHADOW_CANDIDATE run for '
          'real in `trader.agent --mode shadow` for enough calendar time to accumulate a meaningful trade count, '
          'with results consistent with the research-stage numbers.',
          '- **LIVE_ELIGIBLE** (manual): a SHADOW_VALIDATED strategy with a completed Week-1-style review showing '
          'positive expectancy, acceptable drawdown, and no execution anomalies — see `trader/reporting.py`.',
          '- Nothing may be added to `RiskConfig.approved_strategies` below LIVE_ELIGIBLE.', '',
          '**Current state: no strategy is above RESEARCHING/FAILED/RETIRED.** `RiskConfig.approved_strategies` '
          'remains empty by design.']
    with open(os.path.join(HERE, 'STRATEGY_REGISTRY.md'), 'w') as f:
        f.write('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    main()
