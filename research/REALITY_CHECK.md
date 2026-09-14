# Reality Check — candidates that passed formal validation

Generated 2026-09-14 00:23 UTC by `python -m research.reality_check`. Targets are auto-detected from `run_candidates` decisions (nothing hand-picked). 7 of 16 candidates reached this stage. Random-entry null: 2000 simulations of long trades on the same symbols with the same holding periods inside the same window, charged the same round-trip costs. A strategy whose mean does not beat that null is earning market drift, not timing.

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

## pullback_from_high

Formal validation-gate decision: **PASSED VALIDATION — test set already used earlier (see TEST_SET_LOG.md); not re-evaluated**
Hypothesis: Cross-check of the same broad hypothesis (short-term overreaction inside a long-term uptrend reverts) using
    a DIFFERENT technical construction — a simple % pullback from the trailing high instead of RSI(2) — to test
    whether the effect is specific to the RSI formula or a more general short-term-oversold phenomenon.
Parameters (unchanged): `{'high_lookback': 10, 'pullback_pct': 0.03, 'stop_pct': 0.1, 'max_hold': 10}`

| split | n | mean net %/trade | t-stat | random-entry null mean % | strategy percentile vs null | excess %/trade | avg days held | net %/exposure-day | buy&hold %/day | time in market | 1-bar-delayed entry mean % | mean @3x / @5x costs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train | 253 | +0.371 | 2.72 | +0.069 | 96% | +0.302 | 3.4 | +0.1090 | +0.0238 | 4% | +0.170 | +0.271 / +0.170 |
| validation | 93 | +0.631 | 4.78 | +0.121 | 100% | +0.510 | 3.2 | +0.1989 | +0.0519 | 4% | +0.153 | +0.530 / +0.430 |
| test | 113 | +0.152 | 0.70 | +0.168 | 47% | -0.017 | 3.4 | +0.0441 | +0.0529 | 6% | +0.530 | +0.052 / -0.049 |

Test window by year:

| year | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| 2020 | 25.000 | 0.520 | 0.088 | 0.406 | 2.203 |
| 2021 | 18.000 | 0.778 | 0.560 | 0.853 | 10.084 |
| 2022 | 4.000 | 0.500 | -1.123 | 0.886 | -4.494 |
| 2023 | 19.000 | 0.737 | 0.301 | 0.355 | 5.718 |
| 2024 | 26.000 | 0.654 | 0.353 | 0.227 | 9.180 |
| 2025 | 12.000 | 0.333 | -0.386 | -0.390 | -4.631 |
| 2026 | 9.000 | 0.444 | -0.102 | -0.468 | -0.920 |

Test window by symbol:

| symbol | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| DIA | 17.000 | 0.471 | -0.375 | -0.064 | -6.377 |
| IWM | 36.000 | 0.639 | 0.315 | 0.350 | 11.350 |
| QQQ | 41.000 | 0.634 | -0.003 | 0.743 | -0.106 |
| SPY | 19.000 | 0.579 | 0.646 | 0.187 | 12.272 |

Test-window consistency: downside deviation 1.860%, Sortino-like nan, longest losing streak 5 trades, 13% of 340 active weeks profitable.

**Reality-check verdict:** Per-trade gains are explained by market drift while exposed; no timing edge beyond random entries. Per exposure-day it earned +0.0441% vs buy-and-hold +0.0529%/day (worse than simply holding while invested).

## weekly_rsi2

Formal validation-gate decision: **PASSED VALIDATION — test set already used earlier (see TEST_SET_LOG.md); not re-evaluated**
Hypothesis: Same reversion hypothesis sampled at WEEKLY resolution instead of daily — a structurally lower-turnover
    variant, and a check for whether the effect is a short-horizon (daily) microstructure artifact or genuinely
    present at a coarser, even-lower-intervention timescale.
Parameters (unchanged): `{'rsi_max': 10, 'sma_weeks': 40, 'hold_weeks': 3}`

| split | n | mean net %/trade | t-stat | random-entry null mean % | strategy percentile vs null | excess %/trade | avg days held | net %/exposure-day | buy&hold %/day | time in market | 1-bar-delayed entry mean % | mean @3x / @5x costs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train | 79 | +1.838 | 3.65 | +0.425 | 99% | +1.412 | 14.4 | +0.1274 | +0.0238 | 6% | +1.838 | +1.738 / +1.635 |
| validation | 49 | +3.347 | 6.39 | +0.764 | 100% | +2.583 | 14.5 | +0.2310 | +0.0519 | 10% | +3.347 | +3.241 / +3.139 |
| test | 41 | +2.242 | 2.69 | +0.840 | 97% | +1.402 | 14.4 | +0.1561 | +0.0529 | 9% | +2.242 | +2.140 / +2.038 |

