"""Evaluate pre-registered candidates: TRAIN -> VALIDATION -> (once, only if validation passes) sealed TEST.

  venv/bin/python -m research.run_candidates   ->  research/CANDIDATE_STRATEGY_RESULTS.md, research/EXPERIMENT_LOG.md

Pre-registered validation gate (fixed before any result): TRAIN n>=30 and mean net>0; VALIDATION n>=30, mean net>0,
profit factor>=1.10, bootstrap P(mean>0)>=0.80, and mean net still >0 at 2x costs.
"""
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from research import backtest, costs, data, splits, stats
from research.candidates import CANDIDATES

HERE = os.path.dirname(os.path.abspath(__file__))


def trades_for(cand) -> tuple:
    frames, indexes = [], []
    for sym in cand['universe']:
        try:
            df = data.load(cand['source'], sym, cand['interval'])
        except FileNotFoundError:
            continue
        cost = costs.for_symbol(sym)
        kind = cand.get('kind', 'signals')
        if kind == 'trades':
            t = pd.DataFrame(cand['fn'](df, cand['params']))
            if len(t):
                t['gross_ret'] = t['exit_raw'] / t['entry_raw'] - 1
                t['net_ret'] = [cost.net_return(a, b) for a, b in zip(t['entry_raw'], t['exit_raw'])]
                t['cost_ret'] = t['gross_ret'] - t['net_ret']
        elif kind == 'exit_rule':
            sigs, rule = cand['fn'](df, cand['params'])
            t = backtest.run(df, sigs, cost, exit_rule=rule)
        else:
            t = backtest.run(df, cand['fn'](df, cand['params']), cost, flatten_daily=cand.get('flatten_daily', False))
        if len(t):
            t['symbol'] = sym
            frames.append(t)
        indexes.append(df.index)
    if not indexes:
        return pd.DataFrame(), None
    union = indexes[0]
    for ix in indexes[1:]:
        union = union.union(ix)
    return (pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()), union


def net_at(t: pd.DataFrame, k: float) -> float:
    if len(t) == 0:
        return np.nan
    return 100 * float(np.mean([costs.for_symbol(s).scaled(k).net_return(a, b) if k else b / a - 1
                                for s, a, b in zip(t['symbol'], t['entry_raw'], t['exit_raw'])]))


def years(window) -> float:
    return max((window[1] - window[0]).days / 365.25, 1 / 365.25)


def evaluate(cand) -> dict:
    t, index = trades_for(cand)
    res = {'cand': cand, 'trades': len(t)}
    if index is None:
        res['decision'] = 'NO DATA'
        return res
    w = splits.bounds(index)
    res['windows'] = w
    part = {k: (t[splits.in_window(t['entry_ts'], w[k])] if len(t) else t) for k in w}
    res['train'] = stats.summarize(part['train'], years=years(w['train']))
    res['validation'] = stats.summarize(part['validation'], years=years(w['validation']))
    res['validation_cost'] = {f'{k}x': net_at(part['validation'], k) for k in (0, 1, 2, 3)}
    res['train_cost'] = {f'{k}x': net_at(part['train'], k) for k in (0, 1, 2, 3)}
    pre_test = t[t['entry_ts'] < w['test'][0]] if len(t) else t
    folds = splits.walk_forward(index[index < w['test'][0]])
    res['folds'] = [(a[0], b[1], stats.summarize(pre_test[splits.in_window(pre_test['entry_ts'], b)] if len(pre_test) else pre_test))
                    for a, b in folds]
    tr, va = res['train'], res['validation']
    checks = {
        'train n>=30': tr.get('n', 0) >= 30, 'train mean>0': tr.get('mean_pct', -1) > 0,
        'validation n>=30': va.get('n', 0) >= 30, 'validation mean>0': va.get('mean_pct', -1) > 0,
        'validation PF>=1.10': va.get('profit_factor', 0) >= 1.10, 'validation P(mean>0)>=0.80': va.get('p_mean_positive', 0) >= 0.80,
        'validation mean>0 at 2x costs': (res['validation_cost']['2x'] or -1) > 0,
    }
    res['checks'] = checks
    if all(checks.values()):
        if splits.test_already_used(cand['name'], cand['params']):
            res['decision'] = 'PASSED VALIDATION — test set already used earlier (see TEST_SET_LOG.md); not re-evaluated'
        else:
            res['test'] = stats.summarize(part['test'], years=years(w['test']))
            res['test_cost'] = {f'{k}x': net_at(part['test'], k) for k in (0, 1, 2, 3)}
            te = res['test']
            ok = te.get('n', 0) >= 30 and te.get('mean_pct', -1) > 0 and (res['test_cost']['2x'] or -1) > 0
            res['decision'] = 'OUT-OF-SAMPLE POSITIVE' if ok else 'FAILED ON TEST'
            splits.record_test_use(cand['name'], cand['params'],
                                   f"n={te.get('n', 0)} mean={te.get('mean_pct', float('nan')):+.3f}% 2x-cost={res['test_cost']['2x']:+.3f}% → {res['decision']}")
    else:
        res['decision'] = 'REJECTED AT VALIDATION' if tr.get('n', 0) >= 30 else 'INSUFFICIENT SAMPLE'
    return res


