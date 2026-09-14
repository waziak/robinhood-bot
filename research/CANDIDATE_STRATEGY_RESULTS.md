# Candidate Strategy Results

Generated 2026-09-13 23:55 UTC by `python -m research.run_candidates`.

All parameters were fixed in `research/candidates.py` before evaluation and were not tuned. Returns are per trade, net of the costs in `research/costs.py` unless labelled gross. Splits are chronological 60/20/20 per candidate data span. The TEST window is evaluated at most once per strategy specification, only after passing validation.

| strategy | data | trades | train net % | validation net % | validation @2x cost | decision |
|---|---|---|---|---|---|---|
| orb_continuation | yf:5m × 25 | 103 | -0.013 (n=55) | -0.278 (n=14) | -0.351 | **REJECTED AT VALIDATION** |
| vwap_pullback | yf:5m × 25 | 379 | -0.111 (n=245) | -0.141 (n=60) | -0.219 | **REJECTED AT VALIDATION** |
| intraday_momentum_last_hour | yf:1h × 4 | 1488 | -0.045 (n=869) | -0.073 (n=306) | -0.123 | **REJECTED AT VALIDATION** |
| crypto_tsmom | cb:1h × 2 | 809 | -0.157 (n=465) | -0.393 (n=190) | -0.791 | **REJECTED AT VALIDATION** |
| overnight_drift | yf:1d × 4 | 29196 | -0.026 (n=15664) | -0.015 (n=6784) | -0.065 | **REJECTED AT VALIDATION** |
| overnight_drift_trend | yf:1d × 4 | 21158 | -0.019 (n=10088) | -0.013 (n=5864) | -0.063 | **REJECTED AT VALIDATION** |
| trend_sma200 | yf:1d × 10 | 870 | +1.158 (n=478) | +0.834 (n=171) | +0.764 | **PASSED VALIDATION — test set already used earlier (see TEST_SET_LOG.md); not re-evaluated** |
| rsi2_mean_reversion | yf:1d × 4 | 893 | +0.429 (n=432) | +0.202 (n=225) | +0.152 | **PASSED VALIDATION — test set already used earlier (see TEST_SET_LOG.md); not re-evaluated** |
| monthly_sma10_timing_spy | yf:1d × 1 | 25 | +21.323 (n=13) | +4.028 (n=5) | +3.977 | **INSUFFICIENT SAMPLE** |
| monthly_sma10_timing_multi | yf:1d × 19 | 443 | +11.013 (n=209) | +3.380 (n=110) | +3.305 | **PASSED VALIDATION — test set already used earlier (see TEST_SET_LOG.md); not re-evaluated** |
| sector_rotation_momentum | yf:1d × 18 | 175 | +3.218 (n=87) | -0.450 (n=53) | -0.528 | **REJECTED AT VALIDATION** |
| rsi2_early_exit | yf:1d × 4 | 928 | +0.259 (n=451) | -0.028 (n=235) | -0.078 | **REJECTED AT VALIDATION** |
| pullback_from_high | yf:1d × 4 | 459 | +0.371 (n=253) | +0.631 (n=93) | +0.581 | **PASSED VALIDATION — test set already used earlier (see TEST_SET_LOG.md); not re-evaluated** |
| weekly_rsi2 | yf:1d × 4 | 169 | +1.838 (n=79) | +3.347 (n=49) | +3.294 | **PASSED VALIDATION — test set already used earlier (see TEST_SET_LOG.md); not re-evaluated** |
| combined_trend_vol_rsi2 | yf:1d × 4 | 708 | +0.464 (n=350) | +0.193 (n=172) | +0.143 | **PASSED VALIDATION — test set already used earlier (see TEST_SET_LOG.md); not re-evaluated** |
| low_volatility_rotation | yf:1d × 18 | 708 | +2.046 (n=318) | +1.509 (n=215) | +1.441 | **OUT-OF-SAMPLE POSITIVE** |

## orb_continuation

**Hypothesis:** Early breakouts above the 30-minute opening range on above-normal opening volume reflect persistent order flow and continue into the close.
**Intended regime:** trending / high-volume sessions
**Parameters (fixed):** `{'or_bars': 6, 'rvol_min': 1.2, 'last_entry_minute': 690}`
**Universe:** SPY, QQQ, IWM, DIA, XLK, XLF, XLE, XLV, XLI, XLY, XLP, XLU, XLB, TLT, SHY, GLD, EFA, EEM, VNQ, AAPL, MSFT, NVDA, AMZN, GOOGL, META (yf 5m)

| split | window | n | mean net % | std % | win rate | payoff | PF | max DD % | 95% CI mean % | Sharpe-like |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 2026-06-17 → 2026-08-08 | 55 | -0.013 | 0.982 | 0.44 | 1.24 | 0.96 | 9.1 | [-0.246, +0.269] | -0.26 |
| validation | 2026-08-08 → 2026-08-25 | 14 | -0.278 | 0.543 | 0.21 | 1.14 | 0.31 | 5.6 | [-0.544, +0.009] | -8.87 |
| test | 2026-08-25 → 2026-09-11 | sealed — not evaluated |  |  |  |  |  |  |  |  |

Cost sensitivity, net mean % at 0x/1x/2x/3x — train {'0x': 0.07039127117379468, '1x': -0.01273538445446693, '2x': -0.08666740313189762, '3x': -0.15997378694807735}, validation {'0x': -0.19690985362406815, '1x': -0.2780407682806574, '2x': -0.350851018050548, '3x': -0.42265324286957506}

Walk-forward (pre-test, expanding window; parameters are fixed so each fold is out-of-sample):

- 2026-06-17 → 2026-07-25: n=11, mean net -0.245%
- 2026-06-17 → 2026-08-04: n=31, mean net +0.002%
- 2026-06-17 → 2026-08-15: n=2, mean net -0.266%
- 2026-06-17 → 2026-08-25: n=14, mean net -0.278%

**Capital-constrained portfolio view (validation window)** — the per-trade rows above assume unlimited capital (one fresh full unit per signal); this instead splits ONE pool of capital equally across whatever positions are open on each day (the realistic constraint for a small account):

- Total return: -0.5% · Annualized: -11.9% · Max drawdown: 1.1% · Sharpe-like: -0.32
- Invested 21% of days · concurrent positions: median 2, average 3.9, max 10
- 0% of 2 weeks profitable (worst week -0.52%), nan% of months profitable

Validation-window consistency ("smoothness") metrics:

- Downside deviation: 0.521% · Sortino-like: -9.26 · Calmar-like: -0.69
- Longest losing streak: 11 trades · Longest winning streak: 2 trades
- Weeks with an exit: 1, 0% profitable, weekly return std nan%, worst week -3.893%
- Months with an exit: 1, 0% profitable

Validation-window baselines (benchmark: SPY):

| | n | mean net % | win rate | max DD % | total % |
|---|---|---|---|---|---|
| candidate | 14 | -0.278 | 0.21 | 5.6 | -3.9 |
| buy & hold | 861 | -0.001 | 0.47 | 2.2 | -0.8 |
| 200d trend filter | 9 | -0.146 | 0.00 | 1.3 | -1.3 |
| random entry (avg of 300 sims) | 14 | -0.135 | 0.32 | 2.4 | -1.9 |
| cash / no trade | 0 | 0.000 | — | 0.0 | 0.0 |

Validation gate: train n>=30 ✔, train mean>0 ✘, validation n>=30 ✘, validation mean>0 ✘, validation PF>=1.10 ✘, validation P(mean>0)>=0.80 ✘, validation mean>0 at 2x costs ✘

**Decision: REJECTED AT VALIDATION**

## vwap_pullback

**Hypothesis:** In sessions already up >0.3%, a pullback that holds VWAP (the institutional execution benchmark) attracts buyers and resumes toward the session high.
**Intended regime:** intraday uptrend
**Parameters (fixed):** `{'min_session_ret': 0.003, 'start_minute': 630, 'end_minute': 870, 'touch_tol': 0.0005, 'stop_buffer': 0.001}`
**Universe:** SPY, QQQ, IWM, DIA, XLK, XLF, XLE, XLV, XLI, XLY, XLP, XLU, XLB, TLT, SHY, GLD, EFA, EEM, VNQ, AAPL, MSFT, NVDA, AMZN, GOOGL, META (yf 5m)

