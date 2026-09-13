# Reality Check — candidates that passed formal validation

Generated 2026-09-13 20:08 UTC by `python -m research.reality_check`. Targets are auto-detected from `run_candidates` decisions (nothing hand-picked). 3 of 11 candidates reached this stage. Random-entry null: 2000 simulations of long trades on the same symbols with the same holding periods inside the same window, charged the same round-trip costs. A strategy whose mean does not beat that null is earning market drift, not timing.

## trend_sma200

Formal validation-gate decision: **PASSED VALIDATION — test set already used earlier (see TEST_SET_LOG.md); not re-evaluated**
Hypothesis: Trends persist; holding only above the 200-day average keeps most upside while avoiding prolonged bear markets.
Parameters (unchanged): `{'stop_pct': 0.3}`

| split | n | mean net %/trade | t-stat | random-entry null mean % | strategy percentile vs null | excess %/trade | avg days held | net %/exposure-day | buy&hold %/day | time in market | 1-bar-delayed entry mean % | mean @3x / @5x costs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train | 478 | +1.158 | 2.53 | +1.150 | 51% | +0.008 | 39.9 | +0.0290 | +0.0250 | 38% | +1.451 | +1.025 / +0.895 |
| validation | 171 | +0.834 | 1.34 | +1.692 | 1% | -0.858 | 40.8 | +0.0204 | +0.0392 | 41% | +1.755 | +0.695 / +0.554 |
| test | 221 | +2.630 | 3.14 | +2.680 | 47% | -0.050 | 42.4 | +0.0621 | +0.0483 | 55% | +3.101 | +2.484 / +2.341 |

Test window by year:

| year | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| 2020 | 24.000 | 0.333 | 10.458 | -0.859 | 250.986 |
| 2021 | 20.000 | 0.150 | 1.829 | -0.728 | 36.589 |
| 2022 | 52.000 | 0.192 | -1.133 | -1.358 | -58.935 |
| 2023 | 47.000 | 0.298 | 4.097 | -0.746 | 192.574 |
| 2024 | 19.000 | 0.316 | -0.818 | -0.860 | -15.539 |
| 2025 | 39.000 | 0.282 | 2.391 | -0.950 | 93.248 |
| 2026 | 20.000 | 0.300 | 4.115 | -0.297 | 82.299 |

Test window by symbol:

| symbol | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| DIA | 26.000 | 0.269 | 1.918 | -1.122 | 49.858 |
| GLD | 25.000 | 0.200 | -0.293 | -0.648 | -7.325 |
| IWM | 16.000 | 0.312 | 0.572 | -0.832 | 9.158 |
| QQQ | 11.000 | 0.364 | 14.648 | -0.606 | 161.132 |
| SPY | 15.000 | 0.400 | 6.206 | -0.352 | 93.089 |
| TLT | 42.000 | 0.095 | -1.201 | -1.215 | -50.460 |
| XLE | 25.000 | 0.320 | 4.427 | -0.950 | 110.673 |
| XLF | 19.000 | 0.211 | 4.208 | -0.477 | 79.947 |
| XLK | 9.000 | 0.444 | 10.933 | -0.122 | 98.398 |
| XLV | 33.000 | 0.333 | 1.114 | -0.477 | 36.751 |

Test-window consistency: downside deviation 1.878%, Sortino-like nan, longest losing streak 19 trades, 10% of 341 active weeks profitable.

**Reality-check verdict:** Per-trade gains are explained by market drift while exposed; no timing edge beyond random entries. Per exposure-day it earned +0.0621% vs buy-and-hold +0.0483%/day (better than simply holding while invested).

## rsi2_mean_reversion

Formal validation-gate decision: **PASSED VALIDATION — test set already used earlier (see TEST_SET_LOG.md); not re-evaluated**
Hypothesis: Sharp 2-3 day selloffs inside a long-term uptrend overshoot and revert within days as liquidity providers are paid to absorb flow.
Parameters (unchanged): `{'rsi_max': 10, 'stop_pct': 0.1, 'max_hold': 10}`

| split | n | mean net %/trade | t-stat | random-entry null mean % | strategy percentile vs null | excess %/trade | avg days held | net %/exposure-day | buy&hold %/day | time in market | 1-bar-delayed entry mean % | mean @3x / @5x costs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train | 432 | +0.429 | 4.11 | +0.105 | 99% | +0.323 | 4.5 | +0.0947 | +0.0238 | 10% | +0.360 | +0.329 / +0.228 |
| validation | 225 | +0.202 | 1.90 | +0.211 | 46% | -0.009 | 4.6 | +0.0437 | +0.0519 | 15% | +0.196 | +0.102 / +0.002 |
| test | 236 | +0.402 | 2.82 | +0.217 | 85% | +0.185 | 4.3 | +0.0942 | +0.0529 | 15% | +0.264 | +0.302 / +0.202 |

Test window by year:

