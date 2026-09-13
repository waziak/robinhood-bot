"""Autonomous loop: verify account -> reconcile -> monitor -> scan -> score -> risk -> execute -> record.

Position management (monitoring, reconciliation, exits) runs every cycle regardless of entry permission.
NO_TRADE is a valid, logged outcome of every cycle."""
import argparse
import logging
import os
import time
import uuid
from collections import Counter
from datetime import datetime, time as dtime

import pytz

from trader import events as ev, scoring, strategies
from trader.market_data import DataError, check_freshness
from trader.models import OrderState, Position
from trader.risk_engine import utc_day_start

ET = pytz.timezone('America/New_York')
UNMANAGED = ('unmanaged', 'broker_test')
TOL = 1e-6


def market_open(now: float = None) -> bool:
    t = datetime.fromtimestamp(now or time.time(), ET)
    return t.weekday() < 5 and dtime(9, 45) <= t.time() < dtime(15, 30)


def regular_session_open(now: float = None) -> bool:
    t = datetime.fromtimestamp(now or time.time(), ET)
    return t.weekday() < 5 and dtime(9, 30) <= t.time() < dtime(16, 0)


def stock_session_closing(now: float = None) -> bool:
    t = datetime.fromtimestamp(now or time.time(), ET)
    return t.weekday() >= 5 or t.time() >= dtime(15, 50) or t.time() < dtime(9, 30)