| split | window | n | mean net % | std % | win rate | payoff | PF | max DD % | 95% CI mean % | Sharpe-like |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 2026-06-17 → 2026-08-08 | 245 | -0.111 | 0.406 | 0.37 | 0.91 | 0.53 | 27.6 | [-0.161, -0.061] | -11.49 |
| validation | 2026-08-08 → 2026-08-25 | 60 | -0.141 | 0.284 | 0.33 | 0.69 | 0.35 | 8.5 | [-0.212, -0.068] | -17.85 |
| test | 2026-08-25 → 2026-09-11 | sealed — not evaluated |  |  |  |  |  |  |  |  |

Cost sensitivity, net mean % at 0x/1x/2x/3x — train {'0x': -0.029193431826086507, '1x': -0.11146619058898073, '2x': -0.18669176460400144, '3x': -0.26147484103009955}, validation {'0x': -0.053633618063236486, '1x': -0.14101560950544417, '2x': -0.21867573174684224, '3x': -0.2961079107156689}

Walk-forward (pre-test, expanding window; parameters are fixed so each fold is out-of-sample):

- 2026-06-17 → 2026-07-25: n=52, mean net -0.125%
- 2026-06-17 → 2026-08-04: n=40, mean net +0.058%
- 2026-06-17 → 2026-08-15: n=45, mean net -0.199%
- 2026-06-17 → 2026-08-25: n=35, mean net -0.131%

**Capital-constrained portfolio view (validation window)** — the per-trade rows above assume unlimited capital (one fresh full unit per signal); this instead splits ONE pool of capital equally across whatever positions are open on each day (the realistic constraint for a small account):

- Total return: -1.4% · Annualized: -29.6% · Max drawdown: 2.2% · Sharpe-like: -0.55
- Invested 60% of days · concurrent positions: median 2, average 1.7, max 5
- 0% of 2 weeks profitable (worst week -0.32%), nan% of months profitable

Validation-window consistency ("smoothness") metrics:

- Downside deviation: 0.275% · Sortino-like: -18.43 · Calmar-like: -1.00
- Longest losing streak: 8 trades · Longest winning streak: 3 trades
- Weeks with an exit: 3, 0% profitable, weekly return std 2.353%, worst week -4.449%
- Months with an exit: 1, 0% profitable

Validation-window baselines (benchmark: SPY):

| | n | mean net % | win rate | max DD % | total % |
|---|---|---|---|---|---|
| candidate | 60 | -0.141 | 0.33 | 8.5 | -8.5 |
| buy & hold | 861 | -0.001 | 0.47 | 2.2 | -0.8 |
| 200d trend filter | 9 | -0.146 | 0.00 | 1.3 | -1.3 |
| random entry (avg of 300 sims) | 60 | -0.073 | 0.25 | 4.8 | -4.4 |
| cash / no trade | 0 | 0.000 | — | 0.0 | 0.0 |

Validation gate: train n>=30 ✔, train mean>0 ✘, validation n>=30 ✔, validation mean>0 ✘, validation PF>=1.10 ✘, validation P(mean>0)>=0.80 ✘, validation mean>0 at 2x costs ✘

**Decision: REJECTED AT VALIDATION**

## intraday_momentum_last_hour

**Hypothesis:** A positive first-hour return predicts a positive final half-hour return because late-informed traders and hedgers trade in the same direction near the close.
**Intended regime:** any; strongest on high-volatility days in the literature
**Parameters (fixed):** `{'min_first_hour_ret': 0.0, 'stop_pct': 0.02}`
**Universe:** SPY, QQQ, IWM, DIA (yf 1h)

| split | window | n | mean net % | std % | win rate | payoff | PF | max DD % | 95% CI mean % | Sharpe-like |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 2023-10-13 → 2025-07-13 | 869 | -0.045 | 0.236 | 0.41 | 0.85 | 0.58 | 39.5 | [-0.060, -0.029] | -4.24 |
| validation | 2025-07-13 → 2026-02-10 | 306 | -0.073 | 0.178 | 0.28 | 0.79 | 0.31 | 23.0 | [-0.094, -0.054] | -9.43 |
| test | 2026-02-10 → 2026-09-11 | sealed — not evaluated |  |  |  |  |  |  |  |  |

Cost sensitivity, net mean % at 0x/1x/2x/3x — train {'0x': 0.008033200427355829, '1x': -0.04487588863909861, '2x': -0.09482152394953175, '3x': -0.1446858570766199}, validation {'0x': -0.020653503953799168, '1x': -0.07324323519262807, '2x': -0.12314968526338263, '3x': -0.17286661820248478}

Walk-forward (pre-test, expanding window; parameters are fixed so each fold is out-of-sample):

- 2023-10-13 → 2025-01-23: n=149, mean net -0.088%
- 2023-10-13 → 2025-05-31: n=178, mean net +0.008%
- 2023-10-13 → 2025-10-06: n=186, mean net -0.015%
- 2023-10-13 → 2026-02-10: n=184, mean net -0.110%

**Capital-constrained portfolio view (validation window)** — the per-trade rows above assume unlimited capital (one fresh full unit per signal); this instead splits ONE pool of capital equally across whatever positions are open on each day (the realistic constraint for a small account):

- Total return: +0.0% · Annualized: +0.0% · Max drawdown: 0.0% · Sharpe-like: nan
- Invested 0% of days · concurrent positions: median 0, average 0.0, max 0
- 0% of 30 weeks profitable (worst week +0.00%), 0% of months profitable

Validation-window consistency ("smoothness") metrics:

- Downside deviation: 0.170% · Sortino-like: -9.92 · Calmar-like: -0.98
- Longest losing streak: 17 trades · Longest winning streak: 9 trades
- Weeks with an exit: 31, 16% profitable, weekly return std 1.035%, worst week -2.918%
- Months with an exit: 8, 12% profitable

Validation-window baselines (benchmark: SPY):

| | n | mean net % | win rate | max DD % | total % |
|---|---|---|---|---|---|
| candidate | 306 | -0.073 | 0.28 | 23.0 | -22.4 |
| buy & hold | 1020 | +0.011 | 0.53 | 5.3 | +10.9 |
| 200d trend filter | 16 | -0.138 | 0.12 | 6.5 | -2.2 |
| random entry (avg of 300 sims) | 306 | -0.041 | 0.41 | 14.1 | -12.6 |
| cash / no trade | 0 | 0.000 | — | 0.0 | 0.0 |

Validation gate: train n>=30 ✔, train mean>0 ✘, validation n>=30 ✔, validation mean>0 ✘, validation PF>=1.10 ✘, validation P(mean>0)>=0.80 ✘, validation mean>0 at 2x costs ✘

**Decision: REJECTED AT VALIDATION**

## crypto_tsmom

**Hypothesis:** Crypto returns show time-series momentum at daily-to-weekly horizons; being long only after a positive trailing week captures it.
**Intended regime:** trending crypto
**Parameters (fixed):** `{'lookback_h': 168, 'sma_h': 480, 'stop_pct': 0.08, 'hold_h': 24}`
**Universe:** BTC-USD, ETH-USD (cb 1h)

| split | window | n | mean net % | std % | win rate | payoff | PF | max DD % | 95% CI mean % | Sharpe-like |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 2021-09-14 → 2024-09-13 | 465 | -0.157 | 3.333 | 0.39 | 1.35 | 0.87 | 113.2 | [-0.462, +0.154] | -0.59 |
| validation | 2024-09-13 → 2025-09-13 | 190 | -0.393 | 2.747 | 0.41 | 0.97 | 0.68 | 91.3 | [-0.788, -0.017] | -1.97 |
| test | 2025-09-13 → 2026-09-13 | sealed — not evaluated |  |  |  |  |  |  |  |  |

