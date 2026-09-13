"""Evaluate pre-registered candidates: TRAIN -> VALIDATION -> (once, only if validation passes) sealed TEST.

  venv/bin/python -m research.run_candidates   ->  research/CANDIDATE_STRATEGY_RESULTS.md, research/EXPERIMENT_LOG.md

Pre-registered validation gate (fixed before any result): TRAIN n>=30 and mean net>0; VALIDATION n>=30, mean net>0,
profit factor>=1.10, bootstrap P(mean>0)>=0.80, and mean net still >0 at 2x costs.
"""
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from research import backtest, baselines, costs, data, portfolio, splits, stats
from research.candidates import CANDIDATES

HERE = os.path.dirname(os.path.abspath(__file__))


def trades_for(cand) -> tuple:
    if cand.get('kind') == 'portfolio':
        return _portfolio_trades(cand)
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


def _portfolio_trades(cand) -> tuple:
    """kind='portfolio': the strategy function sees the whole universe at once and returns its own trade rows
    (one row per holding period, with a 'symbol' column identifying what was held) — used for rotation strategies
    where only one function call, not one per symbol, makes sense."""
    data_dict = {}
    for sym in cand['universe']:
        try:
            data_dict[sym] = data.load(cand['source'], sym, cand['interval'])
        except FileNotFoundError:
            continue
    if not data_dict:
        return pd.DataFrame(), None
    rows = cand['fn'](data_dict, cand['params'])
    t = pd.DataFrame(rows)
    if len(t):
        t['gross_ret'] = t['exit_raw'] / t['entry_raw'] - 1
        t['net_ret'] = [costs.for_symbol(s).net_return(a, b) for s, a, b in zip(t['symbol'], t['entry_raw'], t['exit_raw'])]
        t['cost_ret'] = t['gross_ret'] - t['net_ret']
    union = list(data_dict.values())[0].index
    for df in list(data_dict.values())[1:]:
        union = union.union(df.index)
    return t, union


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
    res['validation_consistency'] = stats.consistency_metrics(part['validation'], years=years(w['validation']))
    if len(cand['universe']) > 1:
        try:
            price_data = {s: data.load(cand['source'], s, cand['interval']) for s in t['symbol'].unique()} if len(t) else {}
            cal = index[(index >= w['validation'][0]) & (index < w['validation'][1])]
            res['validation_portfolio'] = portfolio.build(part['validation'], price_data, cal)
        except FileNotFoundError:
            pass
    bench_sym = cand.get('benchmark_symbol', cand['universe'][0])
    try:
        bench_df = data.load(cand['source'], bench_sym, cand['interval'])
        res['baselines'] = baselines.compare_table(part['validation'], bench_df, w['validation'],
                                                    costs.for_symbol(bench_sym), years=years(w['validation']))
        res['benchmark_symbol'] = bench_sym
    except FileNotFoundError:
        pass
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
            res['test_consistency'] = stats.consistency_metrics(part['test'], years=years(w['test']))
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
        if 'validation_portfolio' in r and r['validation_portfolio']:
            p = r['validation_portfolio']
            L += ['', "**Capital-constrained portfolio view (validation window)** — the per-trade rows above assume "
                  "unlimited capital (one fresh full unit per signal); this instead splits ONE pool of capital equally "
                  "across whatever positions are open on each day (the realistic constraint for a small account):",
                  '', f"- Total return: {p['total_return_pct']:+.1f}% · Annualized: {p['annualized_return_pct']:+.1f}% · "
                  f"Max drawdown: {p['max_drawdown_pct']:.1f}% · Sharpe-like: {p['sharpe_like']:.2f}",
                  f"- Invested {p['pct_days_invested']:.0%} of days · concurrent positions: median "
                  f"{p['median_concurrent_positions']:.0f}, average {p['avg_concurrent_positions']:.1f}, max {p['max_concurrent_positions']}",
                  f"- {p['pct_profitable_weeks']:.0%} of {p['weeks']} weeks profitable (worst week {p['worst_week_pct']:+.2f}%), "
                  f"{p['pct_profitable_months']:.0%} of months profitable"]
        for label, key in (('Validation', 'validation_consistency'), ('Test', 'test_consistency')):
            cm = r.get(key)
            if cm:
                L += ['', f'{label}-window consistency ("smoothness") metrics:', '',
                      f"- Downside deviation: {cm.get('downside_deviation_pct', float('nan')):.3f}% · "
                      f"Sortino-like: {cm.get('sortino_like', float('nan')):.2f} · Calmar-like: {cm.get('calmar_like', float('nan')):.2f}",
                      f"- Longest losing streak: {cm.get('longest_losing_streak', 0)} trades · "
                      f"Longest winning streak: {cm.get('longest_winning_streak', 0)} trades",
                      f"- Weeks with an exit: {cm.get('weeks_active', 0)}, {cm.get('pct_profitable_weeks', float('nan')):.0%} profitable, "
                      f"weekly return std {cm.get('weekly_return_std_pct', float('nan')):.3f}%, worst week {cm.get('worst_week_pct', float('nan')):+.3f}%",
                      f"- Months with an exit: {cm.get('months_active', 0)}, {cm.get('pct_profitable_months', float('nan')):.0%} profitable"]
        if 'baselines' in r:
            b = r['baselines']
            L += ['', f"Validation-window baselines (benchmark: {r['benchmark_symbol']}):", '',
                  '| | n | mean net % | win rate | max DD % | total % |', '|---|---|---|---|---|---|',
                  f"| candidate | {b['candidate'].get('n', 0)} | {b['candidate'].get('mean_pct', float('nan')):+.3f} | "
                  f"{b['candidate'].get('win_rate', float('nan')):.2f} | {b['candidate'].get('max_dd_pct', float('nan')):.1f} | "
                  f"{b['candidate'].get('total_pct', float('nan')):+.1f} |",
                  f"| buy & hold | {b['buy_and_hold'].get('n', 0)} | {b['buy_and_hold'].get('mean_pct', float('nan')):+.3f} | "
                  f"{b['buy_and_hold'].get('win_rate', float('nan')):.2f} | {b['buy_and_hold'].get('max_dd_pct', float('nan')):.1f} | "
                  f"{b['buy_and_hold'].get('total_pct', float('nan')):+.1f} |",
                  f"| 200d trend filter | {b['trend_filter_200d'].get('n', 0)} | {b['trend_filter_200d'].get('mean_pct', float('nan')):+.3f} | "
                  f"{b['trend_filter_200d'].get('win_rate', float('nan')):.2f} | {b['trend_filter_200d'].get('max_dd_pct', float('nan')):.1f} | "
                  f"{b['trend_filter_200d'].get('total_pct', float('nan')):+.1f} |",
                  f"| random entry (avg of {b['random_entry_n_sims']} sims) | {b['candidate'].get('n', 0)} | "
                  f"{b['random_entry_avg_of_sims'].get('mean_pct', float('nan')):+.3f} | "
                  f"{b['random_entry_avg_of_sims'].get('win_rate', float('nan')):.2f} | "
                  f"{b['random_entry_avg_of_sims'].get('max_dd_pct', float('nan')):.1f} | "
                  f"{b['random_entry_avg_of_sims'].get('total_pct', float('nan')):+.1f} |",
                  "| cash / no trade | 0 | 0.000 | — | 0.0 | 0.0 |"]
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