| year | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| 2020 | 26.000 | 0.769 | -0.384 | 0.845 | -9.991 |
| 2021 | 44.000 | 0.750 | 0.623 | 0.736 | 27.394 |
| 2022 | 8.000 | 0.625 | -0.452 | 0.742 | -3.615 |
| 2023 | 37.000 | 0.595 | 0.057 | 0.208 | 2.116 |
| 2024 | 48.000 | 0.771 | 0.799 | 0.828 | 38.345 |
| 2025 | 35.000 | 0.829 | 0.612 | 0.853 | 21.418 |
| 2026 | 38.000 | 0.684 | 0.507 | 0.494 | 19.256 |

Test window by symbol:

| symbol | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| DIA | 64.000 | 0.688 | 0.346 | 0.637 | 22.154 |
| IWM | 53.000 | 0.774 | 0.414 | 0.765 | 21.957 |
| QQQ | 58.000 | 0.759 | 0.464 | 0.797 | 26.892 |
| SPY | 61.000 | 0.705 | 0.392 | 0.738 | 23.921 |

Test-window consistency: downside deviation 1.749%, Sortino-like nan, longest losing streak 4 trades, 23% of 346 active weeks profitable.

**Reality-check verdict:** Weak evidence of timing edge beyond random entries (80-95th percentile) — not conclusive. Per exposure-day it earned +0.0942% vs buy-and-hold +0.0529%/day (better than simply holding while invested).

## monthly_sma10_timing_multi

Formal validation-gate decision: **PASSED VALIDATION — test set already used earlier (see TEST_SET_LOG.md); not re-evaluated**
Hypothesis: Same as monthly_sma10_timing_spy, applied per-instrument across a broader liquid-ETF universe to see whether the effect is SPY-specific or general.
Parameters (unchanged): `{'sma_months': 10}`

| split | n | mean net %/trade | t-stat | random-entry null mean % | strategy percentile vs null | excess %/trade | avg days held | net %/exposure-day | buy&hold %/day | time in market | 1-bar-delayed entry mean % | mean @3x / @5x costs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train | 209 | +11.013 | 5.96 | +7.133 | 99% | +3.880 | 232.6 | +0.0473 | +0.0259 | 50% | +11.013 | +10.855 / +10.700 |
| validation | 110 | +3.380 | 2.30 | +6.356 | 0% | -2.976 | 171.6 | +0.0197 | +0.0358 | 59% | +3.380 | +3.229 / +3.076 |
| test | 124 | +9.835 | 4.67 | +9.432 | 62% | +0.403 | 174.3 | +0.0564 | +0.0399 | 67% | +9.835 | +9.672 / +9.507 |

Test window by year:

| year | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| 2020 | 20.000 | 0.800 | 34.081 | 29.396 | 681.622 |
| 2021 | 6.000 | 0.167 | -1.038 | -1.868 | -6.225 |
| 2022 | 24.000 | 0.208 | -4.461 | -4.655 | -107.065 |
| 2023 | 37.000 | 0.432 | 8.287 | -1.441 | 306.614 |
| 2024 | 9.000 | 0.444 | 5.096 | -1.909 | 45.861 |
| 2025 | 20.000 | 0.650 | 13.521 | 9.408 | 270.417 |
| 2026 | 8.000 | 0.750 | 3.541 | 3.142 | 28.328 |

Test window by symbol:

| symbol | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| DIA | 5.000 | 0.800 | 13.481 | 17.897 | 67.406 |
| EEM | 4.000 | 0.750 | 23.888 | 19.215 | 95.553 |
| EFA | 5.000 | 0.800 | 16.655 | 12.337 | 83.277 |
| GLD | 6.000 | 0.333 | 14.958 | -1.950 | 89.749 |
| IWM | 6.000 | 0.500 | 13.468 | 7.235 | 80.806 |
| QQQ | 4.000 | 1.000 | 36.839 | 32.548 | 147.357 |
| SHY | 4.000 | 0.250 | 2.677 | -0.201 | 10.709 |
| SPY | 7.000 | 0.714 | 11.022 | 6.360 | 77.154 |
| TLT | 9.000 | 0.000 | -4.518 | -4.386 | -40.658 |
| VNQ | 8.000 | 0.375 | 3.007 | -1.558 | 24.057 |
| XLB | 9.000 | 0.333 | 2.780 | -4.315 | 25.017 |
| XLE | 8.000 | 0.375 | 16.475 | -5.054 | 131.797 |
| XLF | 6.000 | 0.500 | 10.711 | 0.918 | 64.267 |
| XLI | 6.000 | 0.667 | 12.334 | 16.101 | 74.003 |
| XLK | 5.000 | 0.800 | 28.165 | 15.376 | 140.826 |
| XLP | 8.000 | 0.375 | 3.243 | -1.563 | 25.947 |
| XLU | 8.000 | 0.500 | 4.026 | -0.542 | 32.212 |
| XLV | 9.000 | 0.444 | 3.426 | -1.904 | 30.834 |
| XLY | 7.000 | 0.571 | 8.463 | 1.217 | 59.240 |

Test-window consistency: downside deviation 4.419%, Sortino-like nan, longest losing streak 17 trades, 6% of 345 active weeks profitable.

**Reality-check verdict:** Per-trade gains are explained by market drift while exposed; no timing edge beyond random entries. Per exposure-day it earned +0.0564% vs buy-and-hold +0.0399%/day (better than simply holding while invested).