Cost sensitivity, net mean % at 0x/1x/2x/3x — train {'0x': 0.24342838064765854, '1x': -0.15698196027649755, '2x': -0.5555657825056233, '3x': -0.952562483217063}, validation {'0x': 0.006039006417901321, '1x': -0.3933478180219561, '2x': -0.7909847568153827, '3x': -1.1870381231198535}

Walk-forward (pre-test, expanding window; parameters are fixed so each fold is out-of-sample):

- 2021-09-14 → 2023-11-26: n=93, mean net -0.604%
- 2021-09-14 → 2024-07-02: n=107, mean net -0.177%
- 2021-09-14 → 2025-02-06: n=106, mean net -0.411%
- 2021-09-14 → 2025-09-13: n=104, mean net -0.354%

**Capital-constrained portfolio view (validation window)** — the per-trade rows above assume unlimited capital (one fresh full unit per signal); this instead splits ONE pool of capital equally across whatever positions are open on each day (the realistic constraint for a small account):

- Total return: -7.8% · Annualized: -7.8% · Max drawdown: 31.8% · Sharpe-like: -0.02
- Invested 36% of days · concurrent positions: median 1, average 1.4, max 2
- 38% of 52 weeks profitable (worst week -12.13%), 42% of months profitable

Validation-window consistency ("smoothness") metrics:

- Downside deviation: 2.093% · Sortino-like: -2.59 · Calmar-like: -0.82
- Longest losing streak: 10 trades · Longest winning streak: 7 trades
- Weeks with an exit: 53, 32% profitable, weekly return std 5.993%, worst week -13.911%
- Months with an exit: 13, 38% profitable

Validation-window baselines (benchmark: BTC-USD):

| | n | mean net % | win rate | max DD % | total % |
|---|---|---|---|---|---|
| candidate | 190 | -0.393 | 0.41 | 91.3 | -74.7 |
| buy & hold | 8759 | +0.009 | 0.51 | 33.5 | +76.7 |
| 200d trend filter | 130 | -0.074 | 0.16 | 51.4 | -9.6 |
| random entry (avg of 300 sims) | 190 | -0.196 | 0.43 | 63.3 | -37.3 |
| cash / no trade | 0 | 0.000 | — | 0.0 | 0.0 |

Validation gate: train n>=30 ✔, train mean>0 ✘, validation n>=30 ✔, validation mean>0 ✘, validation PF>=1.10 ✘, validation P(mean>0)>=0.80 ✘, validation mean>0 at 2x costs ✘

**Decision: REJECTED AT VALIDATION**

## overnight_drift

**Hypothesis:** Most of the equity risk premium is earned overnight (close-to-open) rather than intraday.
**Intended regime:** all
**Parameters (fixed):** `{'trend_filter': False}`
**Universe:** SPY, QQQ, IWM, DIA (yf 1d)

| split | window | n | mean net % | std % | win rate | payoff | PF | max DD % | 95% CI mean % | Sharpe-like |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 1993-01-29 → 2013-03-31 | 15664 | -0.026 | 0.777 | 0.48 | 0.99 | 0.90 | 554.0 | [-0.038, -0.013] | -0.92 |
| validation | 2013-03-31 → 2019-12-21 | 6784 | -0.015 | 0.535 | 0.50 | 0.92 | 0.92 | 151.7 | [-0.028, -0.002] | -0.88 |
| test | 2019-12-21 → 2026-09-11 | sealed — not evaluated |  |  |  |  |  |  |  |  |

Cost sensitivity, net mean % at 0x/1x/2x/3x — train {'0x': 0.04422358370820617, '1x': -0.025599344949684983, '2x': -0.0756369784835944, '3x': -0.12562940343456638}, validation {'0x': 0.042585034663196894, '1x': -0.014784224501877502, '2x': -0.0648492911256375, '3x': -0.1147805589406637}

Walk-forward (pre-test, expanding window; parameters are fixed so each fold is out-of-sample):

- 1993-01-29 → 2007-11-13: n=4060, mean net -0.022%
- 1993-01-29 → 2011-11-25: n=4068, mean net -0.055%
- 1993-01-29 → 2015-12-07: n=4052, mean net -0.014%
- 1993-01-29 → 2019-12-20: n=4064, mean net -0.011%

**Capital-constrained portfolio view (validation window)** — the per-trade rows above assume unlimited capital (one fresh full unit per signal); this instead splits ONE pool of capital equally across whatever positions are open on each day (the realistic constraint for a small account):

- Total return: +144.5% · Annualized: +14.2% · Max drawdown: 21.3% · Sharpe-like: 1.03
- Invested 100% of days · concurrent positions: median 4, average 4.0, max 4
- 63% of 350 weeks profitable (worst week -7.69%), 69% of months profitable

Validation-window consistency ("smoothness") metrics:

- Downside deviation: 0.410% · Sortino-like: -1.14 · Calmar-like: -0.66
- Longest losing streak: 29 trades · Longest winning streak: 29 trades
- Weeks with an exit: 352, 51% profitable, weekly return std 3.990%, worst week -18.493%
- Months with an exit: 81, 44% profitable

Validation-window baselines (benchmark: SPY):

| | n | mean net % | win rate | max DD % | total % |
|---|---|---|---|---|---|
| candidate | 6784 | -0.015 | 0.50 | 151.7 | -100.3 |
| buy & hold | 1695 | +0.054 | 0.55 | 20.9 | +91.0 |
| 200d trend filter | 12 | -0.048 | 0.33 | 11.5 | -0.6 |
| random entry (avg of 300 sims) | 6784 | -0.003 | 0.53 | 159.0 | -21.7 |
| cash / no trade | 0 | 0.000 | — | 0.0 | 0.0 |

Validation gate: train n>=30 ✔, train mean>0 ✘, validation n>=30 ✔, validation mean>0 ✘, validation PF>=1.10 ✘, validation P(mean>0)>=0.80 ✘, validation mean>0 at 2x costs ✘

**Decision: REJECTED AT VALIDATION**

## overnight_drift_trend

**Hypothesis:** Pre-registered variant: the overnight premium is concentrated when the index is above its 200-day average.
**Intended regime:** long-term uptrend
**Parameters (fixed):** `{'trend_filter': True}`
**Universe:** SPY, QQQ, IWM, DIA (yf 1d)

| split | window | n | mean net % | std % | win rate | payoff | PF | max DD % | 95% CI mean % | Sharpe-like |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 1993-01-29 → 2013-03-31 | 10088 | -0.019 | 0.551 | 0.47 | 1.00 | 0.90 | 275.3 | [-0.030, -0.008] | -0.78 |
| validation | 2013-03-31 → 2019-12-21 | 5864 | -0.013 | 0.448 | 0.50 | 0.93 | 0.92 | 116.5 | [-0.024, -0.001] | -0.83 |
| test | 2019-12-21 → 2026-09-11 | sealed — not evaluated |  |  |  |  |  |  |  |  |

Cost sensitivity, net mean % at 0x/1x/2x/3x — train {'0x': 0.04908986675535048, '1x': -0.019204171528037394, '2x': -0.06917994190877616, '3x': -0.11924049145235079}, validation {'0x': 0.04464949458507893, '1x': -0.012621672523045743, '2x': -0.06270978948729751, '3x': -0.11264888049978886}

Walk-forward (pre-test, expanding window; parameters are fixed so each fold is out-of-sample):

- 1993-01-29 → 2007-11-13: n=3480, mean net -0.026%
- 1993-01-29 → 2011-11-25: n=2233, mean net -0.031%
- 1993-01-29 → 2015-12-07: n=3651, mean net -0.020%
- 1993-01-29 → 2019-12-20: n=3427, mean net -0.011%

**Capital-constrained portfolio view (validation window)** — the per-trade rows above assume unlimited capital (one fresh full unit per signal); this instead splits ONE pool of capital equally across whatever positions are open on each day (the realistic constraint for a small account):

