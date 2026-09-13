"""Status CLI and manual kill-switch control. Never displays secrets.

  python -m trader.status                         # dashboard
  python -m trader.status --halt "reason"         # engage EMERGENCY_HALT
  python -m trader.status --clear-halt "reviewed: <why it is safe>"
  python -m trader.status --week1-review <UTC start YYYY-MM-DD>
"""
import argparse
import os
import time
from datetime import datetime, timezone

from trader import events as ev
from trader.risk_config import load_risk_config
from trader.risk_engine import EMERGENCY_HALT, STOP_NEW_TRADES, utc_day_start
from trader.store import Store


def _ago(ts, now):
    return f'{now - ts:.0f}s ago' if ts else 'never'


def _evt(e, now, *keys):
    if not e:
        return 'none'
    extra = ' '.join(str(e.get(k)) for k in keys if e.get(k) not in (None, ''))
    return f"{e.get('msg', '')} {extra} ({_ago(e.get('ts'), now)})".strip()


def status(store, cfg, cred_status: dict = None, now: float = None) -> str:
    now = now or time.time()
    day = utc_day_start(now)
    halt, halt_reason, _ = store.get_flag(EMERGENCY_HALT)
    stop, stop_reason, stop_ts = store.get_flag(STOP_NEW_TRADES)
    stop = stop and stop_ts >= day
    lock = store.db.execute("SELECT value, ts FROM flags WHERE name='instance_lock'").fetchone()
    running = bool(lock and now - lock['ts'] < 180)
    run, acct, auth, broker = store.get_meta('run'), store.get_meta('account'), store.get_meta('auth'), store.get_meta('broker')
    recon, mkt = store.get_meta('last_reconciliation'), store.get_meta('last_market_data')
    eq = store.equity_since(day)
    realized = sum(p.realized_pnl for p in store.closed_positions_since(day))
    positions, orders = store.open_positions(), store.open_orders()
    last_exec = max([e for e in (store.last_event(ev.ORDER_UPDATE), store.last_event(ev.ORDER_SUBMITTED),
                                 store.last_event(ev.TRADE_EXIT)) if e], key=lambda e: e.get('ts', 0), default=None)
    bot = 'HALTED' if halt or cfg.emergency_stop else ('RUNNING' if running else 'STOPPED')
    if halt or cfg.emergency_stop:
        entries = 'BLOCKED — emergency halt'
    elif stop:
        entries = f'BLOCKED — STOP_NEW_TRADES: {stop_reason}'
    elif not cfg.live_trading_enabled and run.get('mode') == 'live':
        entries = 'BLOCKED — live trading disabled'
    else:
        entries = 'allowed'
    cred = cred_status or {}
    auth_line = (f"{'verified' if auth.get('ok') else 'NOT verified'} via {auth.get('source', '?')} ({_ago(auth.get('_ts'), now)})"
                 if auth else 'no authentication recorded')
    if cred:
        auth_line += (f" | keychain session: {'yes' if cred.get('session_stored') else 'no'}"
                      f"{', plaintext session files present!' if cred.get('legacy_plaintext_session_files') else ''}")
    rows = [
        ('MODE', f"{(run.get('mode') or 'unknown').upper()} | bot {bot}"),
        ('ACCOUNT LAST4', f"••••{acct.get('last4', '????')} {acct.get('type', '')} "
                          f"{'verified' if acct.get('verified') else 'NOT VERIFIED ' + str(acct.get('error', ''))} ({_ago(acct.get('_ts'), now)})"
                          if acct else 'not verified'),
        ('AUTH STATUS', auth_line),
        ('BROKER CONNECTION', (f"{'ok' if broker.get('ok') else 'ERROR ' + str(broker.get('error', ''))} ({_ago(broker.get('_ts'), now)})"
                               if broker else 'no contact recorded')),
        ('EMERGENCY HALT', f'ENGAGED: {halt_reason}' if halt else ('ENGAGED: EMERGENCY_STOP env' if cfg.emergency_stop else 'off')),
        ('NEW-TRADE STATUS', entries),
        ('OPEN POSITIONS', f'{len(positions)} ' + ', '.join(
            f'{p.symbol}×{p.quantity:g}@{p.entry_price:.2f} stop {p.stop:.2f} [{p.status}{"/" + p.reconciliation if p.reconciliation != "ok" else ""}]'
            for p in positions)),
        ('OPEN ORDERS', f'{len(orders)} ' + ', '.join(f'{o.side} {o.quantity:g} {o.symbol} [{o.state}]' for o in orders)),
        ('CASH', f"${eq[-1]['cash']:.2f}" if eq else 'unverified today'),
        ('EQUITY', f"${eq[-1]['equity']:.2f}" if eq else 'unverified today'),
        ('DAILY P&L', f"${eq[-1]['equity'] - eq[0]['equity']:+.2f} (realized ${realized:+.2f})" if len(eq) > 1 else f'realized ${realized:+.2f}'),
        ('DAILY LOSS LIMIT', f'${max(0.0, cfg.max_daily_loss + min(0.0, realized)):.2f} remaining of ${cfg.max_daily_loss:.2f}'),
        ('TRADES TODAY', f'{len(store.positions_entered_since(day))} / {cfg.max_trades_per_day}'),
        ('LAST RECONCILIATION', (f"{'clean' if recon.get('clean') else 'DISCREPANCIES ' + str(recon.get('summary'))} ({_ago(recon.get('_ts'), now)})"
                                 if recon else 'never')),
        ('LAST MARKET DATA', f"{mkt.get('symbol')} ({_ago(mkt.get('_ts'), now)})" if mkt else 'never'),
        ('LAST SIGNAL', _evt(store.last_event(ev.SIGNAL), now, 'symbol', 'strategy', 'score')),
        ('LAST RISK REJECTION', _evt(store.last_event(ev.RISK_DECISION, lambda e: e.get('approved') is False), now, 'symbol', 'strategy')),
        ('LAST EXECUTION EVENT', _evt(last_exec, now, 'symbol', 'side', 'state')),
        ('LAST ERROR', _evt(store.last_event(ev.SYSTEM_ERROR), now, 'symbol', 'error')),
    ]
    return '\n'.join(f'{k + ":":<22}{v}' for k, v in rows)


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
        os.makedirs('reports', exist_ok=True)
        with open('reports/WEEK_1_REVIEW.md', 'w') as f:
            f.write(week1_review(store, cfg, start))
        print('wrote reports/WEEK_1_REVIEW.md')
    cred = None
    try:
        from trader import credentials
        cred = credentials.status(credentials.KeychainStore())
    except Exception:
        pass
    print(status(store, cfg, cred))


if __name__ == '__main__':
    main()
