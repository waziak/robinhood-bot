import pandas as pd
import numpy as np
from config import MAX_POSITION_PCT, CVaR_ALPHA, DYNAMIC_STOP_SCALAR, STOP_LOSS_PCT

try:
    import riskfolio as rp
    RISKFOLIO_AVAILABLE = True
except ImportError:
    RISKFOLIO_AVAILABLE = False
    print("[WARN] riskfolio-lib not installed; using uniform weighting fallback")


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

        # HRP calculation
        portfolio = rp.HCPortfolio(returns=returns)
        weights = portfolio.optimization(method='HRP', codependence='pearson', rm='MV')

        # Convert to dict, clip to MAX_POSITION_PCT
        weight_dict = {}
        for symbol in price_histories.keys():
            w = weights.loc[symbol, 'Allocation'] if symbol in weights.index else 0
            weight_dict[symbol] = min(w, MAX_POSITION_PCT)

        # Renormalize to sum to 1.0
        total = sum(weight_dict.values())
        if total > 0:
            weight_dict = {k: v / total for k, v in weight_dict.items()}
        else:
            n = len(price_histories)
            weight_dict = {symbol: 1.0 / n for symbol in price_histories.keys()}

        return weight_dict

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
        return max(adjusted_stop, -0.01)

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
