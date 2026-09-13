"""Risk engine: the only component that can turn a Proposal into an approved, sized trade. Absolute veto."""
import math
import time
from datetime import datetime, timezone

from trader import events as ev
from trader.models import Proposal, Quote, RiskDecision

STOP_NEW_TRADES = 'STOP_NEW_TRADES'
EMERGENCY_HALT = 'EMERGENCY_HALT'


def utc_day_start(now: float = None) -> float:
    d = datetime.fromtimestamp(now or time.time(), tz=timezone.utc)
    return d.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()


def floor_to(x: float, decimals: int) -> float:
    m = 10 ** decimals
    return math.floor(x * m) / m


class RiskEngine:
    def __init__(self, cfg, store, events, clock=time.time):
        self.cfg, self.store, self.events, self.clock = cfg, store, events, clock
        self.api_error_streak = 0

    # ── kill switches ──────────────────────────────────────────────────────
    def emergency_halt(self, reason: str):
        """Blocks ALL order placement (entries and exits) until cleared manually via `python -m trader.status --clear-halt`."""
        if not self.store.get_flag(EMERGENCY_HALT)[0]:
            self.store.set_flag(EMERGENCY_HALT, True, reason)
            self.events.emit(ev.KILL_SWITCH, 'EMERGENCY_HALT engaged', switch=EMERGENCY_HALT, reason=reason)

    def stop_new_trades(self, reason: str):
        """Blocks new entries for the rest of the UTC day; exits keep working."""
        on, _, ts = self.store.get_flag(STOP_NEW_TRADES)
        if not on or ts < utc_day_start(self.clock()):
            self.store.set_flag(STOP_NEW_TRADES, True, reason)
            self.events.emit(ev.KILL_SWITCH, 'STOP_NEW_TRADES engaged', switch=STOP_NEW_TRADES, reason=reason)

    def is_emergency_halted(self) -> tuple:
        on, reason, _ = self.store.get_flag(EMERGENCY_HALT)
        if self.cfg.emergency_stop:
            return True, 'EMERGENCY_STOP set in config/env'
        return on, reason

    def new_trades_blocked(self, now: float = None) -> tuple:
        now = now or self.clock()
        halted, reason = self.is_emergency_halted()
        if halted:
            return True, f'emergency halt: {reason}'
        on, reason, ts = self.store.get_flag(STOP_NEW_TRADES)
        if on and ts >= utc_day_start(now):
            return True, f'stop new trades: {reason}'
        if on:
            self.store.set_flag(STOP_NEW_TRADES, False, 'auto-cleared at new UTC day')
        return False, ''

    def entries_allowed(self, now: float = None) -> tuple:
        blocked, why = self.new_trades_blocked(now)
        return not blocked, why

    def exits_allowed(self) -> tuple:
        """Position management is independent of entry permission: daily-loss limits, losing streaks and
        STOP_NEW_TRADES never block exits. Only EMERGENCY_HALT can, and only if protective exits are disabled."""
        halted, reason = self.is_emergency_halted()
        if halted and not self.cfg.allow_protective_exits_during_halt:
            return False, f'emergency halt (protective exits disabled): {reason}'
        return True, ''

    def record_api_result(self, ok: bool, what: str = ''):
        self.api_error_streak = 0 if ok else self.api_error_streak + 1
        if self.api_error_streak >= self.cfg.max_api_error_streak:
            self.stop_new_trades(f'{self.api_error_streak} consecutive API failures (last: {what})')

    # ── daily state ────────────────────────────────────────────────────────
    def day_stats(self, now: float = None) -> dict:
        start = utc_day_start(now or self.clock())
        closed = self.store.closed_positions_since(start)
        realized = sum(p.realized_pnl for p in closed)
        entered = self.store.positions_entered_since(start)
        recent = self.store.closed_positions_since(0)[-self.cfg.consecutive_loss_limit * 3:]
        streak = 0
        for p in reversed(recent):
            if p.realized_pnl < 0:
                streak += 1
            else:
                break
        last_loss = max((p.exit_time for p in recent if p.realized_pnl < 0), default=0.0)
        return {'realized_pnl': realized, 'trades_today': len(entered), 'consecutive_losses': streak,
                'last_loss_time': last_loss}

    def check_portfolio_limits(self, account: dict, unrealized_pnl: float, now: float = None) -> None:
        """Called every cycle. Trips kill switches on loss/drawdown limits."""
        stats = self.day_stats(now)
        day_pnl = stats['realized_pnl'] + min(0.0, unrealized_pnl)
        if day_pnl <= -self.cfg.max_daily_loss:
            self.stop_new_trades(f'daily loss ${-day_pnl:.2f} >= ${self.cfg.max_daily_loss:.2f}')
        if stats['consecutive_losses'] >= self.cfg.consecutive_loss_limit:
            self.stop_new_trades(f"{stats['consecutive_losses']} consecutive losses")
        peak = self.store.peak_equity()
        if peak and account.get('equity') is not None:
            dd = (peak - account['equity']) / peak
            if dd >= self.cfg.max_drawdown:
                self.emergency_halt(f'drawdown {dd:.1%} from peak ${peak:.2f} >= {self.cfg.max_drawdown:.0%}')

    # ── per-trade evaluation ───────────────────────────────────────────────
    def evaluate(self, p: Proposal, quote: Quote, candles: list, account: dict, open_positions: list,
                 market_open: bool, unrealized_pnl: float = 0.0, now: float = None) -> RiskDecision:
        now = now or time.time()
        cfg, checks = self.cfg, {}

        def reject(reason):
            checks['result'] = 'rejected'
            return RiskDecision(False, reason, checks=checks)

        blocked, why = self.new_trades_blocked(now)
        if blocked:
            return reject(why)

        sym = p.symbol
        if p.strategy not in cfg.approved_strategies:
            return reject('strategy not approved: no credible out-of-sample evidence after costs')
        if sym not in cfg.universe:
            return reject('symbol not in universe')
        if sym in cfg.leveraged_symbols and not cfg.allow_leverage:
            return reject('leveraged instrument')
        is_crypto = cfg.is_crypto(sym)
        if (is_crypto and not cfg.allow_crypto) or (not is_crypto and not cfg.allow_stocks):
            return reject('asset class disabled')
        if not is_crypto and not market_open:
            return reject('stock market closed')
        if p.direction != 'long' and not cfg.allow_short:
            return reject('short selling not allowed')

        if not account or account.get('equity') is None or account.get('cash') is None:
            return reject('account balance not verified')
        equity, cash = float(account['equity']), float(account['cash'])
        if equity <= 0:
            return reject('non-positive equity')
        checks['equity'], checks['cash'] = equity, cash

        if any(x.symbol == sym for x in open_positions):
            return reject('position already open in symbol (no averaging down)')
        if len(open_positions) >= cfg.max_open_positions:
            return reject('max open positions')
        stats = self.day_stats(now)
        checks.update(stats)
        if stats['trades_today'] >= cfg.max_trades_per_day:
            return reject('max trades per day')
        if stats['consecutive_losses'] >= cfg.consecutive_loss_limit:
            return reject('consecutive loss limit')
        if stats['last_loss_time'] and now - stats['last_loss_time'] < cfg.cooldown_after_loss_seconds:
            return reject('cooldown after loss')
        remaining_loss = cfg.max_daily_loss + stats['realized_pnl'] + min(0.0, unrealized_pnl)
        checks['daily_loss_remaining'] = round(remaining_loss, 4)
        if remaining_loss <= 0:
            return reject('daily loss limit reached')

        age = quote.age(now)
        checks['quote_age_s'], checks['spread_pct'] = round(age, 1), round(quote.spread_pct, 5)
        if age > cfg.stale_quote_seconds:
            return reject(f'stale quote ({age:.0f}s)')
        if not (0 < quote.bid <= quote.ask):
            return reject('invalid quote')
        if quote.spread_pct > cfg.maximum_spread:
            return reject(f'spread {quote.spread_pct:.3%} > {cfg.maximum_spread:.3%}')

        if is_crypto:
            checks['liquidity'] = 'assumed: major crypto pair, venue volume not reported'
        else:
            dollar_vol = sum(c.close * c.volume for c in candles[-78:])
            checks['dollar_volume_1d'] = round(dollar_vol)
            if dollar_vol < cfg.minimum_liquidity_dollars:
                return reject('insufficient liquidity')

        a = p.features.get('atr')
        if not a:
            return reject('volatility unknown')
        if candles and (candles[-1].high - candles[-1].low) > cfg.max_bar_move_multiple * a:
            return reject('abnormal bar range invalidates strategy assumptions')

        if p.score < cfg.minimum_signal_score:
            return reject(f'score {p.score} < {cfg.minimum_signal_score}')
        entry = quote.ask
        risk_unit = entry - p.stop
        if p.stop <= 0 or risk_unit <= 0:
            return reject('stop not below entry')
        rr = (p.target - entry) / risk_unit
        checks['reward_risk'] = round(rr, 3)
        if rr < cfg.minimum_reward_risk:
            return reject(f'reward/risk {rr:.2f} < {cfg.minimum_reward_risk}')

        cost_unit = entry * (quote.spread_pct + 2 * cfg.slippage_rate + 2 * cfg.fee_rate)
        checks['expected_cost_per_unit'] = cost_unit
        if cost_unit > cfg.max_expected_cost_fraction_of_risk * risk_unit:
            return reject('expected costs too large relative to stop distance')

        loss_budget = min(cfg.max_risk_per_trade_dollars, remaining_loss)
        exposure = sum(x.quantity * x.entry_price for x in open_positions)
        notional_cap = min(cfg.max_dollar_position, cfg.max_position_percent * equity, cash * 0.98,
                           cfg.max_total_exposure_percent * equity - exposure)
        decimals = 8 if is_crypto else 6
        limit = round(entry * (1 + cfg.max_order_price_deviation), 2)
        qty = floor_to(min(loss_budget / (risk_unit + cost_unit), notional_cap / limit if notional_cap > 0 else 0), decimals)
        notional = qty * limit
        max_loss = qty * (limit - p.stop + cost_unit)
        checks.update({'loss_budget': loss_budget, 'notional_cap': round(notional_cap, 4), 'qty': qty,
                       'notional': round(notional, 4), 'max_loss': round(max_loss, 4)})
        if qty <= 0 or notional < cfg.min_order_dollars:
            return reject('correctly sized position too small to execute safely')
        if max_loss > loss_budget + 1e-6:
            return reject('max loss exceeds budget after rounding')

        checks['result'] = 'approved'
        return RiskDecision(True, 'approved', quantity=qty, notional=notional, limit_price=limit, max_loss=max_loss,
                            checks=checks)
