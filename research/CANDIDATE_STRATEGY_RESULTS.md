# Candidate Strategy Results

Generated 2026-09-13 18:44 UTC by `python -m research.run_candidates`.

All parameters were fixed in `research/candidates.py` before evaluation and were not tuned. Returns are per trade, net of the costs in `research/costs.py` unless labelled gross. Splits are chronological 60/20/20 per candidate data span. The TEST window is evaluated at most once per strategy specification, only after passing validation.

| strategy | data | trades | train net % | validation net % | validation @2x cost | decision |
|---|---|---|---|---|---|---|
| orb_continuation | yf:5m × 16 | 68 | -0.007 (n=36) | -0.148 (n=9) | -0.218 | **REJECTED AT VALIDATION** |
| vwap_pullback | yf:5m × 16 | 261 | -0.106 (n=168) | -0.149 (n=38) | -0.226 | **REJECTED AT VALIDATION** |
| intraday_momentum_last_hour | yf:1h × 4 | 1488 | -0.045 (n=869) | -0.073 (n=306) | -0.123 | **REJECTED AT VALIDATION** |
| crypto_tsmom | cb:1h × 2 | 510 | -0.330 (n=311) | -0.425 (n=93) | -0.823 | **REJECTED AT VALIDATION** |
| overnight_drift | yf:1d × 4 | 29196 | -0.026 (n=15664) | -0.015 (n=6784) | -0.065 | **REJECTED AT VALIDATION** |
| overnight_drift_trend | yf:1d × 4 | 21158 | -0.019 (n=10088) | -0.013 (n=5864) | -0.063 | **REJECTED AT VALIDATION** |
| trend_sma200 | yf:1d × 10 | 870 | +1.158 (n=478) | +0.834 (n=171) | +0.764 | **OUT-OF-SAMPLE POSITIVE** |
| rsi2_mean_reversion | yf:1d × 4 | 893 | +0.429 (n=432) | +0.202 (n=225) | +0.152 | **OUT-OF-SAMPLE POSITIVE** |

## orb_continuation

**Hypothesis:** Early breakouts above the 30-minute opening range on above-normal opening volume reflect persistent order flow and continue into the close.
**Intended regime:** trending / high-volume sessions
**Parameters (fixed):** `{'or_bars': 6, 'rvol_min': 1.2, 'last_entry_minute': 690}`
**Universe:** SPY, QQQ, IWM, DIA, XLK, XLF, XLE, XLV, TLT, GLD, AAPL, MSFT, NVDA, AMZN, GOOGL, META (yf 5m)

| split | window | n | mean net % | std % | win rate | payoff | PF | max DD % | 95% CI mean % | Sharpe-like |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 2026-06-17 → 2026-08-08 | 36 | -0.007 | 1.124 | 0.39 | 1.54 | 0.98 | 5.4 | [-0.315, +0.409] | -0.10 |
| validation | 2026-08-08 → 2026-08-25 | 9 | -0.148 | 0.491 | 0.22 | 1.78 | 0.51 | 2.1 | [-0.413, +0.194] | -4.21 |
| test | 2026-08-25 → 2026-09-11 | sealed — not evaluated |  |  |  |  |  |  |  |  |

Cost sensitivity, net mean % at 0x/1x/2x/3x — train {'0x': 0.0696385719472682, '1x': -0.007270867605139237, '2x': -0.07788708381207389, '3x': -0.1482496810597558}, validation {'0x': -0.07395078205429209, '1x': -0.14844356649205012, '2x': -0.21798039220238818, '3x': -0.28700990971940205}

Walk-forward (pre-test, expanding window; parameters are fixed so each fold is out-of-sample):

- 2026-06-17 → 2026-07-25: n=8, mean net -0.411%
- 2026-06-17 → 2026-08-04: n=19, mean net -0.017%
- 2026-06-17 → 2026-08-15: n=2, mean net -0.266%
- 2026-06-17 → 2026-08-25: n=9, mean net -0.148%

