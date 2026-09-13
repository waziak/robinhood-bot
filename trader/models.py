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
    PENDING_SUBMIT = 'pending_submit'
    SUBMITTED = 'submitted'
    ACKNOWLEDGED = 'acknowledged'
    PARTIALLY_FILLED = 'partially_filled'
    FILLED = 'filled'
    CANCELLED = 'cancelled'
    REJECTED = 'rejected'
    EXPIRED = 'expired'
    UNKNOWN = 'unknown'

    TERMINAL = {FILLED, CANCELLED, REJECTED, EXPIRED}
    OPEN = {PENDING_SUBMIT, SUBMITTED, ACKNOWLEDGED, PARTIALLY_FILLED, UNKNOWN}


@dataclass
class Order:
    client_id: str
    symbol: str
    side: str
    quantity: float
    limit_price: float
    state: str = OrderState.PENDING_SUBMIT
    broker_id: Optional[str] = None
    filled_qty: float = 0.0
    avg_fill_price: float = 0.0
    fees: float = 0.0
    purpose: str = ''
    position_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    error: str = ''

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


@dataclass
class Position:
    position_id: str
    symbol: str
    strategy: str
    quantity: float
    entry_price: float
    stop: float
    target: float
    entry_time: float
    reason: str
    status: str = 'open'
    realized_pnl: float = 0.0
    fees: float = 0.0
    exit_price: float = 0.0
    exit_time: float = 0.0
    exit_reason: str = ''
    mfe: float = 0.0
    mae: float = 0.0
    candidate_id: Optional[int] = None
    intended_entry: float = 0.0
