# RSI2 Mean-Reversion — Diagnostic Attribution (research only, no parameters changed)

Generated 2026-09-13 23:47 UTC by `python -m research.rsi2_diagnostics`. Explains the already-sealed rsi2_mean_reversion evaluation (46th percentile vs. random-entry null in validation, 85th in test) — every trade below is identical to the sealed run; only the grouping is new. This is NOT a re-evaluation and produces no new candidate; see the note at the end for what a legitimate follow-up would require.

Windows: train 1993-01-29→2013-03-31, validation 2013-03-31→2019-12-21, test 2019-12-21→2026-09-11 (sealed).

### By instrument

train:

| symbol | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| DIA | 98.000 | 0.673 | 0.164 | 0.552 | 16.110 |
| IWM | 92.000 | 0.728 | 0.469 | 0.989 | 43.188 |
| QQQ | 94.000 | 0.628 | 0.336 | 0.766 | 31.548 |
| SPY | 148.000 | 0.770 | 0.638 | 0.700 | 94.388 |

validation:

| symbol | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| DIA | 62.000 | 0.677 | 0.189 | 0.385 | 11.706 |
| IWM | 48.000 | 0.688 | 0.213 | 0.528 | 10.217 |
| QQQ | 61.000 | 0.639 | 0.175 | 0.633 | 10.687 |
| SPY | 54.000 | 0.667 | 0.238 | 0.427 | 12.852 |

test:

| symbol | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| DIA | 64.000 | 0.688 | 0.346 | 0.637 | 22.154 |
| IWM | 53.000 | 0.774 | 0.414 | 0.765 | 21.957 |
| QQQ | 58.000 | 0.759 | 0.464 | 0.797 | 26.892 |
| SPY | 61.000 | 0.705 | 0.392 | 0.738 | 23.921 |

### By market regime (at entry)

train:

| regime_trend | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| range | 28.000 | 0.464 | 0.212 | 0.000 | 5.927 |
| unkno | 4.000 | 1.000 | 2.777 | 0.578 | 11.109 |
| up | 400.000 | 0.723 | 0.420 | 0.724 | 168.198 |

validation:

| regime_trend | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| range | 3.000 | 0.667 | 0.628 | 0.767 | 1.885 |
| up | 222.000 | 0.667 | 0.196 | 0.427 | 43.577 |

test:

| regime_trend | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| range | 9.000 | 0.889 | 1.320 | 1.169 | 11.882 |
| up | 227.000 | 0.722 | 0.366 | 0.719 | 83.041 |

### By volatility regime (at entry, trailing rank vs. own history)

train:

| regime_vol | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| high | 92.000 | 0.609 | -0.042 | 0.821 | -3.837 |
| low | 192.000 | 0.755 | 0.602 | 0.691 | 115.675 |
| mid | 134.000 | 0.687 | 0.423 | 0.659 | 56.697 |
| unknown | 14.000 | 0.929 | 1.193 | 0.694 | 16.700 |

validation:

| regime_vol | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| high | 55.000 | 0.673 | 0.204 | 0.774 | 11.217 |
| low | 97.000 | 0.619 | 0.184 | 0.315 | 17.862 |
| mid | 73.000 | 0.726 | 0.224 | 0.574 | 16.383 |

test:

| regime_vol | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| high | 53.000 | 0.679 | -0.119 | 0.738 | -6.322 |
| low | 112.000 | 0.696 | 0.403 | 0.640 | 45.162 |
| mid | 71.000 | 0.817 | 0.790 | 0.853 | 56.084 |

### By entry severity (RSI(2) value at entry — lower = more oversold)

train:

| rsi_bucket | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| <5 (extreme) | 114.000 | 0.719 | 0.567 | 0.837 | 64.605 |
| 5-8 | 165.000 | 0.691 | 0.464 | 0.736 | 76.584 |
| 8-10 (mild) | 153.000 | 0.719 | 0.288 | 0.642 | 44.045 |

validation:

| rsi_bucket | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| <5 (extreme) | 59.000 | 0.729 | 0.212 | 0.776 | 12.517 |
| 5-8 | 92.000 | 0.630 | 0.135 | 0.400 | 12.381 |
| 8-10 (mild) | 74.000 | 0.662 | 0.278 | 0.421 | 20.564 |

test:

| rsi_bucket | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| <5 (extreme) | 64.000 | 0.750 | 0.167 | 0.883 | 10.706 |
| 5-8 | 102.000 | 0.725 | 0.456 | 0.710 | 46.464 |
| 8-10 (mild) | 70.000 | 0.714 | 0.539 | 0.684 | 37.754 |

### By holding period

train:

| hold_bucket | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| 1-2d | 53.000 | 0.962 | 1.032 | 0.926 | 54.683 |
| 3-4d | 203.000 | 0.906 | 1.283 | 1.231 | 260.405 |
| 5-6d | 106.000 | 0.575 | 0.223 | 0.320 | 23.671 |
| 7-10d | 70.000 | 0.143 | -2.193 | -1.645 | -153.525 |

validation:

| hold_bucket | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| 1-2d | 25.000 | 0.800 | 0.041 | 0.456 | 1.035 |
| 3-4d | 103.000 | 0.883 | 1.027 | 1.060 | 105.730 |
| 5-6d | 60.000 | 0.550 | -0.003 | 0.038 | -0.186 |
| 7-10d | 37.000 | 0.162 | -1.652 | -1.738 | -61.118 |

test:

| hold_bucket | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| 1-2d | 39.000 | 0.846 | 0.780 | 0.790 | 30.407 |
| 3-4d | 114.000 | 0.833 | 0.802 | 1.144 | 91.446 |
| 5-6d | 54.000 | 0.667 | 0.477 | 0.364 | 25.754 |
| 7-10d | 29.000 | 0.276 | -1.817 | -0.914 | -52.684 |

### By exit behavior

train:

| exit_reason | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| rule | 421.000 | 0.727 | 0.643 | 0.731 | 270.609 |
| stop | 6.000 | 0.000 | -9.724 | -10.039 | -58.344 |
| time | 5.000 | 0.000 | -5.406 | -5.231 | -27.031 |

validation:

| exit_reason | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| rule | 222.000 | 0.676 | 0.283 | 0.449 | 62.934 |
| stop_gap | 1.000 | 0.000 | -10.795 | -10.795 | -10.795 |
| time | 2.000 | 0.000 | -3.339 | -3.339 | -6.677 |

test:

| exit_reason | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| rule | 224.000 | 0.763 | 0.702 | 0.788 | 157.317 |
| stop | 1.000 | 0.000 | -7.031 | -7.031 | -7.031 |
| stop_gap | 3.000 | 0.000 | -10.973 | -10.929 | -32.920 |
| time | 8.000 | 0.125 | -2.805 | -1.764 | -22.442 |

### Trend strength (continuous, correlation with outcome)

- train: Spearman(distance above SMA200 %, net return) = +0.121 (n=432)
- validation: Spearman(distance above SMA200 %, net return) = -0.148 (n=225)
- test: Spearman(distance above SMA200 %, net return) = +0.070 (n=236)

## What the validation window actually looked like

The validation window (2013-03-31 → 2019-12-21) was a near-uninterrupted secular bull market for all four ETFs — very few sustained drawdowns, meaning the "sharp 2-3 day selloff inside a long-term uptrend" setup this strategy targets was both rarer and shallower than in the test window (which includes the 2020 COVID crash and 2022 bear market). If the effect concentrates in higher-volatility / sharper-selloff conditions, a quiet validation window would mechanically produce weaker results than a volatile test window — that would be a genuine regime-dependence finding, not noise, but it also means the validation window may simply be a poor test of this specific hypothesis rather than evidence against it.

Check this directly: validation-window volatility-regime mix vs. test-window mix:

- validation: {'low': 0.43, 'mid': 0.32, 'high': 0.24}
- test: {'low': 0.47, 'mid': 0.3, 'high': 0.22}

## What would legitimately follow from this (not done here)

If the breakdowns above show the effect concentrating in a specific slice (e.g., only in "high" volatility regime, or only RSI<5 rather than <10), that becomes a NEW, separately pre-registered hypothesis ("RSI2 pullbacks conditioned on high realized volatility") requiring its own fresh train/validation/test split and its own sealed test window — it would NOT be graded by reapplying it to rsi2_mean_reversion's already-used test data, and it counts as an additional hypothesis for the multiple-testing tally in `research/multiple_testing.py`, raising the bar required of everything else.