def row(s: dict) -> str:
    if not s or s.get('n', 0) == 0:
        return '| 0 | — | — | — | — | — | — | — | — |'
    lo, hi = s['ci95_mean_pct']
    return (f"| {s['n']} | {s['mean_pct']:+.3f} | {s['std_pct']:.3f} | {s['win_rate']:.2f} | {s['payoff']:.2f} | "
            f"{s['profit_factor']:.2f} | {s['max_dd_pct']:.1f} | [{lo:+.3f}, {hi:+.3f}] | {s['sharpe_like']:.2f} |")


def main():
    results = [evaluate(c) for c in CANDIDATES]
    now = datetime.now(timezone.utc)
    L = ['# Candidate Strategy Results', '', f'Generated {now:%Y-%m-%d %H:%M} UTC by `python -m research.run_candidates`.',
         '', 'All parameters were fixed in `research/candidates.py` before evaluation and were not tuned. Returns are per trade, '
         'net of the costs in `research/costs.py` unless labelled gross. Splits are chronological 60/20/20 per candidate '
         'data span. The TEST window is evaluated at most once per strategy specification, only after passing validation.', '',
         '| strategy | data | trades | train net % | validation net % | validation @2x cost | decision |', '|---|---|---|---|---|---|---|']
    for r in results:
        c = r['cand']
        tr, va = r.get('train', {}), r.get('validation', {})
        L.append(f"| {c['name']} | {c['source']}:{c['interval']} × {len(c['universe'])} | {r['trades']} | "
                 f"{tr.get('mean_pct', float('nan')):+.3f} (n={tr.get('n', 0)}) | {va.get('mean_pct', float('nan')):+.3f} (n={va.get('n', 0)}) | "
                 f"{r.get('validation_cost', {}).get('2x', float('nan')):+.3f} | **{r['decision']}** |")
    for r in results:
        c = r['cand']
        L += ['', f"## {c['name']}", '', f"**Hypothesis:** {c['hypothesis']}", f"**Intended regime:** {c['regime']}",
              f"**Parameters (fixed):** `{c['params']}`", f"**Universe:** {', '.join(c['universe'])} ({c['source']} {c['interval']})", '']
        if 'windows' not in r:
            L.append('_no data_')
            continue
        L += ['| split | window | n | mean net % | std % | win rate | payoff | PF | max DD % | 95% CI mean % | Sharpe-like |',
              '|---|---|---|---|---|---|---|---|---|---|---|']
        for k in ('train', 'validation', 'test'):
            a, b = r['windows'][k]
            if k == 'test' and 'test' not in r:
                L.append(f'| test | {a:%Y-%m-%d} → {b:%Y-%m-%d} | sealed — not evaluated |  |  |  |  |  |  |  |  |')
                continue
            L.append(f'| {k} | {a:%Y-%m-%d} → {b:%Y-%m-%d} ' + row(r[k]))
        L += ['', f"Cost sensitivity, net mean % at 0x/1x/2x/3x — train {r['train_cost']}, validation {r['validation_cost']}"
              + (f", test {r['test_cost']}" if 'test_cost' in r else ''), '',
              'Walk-forward (pre-test, expanding window; parameters are fixed so each fold is out-of-sample):', '']
        for a, b, s in r['folds']:
            L.append(f"- {a:%Y-%m-%d} → {b:%Y-%m-%d}: n={s.get('n', 0)}, mean net {s.get('mean_pct', float('nan')):+.3f}%")
        L += ['', 'Validation gate: ' + ', '.join(f"{k} {'✔' if v else '✘'}" for k, v in r['checks'].items()), '',
              f"**Decision: {r['decision']}**"]
    with open(os.path.join(HERE, 'CANDIDATE_STRATEGY_RESULTS.md'), 'w') as f:
        f.write('\n'.join(L) + '\n')
    with open(os.path.join(HERE, 'EXPERIMENT_LOG.md'), 'a') as f:
        if f.tell() == 0:
            f.write('# Experiment Log (append-only; every run and every variant, including failures)\n\n'
                    '| when (UTC) | strategy | params | trades | validation net % | decision |\n|---|---|---|---|---|---|\n')
        for r in results:
            va = r.get('validation', {})
            f.write(f"| {now:%Y-%m-%d %H:%M} | {r['cand']['name']} | `{r['cand']['params']}` | {r['trades']} | "
                    f"{va.get('mean_pct', float('nan')):+.3f} | {r['decision']} |\n")
    print('\n'.join(L[:len(CANDIDATES) + 9]))


if __name__ == '__main__':
    main()