Validation gate: train n>=30 ✔, train mean>0 ✘, validation n>=30 ✘, validation mean>0 ✘, validation PF>=1.10 ✘, validation P(mean>0)>=0.80 ✘, validation mean>0 at 2x costs ✘

**Decision: REJECTED AT VALIDATION**

## vwap_pullback

**Hypothesis:** In sessions already up >0.3%, a pullback that holds VWAP (the institutional execution benchmark) attracts buyers and resumes toward the session high.
**Intended regime:** intraday uptrend
**Parameters (fixed):** `{'min_session_ret': 0.003, 'start_minute': 630, 'end_minute': 870, 'touch_tol': 0.0005, 'stop_buffer': 0.001}`
**Universe:** SPY, QQQ, IWM, DIA, XLK, XLF, XLE, XLV, TLT, GLD, AAPL, MSFT, NVDA, AMZN, GOOGL, META (yf 5m)

| split | window | n | mean net % | std % | win rate | payoff | PF | max DD % | 95% CI mean % | Sharpe-like |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 2026-06-17 → 2026-08-08 | 168 | -0.106 | 0.459 | 0.37 | 1.00 | 0.59 | 19.7 | [-0.174, -0.036] | -7.99 |
| validation | 2026-08-08 → 2026-08-25 | 38 | -0.149 | 0.298 | 0.32 | 0.74 | 0.34 | 6.3 | [-0.239, -0.054] | -14.35 |
| test | 2026-08-25 → 2026-09-11 | sealed — not evaluated |  |  |  |  |  |  |  |  |

Cost sensitivity, net mean % at 0x/1x/2x/3x — train {'0x': -0.02826527386025855, '1x': -0.10570281118506862, '2x': -0.17879253460444447, '3x': -0.25098644663306263}, validation {'0x': -0.06621665353999633, '1x': -0.1493794080046018, '2x': -0.22586034065024918, '3x': -0.30234739913902375}

Walk-forward (pre-test, expanding window; parameters are fixed so each fold is out-of-sample):

- 2026-06-17 → 2026-07-25: n=33, mean net -0.112%
- 2026-06-17 → 2026-08-04: n=28, mean net +0.128%
- 2026-06-17 → 2026-08-15: n=33, mean net -0.219%
- 2026-06-17 → 2026-08-25: n=22, mean net -0.117%

Validation gate: train n>=30 ✔, train mean>0 ✘, validation n>=30 ✔, validation mean>0 ✘, validation PF>=1.10 ✘, validation P(mean>0)>=0.80 ✘, validation mean>0 at 2x costs ✘

**Decision: REJECTED AT VALIDATION**

## intraday_momentum_last_hour

**Hypothesis:** A positive first-hour return predicts a positive final half-hour return because late-informed traders and hedgers trade in the same direction near the close.
**Intended regime:** any; strongest on high-volatility days in the literature
**Parameters (fixed):** `{'min_first_hour_ret': 0.0, 'stop_pct': 0.02}`
**Universe:** SPY, QQQ, IWM, DIA (yf 1h)

| split | window | n | mean net % | std % | win rate | payoff | PF | max DD % | 95% CI mean % | Sharpe-like |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 2023-10-13 → 2025-07-13 | 869 | -0.045 | 0.236 | 0.41 | 0.85 | 0.58 | 39.0 | [-0.060, -0.030] | -4.24 |
| validation | 2025-07-13 → 2026-02-10 | 306 | -0.073 | 0.178 | 0.28 | 0.79 | 0.31 | 22.4 | [-0.094, -0.053] | -9.43 |
| test | 2026-02-10 → 2026-09-11 | sealed — not evaluated |  |  |  |  |  |  |  |  |

Cost sensitivity, net mean % at 0x/1x/2x/3x — train {'0x': 0.008033200427355829, '1x': -0.04487588863909861, '2x': -0.09482152394953175, '3x': -0.1446858570766199}, validation {'0x': -0.020653503953799168, '1x': -0.07324323519262807, '2x': -0.12314968526338263, '3x': -0.17286661820248478}

