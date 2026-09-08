import pandas as pd
import numpy as np
from config import MAX_POSITION_PCT, CVaR_ALPHA, DYNAMIC_STOP_SCALAR, STOP_LOSS_PCT

try:
    import riskfolio as rp
    RISKFOLIO_AVAILABLE = True
except ImportError:
    RISKFOLIO_AVAILABLE = False
    print("[WARN] riskfolio-lib not installed; using uniform weighting fallback")


def _cap_and_normalize(weights: dict, cap: float) -> dict:
    """
    Normalize to sum to 1.0 while keeping every weight at or under `cap`.

    A single clip-then-renormalize pass isn't enough: clipping the biggest
    weight down to `cap` and then renormalizing everything to sum back to 1.0
    can push that same weight right back over the cap (redistributing a large
    clipped-off excess across a couple of tiny remaining weights inflates them
    disproportionately, including the one that was just capped). This
    iterates instead — cap whatever's currently over, redistribute only the
    excess among what's left, repeat — which converges because each pass
    permanently locks at least one more weight at the cap.

    If there are too few weights for the cap to be satisfiable at all (e.g.
    cap=0.25 with only 2 symbols: 2 x 0.25 = 0.5 can never reach 1.0), falls
    back to equal weight among them — the same fallback already used
    everywhere else in this module for a case with no principled answer.
    """
    n = len(weights)
    if n == 0:
        return {}
    if cap * n < 1.0:
        return {k: 1.0 / n for k in weights}

    total = sum(weights.values())
    if total <= 0:
        return {k: 1.0 / n for k in weights}
    remaining = {k: v / total for k, v in weights.items()}  # normalize to 1.0 first
    fixed = {}

    while True:
        over_cap = [k for k, v in remaining.items() if v > cap]
        if not over_cap:
            break
        for k in over_cap:
            fixed[k] = cap
            del remaining[k]
        free_total = sum(remaining.values())
        budget_left = 1.0 - sum(fixed.values())
        remaining = {k: v / free_total * budget_left for k, v in remaining.items()}

    return {**fixed, **remaining}


def calculate_hrp_weights(price_histories: dict) -> dict:
    """
    Calculate Hierarchical Risk Parity weights for watchlist symbols.
    Returns {symbol: weight} summing to 1.0.
    Falls back to equal weight if riskfolio unavailable.
    """
    if not RISKFOLIO_AVAILABLE or len(price_histories) == 0:
        # Equal weight fallback
        n = len(price_histories)
        return {symbol: 1.0 / n for symbol in price_histories.keys()}

    try:
        # Build DataFrame of returns
        prices_df = pd.DataFrame(price_histories)
        returns = prices_df.pct_change().dropna()

        if len(returns) < 5:  # insufficient data
            n = len(price_histories)
            return {symbol: 1.0 / n for symbol in price_histories.keys()}

        # HRP calculation. optimization()'s kwarg was renamed method -> model, and
        # its single weights column was renamed Allocation -> weights at some point
        # after this was last touched (riskfolio-lib>=0.3.0 was unpinned, so a pip
        # install could resolve to any version) — the old names raised/KeyError'd
        # on every call, silently falling back to equal weight forever without
        # anyone noticing beyond a per-cycle log line. Reading the column
        # positionally instead of by name survives another such rename.
        portfolio = rp.HCPortfolio(returns=returns)
        weights = portfolio.optimization(model='HRP', codependence='pearson', rm='MV')
        weight_col = weights.iloc[:, 0]

        raw_weights = {
            symbol: weight_col.loc[symbol] if symbol in weight_col.index else 0
            for symbol in price_histories.keys()
        }
        return _cap_and_normalize(raw_weights, MAX_POSITION_PCT)

    except Exception as e:
        print(f"[WARN] HRP calculation failed: {e}; using equal weight")
        n = len(price_histories)
        return {symbol: 1.0 / n for symbol in price_histories.keys()}


def calculate_position_size(symbol: str, weight: float, portfolio_value: float, current_price: float) -> float:
    """
    Calculate dollar amount to invest based on HRP weight.
    Caps at MAX_POSITION_PCT of portfolio.
    """
    position_dollars = weight * portfolio_value
    # Hard cap at 25% of portfolio per position
    max_position = MAX_POSITION_PCT * portfolio_value
    return min(position_dollars, max_position)


def calculate_dynamic_stop(symbol: str, price_history: pd.Series, base_stop: float = STOP_LOSS_PCT) -> float:
    """
    Calculate dynamic stop loss adjusted by volatility (CVaR).
    More volatile symbols get tighter stops.
    """
    if not RISKFOLIO_AVAILABLE or len(price_history) < 20:
        return base_stop

    try:
        returns = price_history.pct_change().dropna()

        # CVaR = mean of worst (1-alpha)% returns
        # Higher CVaR (more downside risk) → tighter stop
        alpha_idx = int(len(returns) * CVaR_ALPHA)
        cvar = returns.nsmallest(max(1, alpha_idx)).mean()

        # Adjust base stop: if CVaR is worse (more negative), tighten the stop
        # e.g., if CVaR = -3% and base = -2%, apply tighter stop
        adjusted_stop = base_stop + (cvar * DYNAMIC_STOP_SCALAR)

        # But don't make it too tight; minimum is -1%
        return min(adjusted_stop, -0.01)

    except Exception as e:
        print(f"[WARN] Dynamic stop calculation failed: {e}; using base stop")
        return base_stop


def portfolio_drawdown_check(initial_value: float, current_value: float, max_dd: float = -0.08) -> bool:
    """
    Check if portfolio drawdown is within limits.
    Returns True if safe to enter (portfolio hasn't lost >8%).
    Returns False if drawdown exceeded — halt new entries.
    """
    if initial_value <= 0:
        return True

    drawdown = (current_value - initial_value) / initial_value
    return drawdown >= max_dd
