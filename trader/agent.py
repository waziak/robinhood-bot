"""Autonomous loop: observe -> monitor -> reconcile -> scan -> score -> risk -> execute -> record -> evaluate.
NO_TRADE is a valid, logged outcome of every cycle."""
import argparse
import logging
import os
import time
import uuid
from datetime import datetime, time as dtime

import pytz

from trader import events as ev, scoring, strategies
from trader.market_data import DataError, check_freshness
from trader.models import OrderState
from trader.risk_engine import utc_day_start

ET = pytz.timezone('America/New_York')


def market_open(now: float = None) -> bool:
    t = datetime.fromtimestamp(now or time.time(), ET)
    return t.weekday() < 5 and dtime(9, 45) <= t.time() < dtime(15, 30)


def stock_session_closing(now: float = None) -> bool:
    t = datetime.fromtimestamp(now or time.time(), ET)
    return t.weekday() >= 5 or t.time() >= dtime(15, 50) or t.time() < dtime(9, 30)


class Agent:
    def __init__(self, cfg, store, events, data, broker, risk, execution, mode: str, clock=time.time, sleep=time.sleep,
                 scan_interval: int = 60):
        assert mode in ('shadow', 'paper', 'live')
        self.cfg, self.store, self.events, self.data, self.broker = cfg, store, events, data, broker
        self.risk, self.execution, self.mode, self.clock, self.sleep = risk, execution, mode, clock, sleep
        self.scan_interval = scan_interval
        self.owner = f'{mode}-{os.getpid()}-{uuid.uuid4().hex[:6]}'
        self.trading_enabled = False
        self.unmonitored_since = {}
        self.last_equity_record = 0.0
        self.shadow_open = {}

    # ── fail-safe startup ──────────────────────────────────────────────────
    def startup(self) -> bool:
        e = self.events
        try:
            self.cfg.validate()
        except ValueError as x:
            e.emit(ev.SYSTEM_ERROR, 'invalid risk config', error=str(x))
            return False
        if self.mode == 'live' and not self.cfg.live_trading_enabled:
            e.emit(ev.SYSTEM_ERROR, 'live mode requested but live trading is not enabled/acknowledged')
            return False
        if not self.store.acquire_lock(self.owner):
            e.emit(ev.KILL_SWITCH, 'another bot instance holds the lock — refusing to start', switch='DUPLICATE_INSTANCE')
            return False
        e.emit(ev.LIFECYCLE, 'startup', mode=self.mode, owner=self.owner, risk_config=self.cfg.to_dict())
        try:
            account = self.broker.get_account()
            self.store.record_equity(account['equity'], account['cash'], f'startup:{self.mode}')
            self.reconcile()
        except Exception as x:
            e.emit(ev.SYSTEM_ERROR, 'startup verification failed', error=f'{type(x).__name__}: {x}')
            self.risk.stop_new_trades(f'startup verification failed: {x}')
            return True  # keep running in monitor-only mode; entries stay blocked
        halted, reason = self.risk.is_emergency_halted()
        if halted:
            e.emit(ev.KILL_SWITCH, 'emergency halt active at startup — no orders will be placed', reason=reason)
        try:
            crypto_in_universe = [s for s in self.cfg.universe if self.cfg.is_crypto(s)]
            ref = crypto_in_universe[0] if self.cfg.allow_crypto and crypto_in_universe else self.cfg.universe[0]
            check_freshness(self.data.get_quote(ref), self.data.get_candles(ref), self.cfg, market_open(self.clock()),
                            self.clock())
        except Exception as x:
            e.emit(ev.MARKET_DATA, 'market data not fresh at startup', error=str(x))
            self.risk.stop_new_trades(f'market data not fresh at startup: {x}')
        self.trading_enabled = not halted
        self.load_shadow_state()
        e.emit(ev.LIFECYCLE, 'trading loop enabled' if self.trading_enabled else 'monitor-only', mode=self.mode)
        return True

    def reconcile(self):
        for o in self.store.open_orders():
            try:
                st = (self.broker.get_order_status(o.broker_id) if o.broker_id
                      else self.broker.find_recent_order(o.symbol, o.side, o.quantity, o.created_at))
            except Exception as x:
                st = None
                self.events.emit(ev.SYSTEM_ERROR, 'reconcile: order lookup failed', client_id=o.client_id, error=str(x))
            if st is None:
                if o.broker_id:
                    self.risk.emergency_halt(f'reconcile: cannot verify order {o.client_id}')
                    continue
                o.state, o.error = OrderState.CANCELLED, 'not found at broker during reconciliation'
            else:
                o.broker_id = st.broker_id
                o.state, o.filled_qty, o.avg_fill_price, o.fees = st.state, st.filled_qty, st.avg_fill_price, st.fees
                if o.state not in OrderState.TERMINAL:
                    self.broker.cancel_order(o.broker_id)
                    self.risk.stop_new_trades('reconcile: cancelled a working order left from a previous run')
            self.store.upsert_order(o)
            self.events.emit(ev.ORDER_UPDATE, 'reconciled', client_id=o.client_id, state=o.state, filled=o.filled_qty)

        for p in self.store.open_positions():
            rows = self.store.db.execute('SELECT client_id FROM orders WHERE position_id=? ORDER BY created_at',
                                         (p.position_id,)).fetchall()
            orders = [self.store.get_order(r['client_id']) for r in rows]
            if p.status == 'pending_entry':
                entry = next((o for o in orders if o.purpose == 'entry'), None)
                if entry and entry.filled_qty > 0 and entry.state in OrderState.TERMINAL:
                    p.quantity, p.entry_price, p.fees, p.status = entry.filled_qty, entry.avg_fill_price, entry.fees, 'open'
                elif entry is None or entry.state in OrderState.TERMINAL:
                    p.status, p.exit_reason = 'cancelled', 'entry never filled (reconciled)'
                self.store.upsert_position(p)
            elif p.status == 'closing':
                p.status = 'open'
                self.store.upsert_position(p)
                self.risk.stop_new_trades(f'reconcile: {p.symbol} exit was in flight at last shutdown')

        broker_pos = self.broker.get_positions()
        local = {}
        for p in self.store.open_positions():
            if p.status == 'open':
                local[p.symbol] = local.get(p.symbol, 0) + p.quantity
        for sym in set(broker_pos) | set(local):
            b, l = broker_pos.get(sym, 0.0), local.get(sym, 0.0)
            if abs(b - l) > max(1e-6, 1e-4 * max(b, l)):
                self.risk.emergency_halt(f'position mismatch {sym}: broker={b} local={l}')
        tracked = {o.broker_id for o in self.store.open_orders()} | {
            r['broker_id'] for r in self.store.db.execute('SELECT broker_id FROM orders')}
        for st in self.broker.get_open_orders():
            if st.broker_id not in tracked:
                self.risk.emergency_halt(f'untracked open order at broker: {getattr(st, "symbol", "?")}')
        self.events.emit(ev.LIFECYCLE, 'reconciliation complete', broker_positions=broker_pos, local_positions=local)

    # ── monitoring ─────────────────────────────────────────────────────────
    def monitor_positions(self) -> float:
        now, unrealized = self.clock(), 0.0
        for p in self.store.open_positions():
            if p.status != 'open':
                continue
            try:
                q = self.data.get_quote(p.symbol)
                self.risk.record_api_result(True)
            except Exception as x:
                self.risk.record_api_result(False, f'quote {p.symbol}')
                first = self.unmonitored_since.setdefault(p.position_id, now)
                if now - first > 300:
                    self.risk.stop_new_trades(f'{p.symbol} position unmonitorable for {now - first:.0f}s')
                self.events.emit(ev.SYSTEM_ERROR, 'cannot price open position', symbol=p.symbol, error=str(x))
                continue
            self.unmonitored_since.pop(p.position_id, None)
            move = (q.bid - p.entry_price) / p.entry_price
            p.mfe, p.mae = max(p.mfe, move), min(p.mae, move)
            unrealized += (q.bid - p.entry_price) * p.quantity
            reason = None
            if q.bid <= p.stop:
                reason = 'stop'
            elif q.bid >= p.target:
                reason = 'target'
            elif now - p.entry_time >= self.cfg.max_holding_seconds:
                reason = 'time_stop'
            elif not self.cfg.is_crypto(p.symbol) and stock_session_closing(now):
                reason = 'stock_session_close'
            self.store.upsert_position(p)
            if reason:
                self.execution.close_position(p, reason, q.bid)
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
            hit = q.bid <= s['stop'] or q.bid >= s['target'] or now - s['ts'] >= self.cfg.max_holding_seconds
            if hit:
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
            if (crypto and not self.cfg.allow_crypto) or (not crypto and (not self.cfg.allow_stocks or not is_open)):
                continue
            try:
                candles, quote = self.data.get_candles(sym), self.data.get_quote(sym)
                check_freshness(quote, candles, self.cfg, is_open, now)
                self.risk.record_api_result(True)
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
        try:
            account = self.broker.get_account()
            self.risk.record_api_result(True)
        except Exception as x:
            self.risk.record_api_result(False, 'account')
            self.events.emit(ev.SYSTEM_ERROR, 'account balance cannot be verified', error=str(x))
            account = None
        unrealized = self.monitor_positions()
        if self.mode == 'shadow':
            self.resolve_shadow()
        self.resolve_rejected_outcomes()
        if account:
            if self.clock() - self.last_equity_record >= 300:
                self.store.record_equity(account['equity'], account['cash'], self.mode)
                self.last_equity_record = self.clock()
            self.risk.check_portfolio_limits(account, unrealized, self.clock())
        blocked, why = self.risk.new_trades_blocked(self.clock())
        if account is None:
            blocked, why = True, 'account not verified'
        if blocked or not self.trading_enabled:
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
                    if p.status == 'open':
                        try:
                            self.execution.close_position(p, 'session_end', self.data.get_quote(p.symbol).bid)
                        except Exception as x:
                            self.events.emit(ev.SYSTEM_ERROR, 'session-end close failed', symbol=p.symbol, error=str(x))
            from trader import reporting
            path = reporting.write_daily_report(self.store, self.cfg, utc_day_start(self.clock()))
            self.events.emit(ev.LIFECYCLE, 'shutdown', report=path)
            self.store.release_lock(self.owner)