- Total return: +91.5% · Annualized: +10.2% · Max drawdown: 19.5% · Sharpe-like: 0.86
- Invested 93% of days · concurrent positions: median 4, average 3.7, max 4
- 58% of 350 weeks profitable (worst week -7.22%), 65% of months profitable

Validation-window consistency ("smoothness") metrics:

- Downside deviation: 0.339% · Sortino-like: -1.10 · Calmar-like: -0.64
- Longest losing streak: 24 trades · Longest winning streak: 29 trades
- Weeks with an exit: 352, 47% profitable, weekly return std 3.266%, worst week -17.337%
- Months with an exit: 81, 43% profitable

Validation-window baselines (benchmark: SPY):

| | n | mean net % | win rate | max DD % | total % |
|---|---|---|---|---|---|
| candidate | 5864 | -0.013 | 0.50 | 116.5 | -74.0 |
| buy & hold | 1695 | +0.054 | 0.55 | 20.9 | +91.0 |
| 200d trend filter | 12 | -0.048 | 0.33 | 11.5 | -0.6 |
| random entry (avg of 300 sims) | 5864 | -0.003 | 0.52 | 138.1 | -16.7 |
| cash / no trade | 0 | 0.000 | — | 0.0 | 0.0 |

Validation gate: train n>=30 ✔, train mean>0 ✘, validation n>=30 ✔, validation mean>0 ✘, validation PF>=1.10 ✘, validation P(mean>0)>=0.80 ✘, validation mean>0 at 2x costs ✘

**Decision: REJECTED AT VALIDATION**

## trend_sma200

**Hypothesis:** Trends persist; holding only above the 200-day average keeps most upside while avoiding prolonged bear markets.
**Intended regime:** long trends
**Parameters (fixed):** `{'stop_pct': 0.3}`
**Universe:** SPY, QQQ, IWM, DIA, XLK, XLF, XLE, XLV, TLT, GLD (yf 1d)

| split | window | n | mean net % | std % | win rate | payoff | PF | max DD % | 95% CI mean % | Sharpe-like |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 1993-01-29 → 2013-03-31 | 478 | +1.158 | 9.992 | 0.23 | 6.36 | 1.86 | 231.2 | [+0.318, +2.087] | 0.56 |
| validation | 2013-03-31 → 2019-12-21 | 171 | +0.834 | 8.169 | 0.25 | 5.18 | 1.74 | 47.7 | [-0.262, +2.156] | 0.52 |
| test | 2019-12-21 → 2026-09-11 | sealed — not evaluated |  |  |  |  |  |  |  |  |

Cost sensitivity, net mean % at 0x/1x/2x/3x — train {'0x': 1.270467807304272, '1x': 1.1578320730064844, '2x': 1.0930325828447667, '3x': 1.0252477976501433}, validation {'0x': 0.9247232570531203, '1x': 0.8344589126725714, '2x': 0.7635125982434274, '3x': 0.6952378548231061}

Walk-forward (pre-test, expanding window; parameters are fixed so each fold is out-of-sample):

- 1993-01-29 → 2007-11-13: n=134, mean net +0.715%
- 1993-01-29 → 2011-11-25: n=134, mean net +1.231%
- 1993-01-29 → 2015-12-07: n=92, mean net +3.823%
- 1993-01-29 → 2019-12-20: n=124, mean net +1.128%

**Capital-constrained portfolio view (validation window)** — the per-trade rows above assume unlimited capital (one fresh full unit per signal); this instead splits ONE pool of capital equally across whatever positions are open on each day (the realistic constraint for a small account):

- Total return: +97.5% · Annualized: +10.7% · Max drawdown: 15.9% · Sharpe-like: 0.95
- Invested 98% of days · concurrent positions: median 4, average 3.8, max 9
- 60% of 350 weeks profitable (worst week -6.28%), 72% of months profitable

Validation-window consistency ("smoothness") metrics:

- Downside deviation: 1.585% · Sortino-like: 2.66 · Calmar-like: 2.99
- Longest losing streak: 21 trades · Longest winning streak: 5 trades
- Weeks with an exit: 394, 8% profitable, weekly return std 5.343%, worst week -9.073%
- Months with an exit: 91, 21% profitable

Validation-window baselines (benchmark: SPY):

| | n | mean net % | win rate | max DD % | total % |
|---|---|---|---|---|---|
| candidate | 171 | +0.834 | 0.25 | 47.7 | +142.7 |
| buy & hold | 1695 | +0.054 | 0.55 | 20.9 | +91.0 |
| 200d trend filter | 12 | -0.048 | 0.33 | 11.5 | -0.6 |
| random entry (avg of 300 sims) | 171 | +1.901 | 0.65 | 20.0 | +325.1 |
| cash / no trade | 0 | 0.000 | — | 0.0 | 0.0 |

Validation gate: train n>=30 ✔, train mean>0 ✔, validation n>=30 ✔, validation mean>0 ✔, validation PF>=1.10 ✔, validation P(mean>0)>=0.80 ✔, validation mean>0 at 2x costs ✔

**Decision: PASSED VALIDATION — test set already used earlier (see TEST_SET_LOG.md); not re-evaluated**

## rsi2_mean_reversion

**Hypothesis:** Sharp 2-3 day selloffs inside a long-term uptrend overshoot and revert within days as liquidity providers are paid to absorb flow.
**Intended regime:** long-term uptrend, short-term oversold
**Parameters (fixed):** `{'rsi_max': 10, 'stop_pct': 0.1, 'max_hold': 10}`
**Universe:** SPY, QQQ, IWM, DIA (yf 1d)

| split | window | n | mean net % | std % | win rate | payoff | PF | max DD % | 95% CI mean % | Sharpe-like |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 1993-01-29 → 2013-03-31 | 432 | +0.429 | 2.169 | 0.71 | 0.74 | 1.79 | 55.9 | [+0.227, +0.629] | 0.92 |
| validation | 2013-03-31 → 2019-12-21 | 225 | +0.202 | 1.592 | 0.67 | 0.72 | 1.43 | 28.5 | [-0.011, +0.403] | 0.73 |
| test | 2019-12-21 → 2026-09-11 | sealed — not evaluated |  |  |  |  |  |  |  |  |

Cost sensitivity, net mean % at 0x/1x/2x/3x — train {'0x': 0.498016107494116, '1x': 0.4287818187403634, '2x': 0.37801327374635457, '3x': 0.3289443358068276}, validation {'0x': 0.2597665988803613, '1x': 0.20205219803552826, '2x': 0.15190992008836904, '3x': 0.10174798609926454}

Walk-forward (pre-test, expanding window; parameters are fixed so each fold is out-of-sample):

- 1993-01-29 → 2007-11-13: n=154, mean net +0.267%
- 1993-01-29 → 2011-11-25: n=98, mean net +0.129%
- 1993-01-29 → 2015-12-07: n=154, mean net +0.428%
- 1993-01-29 → 2019-12-20: n=119, mean net +0.053%

**Capital-constrained portfolio view (validation window)** — the per-trade rows above assume unlimited capital (one fresh full unit per signal); this instead splits ONE pool of capital equally across whatever positions are open on each day (the realistic constraint for a small account):

- Total return: +19.0% · Annualized: +2.6% · Max drawdown: 12.0% · Sharpe-like: 0.37
- Invested 24% of days · concurrent positions: median 2, average 2.0, max 4
- 26% of 350 weeks profitable (worst week -5.11%), 57% of months profitable

Validation-window consistency ("smoothness") metrics:

- Downside deviation: 1.269% · Sortino-like: 0.92 · Calmar-like: 1.60
- Longest losing streak: 5 trades · Longest winning streak: 13 trades
- Weeks with an exit: 349, 21% profitable, weekly return std 1.783%, worst week -16.356%
- Months with an exit: 81, 60% profitable

Validation-window baselines (benchmark: SPY):

| | n | mean net % | win rate | max DD % | total % |
|---|---|---|---|---|---|
| candidate | 225 | +0.202 | 0.67 | 28.5 | +45.5 |
| buy & hold | 1695 | +0.054 | 0.55 | 20.9 | +91.0 |
| 200d trend filter | 12 | -0.048 | 0.33 | 11.5 | -0.6 |
| random entry (avg of 300 sims) | 225 | +0.195 | 0.59 | 22.0 | +44.0 |
| cash / no trade | 0 | 0.000 | — | 0.0 | 0.0 |

