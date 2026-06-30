import pandas as pd
import numpy as np
from config import (SMA_FAST, SMA_SLOW, RSI_PERIOD, RSI_MIN, RSI_MAX,
                    MACD_FAST, MACD_SLOW, MACD_SIGNAL, PULLBACK_PCT, MIN_VOLUME_RATIO)


def sma(series: pd.Series, period: int) -> float:
    if len(series) < period:
        return None
    return series.tail(period).mean()


def rsi(series: pd.Series, period: int = RSI_PERIOD) -> float:
    if len(series) < period + 1:
        return None
    deltas = series.diff()
    gains = deltas.clip(lower=0)
    losses = -deltas.clip(upper=0)
    avg_gain = gains.iloc[1:period+1].mean()
    avg_loss = losses.iloc[1:period+1].mean()
    for i in range(period + 1, len(series)):
        avg_gain = (avg_gain * (period - 1) + gains.iloc[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses.iloc[i]) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(series: pd.Series, fast: int = MACD_FAST, slow: int = MACD_SLOW,
         signal: int = MACD_SIGNAL) -> dict:
    if len(series) < slow + signal:
        return None
    ema_fast = series.ewm(span=fast).mean()
    ema_slow = series.ewm(span=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    histogram = macd_line - signal_line
    recent_crossover = False
    if len(macd_line) >= 4:
        was_below = macd_line.iloc[-4] < signal_line.iloc[-4]
        now_above = macd_line.iloc[-1] > signal_line.iloc[-1]
        recent_crossover = was_below and now_above
    return {
        'macd_line': macd_line.iloc[-1],
        'signal_line': signal_line.iloc[-1],
        'histogram': histogram.iloc[-1],
        'recent_crossover': recent_crossover,
    }


# [Opt4] Volume gate — required gate before scoring, not a scored signal
def check_volume_confirmation(historicals: list,
                               min_ratio: float = MIN_VOLUME_RATIO) -> tuple:
    """
    Returns (passes: bool, ratio: float).
    Current candle must exceed 1.5x the 20-bar average volume.
    Filters out fake MACD crosses on thin volume.
    """
    if not historicals or len(historicals) < 20:
        return False, 0.0
    try:
        volumes = [float(c['volume']) for c in historicals]
        avg_volume = sum(volumes[-20:]) / 20
        current_volume = volumes[-1]
        ratio = current_volume / avg_volume if avg_volume > 0 else 0.0
        return ratio >= min_ratio, ratio
    except Exception:
        return False, 0.0


# [Opt5] VWAP calculation for 5th signal
def calculate_vwap(historicals: list) -> float:
    """
    Volume-weighted average price across all candles in historicals.
    Institutional benchmark — price above VWAP = buying pressure.
    """
    if not historicals:
        return None
    try:
        cumulative_tp_vol = 0.0
        cumulative_vol = 0.0
        for candle in historicals:
            high = float(candle['high_price'])
            low = float(candle['low_price'])
            close = float(candle['close_price'])
            volume = float(candle['volume'])
            typical_price = (high + low + close) / 3
            cumulative_tp_vol += typical_price * volume
            cumulative_vol += volume
        return cumulative_tp_vol / cumulative_vol if cumulative_vol > 0 else None
    except Exception:
        return None


def score_entry(prices: pd.Series, current_price: float,
                historicals: list = None) -> dict:
    """
    Score entry on 5 signals: SMA trend, RSI zone, MACD cross, pullback, VWAP.
    Returns dict with score (0-5), reasons, and indicator values.
    Threshold unchanged at 3 — now 3-of-5 instead of 3-of-4.
    """
    score = 0
    reasons = []

    sma20 = sma(prices, SMA_FAST)
    sma50 = sma(prices, SMA_SLOW)
    rsi_val = rsi(prices, RSI_PERIOD)
    macd_val = macd(prices, MACD_FAST, MACD_SLOW, MACD_SIGNAL)

    # Signal 1: SMA trend (uptrend)
    if sma20 is not None and sma50 is not None and sma20 > sma50:
        score += 1
        reasons.append(f"SMA20({sma20:.2f}) > SMA50({sma50:.2f})")

    # Signal 2: RSI in sweet spot
    if rsi_val is not None and RSI_MIN <= rsi_val <= RSI_MAX:
        score += 1
        reasons.append(f"RSI={rsi_val:.1f} ({RSI_MIN}-{RSI_MAX})")

    # Signal 3: MACD bullish cross in last 3 bars
    if macd_val is not None and macd_val['recent_crossover']:
        score += 1
        reasons.append(f"MACD crossover (hist={macd_val['histogram']:.4f})")

    # Signal 4: Price within pullback zone of SMA20
    if sma20 is not None:
        distance_pct = (current_price - sma20) / sma20
        if -PULLBACK_PCT <= distance_pct <= PULLBACK_PCT:
            score += 1
            reasons.append(f"Pullback to SMA20 ({distance_pct*100:.2f}%)")

    # [Opt5] Signal 5: Above VWAP — institutional reference point
    if historicals:
        vwap = calculate_vwap(historicals)
        if vwap and current_price > vwap:
            score += 1
            reasons.append(f"Above VWAP ${vwap:.2f}")

    return {
        'score': score,
        'reasons': reasons,
        'sma20': sma20,
        'sma50': sma50,
        'rsi': rsi_val,
        'macd': macd_val,
    }
