"""SQLite persistence: candidates (incl. rejections), orders, positions, events, flags, meta, instance lock."""
import json
import os
import socket
import sqlite3
import time
from dataclasses import asdict, fields
from typing import Optional

from trader.models import Order, OrderState, Position


def _cols(cls, types: dict) -> str:
    return ', '.join(f'{f.name} {types.get(f.name, "")}'.strip() for f in fields(cls))


SCHEMA = f"""
CREATE TABLE IF NOT EXISTS candidates (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, symbol TEXT, strategy TEXT, score INTEGER,
  decision TEXT, rejection_reason TEXT, hypothetical_entry REAL, stop REAL, target REAL,
  reward_risk REAL, quantity REAL, notional REAL, market_state TEXT, proposal TEXT, risk_checks TEXT,
  outcome_price REAL, outcome_ts REAL, hypothetical_return REAL
);
CREATE TABLE IF NOT EXISTS orders ({_cols(Order, {'client_id': 'TEXT PRIMARY KEY'})});
CREATE TABLE IF NOT EXISTS positions ({_cols(Position, {'position_id': 'TEXT PRIMARY KEY'})});
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, kind TEXT, payload TEXT);
CREATE TABLE IF NOT EXISTS flags (name TEXT PRIMARY KEY, value TEXT, reason TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS meta (name TEXT PRIMARY KEY, value TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS equity (ts REAL, equity REAL, cash REAL, source TEXT);
CREATE INDEX IF NOT EXISTS idx_candidates_ts ON candidates(ts);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
CREATE INDEX IF NOT EXISTS idx_orders_broker ON orders(broker_id);
"""

_ORDER_FIELDS = {f.name for f in fields(Order)}
_POSITION_FIELDS = {f.name for f in fields(Position)}