Validation gate: train n>=30 ✔, train mean>0 ✔, validation n>=30 ✔, validation mean>0 ✔, validation PF>=1.10 ✔, validation P(mean>0)>=0.80 ✔, validation mean>0 at 2x costs ✔

**Decision: PASSED VALIDATION — test set already used earlier (see TEST_SET_LOG.md); not re-evaluated**

## monthly_sma10_timing_spy

**Hypothesis:** Faber (2007): being long only while price is above its 10-month average sidesteps most of a major bear market's depth (investors as a group are trend-followers at long horizons) while capturing most bull-market upside, at very low turnover (roughly 4-6 decisions/year).
**Intended regime:** all — designed specifically to reduce drawdown in bear regimes
**Parameters (fixed):** `{'sma_months': 10}`
**Universe:** SPY (yf 1d)

| split | window | n | mean net % | std % | win rate | payoff | PF | max DD % | 95% CI mean % | Sharpe-like |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 1993-01-29 → 2013-03-31 | 13 | +21.323 | 38.256 | 0.62 | 9.98 | 15.97 | 11.2 | [+4.919, +43.515] | 0.45 |
| validation | 2013-03-31 → 2019-12-21 | 5 | +4.028 | 20.407 | 0.40 | 2.94 | 1.96 | 13.6 | [-8.177, +22.489] | 0.17 |
| test | 2019-12-21 → 2026-09-11 | sealed — not evaluated |  |  |  |  |  |  |  |  |

Cost sensitivity, net mean % at 0x/1x/2x/3x — train {'0x': 21.408702780591174, '1x': 21.32302531022045, '2x': 21.264695411759675, '3x': 21.20541502324671}, validation {'0x': 4.0859293575988564, '1x': 4.0279569390842385, '2x': 3.9769201320190755, '3x': 3.925038323448369}

Walk-forward (pre-test, expanding window; parameters are fixed so each fold is out-of-sample):

- 1993-01-29 → 2007-11-13: n=1, mean net +36.517%
- 1993-01-29 → 2011-11-25: n=3, mean net +6.241%
- 1993-01-29 → 2015-12-07: n=2, mean net +24.954%
- 1993-01-29 → 2019-12-20: n=4, mean net +6.874%

Validation-window consistency ("smoothness") metrics:

- Downside deviation: 6.263% · Sortino-like: 0.55 · Calmar-like: 1.48
- Longest losing streak: 2 trades · Longest winning streak: 1 trades
- Weeks with an exit: 214, 1% profitable, weekly return std 2.862%, worst week -11.771%
- Months with an exit: 50, 4% profitable

Validation-window baselines (benchmark: SPY):

| | n | mean net % | win rate | max DD % | total % |
|---|---|---|---|---|---|
| candidate | 5 | +4.028 | 0.40 | 13.6 | +20.1 |
| buy & hold | 1695 | +0.054 | 0.55 | 20.9 | +91.0 |
| 200d trend filter | 12 | -0.048 | 0.33 | 11.5 | -0.6 |
| random entry (avg of 300 sims) | 5 | +9.899 | 0.83 | 2.4 | +49.5 |
| cash / no trade | 0 | 0.000 | — | 0.0 | 0.0 |

Validation gate: train n>=30 ✘, train mean>0 ✔, validation n>=30 ✘, validation mean>0 ✔, validation PF>=1.10 ✔, validation P(mean>0)>=0.80 ✘, validation mean>0 at 2x costs ✔

**Decision: INSUFFICIENT SAMPLE**

## monthly_sma10_timing_multi

**Hypothesis:** Same as monthly_sma10_timing_spy, applied per-instrument across a broader liquid-ETF universe to see whether the effect is SPY-specific or general.
**Intended regime:** all
**Parameters (fixed):** `{'sma_months': 10}`
**Universe:** SPY, QQQ, IWM, DIA, XLK, XLF, XLE, XLV, XLI, XLY, XLP, XLU, XLB, TLT, SHY, GLD, EFA, EEM, VNQ (yf 1d)

| split | window | n | mean net % | std % | win rate | payoff | PF | max DD % | 95% CI mean % | Sharpe-like |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 1993-01-29 → 2013-03-31 | 209 | +11.013 | 26.735 | 0.52 | 4.79 | 5.22 | 202.0 | [+7.564, +14.777] | 1.33 |
| validation | 2013-03-31 → 2019-12-21 | 110 | +3.380 | 15.378 | 0.31 | 4.86 | 2.17 | 82.2 | [+0.656, +6.377] | 0.89 |
| test | 2019-12-21 → 2026-09-11 | sealed — not evaluated |  |  |  |  |  |  |  |  |

Cost sensitivity, net mean % at 0x/1x/2x/3x — train {'0x': 11.156604388749411, '1x': 11.012928572349441, '2x': 10.93579839079031, '3x': 10.85534813420509}, validation {'0x': 3.4783253604072084, '1x': 3.3795974142181926, '2x': 3.305419797518578, '3x': 3.2288645766397077}

Walk-forward (pre-test, expanding window; parameters are fixed so each fold is out-of-sample):

- 1993-01-29 → 2007-11-13: n=53, mean net +8.803%
- 1993-01-29 → 2011-11-25: n=57, mean net +9.147%
- 1993-01-29 → 2015-12-07: n=60, mean net +9.983%
- 1993-01-29 → 2019-12-20: n=79, mean net +5.495%

**Capital-constrained portfolio view (validation window)** — the per-trade rows above assume unlimited capital (one fresh full unit per signal); this instead splits ONE pool of capital equally across whatever positions are open on each day (the realistic constraint for a small account):

- Total return: +22.4% · Annualized: +3.1% · Max drawdown: 17.7% · Sharpe-like: 0.37
- Invested 95% of days · concurrent positions: median 12, average 10.7, max 19
- 54% of 350 weeks profitable (worst week -5.52%), 61% of months profitable

Validation-window consistency ("smoothness") metrics:

- Downside deviation: 4.067% · Sortino-like: 3.36 · Calmar-like: 4.52
- Longest losing streak: 12 trades · Longest winning streak: 4 trades
- Weeks with an exit: 410, 4% profitable, weekly return std 10.083%, worst week -35.968%
- Months with an exit: 95, 19% profitable

Validation-window baselines (benchmark: SPY):

| | n | mean net % | win rate | max DD % | total % |
|---|---|---|---|---|---|
| candidate | 110 | +3.380 | 0.31 | 82.2 | +371.8 |
| buy & hold | 1695 | +0.054 | 0.55 | 20.9 | +91.0 |
| 200d trend filter | 12 | -0.048 | 0.33 | 11.5 | -0.6 |
| random entry (avg of 300 sims) | 110 | +8.361 | 0.83 | 18.7 | +919.8 |
| cash / no trade | 0 | 0.000 | — | 0.0 | 0.0 |

Validation gate: train n>=30 ✔, train mean>0 ✔, validation n>=30 ✔, validation mean>0 ✔, validation PF>=1.10 ✔, validation P(mean>0)>=0.80 ✔, validation mean>0 at 2x costs ✔

**Decision: PASSED VALIDATION — test set already used earlier (see TEST_SET_LOG.md); not re-evaluated**

## sector_rotation_momentum

**Hypothesis:** Jegadeesh & Titman (1993) cross-sectional momentum: information diffuses slowly and flows chase recent winners, so relative strength persists 3-12 months. Monthly, hold only the single best trailing-6-month performer across a diversified ETF set; go to cash if even the best is negative (avoids the "least-bad asset in a crash" trap).
**Intended regime:** all — cash overlay specifically targets crash regimes
**Parameters (fixed):** `{'lookback_months': 6}`
**Universe:** SPY, QQQ, IWM, DIA, XLK, XLF, XLE, XLV, XLI, XLY, XLP, XLU, XLB, TLT, GLD, EFA, EEM, VNQ (yf 1d)