class Agent:
    def __init__(self, cfg, store, events, data, broker, risk, execution, mode: str, clock=time.time, sleep=time.sleep,
                 scan_interval: int = 60, guard=None):
        assert mode in ('shadow', 'paper', 'live')
        self.cfg, self.store, self.events, self.data, self.broker = cfg, store, events, data, broker
        self.risk, self.execution, self.mode, self.clock, self.sleep = risk, execution, mode, clock, sleep
        self.scan_interval, self.guard = scan_interval, guard
        self.owner = f'{mode}-{os.getpid()}-{uuid.uuid4().hex[:6]}'
        self.trading_enabled = False
        self.unmonitored_since = {}
        self.last_equity_record = 0.0
        self.last_reconcile = 0.0
        self.shadow_open = {}

    # ── fail-safe startup ──────────────────────────────────────────────────
    def startup(self) -> bool:
        e = self.events
        try:
            self.cfg.validate()
        except ValueError as x:
            e.emit(ev.SYSTEM_ERROR, 'invalid risk config', error=str(x))
            return False
        if self.mode == 'live' and (not self.cfg.live_trading_enabled or self.guard is None):
            e.emit(ev.SYSTEM_ERROR, 'live mode requires live_trading_enabled, acknowledgement and an account guard')
            return False
        if not self.store.acquire_lock(self.owner):
            e.emit(ev.KILL_SWITCH, 'another bot instance holds the lock — refusing to start', switch='DUPLICATE_INSTANCE')
            return False
        self.store.set_meta('run', {'mode': self.mode, 'owner': self.owner, 'started': self.clock()})
        e.emit(ev.LIFECYCLE, 'startup', mode=self.mode, owner=self.owner, risk_config=self.cfg.to_dict())
        if self.guard is not None:
            try:
                v = self.guard.verify()
                self.store.set_meta('account', {'last4': v.last4, 'type': v.type, 'verified': True})
            except Exception as x:
                self.store.set_meta('account', {'last4': self.guard.last4, 'verified': False, 'error': str(x)[:200]})
                self.risk.emergency_halt(f'account verification failed at startup: {x}')
                return True
        else:
            self.store.set_meta('account', {'last4': 'n/a', 'type': f'{self.mode} (simulated)', 'verified': True})
        try:
            account = self.broker.get_account()
            self.store.set_meta('broker', {'ok': True})
            self.store.record_equity(account['equity'], account['cash'], f'startup:{self.mode}')
            summary = self.reconcile()
        except Exception as x:
            self.store.set_meta('broker', {'ok': False, 'error': f'{type(x).__name__}: {str(x)[:160]}'})
            e.emit(ev.SYSTEM_ERROR, 'startup verification failed', error=f'{type(x).__name__}: {x}')
            self.risk.stop_new_trades(f'startup verification failed: {x}')
            return True
        halted, reason = self.risk.is_emergency_halted()
        if halted:
            e.emit(ev.KILL_SWITCH, 'emergency halt active at startup — entries blocked', reason=reason)
        try:
            crypto = [s for s in self.cfg.universe if self.cfg.is_crypto(s)]
            ref = crypto[0] if self.cfg.allow_crypto and crypto else self.cfg.universe[0]
            check_freshness(self.data.get_quote(ref), self.data.get_candles(ref), self.cfg, market_open(self.clock()), self.clock())
            self.store.set_meta('last_market_data', {'symbol': ref})
        except Exception as x:
            e.emit(ev.MARKET_DATA, 'market data not fresh at startup', error=str(x))
            self.risk.stop_new_trades(f'market data not fresh at startup: {x}')
        self.trading_enabled = not halted
        self.load_shadow_state()
        e.emit(ev.LIFECYCLE, 'trading loop enabled' if self.trading_enabled else 'monitor-only', mode=self.mode,
               reconciliation=summary)
        return True

    # ── reconciliation: broker truth > local assumptions ──────────────────
    def reconcile(self) -> dict:
        now, summary = self.clock(), Counter()
        for o in self.store.open_orders():
            if self.execution.refresh_order(o).state == OrderState.UNKNOWN:
                summary['UNKNOWN_ORDER'] += 1
        for p in self.store.open_positions():
            if p.status == 'pending_entry':
                self.execution.resolve_entry(p)
            elif p.status == 'exit_pending':
                self.execution.reconcile_exit(p)
        still_unknown = [o for o in self.store.open_orders() if o.state in (OrderState.UNKNOWN, OrderState.SUBMITTING)]
        summary['UNKNOWN_ORDER'] = len(still_unknown)
        if not summary['UNKNOWN_ORDER']:
            del summary['UNKNOWN_ORDER']

        broker_pos, working = self.broker.get_positions(), self.broker.get_open_orders()
        local = {}
        for p in self.store.open_positions():
            if p.status in ('open', 'exit_pending'):
                local.setdefault(p.symbol, []).append(p)
        for sym in sorted(set(broker_pos) | set(local)):
            b, ps = broker_pos.get(sym, 0.0), local.get(sym, [])
            l = sum(p.quantity for p in ps)
            if abs(b - l) <= TOL:
                for p in ps:
                    p.last_reconciled_at = now
                    self.store.upsert_position(p)
                continue
            if b <= TOL:
                category = 'LOCAL_POSITION_NO_BROKER_POSITION'
                for p in ps:
                    p.status, p.exit_time, p.pnl_verified, p.reconciliation = 'closed', now, 0, 'discrepancy'
                    p.exit_reason = 'reconciled: position absent at broker (exit price unverified)'
                    self.store.upsert_position(p)
            elif l <= TOL:
                category = 'BROKER_POSITION_NO_LOCAL_POSITION'
                self.store.upsert_position(Position(str(uuid.uuid4()), sym, 'unmanaged', b, 0.0, 0.0, 0.0, now,
                                                    'broker position with no local record', reconciliation='discrepancy',
                                                    last_reconciled_at=now))
            else:
                category = 'QUANTITY_MISMATCH'
                for p in ps:
                    p.reconciliation = 'discrepancy'
                ps[0].quantity = round(b - sum(p.quantity for p in ps[1:]), 10)
                for p in ps:
                    self.store.upsert_position(p)
            summary[category] += 1
            self.events.emit(ev.SYSTEM_ERROR, category, symbol=sym, broker_qty=b, local_qty=l)

        known = self.store.db.execute('SELECT client_id, broker_id FROM orders').fetchall()
        known_ids = {r['client_id'] for r in known} | {r['broker_id'] for r in known if r['broker_id']}
        for w in working:
            if w.broker_id not in known_ids and w.ref_id not in known_ids:
                summary['UNEXPECTED_OPEN_ORDER'] += 1
                self.events.emit(ev.SYSTEM_ERROR, 'UNEXPECTED_OPEN_ORDER — not cancelled automatically', symbol=w.symbol,
                                 side=w.side, state=w.state)
        if summary:
            self.risk.stop_new_trades(f'reconciliation discrepancies: {dict(summary)}')
        self.last_reconcile = now
        self.store.set_meta('last_reconciliation', {'clean': not summary, 'summary': dict(summary)})
        self.events.emit(ev.LIFECYCLE, 'reconciliation complete', summary=dict(summary), broker_positions=broker_pos)
        return dict(summary)

    # ── position management (never gated by entry permission) ─────────────
    def monitor_positions(self) -> float:
        now, unrealized = self.clock(), 0.0
        for p in self.store.open_positions():
            try:
                if p.status == 'pending_entry':
                    self.execution.resolve_entry(p)
                    continue
                if p.status == 'exit_pending':
                    self.execution.reconcile_exit(p)
                    continue
            except Exception as x:
                self.events.emit(ev.SYSTEM_ERROR, 'in-flight order reconciliation failed', symbol=p.symbol, error=str(x))
                continue
            try:
                q = self.data.get_quote(p.symbol)
                self.risk.record_api_result(True)
                self.store.set_meta('last_market_data', {'symbol': p.symbol})
            except Exception as x:
                self.risk.record_api_result(False, f'quote {p.symbol}')
                first = self.unmonitored_since.setdefault(p.position_id, now)
                if now - first > 300:
                    self.risk.stop_new_trades(f'{p.symbol} position unmonitorable for {now - first:.0f}s')
                self.events.emit(ev.SYSTEM_ERROR, 'cannot price open position', symbol=p.symbol, error=str(x))
                continue
            self.unmonitored_since.pop(p.position_id, None)
            if p.entry_price > 0:
                move = (q.bid - p.entry_price) / p.entry_price
                p.mfe, p.mae = max(p.mfe, move), min(p.mae, move)
                unrealized += (q.bid - p.entry_price) * p.quantity
            self.store.upsert_position(p)
            if p.strategy in UNMANAGED or p.reconciliation != 'ok':
                continue
            reason = None
            if q.bid <= p.stop:
                reason = 'stop'
            elif q.bid >= p.target:
                reason = 'target'
            elif now - p.entry_time >= self.cfg.max_holding_seconds:
                reason = 'time_stop'
            elif not self.cfg.is_crypto(p.symbol) and stock_session_closing(now):
                reason = 'stock_session_close'
            if reason:
                outcome = self.execution.request_exit(p, reason, q.bid, reference_price=q.mid)
                self.events.emit(ev.POSITION_UPDATE, 'exit requested', symbol=p.symbol, reason=reason, outcome=outcome)
        return unrealized

    # ── shadow bookkeeping ─────────────────────────────────────────────────
    def load_shadow_state(self):
        if self.mode != 'shadow':
            return
        for r in self.store.db.execute("SELECT id, symbol, hypothetical_entry, stop, target, ts, quantity FROM candidates "
                                       "WHERE decision='shadow_approved' AND outcome_price IS NULL"):
            self.shadow_open[r['id']] = dict(r)

    def resolve_shadow(self):
        now = self.clock()
        for cid, s in list(self.shadow_open.items()):
            try:
                q = self.data.get_quote(s['symbol'])
            except Exception:
                continue
            if q.bid <= s['stop'] or q.bid >= s['target'] or now - s['ts'] >= self.cfg.max_holding_seconds:
                exit_px = q.bid * (1 - self.cfg.slippage_rate)
                self.store.set_outcome(cid, exit_px, s['hypothetical_entry'])
                self.events.emit(ev.TRADE_EXIT, 'shadow trade resolved', candidate_id=cid, symbol=s['symbol'],
                                 entry=s['hypothetical_entry'], exit=exit_px,
                                 pnl=round((exit_px - s['hypothetical_entry']) * s['quantity'], 4))
                del self.shadow_open[cid]

    def resolve_rejected_outcomes(self):
        for c in self.store.pending_outcomes(self.clock() - 3600)[:10]:
            if c['id'] in self.shadow_open:
                continue
            try:
                self.store.set_outcome(c['id'], self.data.get_quote(c['symbol']).bid, c['hypothetical_entry'])
            except Exception:
                pass

    # ── scanning ───────────────────────────────────────────────────────────
    def scan(self, account: dict, unrealized: float) -> dict:
        now, is_open = self.clock(), market_open(self.clock())
        summary = {'scanned': 0, 'proposals': 0, 'approved': 0, 'executed': 0}
        regimes = {}
        for ref in ('BTC', 'SPY'):
            try:
                regimes[ref] = strategies.regime(self.data.get_candles(ref))
            except Exception:
                regimes[ref] = 'unknown'
        stats = self.strategy_stats()
        for sym in self.cfg.universe:
            crypto = self.cfg.is_crypto(sym)
            if crypto and (not self.cfg.allow_crypto or self.mode == 'live'):
                continue
            if not crypto and (not self.cfg.allow_stocks or not is_open):
                continue
            try:
                candles, quote = self.data.get_candles(sym), self.data.get_quote(sym)
                check_freshness(quote, candles, self.cfg, is_open, now)
                self.risk.record_api_result(True)
                self.store.set_meta('last_market_data', {'symbol': sym})
            except DataError as x:
                self.events.emit(ev.MARKET_DATA, 'symbol skipped', symbol=sym, error=str(x))
                continue
            except Exception as x:
                self.risk.record_api_result(False, f'data {sym}')
                self.events.emit(ev.SYSTEM_ERROR, 'market data failure', symbol=sym, error=f'{type(x).__name__}: {x}')
                continue
            summary['scanned'] += 1
            market_regime = regimes['BTC' if crypto else 'SPY']
            for p in strategies.generate(sym, candles, quote):
                scoring.score(p, market_regime, self.cfg, stats)
                summary['proposals'] += 1
                self.events.emit(ev.SIGNAL, 'proposal', **{k: v for k, v in p.to_dict().items() if k != 'features'})
                d = self.risk.evaluate(p, quote, candles, account, self.store.open_positions(), is_open, unrealized, now)
                state = {'regime': market_regime, 'bid': quote.bid, 'ask': quote.ask, 'spread': quote.spread_pct}
                self.events.emit(ev.RISK_DECISION, d.reason, symbol=sym, strategy=p.strategy, approved=d.approved,
                                 score=p.score, checks=d.checks)
                if not d.approved:
                    self.store.add_candidate(p, 'rejected', d.reason, state, risk_checks=d.checks)
                    continue
                summary['approved'] += 1
                if self.mode == 'shadow':
                    cid = self.store.add_candidate(p, 'shadow_approved', '', state, d.quantity, d.notional, d.checks)
                    self.shadow_open[cid] = {'id': cid, 'symbol': sym, 'hypothetical_entry': d.limit_price, 'stop': p.stop,
                                             'target': p.target, 'ts': now, 'quantity': d.quantity}
                    continue
                cid = self.store.add_candidate(p, 'approved', '', state, d.quantity, d.notional, d.checks)
                if self.execution.open_position(p, d, cid):
                    summary['executed'] += 1
                    account = self.broker.get_account()
        return summary

    def strategy_stats(self) -> dict:
        out = {}
        for p in self.store.closed_positions_since(0):
            if p.strategy in UNMANAGED:
                continue
            s = out.setdefault(p.strategy, {'trades': 0, 'pnl': 0.0})
            s['trades'] += 1
            s['pnl'] += p.realized_pnl
        for s in out.values():
            s['expectancy'] = s['pnl'] / s['trades']
        return out

    # ── loop ───────────────────────────────────────────────────────────────
    def cycle(self):
        if not self.store.heartbeat(self.owner):
            self.risk.emergency_halt('instance lock lost — possible duplicate instance')
            return False
        now = self.clock()
        account = None
        try:
            account = self.broker.get_account()
            self.risk.record_api_result(True)
            self.store.set_meta('broker', {'ok': True})
        except Exception as x:
            self.risk.record_api_result(False, 'account')
            self.store.set_meta('broker', {'ok': False, 'error': f'{type(x).__name__}: {str(x)[:160]}'})
            self.events.emit(ev.SYSTEM_ERROR, 'account balance cannot be verified', error=str(x))
        unrealized = self.monitor_positions()
        if now - self.last_reconcile >= self.cfg.reconcile_interval_seconds:
            try:
                self.reconcile()
            except Exception as x:
                self.risk.stop_new_trades(f'periodic reconciliation failed: {type(x).__name__}')
                self.events.emit(ev.SYSTEM_ERROR, 'periodic reconciliation failed', error=str(x))
        if self.mode == 'shadow':
            self.resolve_shadow()
        self.resolve_rejected_outcomes()
        if account:
            if now - self.last_equity_record >= 300:
                self.store.record_equity(account['equity'], account['cash'], self.mode)
                self.last_equity_record = now
            self.risk.check_portfolio_limits(account, unrealized, now)
        allowed, why = self.risk.entries_allowed(now)
        if account is None:
            allowed, why = False, 'account not verified'
        if not allowed or not self.trading_enabled:
            self.events.emit(ev.LIFECYCLE, 'cycle', decision='NO_TRADE', reason=why or 'monitor-only')
            return True
        summary = self.scan(account, unrealized)
        self.events.emit(ev.LIFECYCLE, 'cycle', decision='TRADE' if summary['executed'] else 'NO_TRADE', **summary)
        return True

    def run(self, duration: float, flatten_on_exit: bool):
        if not self.startup():
            return
        end = self.clock() + duration
        try:
            while self.clock() < end:
                try:
                    if not self.cycle():
                        break
                except Exception as x:
                    self.events.emit(ev.SYSTEM_ERROR, 'cycle crashed', error=f'{type(x).__name__}: {x}')
                    self.risk.record_api_result(False, 'cycle crash')
                self.sleep(self.scan_interval)
        except KeyboardInterrupt:
            self.events.emit(ev.LIFECYCLE, 'interrupted')
        finally:
            if flatten_on_exit and self.mode == 'paper':
                for p in self.store.open_positions():
                    if p.status == 'open' and p.strategy not in UNMANAGED:
                        try:
                            self.execution.request_exit(p, 'session_end', self.data.get_quote(p.symbol).bid)
                        except Exception as x:
                            self.events.emit(ev.SYSTEM_ERROR, 'session-end close failed', symbol=p.symbol, error=str(x))
            from trader import reporting
            path = reporting.write_daily_report(self.store, self.cfg, utc_day_start(self.clock()))
            self.events.emit(ev.LIFECYCLE, 'shutdown', report=path)
            self.store.release_lock(self.owner)


