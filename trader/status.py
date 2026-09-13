"""Status CLI and manual kill-switch control.

  python -m trader.status                         # dashboard
  python -m trader.status --halt "reason"         # engage EMERGENCY_HALT
  python -m trader.status --clear-halt "reviewed: <why it is safe>"
  python -m trader.status --week1-review <UTC start YYYY-MM-DD>
"""
import argparse
import json
import time
from datetime import datetime, timezone

from trader import events as ev
from trader.risk_config import load_risk_config
from trader.risk_engine import EMERGENCY_HALT, STOP_NEW_TRADES, utc_day_start
from trader.store import Store


def status(store, cfg) -> str:
    now = time.time()
    halt, halt_reason, _ = store.get_flag(EMERGENCY_HALT)
    stop, stop_reason, stop_ts = store.get_flag(STOP_NEW_TRADES)
    stop = stop and stop_ts >= utc_day_start(now)
    lock = store.db.execute("SELECT value, ts FROM flags WHERE name='instance_lock'").fetchone()
    running = bool(lock and now - lock['ts'] < 180)
    start = store.last_event(ev.LIFECYCLE) or {}
    startup = next((json.loads(e['payload']) for e in reversed(store.events_since(0, (ev.LIFECYCLE,)))
                    if json.loads(e['payload']).get('msg') == 'startup'), {})
    eq = store.equity_since(utc_day_start(now))
    closed = store.closed_positions_since(utc_day_start(now))
    realized = sum(p.realized_pnl for p in closed)
    positions = store.open_positions()
    last_scan = store.last_event(ev.MARKET_DATA) or {}
    last_decision = store.last_event(ev.RISK_DECISION) or {}
    last_error = store.last_event(ev.SYSTEM_ERROR) or {}
    bot = 'HALTED' if halt or cfg.emergency_stop else ('PAUSED' if stop else ('RUNNING' if running else 'STOPPED'))

    def ago(ts):
        return f'{now - ts:.0f}s ago' if ts else 'never'

    lines = [
        f"MODE:                 {'LIVE' if startup.get('mode') == 'live' else (startup.get('mode') or 'unknown').upper()}",
        f'BOT:                  {bot}',
        f"EQUITY:               {'$%.2f' % eq[-1]['equity'] if eq else 'unverified today'}",
        f"TODAY P&L:            {'$%+.2f' % (eq[-1]['equity'] - eq[0]['equity']) if len(eq) > 1 else 'n/a'} (realized ${realized:+.2f})",
        f'OPEN POSITIONS:       {len(positions)} ' + ', '.join(f'{p.symbol}×{p.quantity:g}@{p.entry_price:.2f}[{p.status}]' for p in positions),
        f'TRADES TODAY:         {len(store.positions_entered_since(utc_day_start(now)))} / {cfg.max_trades_per_day}',
        f'DAILY LOSS REMAINING: ${max(0.0, cfg.max_daily_loss + min(0.0, realized)):.2f} of ${cfg.max_daily_loss:.2f}',
        'CURRENT STRATEGY:     trend_pullback, breakout, mean_reversion (min score %d)' % cfg.minimum_signal_score,
        f"LAST MARKET SCAN:     {ago(start.get('ts'))}  {last_scan.get('msg', '')} {last_scan.get('symbol', '')}",
        f"LAST DECISION:        {last_decision.get('symbol', '-')} {last_decision.get('msg', '-')}",
        f"LAST ERROR:           {last_error.get('msg', 'none')} {last_error.get('error', '')}",
        f"RISK STATUS:          {'EMERGENCY_HALT: ' + halt_reason if halt else ('STOP_NEW_TRADES: ' + stop_reason if stop else 'normal')}"
        f"{' | live trading ENABLED' if cfg.live_trading_enabled else ' | live trading disabled'}",
    ]
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default='data/trader.db')
    ap.add_argument('--halt')
    ap.add_argument('--clear-halt')
    ap.add_argument('--week1-review')
    a = ap.parse_args()
    store, cfg = Store(a.db), load_risk_config()
    log = ev.EventLog(store)
    if a.halt:
        store.set_flag(EMERGENCY_HALT, True, f'manual: {a.halt}')
        log.emit(ev.KILL_SWITCH, 'EMERGENCY_HALT engaged manually', reason=a.halt)
    if a.clear_halt:
        if len(a.clear_halt.strip()) < 10:
            raise SystemExit('Provide a real review note (>=10 chars) explaining why clearing the halt is safe.')
        store.set_flag(EMERGENCY_HALT, False, f'cleared manually: {a.clear_halt}')
        log.emit(ev.KILL_SWITCH, 'EMERGENCY_HALT cleared manually', reason=a.clear_halt)
    if a.week1_review:
        from trader.reporting import week1_review
        start = datetime.strptime(a.week1_review, '%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp()
        import os
        os.makedirs('reports', exist_ok=True)
        with open('reports/WEEK_1_REVIEW.md', 'w') as f:
            f.write(week1_review(store, cfg, start))
        print('wrote reports/WEEK_1_REVIEW.md')
    print(status(store, cfg))


if __name__ == '__main__':
    main()
