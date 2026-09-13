#!/usr/bin/env python3
"""Replay real historical 5-minute candles through the full trader stack (strategies -> scoring -> risk ->
execution -> PaperBroker -> monitor -> reports) on a simulated clock.

Validates pipeline behaviour and safety invariants on real price paths, and measures what every proposal
(approved or rejected) would have done afterwards. It does NOT prove edge: quotes are synthesised from bar
closes with an assumed spread, and stops are assumed to fill at the stop price even when a bar gaps through.

Input: <data-dir>/<SYM>-USD.json as [[ts, open, high, low, close, volume], ...].
--diagnostic-min-score runs OUTSIDE week-1 mode with a lower score floor purely to exercise the execution path;
its results are labelled DIAGNOSTIC and are never a configuration recommendation.
"""
import argparse
import bisect
import json
import logging
import os
import sys
from collections import Counter, defaultdict
from dataclasses import replace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trader.agent import Agent  # noqa: E402
from trader.broker import PaperBroker  # noqa: E402
from trader.events import EventLog  # noqa: E402
from trader.execution import ExecutionEngine  # noqa: E402
from trader.market_data import DataError  # noqa: E402
from trader.models import Candle, Quote  # noqa: E402
from trader.reporting import collect, week1_review  # noqa: E402
from trader.risk_config import WEEK_1_VALIDATION_MODE  # noqa: E402
from trader.risk_engine import EMERGENCY_HALT, RiskEngine  # noqa: E402
from trader.store import Store  # noqa: E402


class Clock:
    def __init__(self, t):
        self.t = t

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


class ReplayData:
    def __init__(self, clock, bars: dict, spread: float, window: int = 2016):
        self.clock, self.bars, self.spread, self.window = clock, bars, spread, window
        self.ts = {s: [b[0] for b in rows] for s, rows in bars.items()}

    def _completed(self, sym):
        if sym not in self.bars:
            raise DataError(f'{sym} not in replay set')
        i = bisect.bisect_right(self.ts[sym], self.clock.now() - 300)
        if i == 0:
            raise DataError('no completed bars yet')
        return self.bars[sym][max(0, i - self.window):i]

    def get_candles(self, sym):
        return [Candle(b[0], b[1], b[2], b[3], b[4], b[5]) for b in self._completed(sym)]

    def get_quote(self, sym):
        close = self._completed(sym)[-1][4]
        h = self.spread / 2
        return Quote(sym, close * (1 - h), close * (1 + h), close, self.clock.now())


def load(data_dir, symbols):
    bars = {}
    for sym in symbols:
        with open(os.path.join(data_dir, f'{sym}-USD.json')) as f:
            bars[sym] = json.load(f)
    return bars


def run(bars, spread, db_path, starting_cash, warmup_bars, crypto, diagnostic_min_score=None):
    first = min(rows[0][0] for rows in bars.values())
    start = first + warmup_bars * 300
    end = min(rows[-1][0] for rows in bars.values()) + 300
    clock = Clock(start)
    cfg = replace(WEEK_1_VALIDATION_MODE, universe=tuple(bars), crypto_symbols=tuple(s for s in bars if s in crypto))
    if diagnostic_min_score is not None:
        cfg = replace(cfg, week1_validation_mode=False, minimum_signal_score=diagnostic_min_score,
                      approved_strategies=('trend_pullback', 'breakout', 'mean_reversion'))
    cfg.validate()
    if os.path.exists(db_path):
        os.remove(db_path)
    store = Store(db_path, clock=clock.now)
    events = EventLog(store, clock=clock.now)
    data = ReplayData(clock, bars, spread)
    broker = PaperBroker(data, cfg, starting_cash)
    risk = RiskEngine(cfg, store, events, clock=clock.now)
    execution = ExecutionEngine(broker, store, events, risk, cfg, sleep=clock.sleep, clock=clock.now)
    agent = Agent(cfg, store, events, data, broker, risk, execution, 'paper', clock=clock.now, sleep=clock.sleep,
                  scan_interval=300)
    agent.run(end - start, flatten_on_exit=True)
    return cfg, store, broker, start, end


