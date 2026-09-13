"""Daily report and Week-1 review. Reports describe; they never change risk settings."""
import json
import os
from collections import Counter
from datetime import datetime, timezone

from trader import events as ev

DAY = 86400


def _metrics(pnls: list) -> dict:
    wins, losses = [x for x in pnls if x > 0], [x for x in pnls if x <= 0]
    gross_loss = -sum(losses)
    return {'n': len(pnls), 'wins': len(wins), 'losses': len(losses),
            'win_rate': len(wins) / len(pnls) if pnls else 0.0,
            'avg_win': sum(wins) / len(wins) if wins else 0.0, 'avg_loss': sum(losses) / len(losses) if losses else 0.0,
            'profit_factor': (sum(wins) / gross_loss) if gross_loss > 0 else (float('inf') if wins else 0.0),
            'expectancy': sum(pnls) / len(pnls) if pnls else 0.0, 'total': sum(pnls)}


def _max_drawdown(values: list) -> float:
    peak, dd = None, 0.0
    for v in values:
        peak = v if peak is None or v > peak else peak
        if peak:
            dd = max(dd, (peak - v) / peak)
    return dd


def _fmt(x, money=True):
    if x == float('inf'):
        return '∞'
    return f'${x:+.2f}' if money else f'{x:.2f}'


def collect(store, start: float, end: float) -> dict:
    eq = [e for e in store.equity_since(start) if e['ts'] < end]
    closed = [p for p in store.closed_positions_since(start) if p.exit_time < end]
    cands = [c for c in store.candidates_since(start) if c['ts'] < end]
    evts = [e for e in store.events_since(start) if e['ts'] < end]
    kinds = Counter(e['kind'] for e in evts)
    rejections = Counter(c['rejection_reason'].split(' (')[0] for c in cands if c['decision'] == 'rejected')
    shadow = [c for c in cands if c['decision'] == 'shadow_approved' and c['hypothetical_return'] is not None]
    by_strategy = {}
    for p in closed:
        by_strategy.setdefault(p.strategy, []).append(p.realized_pnl)
    kill = [json.loads(e['payload']) for e in evts if e['kind'] == ev.KILL_SWITCH]
    errors = [json.loads(e['payload']) for e in evts if e['kind'] == ev.SYSTEM_ERROR]
    return {'equity': eq, 'closed': closed, 'candidates': cands, 'rejections': rejections, 'shadow': shadow,
            'by_strategy': by_strategy, 'kill': kill, 'errors': errors, 'kinds': kinds,
            'metrics': _metrics([p.realized_pnl for p in closed]),
            'shadow_metrics': _metrics([c['hypothetical_return'] for c in shadow])}


def daily_report(store, cfg, day_start: float) -> str:
    d = collect(store, day_start, day_start + DAY)
    eq, m = d['equity'], d['metrics']
    start_eq = eq[0]['equity'] if eq else None
    end_eq = eq[-1]['equity'] if eq else None
    day = datetime.fromtimestamp(day_start, tz=timezone.utc).strftime('%Y-%m-%d')
    L = [f'# Daily Report — {day} (UTC)', '', '## ACCOUNT']
    if eq:
        ret = (end_eq - start_eq) / start_eq if start_eq else 0
        L += [f'- Starting equity: ${start_eq:.2f}', f'- Ending equity: ${end_eq:.2f}', f"- Cash: ${eq[-1]['cash']:.2f}",
              f"- Realized P&L: {_fmt(m['total'])}", f'- Unrealized P&L (end): {_fmt(end_eq - start_eq - m["total"])}',
              f'- Daily return: {ret:+.2%}', f"- Max drawdown (intraday): {_max_drawdown([e['equity'] for e in eq]):.2%}"]
    else:
        L.append('- No verified equity snapshots recorded.')
    taken = sum(1 for c in d['candidates'] if c['decision'] == 'approved')
    L += ['', '## TRADES', f"- Candidates: {len(d['candidates'])}", f'- Approved & sent to execution: {taken}',
          f"- Rejected: {sum(d['rejections'].values())}", f"- Closed trades: {m['n']} ({m['wins']}W / {m['losses']}L)",
          f"- Win rate: {m['win_rate']:.0%}", f"- Average win: {_fmt(m['avg_win'])} · Average loss: {_fmt(m['avg_loss'])}",
          f"- Profit factor: {_fmt(m['profit_factor'], False)} · Expectancy/trade: {_fmt(m['expectancy'])}"]
    if d['shadow']:
        sm = d['shadow_metrics']
        L.append(f"- Shadow (hypothetical) trades: {sm['n']}, win rate {sm['win_rate']:.0%}, "
                 f"avg return {sm['expectancy']:+.3%} (after modelled slippage)")
    L += ['', '## STRATEGIES']
    if d['by_strategy']:
        L += ['| Strategy | Trades | Win rate | Expectancy | Total |', '|---|---|---|---|---|']
        for s, pnls in sorted(d['by_strategy'].items()):
            sm = _metrics(pnls)
            L.append(f"| {s} | {sm['n']} | {sm['win_rate']:.0%} | {_fmt(sm['expectancy'])} | {_fmt(sm['total'])} |")
    else:
        L.append('- No closed trades.')
    losses = [p.realized_pnl for p in d['closed'] if p.realized_pnl < 0]
    L += ['', '## RISK', f"- Largest trade loss: {_fmt(min(losses)) if losses else 'none'}",
          f"- Risk-engine blocks: {sum(d['rejections'].values())}"]
    L += [f'  - {r}: {n}' for r, n in d['rejections'].most_common(8)]
    L += [f"- Kill switches: {len(d['kill'])}"] + [f"  - {k.get('msg')}: {k.get('reason', '')}" for k in d['kill']]
    L += [f"- System errors / broker-API anomalies: {len(d['errors'])}"]
    L += [f"  - {msg}: {n}" for msg, n in Counter(e.get('msg') for e in d['errors']).most_common(5)]
    L += ['', '## LESSONS'] + lessons(d, cfg)
    return '\n'.join(L) + '\n'