Test window by year:

| year | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| 2020 | 4.000 | 0.750 | 0.959 | 6.132 | 3.835 |
| 2021 | 7.000 | 0.857 | 3.564 | 3.748 | 24.951 |
| 2023 | 8.000 | 0.625 | 1.674 | 0.639 | 13.391 |
| 2024 | 8.000 | 0.875 | 5.482 | 5.484 | 43.856 |
| 2025 | 4.000 | 0.750 | 3.299 | 3.921 | 13.197 |
| 2026 | 10.000 | 0.200 | -0.730 | -1.289 | -7.297 |

Test window by symbol:

| symbol | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| DIA | 9.000 | 0.556 | 1.941 | 3.228 | 17.471 |
| IWM | 11.000 | 0.727 | 2.608 | 2.161 | 28.685 |
| QQQ | 10.000 | 0.600 | 1.985 | 3.781 | 19.853 |
| SPY | 11.000 | 0.636 | 2.357 | 2.388 | 25.924 |

Test-window consistency: downside deviation 3.067%, Sortino-like nan, longest losing streak 7 trades, 6% of 317 active weeks profitable.

**Reality-check verdict:** Timing edge beyond random entries at the 95% level. Per exposure-day it earned +0.1561% vs buy-and-hold +0.0529%/day (better than simply holding while invested).

## combined_trend_vol_rsi2

Formal validation-gate decision: **PASSED VALIDATION — test set already used earlier (see TEST_SET_LOG.md); not re-evaluated**
Hypothesis: Combines three INDEPENDENTLY defensible signals rather than adding indicators for their own sake: (1) the
    existing trend filter (price above its 200-day average), (2) the existing RSI(2) oversold pullback, and (3) a
    volatility filter requiring the instrument NOT be in its own trailing-high-volatility tercile. Hypothesis:
    rsi2_mean_reversion's diagnostic breakdown showed its 'high' realized-volatility bucket was flat-to-negative in
    2 of 3 splits (train -0.04%, test -0.12%) while 'low'/'mid' were consistently positive in all three — excluding
    the high-volatility tercile should remove a specifically weak slice rather than mine for a better one, since the
    other two buckets are kept exactly as before, unfiltered.
Parameters (unchanged): `{'rsi_max': 10, 'stop_pct': 0.1, 'max_hold': 10}`

| split | n | mean net %/trade | t-stat | random-entry null mean % | strategy percentile vs null | excess %/trade | avg days held | net %/exposure-day | buy&hold %/day | time in market | 1-bar-delayed entry mean % | mean @3x / @5x costs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train | 350 | +0.464 | 4.34 | +0.095 | 99% | +0.368 | 4.3 | +0.1076 | +0.0238 | 7% | +0.423 | +0.364 / +0.263 |
| validation | 172 | +0.193 | 1.89 | +0.202 | 46% | -0.009 | 4.6 | +0.0417 | +0.0519 | 12% | +0.049 | +0.092 / -0.007 |
| test | 186 | +0.519 | 4.19 | +0.209 | 95% | +0.310 | 4.2 | +0.1222 | +0.0529 | 12% | +0.357 | +0.419 / +0.318 |

Test window by year:

| year | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| 2020 | 19.000 | 0.947 | 1.296 | 1.003 | 24.632 |
| 2021 | 42.000 | 0.762 | 0.617 | 0.736 | 25.930 |
| 2022 | 5.000 | 0.600 | 0.275 | 0.746 | 1.374 |
| 2023 | 37.000 | 0.595 | 0.057 | 0.208 | 2.116 |
| 2024 | 26.000 | 0.731 | 0.511 | 0.576 | 13.292 |
| 2025 | 27.000 | 0.778 | 0.306 | 0.786 | 8.262 |
| 2026 | 30.000 | 0.700 | 0.699 | 0.887 | 20.964 |

Test window by symbol:

