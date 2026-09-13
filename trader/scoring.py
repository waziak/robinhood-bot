"""Normalized 0–100 opportunity score. Weights sum to 100; missing evidence scores zero, never a default credit."""
from trader.models import Proposal

WEIGHTS = {'setup': 25, 'trend_alignment': 20, 'reward_risk': 15, 'spread': 15, 'volatility': 10, 'volume': 10, 'history': 5}


def _lin(x, lo, hi):
    if x is None:
        return 0.0
    return max(0.0, min(1.0, (x - lo) / (hi - lo)))


def score(p: Proposal, market_regime: str, cfg, strategy_stats: dict = None) -> Proposal:
    f = p.features
    parts = {'setup': p.confidence}

    wanted = {'trend_pullback': 'up', 'breakout': 'up', 'mean_reversion': 'range'}[p.strategy]
    parts['trend_alignment'] = 1.0 if market_regime == wanted else (0.4 if market_regime == 'range' and wanted == 'up' else 0.0)

    parts['reward_risk'] = _lin(p.estimated_reward_risk, 1.0, 3.0)
    sp = f.get('spread_pct')
    parts['spread'] = 0.0 if sp is None or sp > cfg.maximum_spread else 1.0 - sp / cfg.maximum_spread

    atrp = f.get('atr_pct')
    parts['volatility'] = 0.0 if atrp is None else (1.0 if 0.001 <= atrp <= 0.012 else 0.3 if atrp <= 0.02 else 0.0)

    rv = f.get('rel_volume')
    parts['volume'] = _lin(rv, 0.8, 2.0)

    st = (strategy_stats or {}).get(p.strategy)
    if st and st.get('trades', 0) >= 20:
        parts['history'] = 1.0 if st['expectancy'] > 0 else 0.0
    else:
        parts['history'] = 0.5  # insufficient sample: neither reward nor punish

    p.score_breakdown = {k: round(v * WEIGHTS[k], 1) for k, v in parts.items()}
    p.score = int(round(sum(p.score_breakdown.values())))
    return p
