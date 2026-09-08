"""
Optional short-horizon price forecasting via Google's TimesFM 2.5 (200M params,
Apache-2.0) — https://github.com/google-research/timesfm.

Adds one extra filter on top of the existing 3-of-5 indicator score: a
foundation model's opinion on where each symbol is headed over the next hour.
It only ever blocks an entry the indicators already liked; it can't add
entries the indicators missed. That keeps the existing (already-tuned)
MIN_ENTRY_SCORE/TOTAL_SIGNALS calibration untouched.

Deliberately pinned to the "google/timesfm-2.5-200m-pytorch" checkpoint rather
than whatever ships as this package's default. TimesFM 3.0's default
pretrained weights are licensed for non-commercial/non-production use only;
weights up to 2.5 remain Apache-2.0. This bot has a real-order LIVE mode
(bot.py), so 3.0's default weights are off the table here regardless of which
mode happens to be active today.

The import and model load are both wrapped in try/except — a missing package,
a failed ~800MB weight download, or an OOM on a small CI runner just disables
this signal for the session (logged once) rather than taking down the trading
loop. config.ENABLE_FORECAST is the manual off-switch.
"""
import logging

import numpy as np

import config

log = logging.getLogger(__name__)

CHECKPOINT = "google/timesfm-2.5-200m-pytorch"  # Apache-2.0 — see module docstring

_model = None
_load_failed = False


def _get_model():
    global _model, _load_failed
    if _model is not None or _load_failed:
        return _model
    try:
        import timesfm
        m = timesfm.TimesFM_2p5_200M_torch.from_pretrained(CHECKPOINT)
        m.compile(timesfm.ForecastConfig(
            max_context=config.FORECAST_MAX_CONTEXT,
            max_horizon=config.FORECAST_HORIZON,
            normalize_inputs=True,
            per_core_batch_size=max(1, len(config.WATCHLIST)),
            use_continuous_quantile_head=True,
            fix_quantile_crossing=True,
        ))
        _model = m
        log.info(f"✓ TimesFM 2.5 loaded ({CHECKPOINT}) — forecast filter enabled")
    except Exception as e:
        log.warning(f"TimesFM unavailable ({e}) — forecast filter disabled for this session")
        _load_failed = True
        _model = None
    return _model


def forecast_direction(price_histories: dict) -> dict:
    """
    price_histories: {symbol: pd.Series of closes}.
    Returns {symbol: bool} — True if TimesFM's median forecast
    config.FORECAST_HORIZON bars out is at or above the last observed close.
    Symbols with too little history, or any failure, are simply absent from
    the result — scan_for_entries treats a missing symbol as "no opinion",
    never as a reason to skip.
    """
    if not config.ENABLE_FORECAST or not price_histories:
        return {}

    model = _get_model()
    if model is None:
        return {}

    symbols, series = [], []
    for symbol, prices in price_histories.items():
        if len(prices) >= 20:
            symbols.append(symbol)
            series.append(prices.values.astype(np.float64))

    if not series:
        return {}

    try:
        point_forecast, _ = model.forecast(horizon=config.FORECAST_HORIZON, inputs=series)
    except Exception as e:
        log.warning(f"TimesFM forecast call failed: {e}")
        return {}

    return {
        symbol: bool(forecast[-1] >= series_i[-1])
        for symbol, series_i, forecast in zip(symbols, series, point_forecast)
    }