def forward_outcomes(store, bars, cfg, horizon_bars=48):
    """First-touch stop/target walk over subsequent bars for EVERY proposal. Stop assumed hit first when a bar
    touches both (conservative). Net of spread and slippage both ways."""
    buckets, by_strat = defaultdict(list), defaultdict(list)
    for c in store.candidates_since(0):
        rows, ts = bars[c['symbol']], [b[0] for b in bars[c['symbol']]]
        i = bisect.bisect_right(ts, c['ts'] - 300)
        entry, stop, target = c['hypothetical_entry'] * (1 + cfg.slippage_rate), c['stop'], c['target']
        exit_px = None
        for b in rows[i:i + horizon_bars]:
            if b[3] <= stop:
                exit_px = stop
                break
            if b[2] >= target:
                exit_px = target
                break
        if exit_px is None:
            seg = rows[i:i + horizon_bars]
            if not seg:
                continue
            exit_px = seg[-1][4]
        net = (exit_px * (1 - cfg.slippage_rate) - entry) / entry
        r_mult = (exit_px - entry) / (entry - stop) if entry > stop else 0.0
        s = c['score']
        bucket = '<50' if s < 50 else '50-59' if s < 60 else '60-69' if s < 70 else '>=70'
        buckets[bucket].append((net, r_mult))
        by_strat[c['strategy']].append((net, r_mult))

    def agg(xs):
        if not xs:
            return {}
        n = len(xs)
        return {'n': n, 'win_rate': round(sum(1 for x in xs if x[0] > 0) / n, 3),
                'avg_net_return_pct': round(100 * sum(x[0] for x in xs) / n, 4),
                'avg_R': round(sum(x[1] for x in xs) / n, 3)}

    return {'by_score': {k: agg(v) for k, v in sorted(buckets.items())},
            'by_strategy': {k: agg(v) for k, v in sorted(by_strat.items())}}


def invariants(cfg, store, broker) -> dict:
    closed = store.closed_positions_since(0)
    rows = store.db.execute("SELECT quantity, entry_price FROM positions WHERE status!='cancelled'").fetchall()
    worst = min((p.realized_pnl for p in closed), default=0.0)
    by_day = Counter()
    for p in closed:
        by_day[int(p.exit_time // 86400)] += p.realized_pnl
    orders = store.db.execute('SELECT state FROM orders').fetchall()
    return {
        'max_entry_notional': round(max((r['quantity'] * r['entry_price'] for r in rows), default=0.0), 4),
        'entry_notional_within_cap': all(r['quantity'] * r['entry_price'] <= cfg.max_dollar_position * 1.01 for r in rows),
        'worst_trade_loss': round(worst, 4),
        'worst_trade_within_1.5x_budget': worst >= -1.5 * cfg.max_risk_per_trade_dollars,
        'worst_day_pnl': round(min(by_day.values(), default=0.0), 4),
        'days_breaching_daily_loss': sum(1 for v in by_day.values() if v < -cfg.max_daily_loss),
        'open_positions_at_end': len(store.open_positions()),
        'broker_positions_at_end': broker.get_positions(),
        'unresolved_orders': len(store.open_orders()),
        'order_states': dict(Counter(o['state'] for o in orders)),
        'emergency_halt': list(store.get_flag(EMERGENCY_HALT)[:2]),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', required=True)
    ap.add_argument('--symbols', default='BTC,ETH')
    ap.add_argument('--crypto', default='BTC,ETH')
    ap.add_argument('--spread', type=float, default=0.0025)
    ap.add_argument('--warmup', type=int, default=150)
    ap.add_argument('--db', default='data/replay.db')
    ap.add_argument('--starting-cash', type=float, default=26.86)
    ap.add_argument('--diagnostic-min-score', type=int)
    ap.add_argument('--review-out')
    a = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)
    symbols = a.symbols.split(',')
    bars = load(a.data_dir, symbols)
    cfg, store, broker, start, end = run(bars, a.spread, a.db, a.starting_cash, a.warmup, set(a.crypto.split(',')),
                                         a.diagnostic_min_score)
    d = collect(store, 0, end + 86400)
    m = d['metrics']
    summary = {
        'label': 'DIAGNOSTIC (not week-1 config)' if a.diagnostic_min_score is not None else 'WEEK_1_VALIDATION_MODE',
        'symbols': symbols, 'spread_assumption': a.spread, 'bars_replayed': int((end - start) / 300),
        'start_equity': a.starting_cash, 'end_equity': round(broker.get_account()['equity'], 4),
        'candidates': len(d['candidates']), 'approved': sum(1 for c in d['candidates'] if c['decision'] == 'approved'),
        'rejection_reasons': dict(d['rejections'].most_common(8)),
        'proposals_by_strategy': dict(Counter(c['strategy'] for c in d['candidates'])),
        'closed_trades': m['n'], 'win_rate': round(m['win_rate'], 3), 'profit_factor': m['profit_factor'],
        'expectancy': round(m['expectancy'], 4), 'total_pnl': round(m['total'], 4),
        'by_strategy_pnl': {s: round(sum(v), 4) for s, v in d['by_strategy'].items()},
        'exit_reasons': dict(Counter(p.exit_reason for p in store.closed_positions_since(0))),
        'kill_switch_events': [f"{k.get('msg')}: {k.get('reason')}" for k in d['kill']],
        'system_errors': dict(Counter(e.get('msg') for e in d['errors'])),
        'forward_outcomes_all_proposals': forward_outcomes(store, bars, cfg),
        'invariants': invariants(cfg, store, broker),
    }
    print(json.dumps(summary, indent=2, default=str))
    if a.review_out:
        with open(a.review_out, 'w') as f:
            f.write(week1_review(store, cfg, start))


if __name__ == '__main__':
    main()