class Store:
    def __init__(self, path: str, clock=time.time):
        self.clock = clock
        if path != ':memory:':
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.path = path
        self.db = sqlite3.connect(path, isolation_level=None, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL' if path != ':memory:' else 'PRAGMA journal_mode=MEMORY')
        self.db.executescript(SCHEMA)

    # ── flags / kill switches / meta ───────────────────────────────────────
    def set_flag(self, name: str, value: bool, reason: str = ''):
        self.db.execute('INSERT OR REPLACE INTO flags(name, value, reason, ts) VALUES (?,?,?,?)',
                        (name, 'true' if value else 'false', reason, self.clock()))

    def get_flag(self, name: str) -> tuple:
        row = self.db.execute('SELECT value, reason, ts FROM flags WHERE name=?', (name,)).fetchone()
        if not row:
            return False, '', 0.0
        return row['value'] == 'true', row['reason'], row['ts']

    def set_meta(self, name: str, value: dict):
        self.db.execute('INSERT OR REPLACE INTO meta(name, value, ts) VALUES (?,?,?)',
                        (name, json.dumps(value, default=str), self.clock()))

    def get_meta(self, name: str) -> dict:
        row = self.db.execute('SELECT value, ts FROM meta WHERE name=?', (name,)).fetchone()
        return {**json.loads(row['value']), '_ts': row['ts']} if row else {}

    # ── single-instance lock ───────────────────────────────────────────────
    def acquire_lock(self, owner: str, stale_after: int = 180) -> bool:
        now = self.clock()
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row = self.db.execute("SELECT value, ts FROM flags WHERE name='instance_lock'").fetchone()
            if row and row['value'] != owner and now - row['ts'] < stale_after:
                self.db.execute('ROLLBACK')
                return False
            self.db.execute("INSERT OR REPLACE INTO flags(name, value, reason, ts) VALUES ('instance_lock', ?, ?, ?)",
                            (owner, socket.gethostname(), now))
            self.db.execute('COMMIT')
            return True
        except Exception:
            self.db.execute('ROLLBACK')
            raise

    def heartbeat(self, owner: str) -> bool:
        cur = self.db.execute("UPDATE flags SET ts=? WHERE name='instance_lock' AND value=?", (self.clock(), owner))
        return cur.rowcount == 1

    def release_lock(self, owner: str):
        self.db.execute("DELETE FROM flags WHERE name='instance_lock' AND value=?", (owner,))

    # ── orders ─────────────────────────────────────────────────────────────
    def upsert_order(self, o: Order):
        o.updated_at = self.clock()
        d = asdict(o)
        self.db.execute(f'INSERT OR REPLACE INTO orders({",".join(d)}) VALUES ({",".join("?" * len(d))})', tuple(d.values()))

    @staticmethod
    def _order(row) -> Order:
        return Order(**{k: row[k] for k in row.keys() if k in _ORDER_FIELDS})

    def get_order(self, client_id: str) -> Optional[Order]:
        row = self.db.execute('SELECT * FROM orders WHERE client_id=?', (client_id,)).fetchone()
        return self._order(row) if row else None

    def order_by_broker_id(self, broker_id: str) -> Optional[Order]:
        row = self.db.execute('SELECT * FROM orders WHERE broker_id=?', (broker_id,)).fetchone()
        return self._order(row) if row else None

    def open_orders(self) -> list:
        q = f"SELECT * FROM orders WHERE state IN ({','.join('?' * len(OrderState.OPEN))}) ORDER BY created_at"
        return [self._order(r) for r in self.db.execute(q, tuple(OrderState.OPEN))]

    def orders_for_position(self, position_id: str) -> list:
        return [self._order(r) for r in
                self.db.execute('SELECT * FROM orders WHERE position_id=? ORDER BY created_at', (position_id,))]

    def orders_since(self, ts: float) -> list:
        return [self._order(r) for r in self.db.execute('SELECT * FROM orders WHERE created_at>=? ORDER BY created_at', (ts,))]

    # ── positions ──────────────────────────────────────────────────────────
    def upsert_position(self, p: Position):
        d = asdict(p)
        self.db.execute(f'INSERT OR REPLACE INTO positions({",".join(d)}) VALUES ({",".join("?" * len(d))})', tuple(d.values()))

    @staticmethod
    def _position(row) -> Position:
        return Position(**{k: row[k] for k in row.keys() if k in _POSITION_FIELDS})

    def open_positions(self) -> list:
        q = f"SELECT * FROM positions WHERE status IN ({','.join('?' * len(Position.ACTIVE))}) ORDER BY entry_time"
        return [self._position(r) for r in self.db.execute(q, Position.ACTIVE)]

    def get_position(self, position_id: str) -> Optional[Position]:
        row = self.db.execute('SELECT * FROM positions WHERE position_id=?', (position_id,)).fetchone()
        return self._position(row) if row else None

    def closed_positions_since(self, ts: float) -> list:
        return [self._position(r) for r in
                self.db.execute("SELECT * FROM positions WHERE status='closed' AND exit_time>=? ORDER BY exit_time", (ts,))]

    def positions_entered_since(self, ts: float) -> list:
        return [self._position(r) for r in self.db.execute(
            "SELECT * FROM positions WHERE entry_time>=? AND status!='cancelled' AND strategy!='unmanaged'", (ts,))]

    # ── candidates ─────────────────────────────────────────────────────────
    def add_candidate(self, proposal, decision: str, reason: str, market_state: dict,
                      quantity: float = 0.0, notional: float = 0.0, risk_checks: dict = None) -> int:
        cur = self.db.execute(
            'INSERT INTO candidates(ts, symbol, strategy, score, decision, rejection_reason, hypothetical_entry, stop, '
            'target, reward_risk, quantity, notional, market_state, proposal, risk_checks) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (self.clock(), proposal.symbol, proposal.strategy, proposal.score, decision, reason, proposal.entry,
             proposal.stop, proposal.target, proposal.estimated_reward_risk, quantity, notional,
             json.dumps(market_state, default=str), json.dumps(proposal.to_dict(), default=str),
             json.dumps(risk_checks or {}, default=str)))
        return cur.lastrowid

    def pending_outcomes(self, older_than: float) -> list:
        return [dict(r) for r in self.db.execute(
            'SELECT id, symbol, hypothetical_entry, ts FROM candidates WHERE outcome_price IS NULL AND ts<=?', (older_than,))]

    def set_outcome(self, cid: int, price: float, entry: float):
        self.db.execute('UPDATE candidates SET outcome_price=?, outcome_ts=?, hypothetical_return=? WHERE id=?',
                        (price, self.clock(), (price - entry) / entry if entry else None, cid))

    def candidates_since(self, ts: float) -> list:
        return [dict(r) for r in self.db.execute('SELECT * FROM candidates WHERE ts>=? ORDER BY ts', (ts,))]

    # ── events / equity ────────────────────────────────────────────────────
    def add_event(self, kind: str, payload: dict):
        self.db.execute('INSERT INTO events(ts, kind, payload) VALUES (?,?,?)',
                        (payload.get('ts', self.clock()), kind, json.dumps(payload, default=str)))

    def events_since(self, ts: float, kinds: tuple = None) -> list:
        rows = self.db.execute('SELECT * FROM events WHERE ts>=? ORDER BY id', (ts,)).fetchall()
        return [dict(r) for r in rows if not kinds or r['kind'] in kinds]

    def last_event(self, kind: str, where=None) -> Optional[dict]:
        for row in self.db.execute('SELECT payload FROM events WHERE kind=? ORDER BY id DESC LIMIT 500', (kind,)):
            p = json.loads(row['payload'])
            if where is None or where(p):
                return p
        return None

    def record_equity(self, equity: float, cash: float, source: str):
        self.db.execute('INSERT INTO equity(ts, equity, cash, source) VALUES (?,?,?,?)', (self.clock(), equity, cash, source))

    def equity_since(self, ts: float) -> list:
        return [dict(r) for r in self.db.execute('SELECT * FROM equity WHERE ts>=? ORDER BY ts', (ts,))]

    def peak_equity(self) -> Optional[float]:
        row = self.db.execute('SELECT MAX(equity) AS m FROM equity').fetchone()
        return row['m'] if row and row['m'] is not None else None

    def first_equity(self) -> Optional[dict]:
        row = self.db.execute('SELECT * FROM equity ORDER BY ts LIMIT 1').fetchone()
        return dict(row) if row else None

    def last_cash(self) -> Optional[float]:
        row = self.db.execute('SELECT cash FROM equity ORDER BY ts DESC LIMIT 1').fetchone()
        return row['cash'] if row else None
