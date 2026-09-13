import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Quote:
    symbol: str
    bid: float
    ask: float
    last: float
    timestamp: float

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2

    @property
    def spread_pct(self) -> float:
        return (self.ask - self.bid) / self.mid if self.mid > 0 else float('inf')

    def age(self, now: float = None) -> float:
        return (now or time.time()) - self.timestamp


@dataclass
class Candle:
    ts: float
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Proposal:
    symbol: str
    strategy: str
    direction: str
    entry: float
    stop: float
    target: float
    confidence: float
    reasoning: str
    invalidation: str
    timestamp: float = field(default_factory=time.time)
    features: dict = field(default_factory=dict)
    score: int = 0
    score_breakdown: dict = field(default_factory=dict)

    @property
    def risk_per_unit(self) -> float:
        return self.entry - self.stop

    @property
    def estimated_reward_risk(self) -> float:
        r = self.risk_per_unit
        return (self.target - self.entry) / r if r > 0 else 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d['estimated_reward_risk'] = round(self.estimated_reward_risk, 3)
        return d


@dataclass
class RiskDecision:
    approved: bool
    reason: str
    quantity: float = 0.0
    notional: float = 0.0
    limit_price: float = 0.0
    max_loss: float = 0.0
    checks: dict = field(default_factory=dict)


class OrderState:
    CREATED = 'created'              # persisted intent, nothing sent
    SUBMITTING = 'submitting'        # network call in flight; a crash here means UNKNOWN
    SUBMITTED = 'submitted'          # broker returned an id
    ACKNOWLEDGED = 'acknowledged'    # broker confirmed working
    PARTIALLY_FILLED = 'partially_filled'
    FILLED = 'filled'
    CANCELLED = 'cancelled'
    REJECTED = 'rejected'
    EXPIRED = 'expired'
    UNKNOWN = 'unknown'              # may or may not exist at the broker — never treated as filled or failed

    TERMINAL = {FILLED, CANCELLED, REJECTED, EXPIRED}
    OPEN = {CREATED, SUBMITTING, SUBMITTED, ACKNOWLEDGED, PARTIALLY_FILLED, UNKNOWN}
    _RANK = {CREATED: 0, SUBMITTING: 1, SUBMITTED: 2, ACKNOWLEDGED: 3, PARTIALLY_FILLED: 4,
             FILLED: 5, CANCELLED: 5, REJECTED: 5, EXPIRED: 5}

    @classmethod
    def is_regression(cls, old: str, new: str) -> bool:
        """A broker report that would move an order backwards is stale and must be ignored."""
        if old == cls.UNKNOWN or new == cls.UNKNOWN:
            return False
        if old in cls.TERMINAL:
            return new != old
        return cls._RANK.get(new, 0) < cls._RANK.get(old, 0)


@dataclass
class Order:
    client_id: str
    symbol: str
    side: str
    quantity: float
    limit_price: float
    state: str = OrderState.CREATED
    broker_id: Optional[str] = None
    filled_qty: float = 0.0
    avg_fill_price: float = 0.0
    fees: float = 0.0
    purpose: str = ''
    position_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    error: str = ''
    broker_updated_at: float = 0.0
    submitted_at: float = 0.0

    @staticmethod
    def new_client_id() -> str:
        return str(uuid.uuid4())


@dataclass
class BrokerOrderStatus:
    broker_id: str
    state: str
    filled_qty: float
    avg_fill_price: float
    fees: float = 0.0
    raw_state: str = ''
    symbol: str = ''
    side: str = ''
    quantity: float = 0.0
    ref_id: str = ''
    account: str = ''
    updated_at: float = 0.0
    created_at: float = 0.0


@dataclass
class Position:
    position_id: str                 # also the trade id
    symbol: str
    strategy: str
    quantity: float
    entry_price: float
    stop: float
    target: float
    entry_time: float
    reason: str
    status: str = 'open'             # pending_entry | open | exit_pending | closed | cancelled
    realized_pnl: float = 0.0
    fees: float = 0.0
    exit_price: float = 0.0
    exit_time: float = 0.0
    exit_reason: str = ''
    mfe: float = 0.0
    mae: float = 0.0
    candidate_id: Optional[int] = None
    intended_entry: float = 0.0
    initial_stop: float = 0.0
    entry_order_id: Optional[str] = None
    exit_order_id: Optional[str] = None
    reconciliation: str = 'ok'       # ok | discrepancy  (discrepancy = frozen: no automated orders)
    last_reconciled_at: float = 0.0
    pnl_verified: int = 1
    exit_attempts: int = 0
    entry_reference: float = 0.0     # mid/last price when the entry was decided
    exit_reference: float = 0.0      # mid price when the exit was decided
    idealized_pnl: float = 0.0       # P&L at reference prices: no spread, slippage, fees or fill uncertainty

    ACTIVE = ('pending_entry', 'open', 'exit_pending')
