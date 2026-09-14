"""Multiple-testing / strategy-selection-bias accounting.

Every distinct strategy specification (name + fixed params) ever evaluated through the pre-registered
train/validation/test gate counts as one hypothesis test against the random-entry null. Testing many hypotheses
and reporting only the best one inflates the apparent significance of that best result — the more we test, the
higher the bar a single "pass" must clear before it means anything. This module counts every hypothesis ever
logged (including this phase's) and reports the Bonferroni-adjusted percentile bar implied by that count,
alongside the nominal (single-test) bars used elsewhere in this codebase.

Family-wise error rate target: alpha = 0.05 (a 5% chance of at least one false "significant" result across ALL
hypotheses ever tested, not just this run). Required per-test p-value: alpha / n. Since a candidate's evidence is
expressed as a percentile against a random-entry null (p = 1 - percentile), the adjusted percentile bar is
1 - alpha / n.

  venv/bin/python -m research.multiple_testing        # standalone: counts and the bar only
  (research.registry calls render_report(rows) directly so the accurate per-candidate picture is written without
  re-running the expensive evaluation pipeline a second time)
"""
import os
from datetime import datetime, timezone

from research.candidates import CANDIDATES

HERE = os.path.dirname(os.path.abspath(__file__))
ALPHA = 0.05

# Strategies evaluated outside this candidate framework (the production strategies, via a separate postmortem
# pipeline) still count toward the family-wise total — they were hypotheses tested against the same body of
# evidence and history, and excluding them would understate how much searching has actually happened.
LEGACY_HYPOTHESES = ['trend_pullback', 'breakout', 'mean_reversion']


def total_hypotheses() -> int:
    return len(CANDIDATES) + len(LEGACY_HYPOTHESES)


def bonferroni_percentile(n: int, alpha: float = ALPHA) -> float:
    return 1 - alpha / n


def render_report(rows: list = None) -> str:
    """rows: optional list of registry-style dicts (name, status, rationale) for an accurate per-candidate
    picture. Without it (standalone invocation), the report states the bar but not which candidates clear which
    threshold, since that requires re-running the full evaluation pipeline."""
    n, adjusted = total_hypotheses(), bonferroni_percentile(total_hypotheses())
    now = datetime.now(timezone.utc)
    names = LEGACY_HYPOTHESES + [c['name'] for c in CANDIDATES]
    L = ['# Multiple-Testing Accounting', '',
         f'Generated {now:%Y-%m-%d %H:%M} UTC.', '',
         f'**Total hypotheses tested to date: {n}** (3 legacy production strategies + {len(CANDIDATES)} pre-registered '
         'research candidates across Phases 3-4). Each is a distinct, fixed strategy specification evaluated once '
         'against its own train/validation/(sealed once) test split.', '',
         f'At a family-wise error rate of {ALPHA:.0%} across all {n} hypotheses, the Bonferroni-adjusted single-test '
         f'significance level is {ALPHA / n:.5f}, which in percentile-vs-random-entry-null terms requires a result '
         f'at or above the **{100 * adjusted:.2f}th percentile** — not the 95th percentile used as this codebase\'s '
         'nominal "strong evidence" bar elsewhere.', '',
         '| n hypotheses | nominal bar | Bonferroni-adjusted bar |', '|---|---|---|',
         '| 1 (single pre-registered test) | 95th pct | 95th pct |',
         f'| {n} (actual, this program) | 95th pct | {100 * adjusted:.2f}th pct |', '']
    if rows:
        promoted = [r for r in rows if r.get('status') == 'SHADOW_CANDIDATE']
        near_miss = [r for r in rows if 'nominal single-test 95th' in r.get('rationale', '')]
        if promoted:
            L.append(f"**{len(promoted)} candidate(s) clear the adjusted {100 * adjusted:.2f}th-percentile bar: "
                     + ', '.join(r['name'] for r in promoted) + '.**')
        else:
            L.append(f'**No candidate clears the adjusted {100 * adjusted:.2f}th-percentile bar.**')
        if near_miss:
            L.append('Candidate(s) that clear the *nominal* single-test 95th percentile but NOT the adjusted bar '
                     '(exactly the situation this correction exists for): ' + ', '.join(r['name'] for r in near_miss) + '.')
        L.append('')
    else:
        L += ['_Standalone run: per-candidate pass/fail against these bars is written by `research.registry`, which '
             'has already run the full evaluation pipeline once and calls this module directly instead of re-running it._', '']
    L += ['## Hypotheses counted', ''] + [f'{i + 1}. {name}' for i, name in enumerate(names)] + ['', '## Why this matters',
         '', 'If 20 independent, genuinely edge-less strategies are each tested at the 95th-percentile (one-sided '
         '5%) bar, the expected number that pass by chance alone is 20 × 0.05 = 1 — i.e., roughly one "discovery" per '
         '20 hypotheses tested is expected noise, not edge. Any single result that clears the nominal 95th but not '
         'the adjusted bar above should be treated with real skepticism — it is exactly the pattern expected from '
         'chance alone at this sample size, not confirmed evidence.']
    return '\n'.join(L) + '\n'


def main():
    report = render_report()
    with open(os.path.join(HERE, 'MULTIPLE_TESTING.md'), 'w') as f:
        f.write(report)
    print(report)


if __name__ == '__main__':
    main()