Walk-forward (pre-test, expanding window; parameters are fixed so each fold is out-of-sample):

- 2023-10-13 → 2025-01-23: n=149, mean net -0.088%
- 2023-10-13 → 2025-05-31: n=178, mean net +0.008%
- 2023-10-13 → 2025-10-06: n=186, mean net -0.015%
- 2023-10-13 → 2026-02-10: n=184, mean net -0.110%

Validation gate: train n>=30 ✔, train mean>0 ✘, validation n>=30 ✔, validation mean>0 ✘, validation PF>=1.10 ✘, validation P(mean>0)>=0.80 ✘, validation mean>0 at 2x costs ✘

**Decision: REJECTED AT VALIDATION**

## crypto_tsmom

**Hypothesis:** Crypto returns show time-series momentum at daily-to-weekly horizons; being long only after a positive trailing week captures it.
**Intended regime:** trending crypto
**Parameters (fixed):** `{'lookback_h': 168, 'sma_h': 480, 'stop_pct': 0.08, 'hold_h': 24}`
**Universe:** BTC-USD, ETH-USD (cb 1h)

| split | window | n | mean net % | std % | win rate | payoff | PF | max DD % | 95% CI mean % | Sharpe-like |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 2023-09-14 → 2025-07-02 | 311 | -0.330 | 2.993 | 0.40 | 1.10 | 0.73 | 113.5 | [-0.663, -0.002] | -1.45 |
| validation | 2025-07-02 → 2026-02-06 | 93 | -0.425 | 2.769 | 0.40 | 0.98 | 0.65 | 42.1 | [-0.976, +0.112] | -1.91 |
| test | 2026-02-06 → 2026-09-13 | sealed — not evaluated |  |  |  |  |  |  |  |  |

Cost sensitivity, net mean % at 0x/1x/2x/3x — train {'0x': 0.06983166787717751, '1x': -0.3298129652842767, '2x': -0.7277027151448741, '3x': -1.1240181284339372}, validation {'0x': -0.025827449101526113, '1x': -0.42508788316828905, '2x': -0.8225854412455984, '3x': -1.218514264791727}

Walk-forward (pre-test, expanding window; parameters are fixed so each fold is out-of-sample):

- 2023-09-14 → 2025-01-08: n=75, mean net -0.245%
- 2023-09-14 → 2025-05-19: n=51, mean net -0.598%
- 2023-09-14 → 2025-09-28: n=70, mean net -0.441%
- 2023-09-14 → 2026-02-06: n=42, mean net -0.669%

Validation gate: train n>=30 ✔, train mean>0 ✘, validation n>=30 ✔, validation mean>0 ✘, validation PF>=1.10 ✘, validation P(mean>0)>=0.80 ✘, validation mean>0 at 2x costs ✘

**Decision: REJECTED AT VALIDATION**

## overnight_drift

**Hypothesis:** Most of the equity risk premium is earned overnight (close-to-open) rather than intraday.
**Intended regime:** all
**Parameters (fixed):** `{'trend_filter': False}`
**Universe:** SPY, QQQ, IWM, DIA (yf 1d)

| split | window | n | mean net % | std % | win rate | payoff | PF | max DD % | 95% CI mean % | Sharpe-like |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 1993-01-29 → 2013-03-31 | 15664 | -0.026 | 0.777 | 0.48 | 0.99 | 0.90 | 420.9 | [-0.038, -0.013] | -0.92 |
| validation | 2013-03-31 → 2019-12-21 | 6784 | -0.015 | 0.535 | 0.50 | 0.92 | 0.92 | 112.0 | [-0.027, -0.002] | -0.88 |
| test | 2019-12-21 → 2026-09-11 | sealed — not evaluated |  |  |  |  |  |  |  |  |