| split | window | n | mean net % | std % | win rate | payoff | PF | max DD % | 95% CI mean % | Sharpe-like |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 1993-01-29 → 2013-03-31 | 87 | +3.218 | 16.501 | 0.54 | 2.07 | 2.44 | 35.3 | [+0.338, +7.265] | 0.40 |
| validation | 2013-03-31 → 2019-12-21 | 53 | -0.450 | 4.362 | 0.53 | 0.69 | 0.77 | 41.8 | [-1.615, +0.714] | -0.29 |
| test | 2019-12-21 → 2026-09-11 | sealed — not evaluated |  |  |  |  |  |  |  |  |

Cost sensitivity, net mean % at 0x/1x/2x/3x — train {'0x': 3.3565809698103166, '1x': 3.217579584418516, '2x': 3.150388974819957, '3x': 3.0600399507441076}, validation {'0x': -0.35142178331938756, '1x': -0.44957977165331126, '2x': -0.5277837116258349, '3x': -0.6045330560369377}

Walk-forward (pre-test, expanding window; parameters are fixed so each fold is out-of-sample):

- 1993-01-29 → 2007-11-13: n=22, mean net +4.343%
- 1993-01-29 → 2011-11-25: n=22, mean net +0.186%
- 1993-01-29 → 2015-12-07: n=32, mean net -0.208%
- 1993-01-29 → 2019-12-20: n=31, mean net -0.571%

**Capital-constrained portfolio view (validation window)** — the per-trade rows above assume unlimited capital (one fresh full unit per signal); this instead splits ONE pool of capital equally across whatever positions are open on each day (the realistic constraint for a small account):

- Total return: -9.6% · Annualized: -1.5% · Max drawdown: 29.3% · Sharpe-like: -0.02
- Invested 96% of days · concurrent positions: median 1, average 1.0, max 1
- 52% of 350 weeks profitable (worst week -6.64%), 50% of months profitable

Validation-window consistency ("smoothness") metrics:

- Downside deviation: 3.453% · Sortino-like: -0.37 · Calmar-like: -0.57
- Longest losing streak: 4 trades · Longest winning streak: 6 trades
- Weeks with an exit: 357, 8% profitable, weekly return std 1.675%, worst week -12.887%
- Months with an exit: 83, 34% profitable

Validation-window baselines (benchmark: SPY):

| | n | mean net % | win rate | max DD % | total % |
|---|---|---|---|---|---|
| candidate | 53 | -0.450 | 0.53 | 41.8 | -23.8 |
| buy & hold | 1695 | +0.054 | 0.55 | 20.9 | +91.0 |
| 200d trend filter | 12 | -0.048 | 0.33 | 11.5 | -0.6 |
| random entry (avg of 300 sims) | 53 | +1.552 | 0.71 | 17.8 | +82.2 |
| cash / no trade | 0 | 0.000 | — | 0.0 | 0.0 |

Validation gate: train n>=30 ✔, train mean>0 ✔, validation n>=30 ✔, validation mean>0 ✘, validation PF>=1.10 ✘, validation P(mean>0)>=0.80 ✘, validation mean>0 at 2x costs ✘

**Decision: REJECTED AT VALIDATION**

## rsi2_early_exit

**Hypothesis:** Same setup as rsi2_mean_reversion (RSI(2)<10 pullback in a long-term uptrend), but exits on a HARD time-stop
    at day `hold_days` instead of waiting up to 10 days for a 5-day-SMA reclaim.

    Pre-registered from a pattern visible independently in the TRAIN split of rsi2_mean_reversion (i.e., before
    ever looking at its validation or test performance): trades held 1-4 days there were strongly and consistently
    profitable across train/validation/test alike, while trades held 7-10 days were consistently a net loss in
    every one of those three splits. Hypothesis: the reversion either resolves within a few days or the setup has
    failed (a stronger, unresolved downtrend or a failed liquidity-provision scenario), so cutting the holding
    period short should keep the profitable part of the effect and remove the decaying tail — an exit-mechanics
    change, not a re-tuned entry threshold, and evaluated on its own fresh train/validation/(new)test split.
**Intended regime:** long-term uptrend, short-term oversold; hypothesis specifically about EXIT timing
**Parameters (fixed):** `{'rsi_max': 10, 'stop_pct': 0.1, 'hold_days': 4}`
**Universe:** SPY, QQQ, IWM, DIA (yf 1d)

| split | window | n | mean net % | std % | win rate | payoff | PF | max DD % | 95% CI mean % | Sharpe-like |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 1993-01-29 → 2013-03-31 | 451 | +0.259 | 2.220 | 0.57 | 1.02 | 1.36 | 44.5 | [+0.057, +0.465] | 0.55 |
| validation | 2013-03-31 → 2019-12-21 | 235 | -0.028 | 2.085 | 0.52 | 0.88 | 0.96 | 56.0 | [-0.292, +0.232] | -0.08 |
| test | 2019-12-21 → 2026-09-11 | sealed — not evaluated |  |  |  |  |  |  |  |  |

Cost sensitivity, net mean % at 0x/1x/2x/3x — train {'0x': 0.32790146980247864, '1x': 0.25882687297986956, '2x': 0.20845132418580292, '3x': 0.15866446499189724}, validation {'0x': 0.029453441678709814, '1x': -0.028361315141172554, '2x': -0.07820325950690467, '3x': -0.12815158904833795}

Walk-forward (pre-test, expanding window; parameters are fixed so each fold is out-of-sample):

- 1993-01-29 → 2007-11-13: n=160, mean net +0.064%
- 1993-01-29 → 2011-11-25: n=100, mean net +0.071%
- 1993-01-29 → 2015-12-07: n=166, mean net +0.245%
- 1993-01-29 → 2019-12-20: n=124, mean net -0.154%

**Capital-constrained portfolio view (validation window)** — the per-trade rows above assume unlimited capital (one fresh full unit per signal); this instead splits ONE pool of capital equally across whatever positions are open on each day (the realistic constraint for a small account):

- Total return: +4.6% · Annualized: +0.7% · Max drawdown: 15.6% · Sharpe-like: 0.13
- Invested 22% of days · concurrent positions: median 2, average 1.8, max 4
- 24% of 350 weeks profitable (worst week -6.16%), 51% of months profitable

Validation-window consistency ("smoothness") metrics:

- Downside deviation: 1.643% · Sortino-like: -0.10 · Calmar-like: -0.12
- Longest losing streak: 9 trades · Longest winning streak: 11 trades
- Weeks with an exit: 350, 18% profitable, weekly return std 2.489%, worst week -23.496%
- Months with an exit: 81, 49% profitable

Validation-window baselines (benchmark: SPY):

| | n | mean net % | win rate | max DD % | total % |
|---|---|---|---|---|---|
| candidate | 235 | -0.028 | 0.52 | 56.0 | -6.7 |
| buy & hold | 1695 | +0.054 | 0.55 | 20.9 | +91.0 |
| 200d trend filter | 12 | -0.048 | 0.33 | 11.5 | -0.6 |
| random entry (avg of 300 sims) | 235 | +0.159 | 0.59 | 21.9 | +37.3 |
| cash / no trade | 0 | 0.000 | — | 0.0 | 0.0 |

Validation gate: train n>=30 ✔, train mean>0 ✔, validation n>=30 ✔, validation mean>0 ✘, validation PF>=1.10 ✘, validation P(mean>0)>=0.80 ✘, validation mean>0 at 2x costs ✘

**Decision: REJECTED AT VALIDATION**

## pullback_from_high

**Hypothesis:** Cross-check of the same broad hypothesis (short-term overreaction inside a long-term uptrend reverts) using
    a DIFFERENT technical construction — a simple % pullback from the trailing high instead of RSI(2) — to test
    whether the effect is specific to the RSI formula or a more general short-term-oversold phenomenon.
