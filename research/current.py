"""Adapter that runs the PRODUCTION strategy + scoring code (trader.strategies, trader.scoring) bar by bar over history.

Faithfulness notes:
- Each bar i sees only the trailing WINDOW candles ending at i; the synthetic quote is bar i's close +/- half-spread.
- Robinhood crypto candles report zero volume, so crypto volume is zeroed here to reproduce production scoring.
- Equities are only evaluated inside production's entry window (09:45-15:30 ET).
- `gated` replicates the risk engine's proposal-level checks (score, reward/risk, cost vs stop, abnormal bar).
"""
from dataclasses import replace

import numpy as np
import pandas as pd

from research.backtest import Signal
from trader import scoring, strategies
from trader.models import Candle, Quote
from trader.risk_config import WEEK_1_VALIDATION_MODE

WINDOW = 200


def regime_series(df: pd.DataFrame) -> np.ndarray:
    c = df['close']
    sma50 = c.rolling(50).mean()
    prev = c.shift(10).rolling(50).mean()
    slope = (sma50 - prev) / prev
    out = np.where((c > sma50) & (slope > 0.0005), 'up', np.where((c < sma50) & (slope < -0.0005), 'down', 'range'))
    out[:60] = 'unknown'
    return out


def entry_window_mask(index: pd.DatetimeIndex, is_crypto: bool) -> np.ndarray:
    if is_crypto:
        return np.ones(len(index), dtype=bool)
    et = index.tz_convert('America/New_York')
    minutes = et.hour * 60 + et.minute
    return np.asarray((et.weekday < 5) & (minutes >= 9 * 60 + 45) & (minutes < 15 * 60 + 30))


def gate(p, quote, cfg, candle, cost) -> tuple:
    if p.score < cfg.minimum_signal_score:
        return False, 'score'
    risk = quote.ask - p.stop
    if risk <= 0:
        return False, 'stop_not_below_entry'
    if (p.target - quote.ask) / risk < cfg.minimum_reward_risk:
        return False, 'reward_risk'
    cost_unit = quote.ask * (quote.spread_pct + 2 * cost.slippage_bps / 1e4)
    if cost_unit > cfg.max_expected_cost_fraction_of_risk * risk:
        return False, 'costs_vs_stop'
    atr = p.features.get('atr')
    if not atr or candle.high - candle.low > cfg.max_bar_move_multiple * atr:
        return False, 'abnormal_bar'
    return True, 'approved'


def signals(symbol: str, df: pd.DataFrame, cost, reference_regime: np.ndarray, is_crypto: bool, max_hold: int = 48) -> list:
    cfg = replace(WEEK_1_VALIDATION_MODE, crypto_symbols=(symbol,) if is_crypto else ())
    vol = np.zeros(len(df)) if is_crypto else df['volume'].to_numpy(float)
    ts = (df.index.asi8 // 10**9).astype(float)
    o, h, l, c = (df[k].to_numpy(float) for k in ('open', 'high', 'low', 'close'))
    candles = [Candle(ts[i], o[i], h[i], l[i], c[i], vol[i]) for i in range(len(df))]
    allowed = entry_window_mask(df.index, is_crypto)
    et_hour = df.index.tz_convert('America/New_York').hour
    half = cost.half_spread_bps / 1e4
    out = []
    for i in range(WINDOW, len(df) - 1):
        if not allowed[i]:
            continue
        window = candles[i - WINDOW + 1:i + 1]
        quote = Quote(symbol, c[i] * (1 - half), c[i] * (1 + half), c[i], ts[i])
        for p in strategies.generate(symbol, window, quote):
            reg = reference_regime[i]
            scoring.score(p, reg, cfg, None)
            ok, why = gate(p, quote, cfg, candles[i], cost)
            f = p.features
            out.append(Signal(i, p.stop, p.target, max_hold, {
                'symbol': symbol, 'strategy': p.strategy, 'score': p.score, 'regime': reg, 'gated': ok,
                'gate_reason': why, 'hour_et': int(et_hour[i]), 'atr_pct': f.get('atr_pct'),
                'rel_volume': f.get('rel_volume'), 'planned_rr': p.estimated_reward_risk,
                'planned_risk_pct': (quote.ask - p.stop) / quote.ask}))
    return out


def forward_returns(df: pd.DataFrame, idx: list, horizons=(1, 6, 12, 48)) -> pd.DataFrame:
    """Raw forward return from the NEXT bar's open to the close h bars later — the signal's predictive content,
    independent of stops, targets and costs."""
    o, c = df['open'].to_numpy(float), df['close'].to_numpy(float)
    rows = []
    for i in idx:
        if i + 1 >= len(df):
            continue
        rows.append({f'fwd_{hz}': c[min(len(df) - 1, i + hz)] / o[i + 1] - 1 for hz in horizons})
    return pd.DataFrame(rows)