Cost sensitivity, net mean % at 0x/1x/2x/3x — train {'0x': 0.04422358807797205, '1x': -0.02560386601783495, '2x': -0.07562928368894566, '3x': -0.12563663197378327}, validation {'0x': 0.04258503794735784, '1x': -0.014783553293026098, '2x': -0.06484535588357526, '3x': -0.11477763858561811}

Walk-forward (pre-test, expanding window; parameters are fixed so each fold is out-of-sample):

- 1993-01-29 → 2007-11-13: n=4060, mean net -0.022%
- 1993-01-29 → 2011-11-25: n=4068, mean net -0.055%
- 1993-01-29 → 2015-12-07: n=4052, mean net -0.014%
- 1993-01-29 → 2019-12-20: n=4064, mean net -0.011%

Validation gate: train n>=30 ✔, train mean>0 ✘, validation n>=30 ✔, validation mean>0 ✘, validation PF>=1.10 ✘, validation P(mean>0)>=0.80 ✘, validation mean>0 at 2x costs ✘

**Decision: REJECTED AT VALIDATION**

## overnight_drift_trend

**Hypothesis:** Pre-registered variant: the overnight premium is concentrated when the index is above its 200-day average.
**Intended regime:** long-term uptrend
**Parameters (fixed):** `{'trend_filter': True}`
**Universe:** SPY, QQQ, IWM, DIA (yf 1d)

| split | window | n | mean net % | std % | win rate | payoff | PF | max DD % | 95% CI mean % | Sharpe-like |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 1993-01-29 → 2013-03-31 | 10088 | -0.019 | 0.551 | 0.47 | 1.00 | 0.90 | 224.6 | [-0.030, -0.009] | -0.78 |
| validation | 2013-03-31 → 2019-12-21 | 5864 | -0.013 | 0.448 | 0.50 | 0.93 | 0.92 | 84.6 | [-0.024, -0.002] | -0.83 |
| test | 2019-12-21 → 2026-09-11 | sealed — not evaluated |  |  |  |  |  |  |  |  |

Cost sensitivity, net mean % at 0x/1x/2x/3x — train {'0x': 0.04908991111998934, '1x': -0.01919735589837298, '2x': -0.06917825945359925, '3x': -0.11925233359048636}, validation {'0x': 0.04464946598012308, '1x': -0.012619035283653084, '2x': -0.06270532417331426, '3x': -0.11264360884034885}

Walk-forward (pre-test, expanding window; parameters are fixed so each fold is out-of-sample):

- 1993-01-29 → 2007-11-13: n=3480, mean net -0.026%
- 1993-01-29 → 2011-11-25: n=2233, mean net -0.031%
- 1993-01-29 → 2015-12-07: n=3651, mean net -0.020%
- 1993-01-29 → 2019-12-20: n=3427, mean net -0.011%

Validation gate: train n>=30 ✔, train mean>0 ✘, validation n>=30 ✔, validation mean>0 ✘, validation PF>=1.10 ✘, validation P(mean>0)>=0.80 ✘, validation mean>0 at 2x costs ✘

**Decision: REJECTED AT VALIDATION**

## trend_sma200

**Hypothesis:** Trends persist; holding only above the 200-day average keeps most upside while avoiding prolonged bear markets.
**Intended regime:** long trends
**Parameters (fixed):** `{'stop_pct': 0.3}`
**Universe:** SPY, QQQ, IWM, DIA, XLK, XLF, XLE, XLV, TLT, GLD (yf 1d)

| split | window | n | mean net % | std % | win rate | payoff | PF | max DD % | 95% CI mean % | Sharpe-like |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 1993-01-29 → 2013-03-31 | 478 | +1.158 | 9.992 | 0.23 | 6.36 | 1.86 | 73.0 | [+0.320, +2.136] | 0.56 |
| validation | 2013-03-31 → 2019-12-21 | 171 | +0.834 | 8.169 | 0.25 | 5.18 | 1.74 | 27.7 | [-0.277, +2.234] | 0.52 |
| test | 2019-12-21 → 2026-09-11 | 221 | +2.630 | 12.451 | 0.26 | 8.98 | 3.20 | 60.1 | [+1.095, +4.332] | 1.21 |

