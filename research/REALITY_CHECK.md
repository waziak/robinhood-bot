# Reality Check — candidates that passed validation

Generated 2026-09-13 18:47 UTC by `python -m research.reality_check`. Random-entry null: 2000 simulations of long trades on the same symbols with the same holding periods inside the same window, charged the same round-trip costs. A strategy whose mean does not beat that null is earning market drift, not timing.

## trend_sma200

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
| 2022 | 52.000 | 0.192 | -1.134 | -1.358 | -58.943 |
| 2023 | 47.000 | 0.298 | 4.097 | -0.746 | 192.574 |
| 2024 | 19.000 | 0.316 | -0.818 | -0.860 | -15.539 |
| 2025 | 39.000 | 0.282 | 2.391 | -0.950 | 93.246 |
| 2026 | 20.000 | 0.300 | 4.115 | -0.297 | 82.299 |

Test window by symbol:

| symbol | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| DIA | 26.000 | 0.269 | 1.918 | -1.122 | 49.858 |
| GLD | 25.000 | 0.200 | -0.293 | -0.648 | -7.325 |
| IWM | 16.000 | 0.312 | 0.572 | -0.832 | 9.158 |
| QQQ | 11.000 | 0.364 | 14.648 | -0.606 | 161.132 |
| SPY | 15.000 | 0.400 | 6.206 | -0.352 | 93.087 |
| TLT | 42.000 | 0.095 | -1.201 | -1.215 | -50.460 |
| XLE | 25.000 | 0.320 | 4.427 | -0.950 | 110.673 |
| XLF | 19.000 | 0.211 | 4.208 | -0.477 | 79.947 |
| XLK | 9.000 | 0.444 | 10.933 | -0.122 | 98.398 |
| XLV | 33.000 | 0.333 | 1.113 | -0.477 | 36.742 |

**Reality-check verdict:** Per-trade gains are explained by market drift while exposed; no timing edge beyond random entries. Per exposure-day it earned +0.0621% vs buy-and-hold +0.0483%/day (better than simply holding while invested).

## rsi2_mean_reversion

Hypothesis: Sharp 2-3 day selloffs inside a long-term uptrend overshoot and revert within days as liquidity providers are paid to absorb flow.
Parameters (unchanged): `{'rsi_max': 10, 'stop_pct': 0.1, 'max_hold': 10}`

| split | n | mean net %/trade | t-stat | random-entry null mean % | strategy percentile vs null | excess %/trade | avg days held | net %/exposure-day | buy&hold %/day | time in market | 1-bar-delayed entry mean % | mean @3x / @5x costs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train | 432 | +0.429 | 4.11 | +0.105 | 99% | +0.323 | 4.5 | +0.0947 | +0.0238 | 10% | +0.360 | +0.329 / +0.228 |
| validation | 225 | +0.202 | 1.91 | +0.211 | 46% | -0.008 | 4.6 | +0.0438 | +0.0519 | 15% | +0.197 | +0.102 / +0.002 |
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

**Reality-check verdict:** Weak evidence of timing edge beyond random entries (80-95% percentile) — not conclusive. Per exposure-day it earned +0.0942% vs buy-and-hold +0.0529%/day (better than simply holding while invested).