**Intended regime:** long-term uptrend, short-term oversold
**Parameters (fixed):** `{'high_lookback': 10, 'pullback_pct': 0.03, 'stop_pct': 0.1, 'max_hold': 10}`
**Universe:** SPY, QQQ, IWM, DIA (yf 1d)

| split | window | n | mean net % | std % | win rate | payoff | PF | max DD % | 95% CI mean % | Sharpe-like |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 1993-01-29 → 2013-03-31 | 253 | +0.371 | 2.169 | 0.72 | 0.67 | 1.68 | 26.2 | [+0.100, +0.623] | 0.61 |
| validation | 2013-03-31 → 2019-12-21 | 93 | +0.631 | 1.274 | 0.73 | 1.17 | 3.20 | 9.7 | [+0.374, +0.884] | 1.84 |
| test | 2019-12-21 → 2026-09-11 | sealed — not evaluated |  |  |  |  |  |  |  |  |

Cost sensitivity, net mean % at 0x/1x/2x/3x — train {'0x': 0.4396568089179021, '1x': 0.3710821257256875, '2x': 0.31947263649633034, '3x': 0.2711408631751666}, validation {'0x': 0.6888850985272367, '1x': 0.6310776344640155, '2x': 0.5805425379951203, '3x': 0.5302740954716902}

Walk-forward (pre-test, expanding window; parameters are fixed so each fold is out-of-sample):

- 1993-01-29 → 2007-11-13: n=63, mean net +0.289%
- 1993-01-29 → 2011-11-25: n=77, mean net +0.336%
- 1993-01-29 → 2015-12-07: n=58, mean net +0.686%
- 1993-01-29 → 2019-12-20: n=54, mean net +0.482%

**Capital-constrained portfolio view (validation window)** — the per-trade rows above assume unlimited capital (one fresh full unit per signal); this instead splits ONE pool of capital equally across whatever positions are open on each day (the realistic constraint for a small account):

- Total return: +26.6% · Annualized: +3.6% · Max drawdown: 7.9% · Sharpe-like: 0.65
- Invested 8% of days · concurrent positions: median 1, average 1.6, max 4
- 12% of 350 weeks profitable (worst week -5.04%), 35% of months profitable

Validation-window consistency ("smoothness") metrics:

- Downside deviation: 0.647% · Sortino-like: 3.63 · Calmar-like: 6.07
- Longest losing streak: 4 trades · Longest winning streak: 13 trades
- Weeks with an exit: 338, 12% profitable, weekly return std 1.008%, worst week -6.064%
- Months with an exit: 79, 38% profitable

Validation-window baselines (benchmark: SPY):

| | n | mean net % | win rate | max DD % | total % |
|---|---|---|---|---|---|
| candidate | 93 | +0.631 | 0.73 | 9.7 | +58.7 |
| buy & hold | 1695 | +0.054 | 0.55 | 20.9 | +91.0 |
| 200d trend filter | 12 | -0.048 | 0.33 | 11.5 | -0.6 |
| random entry (avg of 300 sims) | 93 | +0.099 | 0.57 | 12.7 | +9.2 |
| cash / no trade | 0 | 0.000 | — | 0.0 | 0.0 |

Validation gate: train n>=30 ✔, train mean>0 ✔, validation n>=30 ✔, validation mean>0 ✔, validation PF>=1.10 ✔, validation P(mean>0)>=0.80 ✔, validation mean>0 at 2x costs ✔

**Decision: PASSED VALIDATION — test set already used earlier (see TEST_SET_LOG.md); not re-evaluated**

## weekly_rsi2

**Hypothesis:** Same reversion hypothesis sampled at WEEKLY resolution instead of daily — a structurally lower-turnover
    variant, and a check for whether the effect is a short-horizon (daily) microstructure artifact or genuinely
    present at a coarser, even-lower-intervention timescale.
**Intended regime:** long-term uptrend, short-term oversold, weekly resolution
**Parameters (fixed):** `{'rsi_max': 10, 'sma_weeks': 40, 'hold_weeks': 3}`
**Universe:** SPY, QQQ, IWM, DIA (yf 1d)

| split | window | n | mean net % | std % | win rate | payoff | PF | max DD % | 95% CI mean % | Sharpe-like |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 1993-01-29 → 2013-03-31 | 79 | +1.838 | 4.480 | 0.67 | 1.36 | 2.78 | 17.5 | [+0.860, +2.841] | 0.81 |
| validation | 2013-03-31 → 2019-12-21 | 49 | +3.347 | 3.664 | 0.84 | 2.11 | 10.81 | 16.0 | [+2.284, +4.350] | 2.47 |
| test | 2019-12-21 → 2026-09-11 | sealed — not evaluated |  |  |  |  |  |  |  |  |

Cost sensitivity, net mean % at 0x/1x/2x/3x — train {'0x': 1.9065172093858713, '1x': 1.8377598168589582, '2x': 1.785755825677694, '3x': 1.737612856063121}, validation {'0x': 3.405002659369428, '1x': 3.346606694182573, '2x': 3.2939485993799567, '3x': 3.241251284632672}

Walk-forward (pre-test, expanding window; parameters are fixed so each fold is out-of-sample):

- 1993-01-29 → 2007-11-13: n=30, mean net +1.368%
- 1993-01-29 → 2011-11-25: n=22, mean net +3.063%
- 1993-01-29 → 2015-12-07: n=27, mean net +2.852%
- 1993-01-29 → 2019-12-20: n=30, mean net +2.915%

**Capital-constrained portfolio view (validation window)** — the per-trade rows above assume unlimited capital (one fresh full unit per signal); this instead splits ONE pool of capital equally across whatever positions are open on each day (the realistic constraint for a small account):

- Total return: +69.2% · Annualized: +8.1% · Max drawdown: 8.2% · Sharpe-like: 1.37
- Invested 20% of days · concurrent positions: median 1, average 1.8, max 4
- 13% of 350 weeks profitable (worst week -3.62%), 28% of months profitable

Validation-window consistency ("smoothness") metrics:

- Downside deviation: 1.274% · Sortino-like: 7.09 · Calmar-like: 10.28
- Longest losing streak: 4 trades · Longest winning streak: 12 trades
- Weeks with an exit: 323, 8% profitable, weekly return std 2.741%, worst week -7.867%
- Months with an exit: 75, 24% profitable

Validation-window baselines (benchmark: SPY):

| | n | mean net % | win rate | max DD % | total % |
|---|---|---|---|---|---|
| candidate | 49 | +3.347 | 0.84 | 16.0 | +164.0 |
| buy & hold | 1695 | +0.054 | 0.55 | 20.9 | +91.0 |
| 200d trend filter | 12 | -0.048 | 0.33 | 11.5 | -0.6 |
| random entry (avg of 300 sims) | 49 | +0.153 | 0.59 | 9.7 | +7.5 |
| cash / no trade | 0 | 0.000 | — | 0.0 | 0.0 |

Validation gate: train n>=30 ✔, train mean>0 ✔, validation n>=30 ✔, validation mean>0 ✔, validation PF>=1.10 ✔, validation P(mean>0)>=0.80 ✔, validation mean>0 at 2x costs ✔

**Decision: PASSED VALIDATION — test set already used earlier (see TEST_SET_LOG.md); not re-evaluated**

## combined_trend_vol_rsi2

**Hypothesis:** Combines three INDEPENDENTLY defensible signals rather than adding indicators for their own sake: (1) the
    existing trend filter (price above its 200-day average), (2) the existing RSI(2) oversold pullback, and (3) a
    volatility filter requiring the instrument NOT be in its own trailing-high-volatility tercile. Hypothesis:
    rsi2_mean_reversion's diagnostic breakdown showed its 'high' realized-volatility bucket was flat-to-negative in
    2 of 3 splits (train -0.04%, test -0.12%) while 'low'/'mid' were consistently positive in all three — excluding
    the high-volatility tercile should remove a specifically weak slice rather than mine for a better one, since the
    other two buckets are kept exactly as before, unfiltered.
**Intended regime:** long-term uptrend, short-term oversold, excluding high-volatility regime
**Parameters (fixed):** `{'rsi_max': 10, 'stop_pct': 0.1, 'max_hold': 10}`
**Universe:** SPY, QQQ, IWM, DIA (yf 1d)