| symbol | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| DIA | 51.000 | 0.706 | 0.402 | 0.518 | 20.527 |
| IWM | 46.000 | 0.761 | 0.538 | 0.742 | 24.737 |
| QQQ | 40.000 | 0.800 | 0.609 | 0.737 | 24.377 |
| SPY | 49.000 | 0.673 | 0.550 | 0.715 | 26.929 |

Test-window consistency: downside deviation 1.172%, Sortino-like nan, longest losing streak 4 trades, 20% of 346 active weeks profitable.

**Reality-check verdict:** Weak evidence of timing edge beyond random entries (80-95th percentile) — not conclusive. Per exposure-day it earned +0.1222% vs buy-and-hold +0.0529%/day (better than simply holding while invested).

## low_volatility_rotation

Formal validation-gate decision: **PASSED VALIDATION — test set already used earlier (see TEST_SET_LOG.md); not re-evaluated**
Hypothesis: Low-volatility anomaly (Ang, Hodges, Xing & Zhang 2006; Baker, Bradley & Wurgler 2011): lower-volatility
    assets have historically delivered comparable or better risk-adjusted returns than higher-volatility ones,
    plausibly because leverage-constrained investors bid up higher-beta assets for a given expected return. Monthly,
    equal-weight-hold the `top_n` lowest-trailing-realized-volatility instruments in the universe; no absolute
    filter (always invested, unlike the momentum rotation candidate) since low-vol is a relative-ranking effect.
Parameters (unchanged): `{'vol_lookback_months': 6, 'top_n': 5}`

| split | n | mean net %/trade | t-stat | random-entry null mean % | strategy percentile vs null | excess %/trade | avg days held | net %/exposure-day | buy&hold %/day | time in market | 1-bar-delayed entry mean % | mean @3x / @5x costs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train | 318 | +2.046 | 2.92 | +1.788 | 69% | +0.258 | 61.3 | +0.0334 | +0.0258 | 384% | +nan | +1.896 / +1.756 |
| validation | 215 | +1.509 | 4.58 | +1.457 | 57% | +0.052 | 39.0 | +0.0386 | +0.0418 | 495% | +nan | +1.368 / +1.229 |
| test | 175 | +1.604 | 2.63 | +1.802 | 34% | -0.198 | 47.4 | +0.0338 | +0.0334 | 492% | +nan | +1.457 / +1.310 |

Test window by year:

| year | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| 2020 | 15.000 | 0.400 | 2.450 | -6.716 | 36.748 |
| 2021 | 35.000 | 0.714 | 2.080 | 2.139 | 72.783 |
| 2022 | 30.000 | 0.400 | -0.247 | -1.125 | -7.411 |
| 2023 | 15.000 | 0.733 | 4.550 | 2.485 | 68.252 |
| 2024 | 30.000 | 0.567 | 0.999 | 1.125 | 29.958 |
| 2025 | 40.000 | 0.525 | 0.941 | 0.712 | 37.639 |
| 2026 | 10.000 | 0.600 | 4.275 | 1.072 | 42.752 |

Test window by symbol:

| symbol | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| DIA | 26.000 | 0.615 | 2.705 | 1.781 | 70.339 |
| EEM | 1.000 | 1.000 | 2.363 | 2.363 | 2.363 |
| EFA | 16.000 | 0.438 | 2.215 | -0.920 | 35.437 |
| GLD | 13.000 | 0.615 | 4.645 | 0.820 | 60.386 |
| SPY | 18.000 | 0.667 | 1.874 | 2.520 | 33.733 |
| TLT | 20.000 | 0.550 | -0.802 | 0.471 | -16.044 |
| VNQ | 6.000 | 0.500 | 0.170 | -1.370 | 1.020 |
| XLB | 1.000 | 0.000 | -10.518 | -10.518 | -10.518 |
| XLF | 3.000 | 1.000 | 5.385 | 2.342 | 16.154 |
| XLP | 34.000 | 0.500 | 1.548 | -0.080 | 52.619 |
| XLU | 10.000 | 0.400 | -2.399 | -1.803 | -23.995 |
| XLV | 27.000 | 0.593 | 2.194 | 1.506 | 59.226 |

Test-window consistency: downside deviation 3.837%, Sortino-like nan, longest losing streak 11 trades, 6% of 341 active weeks profitable.

**Reality-check verdict:** Per-trade gains are explained by market drift while exposed; no timing edge beyond random entries. Per exposure-day it earned +0.0338% vs buy-and-hold +0.0334%/day (better than simply holding while invested).

