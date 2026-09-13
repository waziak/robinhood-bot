# Sealed TEST set evaluations (append-only)

| when (UTC) | strategy | spec hash | params | result |
|---|---|---|---|---|
| 2026-09-13 18:44 | trend_sma200 | 1f49e46d5301 | `{"stop_pct": 0.3}` | n=221 mean=+2.630% 2x-cost=+2.557% → OUT-OF-SAMPLE POSITIVE |
| 2026-09-13 18:44 | rsi2_mean_reversion | 5ba9600a7ea7 | `{"max_hold": 10, "rsi_max": 10, "stop_pct": 0.1}` | n=236 mean=+0.402% 2x-cost=+0.352% → OUT-OF-SAMPLE POSITIVE |
| 2026-09-13 19:54 | monthly_sma10_timing_multi | 4f932021830f | `{"sma_months": 10}` | n=124 mean=+9.835% 2x-cost=+9.751% → OUT-OF-SAMPLE POSITIVE |

<!-- ADDENDUM 2026-09-13 20:02 UTC: display-only recomputation (drawdown/consistency bug fix) for ['trend_sma200', 'rsi2_mean_reversion', 'monthly_sma10_timing_multi'] — no decision changed, see TEST_SET_ADDENDUM.md -->