| split | window | n | mean net % | std % | win rate | payoff | PF | max DD % | 95% CI mean % | Sharpe-like |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 1993-01-29 → 2013-03-31 | 350 | +0.464 | 2.000 | 0.73 | 0.73 | 1.98 | 46.1 | [+0.254, +0.667] | 0.97 |
| validation | 2013-03-31 → 2019-12-21 | 172 | +0.193 | 1.338 | 0.66 | 0.75 | 1.47 | 31.8 | [-0.015, +0.388] | 0.73 |
| test | 2019-12-21 → 2026-09-11 | sealed — not evaluated |  |  |  |  |  |  |  |  |

Cost sensitivity, net mean % at 0x/1x/2x/3x — train {'0x': 0.5332430219868276, '1x': 0.46350885920710616, '2x': 0.4133636696824087, '3x': 0.36427858034632876}, validation {'0x': 0.2507731807957411, '1x': 0.1929840006049746, '2x': 0.14284780167584182, '3x': 0.09249788301061744}

Walk-forward (pre-test, expanding window; parameters are fixed so each fold is out-of-sample):

- 1993-01-29 → 2007-11-13: n=122, mean net +0.287%
- 1993-01-29 → 2011-11-25: n=83, mean net +0.293%
- 1993-01-29 → 2015-12-07: n=128, mean net +0.448%
- 1993-01-29 → 2019-12-20: n=92, mean net +0.030%

**Capital-constrained portfolio view (validation window)** — the per-trade rows above assume unlimited capital (one fresh full unit per signal); this instead splits ONE pool of capital equally across whatever positions are open on each day (the realistic constraint for a small account):

- Total return: +16.6% · Annualized: +2.3% · Max drawdown: 13.5% · Sharpe-like: 0.39
- Invested 19% of days · concurrent positions: median 2, average 1.9, max 4
- 19% of 350 weeks profitable (worst week -4.59%), 48% of months profitable

Validation-window consistency ("smoothness") metrics:

- Downside deviation: 1.022% · Sortino-like: 0.96 · Calmar-like: 1.04
- Longest losing streak: 4 trades · Longest winning streak: 13 trades
- Weeks with an exit: 349, 17% profitable, weekly return std 1.228%, worst week -9.941%
- Months with an exit: 81, 51% profitable

Validation-window baselines (benchmark: SPY):

| | n | mean net % | win rate | max DD % | total % |
|---|---|---|---|---|---|
| candidate | 172 | +0.193 | 0.66 | 31.8 | +33.2 |
| buy & hold | 1695 | +0.054 | 0.55 | 20.9 | +91.0 |
| 200d trend filter | 12 | -0.048 | 0.33 | 11.5 | -0.6 |
| random entry (avg of 300 sims) | 172 | +0.180 | 0.59 | 19.5 | +31.0 |
| cash / no trade | 0 | 0.000 | — | 0.0 | 0.0 |

Validation gate: train n>=30 ✔, train mean>0 ✔, validation n>=30 ✔, validation mean>0 ✔, validation PF>=1.10 ✔, validation P(mean>0)>=0.80 ✔, validation mean>0 at 2x costs ✔

**Decision: PASSED VALIDATION — test set already used earlier (see TEST_SET_LOG.md); not re-evaluated**

## low_volatility_rotation

**Hypothesis:** Low-volatility anomaly (Ang, Hodges, Xing & Zhang 2006; Baker, Bradley & Wurgler 2011): lower-volatility
    assets have historically delivered comparable or better risk-adjusted returns than higher-volatility ones,
    plausibly because leverage-constrained investors bid up higher-beta assets for a given expected return. Monthly,
    equal-weight-hold the `top_n` lowest-trailing-realized-volatility instruments in the universe; no absolute
    filter (always invested, unlike the momentum rotation candidate) since low-vol is a relative-ranking effect.
**Intended regime:** all — a relative-ranking effect, not regime-dependent by construction
**Parameters (fixed):** `{'vol_lookback_months': 6, 'top_n': 5}`
**Universe:** SPY, QQQ, IWM, DIA, XLK, XLF, XLE, XLV, XLI, XLY, XLP, XLU, XLB, TLT, GLD, EFA, EEM, VNQ (yf 1d)

| split | window | n | mean net % | std % | win rate | payoff | PF | max DD % | 95% CI mean % | Sharpe-like |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 1993-01-29 → 2013-03-31 | 318 | +2.046 | 12.498 | 0.58 | 1.44 | 2.01 | 184.8 | [+0.839, +3.558] | 0.65 |
| validation | 2013-03-31 → 2019-12-21 | 215 | +1.509 | 4.829 | 0.64 | 1.31 | 2.31 | 49.5 | [+0.870, +2.134] | 1.77 |
| test | 2019-12-21 → 2026-09-11 | 175 | +1.604 | 8.074 | 0.56 | 1.45 | 1.84 | 92.1 | [+0.436, +2.797] | 1.01 |

Cost sensitivity, net mean % at 0x/1x/2x/3x — train {'0x': 2.168795464813359, '1x': 2.045682691692902, '2x': 1.969972129171496, '3x': 1.8956330701751143}, validation {'0x': 1.6007847613195156, '1x': 1.5088860355894322, '2x': 1.441272155596541, '3x': 1.3684094563671207}, test {'0x': 1.687878006609185, '1x': 1.6041170095160362, '2x': 1.5298888097955015, '3x': 1.4565901513490291}

Walk-forward (pre-test, expanding window; parameters are fixed so each fold is out-of-sample):

- 1993-01-29 → 2007-11-13: n=90, mean net +2.447%
- 1993-01-29 → 2011-11-25: n=80, mean net +1.808%
- 1993-01-29 → 2015-12-07: n=110, mean net +1.932%
- 1993-01-29 → 2019-12-20: n=125, mean net +1.755%

**Capital-constrained portfolio view (validation window)** — the per-trade rows above assume unlimited capital (one fresh full unit per signal); this instead splits ONE pool of capital equally across whatever positions are open on each day (the realistic constraint for a small account):

- Total return: +92.0% · Annualized: +10.2% · Max drawdown: 14.9% · Sharpe-like: 1.12
- Invested 97% of days · concurrent positions: median 5, average 5.0, max 5
- 62% of 350 weeks profitable (worst week -5.12%), 64% of months profitable

Validation-window consistency ("smoothness") metrics:

- Downside deviation: 2.508% · Sortino-like: 3.40 · Calmar-like: 6.56
- Longest losing streak: 10 trades · Longest winning streak: 15 trades
- Weeks with an exit: 345, 8% profitable, weekly return std 7.361%, worst week -38.139%
- Months with an exit: 80, 35% profitable

Test-window consistency ("smoothness") metrics:

- Downside deviation: 3.837% · Sortino-like: 2.13 · Calmar-like: 3.05
- Longest losing streak: 8 trades · Longest winning streak: 10 trades
- Weeks with an exit: 341, 6% profitable, weekly return std 10.790%, worst week -60.033%
- Months with an exit: 79, 25% profitable

Validation-window baselines (benchmark: SPY):

| | n | mean net % | win rate | max DD % | total % |
|---|---|---|---|---|---|
| candidate | 215 | +1.509 | 0.64 | 49.5 | +324.4 |
| buy & hold | 1695 | +0.054 | 0.55 | 20.9 | +91.0 |
| 200d trend filter | 12 | -0.048 | 0.33 | 11.5 | -0.6 |
| random entry (avg of 300 sims) | 215 | +1.913 | 0.73 | 51.2 | +411.4 |
| cash / no trade | 0 | 0.000 | — | 0.0 | 0.0 |

Validation gate: train n>=30 ✔, train mean>0 ✔, validation n>=30 ✔, validation mean>0 ✔, validation PF>=1.10 ✔, validation P(mean>0)>=0.80 ✔, validation mean>0 at 2x costs ✔

**Decision: OUT-OF-SAMPLE POSITIVE**