Cost sensitivity, net mean % at 0x/1x/2x/3x — train {'0x': 1.2704647326082315, '1x': 1.1578320730064844, '2x': 1.0929759639574206, '3x': 1.0252477976501433}, validation {'0x': 0.9247238192490536, '1x': 0.8344589126725714, '2x': 0.7635125982434274, '3x': 0.6951975898311411}, test {'0x': 2.7133837327800023, '1x': 2.6299168027235758, '2x': 2.556869932846551, '3x': 2.484404615331842}

Walk-forward (pre-test, expanding window; parameters are fixed so each fold is out-of-sample):

- 1993-01-29 → 2007-11-13: n=134, mean net +0.715%
- 1993-01-29 → 2011-11-25: n=134, mean net +1.231%
- 1993-01-29 → 2015-12-07: n=92, mean net +3.823%
- 1993-01-29 → 2019-12-20: n=124, mean net +1.128%

Validation gate: train n>=30 ✔, train mean>0 ✔, validation n>=30 ✔, validation mean>0 ✔, validation PF>=1.10 ✔, validation P(mean>0)>=0.80 ✔, validation mean>0 at 2x costs ✔

**Decision: OUT-OF-SAMPLE POSITIVE**

## rsi2_mean_reversion

**Hypothesis:** Sharp 2-3 day selloffs inside a long-term uptrend overshoot and revert within days as liquidity providers are paid to absorb flow.
**Intended regime:** long-term uptrend, short-term oversold
**Parameters (fixed):** `{'rsi_max': 10, 'stop_pct': 0.1, 'max_hold': 10}`
**Universe:** SPY, QQQ, IWM, DIA (yf 1d)

| split | window | n | mean net % | std % | win rate | payoff | PF | max DD % | 95% CI mean % | Sharpe-like |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 1993-01-29 → 2013-03-31 | 432 | +0.429 | 2.169 | 0.71 | 0.74 | 1.79 | 18.0 | [+0.228, +0.633] | 0.91 |
| validation | 2013-03-31 → 2019-12-21 | 225 | +0.202 | 1.592 | 0.67 | 0.72 | 1.43 | 17.8 | [-0.009, +0.399] | 0.74 |
| test | 2019-12-21 → 2026-09-11 | 236 | +0.402 | 2.188 | 0.73 | 0.65 | 1.74 | 13.3 | [+0.122, +0.674] | 1.09 |

Cost sensitivity, net mean % at 0x/1x/2x/3x — train {'0x': 0.4980109784181984, '1x': 0.42873126922054133, '2x': 0.3780845849782738, '3x': 0.3288943376022177}, validation {'0x': 0.2601341230406507, '1x': 0.20239847341102063, '2x': 0.15225610555723396, '3x': 0.10220730794052353}, test {'0x': 0.45551446242710947, '1x': 0.4022176721326374, '2x': 0.3521724598099073, '3x': 0.3019568841019078}

Walk-forward (pre-test, expanding window; parameters are fixed so each fold is out-of-sample):

- 1993-01-29 → 2007-11-13: n=154, mean net +0.267%
- 1993-01-29 → 2011-11-25: n=98, mean net +0.129%
- 1993-01-29 → 2015-12-07: n=154, mean net +0.429%
- 1993-01-29 → 2019-12-20: n=119, mean net +0.053%

Validation gate: train n>=30 ✔, train mean>0 ✔, validation n>=30 ✔, validation mean>0 ✔, validation PF>=1.10 ✔, validation P(mean>0)>=0.80 ✔, validation mean>0 at 2x costs ✔

**Decision: OUT-OF-SAMPLE POSITIVE**