def build(mode: str, db_path: str, starting_cash: float, account_number: str = None):
    import robin_stocks.robinhood as rh
    import session_auth
    from trader.broker import PaperBroker, RobinhoodBroker
    from trader.events import EventLog
    from trader.execution import ExecutionEngine
    from trader.market_data import RobinhoodMarketData
    from trader.risk_config import load_risk_config
    from trader.risk_engine import RiskEngine
    from trader.store import Store

    cfg = load_risk_config()
    store = Store(db_path)
    events = EventLog(store)
    if not session_auth.authenticate(os.getenv('RH_USERNAME'), os.getenv('RH_PASSWORD')):
        raise SystemExit('Robinhood authentication could not be verified — refusing to start')
    data = RobinhoodMarketData(cfg, rh)
    if mode == 'live':
        broker = RobinhoodBroker(data, cfg, account_number or os.getenv('RH_ACCOUNT_NUMBER'), rh)
    else:
        broker = PaperBroker(data, cfg, store.last_cash() if store.last_cash() is not None else starting_cash)
        for p in store.open_positions():
            if p.status == 'open':
                broker.positions[p.symbol] = broker.positions.get(p.symbol, 0) + p.quantity
    risk = RiskEngine(cfg, store, events)
    return Agent(cfg, store, events, data, broker, risk, ExecutionEngine(broker, store, events, risk, cfg), mode)


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
