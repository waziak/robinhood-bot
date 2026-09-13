# Experiment Log (append-only; every run and every variant, including failures)

| when (UTC) | strategy | params | trades | validation net % | decision |
|---|---|---|---|---|---|
| 2026-09-13 18:44 | orb_continuation | `{'or_bars': 6, 'rvol_min': 1.2, 'last_entry_minute': 690}` | 68 | -0.148 | REJECTED AT VALIDATION |
| 2026-09-13 18:44 | vwap_pullback | `{'min_session_ret': 0.003, 'start_minute': 630, 'end_minute': 870, 'touch_tol': 0.0005, 'stop_buffer': 0.001}` | 261 | -0.149 | REJECTED AT VALIDATION |
| 2026-09-13 18:44 | intraday_momentum_last_hour | `{'min_first_hour_ret': 0.0, 'stop_pct': 0.02}` | 1488 | -0.073 | REJECTED AT VALIDATION |
| 2026-09-13 18:44 | crypto_tsmom | `{'lookback_h': 168, 'sma_h': 480, 'stop_pct': 0.08, 'hold_h': 24}` | 510 | -0.425 | REJECTED AT VALIDATION |
| 2026-09-13 18:44 | overnight_drift | `{'trend_filter': False}` | 29196 | -0.015 | REJECTED AT VALIDATION |
| 2026-09-13 18:44 | overnight_drift_trend | `{'trend_filter': True}` | 21158 | -0.013 | REJECTED AT VALIDATION |
| 2026-09-13 18:44 | trend_sma200 | `{'stop_pct': 0.3}` | 870 | +0.834 | OUT-OF-SAMPLE POSITIVE |
| 2026-09-13 18:44 | rsi2_mean_reversion | `{'rsi_max': 10, 'stop_pct': 0.1, 'max_hold': 10}` | 893 | +0.202 | OUT-OF-SAMPLE POSITIVE |
