"""The single source of every risk limit. Nothing else in the codebase may hard-code a risk value."""
import json
import os
from dataclasses import dataclass, asdict, fields, replace


@dataclass(frozen=True)
class RiskConfig:
    live_trading_enabled: bool = False
    week1_validation_mode: bool = True

    max_position_percent: float = 0.20
    max_dollar_position: float = 6.00
    max_risk_per_trade_dollars: float = 0.30
    min_order_dollars: float = 1.00
    max_daily_loss: float = 1.00
    max_drawdown: float = 0.10
    max_open_positions: int = 2
    max_trades_per_day: int = 4
    max_total_exposure_percent: float = 0.40

    minimum_signal_score: int = 70
    minimum_reward_risk: float = 1.8
    minimum_liquidity_dollars: float = 5_000_000
    maximum_spread: float = 0.004
    max_expected_cost_fraction_of_risk: float = 0.35
    fee_rate: float = 0.0
    slippage_rate: float = 0.0010

    cooldown_after_loss_seconds: int = 1800
    consecutive_loss_limit: int = 3
    stale_quote_seconds: int = 20
    stale_candle_seconds: int = 900
    max_api_error_streak: int = 5
    max_bar_move_multiple: float = 6.0
    max_holding_seconds: int = 4 * 3600
    order_ack_timeout_seconds: int = 30
    unknown_order_grace_seconds: int = 120
    max_order_price_deviation: float = 0.003
    max_exit_attempts_before_alert: int = 3
    allow_protective_exits_during_halt: bool = True
    reconcile_interval_seconds: int = 300

    allow_crypto: bool = True
    allow_stocks: bool = True
    allow_leverage: bool = False
    allow_margin: bool = False
    allow_options: bool = False
    allow_short: bool = False
    allow_averaging_down: bool = False
    emergency_stop: bool = False

    # Strategies allowed to open positions. Empty by default: a strategy is added only with credible positive
    # out-of-sample evidence after realistic costs (see research/). Unapproved proposals are still scored and logged.
    approved_strategies: tuple = ()
    universe: tuple = ('BTC', 'ETH', 'SPY', 'QQQ', 'AAPL', 'NVDA', 'MSFT')
    crypto_symbols: tuple = ('BTC', 'ETH')
    leveraged_symbols: tuple = ('TQQQ', 'SQQQ', 'SOXL', 'SOXS', 'UVXY', 'SPXL', 'SPXS', 'TNA', 'TZA')

    def is_crypto(self, symbol: str) -> bool:
        return symbol in self.crypto_symbols

    def validate(self) -> None:
        """Week-1 mode is a ceiling: any setting that loosens its hard limits is rejected, not clipped."""
        errs = []
        if not 0 < self.max_position_percent <= 1:
            errs.append('max_position_percent must be in (0, 1]')
        if self.max_daily_loss <= 0 or self.max_risk_per_trade_dollars <= 0:
            errs.append('loss limits must be positive')
        if not 0 < self.max_drawdown < 1:
            errs.append('max_drawdown must be in (0, 1)')
        if self.week1_validation_mode:
            ceiling = WEEK_1_VALIDATION_MODE
            for name in ('max_position_percent', 'max_dollar_position', 'max_risk_per_trade_dollars', 'max_daily_loss',
                         'max_drawdown', 'max_open_positions', 'max_trades_per_day', 'max_total_exposure_percent',
                         'maximum_spread', 'stale_quote_seconds', 'consecutive_loss_limit'):
                if getattr(self, name) > getattr(ceiling, name):
                    errs.append(f'{name}={getattr(self, name)} exceeds week-1 ceiling {getattr(ceiling, name)}')
            for name in ('minimum_signal_score', 'minimum_reward_risk', 'cooldown_after_loss_seconds'):
                if getattr(self, name) < getattr(ceiling, name):
                    errs.append(f'{name}={getattr(self, name)} is below week-1 floor {getattr(ceiling, name)}')
            for name in ('allow_leverage', 'allow_margin', 'allow_options', 'allow_short', 'allow_averaging_down'):
                if getattr(self, name):
                    errs.append(f'{name} is forbidden in week-1 validation mode')
            if set(self.universe) & set(self.leveraged_symbols):
                errs.append('leveraged instruments are forbidden in week-1 validation mode')
        if errs:
            raise ValueError('Invalid RiskConfig: ' + '; '.join(errs))

    def to_dict(self) -> dict:
        return asdict(self)


WEEK_1_VALIDATION_MODE = RiskConfig()


def load_risk_config(path: str = None) -> RiskConfig:
    """Defaults = WEEK_1_VALIDATION_MODE. Optional JSON overrides may only tighten while week-1 mode is on.
    live_trading_enabled additionally requires LIVE_TRADING_ACK=I_ACCEPT_REAL_MONEY_RISK in the environment."""
    cfg = WEEK_1_VALIDATION_MODE
    path = path or os.getenv('RISK_CONFIG_PATH')
    if path and os.path.isfile(path):
        with open(path) as f:
            overrides = json.load(f)
        known = {f.name for f in fields(RiskConfig)}
        unknown = set(overrides) - known
        if unknown:
            raise ValueError(f'Unknown risk config keys: {sorted(unknown)}')
        for k in ('universe', 'crypto_symbols', 'leveraged_symbols'):
            if k in overrides:
                overrides[k] = tuple(overrides[k])
        cfg = replace(cfg, **overrides)
    if os.getenv('EMERGENCY_STOP', '').lower() == 'true':
        cfg = replace(cfg, emergency_stop=True)
    if cfg.live_trading_enabled and os.getenv('LIVE_TRADING_ACK') != 'I_ACCEPT_REAL_MONEY_RISK':
        cfg = replace(cfg, live_trading_enabled=False)
    cfg.validate()
    return cfg