def build(mode: str, db_path: str, starting_cash: float):
    from trader import credentials
    from trader.accounts import AccountGuard
    from trader.broker import PaperBroker, RobinhoodApi, RobinhoodBroker
    from trader.events import EventLog
    from trader.execution import ExecutionEngine
    from trader.market_data import RobinhoodMarketData
    from trader.risk_config import load_risk_config
    from trader.risk_engine import RiskEngine
    from trader.store import Store

    cfg = load_risk_config()
    store = Store(db_path)
    events = EventLog(store)
    ok = credentials.resume(credentials.KeychainStore())
    store.set_meta('auth', {'ok': ok, 'source': 'keychain'})
    if not ok:
        raise SystemExit('No valid Keychain session. Run: venv/bin/python -m trader.credentials login')
    api = RobinhoodApi()
    data = RobinhoodMarketData(cfg)
    guard = AccountGuard(api.account_list)
    if mode == 'live':
        broker = RobinhoodBroker(data, cfg, guard, api)
    else:
        broker = PaperBroker(data, cfg, store.last_cash() if store.last_cash() is not None else starting_cash)
        for p in store.open_positions():
            if p.status in ('open', 'exit_pending'):
                broker.positions[p.symbol] = broker.positions.get(p.symbol, 0) + p.quantity
    risk = RiskEngine(cfg, store, events)
    return Agent(cfg, store, events, data, broker, risk, ExecutionEngine(broker, store, events, risk, cfg), mode,
                 guard=guard if mode == 'live' else None)


def main():
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=('shadow', 'paper', 'live'), default='shadow')
    ap.add_argument('--db', default='data/trader.db')
    ap.add_argument('--duration', type=float, default=5.5 * 3600)
    ap.add_argument('--starting-cash', type=float, default=26.86)
    ap.add_argument('--no-flatten', action='store_true')
    a = ap.parse_args()
    build(a.mode, a.db, a.starting_cash).run(a.duration, flatten_on_exit=not a.no_flatten)


if __name__ == '__main__':
    main()