def lessons(d: dict, cfg) -> list:
    out, m = [], d['metrics']
    if m['n'] == 0:
        top = d['rejections'].most_common(1)
        out.append(f"- No trades taken{'; most common block: ' + top[0][0] if top else ''}. Doing nothing is a valid result.")
    for s, pnls in d['by_strategy'].items():
        sm = _metrics(pnls)
        note = 'sample too small to judge (<20)' if sm['n'] < 20 else ('negative expectancy — investigate' if sm['expectancy'] <= 0 else 'positive so far')
        out.append(f"- {s}: {sm['n']} trades, expectancy {_fmt(sm['expectancy'])} — {note}.")
    if d['errors']:
        out.append('- Investigate every SYSTEM_ERROR above before trusting the P&L.')
    if d['kill']:
        out.append('- A kill switch fired; review its cause before clearing anything.')
    out.append('- Risk settings are not loosened automatically, regardless of today’s result.')
    return out


def write_daily_report(store, cfg, day_start: float, root: str = 'reports/daily') -> str:
    os.makedirs(root, exist_ok=True)
    path = os.path.join(root, datetime.fromtimestamp(day_start, tz=timezone.utc).strftime('%Y-%m-%d') + '.md')
    with open(path, 'w') as f:
        f.write(daily_report(store, cfg, day_start))
    return path


def classify(d: dict, cfg) -> tuple:
    m = d['metrics']
    unsafe = [k for k in d['kill'] if any(w in str(k.get('reason', '')) for w in ('unknown', 'mismatch', 'untracked', 'lock', 'cancelled'))]
    dd = _max_drawdown([e['equity'] for e in d['equity']])
    if unsafe or dd >= cfg.max_drawdown:
        return 'D', 'unsafe / stop live trading: ' + ('execution-integrity kill switches fired' if unsafe else f'drawdown {dd:.1%}')
    if m['n'] < 20:
        return 'B', f"needs more data: {m['n']} closed trades (<20) cannot distinguish edge from luck"
    if m['expectancy'] <= 0 or m['profit_factor'] < 1.0:
        return 'C', 'needs strategy changes: non-positive expectancy'
    if m['profit_factor'] >= 1.2 and not d['errors']:
        return 'A', 'promising — still requires a larger sample before any size increase'
    return 'B', 'marginal edge or unresolved errors — needs more data'


def week1_review(store, cfg, start: float) -> str:
    d = collect(store, start, start + 7 * DAY)
    m, eq = d['metrics'], d['equity']
    grade, why = classify(d, cfg)
    days = max(1.0, ((eq[-1]['ts'] - eq[0]['ts']) / DAY) if len(eq) > 1 else 1.0)
    L = ['# Week 1 Review', '', f'Classification: **{grade}** — {why}', '', '## Results']
    if eq:
        s, e = eq[0]['equity'], eq[-1]['equity']
        L += [f'- Starting capital: ${s:.2f}', f'- Ending capital: ${e:.2f}', f'- Return: {(e - s) / s:+.2%}']
    L += [f"- Realized P&L: {_fmt(m['total'])}", f"- Max drawdown: {_max_drawdown([x['equity'] for x in eq]):.2%}",
          f"- Win rate: {m['win_rate']:.0%} · Profit factor: {_fmt(m['profit_factor'], False)} · Expectancy: {_fmt(m['expectancy'])}",
          f"- Average winner: {_fmt(m['avg_win'])} · Average loser: {_fmt(m['avg_loss'])}",
          f"- Trades/day: {m['n'] / days:.2f}", '', '## By strategy']
    for s, pnls in sorted(d['by_strategy'].items()):
        sm = _metrics(pnls)
        L.append(f"- {s}: {sm['n']} trades, win {sm['win_rate']:.0%}, expectancy {_fmt(sm['expectancy'])}")
    regimes = Counter(json.loads(c['market_state']).get('regime') for c in d['candidates'] if c['decision'] != 'rejected')
    L += ['', '## By market regime (approved candidates)'] + [f'- {r}: {n}' for r, n in regimes.items()]
    L += ['', '## Execution & risk', f"- Execution failures / system errors: {len(d['errors'])}",
          f"- Skipped (rejected) candidates: {sum(d['rejections'].values())}",
          f"- Risk-engine interventions (kill switches): {len(d['kill'])}", '',
          'Position sizes are **not** increased on the basis of this review alone. Scaling requires a statistically '
          'meaningful sample (dozens of trades per strategy) with positive expectancy after costs.']
    return '\n'.join(L) + '\n'
