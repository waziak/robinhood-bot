# Sealed TEST set evaluations (append-only)

| when (UTC) | strategy | spec hash | params | result |
|---|---|---|---|---|
| 2026-09-13 18:44 | trend_sma200 | 1f49e46d5301 | `{"stop_pct": 0.3}` | n=221 mean=+2.630% 2x-cost=+2.557% → OUT-OF-SAMPLE POSITIVE |
| 2026-09-13 18:44 | rsi2_mean_reversion | 5ba9600a7ea7 | `{"max_hold": 10, "rsi_max": 10, "stop_pct": 0.1}` | n=236 mean=+0.402% 2x-cost=+0.352% → OUT-OF-SAMPLE POSITIVE |
| 2026-09-13 19:54 | monthly_sma10_timing_multi | 4f932021830f | `{"sma_months": 10}` | n=124 mean=+9.835% 2x-cost=+9.751% → OUT-OF-SAMPLE POSITIVE |

<!-- ADDENDUM 2026-09-13 20:02 UTC: display-only recomputation (drawdown/consistency bug fix) for ['trend_sma200', 'rsi2_mean_reversion', 'monthly_sma10_timing_multi'] — no decision changed, see TEST_SET_ADDENDUM.md -->
| 2026-09-13 23:52 | pullback_from_high | f3cf0c90207f | `{"high_lookback": 10, "max_hold": 10, "pullback_pct": 0.03, "stop_pct": 0.1}` | n=113 mean=+0.152% 2x-cost=+0.102% → OUT-OF-SAMPLE POSITIVE |
| 2026-09-13 23:52 | weekly_rsi2 | d4720f6e96fa | `{"hold_weeks": 3, "rsi_max": 10, "sma_weeks": 40}` | n=41 mean=+2.242% 2x-cost=+2.192% → OUT-OF-SAMPLE POSITIVE |
| 2026-09-13 23:52 | combined_trend_vol_rsi2 | 18e367c47acd | `{"max_hold": 10, "rsi_max": 10, "stop_pct": 0.1}` | n=186 mean=+0.519% 2x-cost=+0.469% → OUT-OF-SAMPLE POSITIVE |
| 2026-09-13 23:55 | low_volatility_rotation | 7e35a6f0a37b | `{"top_n": 5, "vol_lookback_months": 6}` | n=175 mean=+1.604% 2x-cost=+1.530% → OUT-OF-SAMPLE POSITIVE |

<!-- ADDENDUM 2026-09-14 00:06 UTC: display-only recomputation (drawdown/consistency bug fix) for ['trend_sma200', 'rsi2_mean_reversion', 'monthly_sma10_timing_multi', 'pullback_from_high', 'weekly_rsi2', 'combined_trend_vol_rsi2', 'low_volatility_rotation'] — no decision changed, see TEST_SET_ADDENDUM.md -->

<!-- ADDENDUM 2026-09-14 00:24 UTC: display-only recomputation (drawdown/consistency bug fix) for ['trend_sma200', 'rsi2_mean_reversion', 'monthly_sma10_timing_multi', 'pullback_from_high', 'weekly_rsi2', 'combined_trend_vol_rsi2', 'low_volatility_rotation'] — no decision changed, see TEST_SET_ADDENDUM.md -->
