# Current Strategy Post-mortem

## Findings (written 2026-09-13 from the tables below; regenerating this file replaces everything, including this section)

**Verdict: all three production strategies have negative expectancy after realistic costs, on every asset class, and
the cause is primarily the absence of a predictive signal — costs then turn a ~zero gross edge into a reliable loss.**

| strategy | crypto net/trade (n) | equity net/trade (n) | equity, risk-engine approved (n) | gross/trade (crypto, equity) |
|---|---|---|---|---|
| trend_pullback | −0.430% (970) | −0.084% (546) | −0.084% (86) | −0.030%, −0.006% |
| breakout | −0.404% (1,044) | −0.059% (185) | −0.202% (18) | −0.005%, +0.020% |
| mean_reversion | −0.427% (452) | −0.109% (186) | −0.144% (40) | −0.028%, −0.033% |

Sample: 5,614 proposals — BTC/ETH 5-minute bars 2026-03-17 → 09-13 (180 days) and 16 ETFs/stocks 5-minute bars
2026-06-17 → 09-11 (60 days, the maximum available). No crypto proposal ever passed the risk engine.

Failure attribution, most to least important:

1. **Weak predictive signal (primary).** Forward returns after a signal are indistinguishable from unconditional
   forward returns at 6, 12 and 48 bars for every strategy (all |t| ≤ 1.43). Gross return per trade is ≈ 0
   (−0.03% to +0.02%). There is nothing for exits, sizing or regime filters to amplify.
2. **Spreads and slippage.** Crypto round-trip cost (~0.40%) is ~80% of the typical stop distance (~0.5%), so a
   coin-flip signal becomes a 14% win rate and profit factor ≈ 0.1. Equity costs (~0.08%) turn ~0 gross into
   −0.06% to −0.11% net. Net expectancy degrades linearly at 2× and 3× costs.
3. **Inadequate reward/risk realisation.** Planned 2R targets need ≥33% winners before costs; realised win rates are
   14% (crypto) and 22–33% (equities); realised mean R is −0.40 to −1.20.
4. **Exits (secondary).** 15–22% of trades reached +1R and still finished as losers; stops account for 58–83% of
   exits and 19–50% of trades are stopped within 3 bars. Better exits cannot rescue a zero-gross entry.
5. **Regime selection (no help).** Trades in each strategy's intended regime did no better than trades outside it.
6. **Turnover.** Multiplies cost drag (crypto trend_pullback: ~5 trades/day), but even at zero cost the gross mean
   is ~0, so lower turnover alone would not create an edge.
7. **Position sizing / random noise.** Not causes: results are per-trade percentages, and bootstrap 95% intervals
   exclude zero on the negative side for every crypto book and every all-proposal equity book.

**Score calibration.** Spearman correlation of score with net outcome is +0.14 (n = 5,517), driven by the spread and
reward/risk components (less cost drag), but only +0.01 with the 12-bar forward price move: the score has no
directional predictive value. Even the 80–100 bucket loses −0.12% per trade. Decision: the score is kept as a
descriptive/cost-quality metric only; it is no longer treated as evidence of edge. A new risk-engine gate
(`RiskConfig.approved_strategies`, empty by default) blocks all three strategies from opening positions.

**Recommendation:** retire trend_pullback, breakout and mean_reversion from any live consideration. Do not re-tune
them on this data — that would be fitting noise.

Caveats: equity intraday history is only 60 days (Yahoo Finance limit); crypto costs are an assumption for Robinhood's
embedded spread (stress-tested at 2–3×); crypto volume is zeroed to mirror Robinhood data, which also removes the
volume component of the score for crypto.

---

Generated 2026-09-13 18:44 UTC by `python -m research.run_postmortem`. Runs the production `trader.strategies` + `trader.scoring` code bar-by-bar with no lookahead; entries at the next bar open; stops assumed to hit before targets inside a bar; costs per `research/costs.py`.

## Data

| symbol | 5m bars | from | to | proposals |
|---|---|---|---|---|
| BTC-USD | 51762 | 2026-03-17 | 2026-09-13 | 2003 |
| ETH-USD | 51761 | 2026-03-17 | 2026-09-13 | 2033 |
| SPY | 4680 | 2026-06-17 | 2026-09-11 | 83 |
| QQQ | 4680 | 2026-06-17 | 2026-09-11 | 87 |
| IWM | 4680 | 2026-06-17 | 2026-09-11 | 107 |
| DIA | 4680 | 2026-06-17 | 2026-09-11 | 102 |
| XLK | 4680 | 2026-06-17 | 2026-09-11 | 105 |
| XLF | 4680 | 2026-06-17 | 2026-09-11 | 69 |
| XLE | 4680 | 2026-06-17 | 2026-09-11 | 106 |
| XLV | 4680 | 2026-06-17 | 2026-09-11 | 101 |
| TLT | 4680 | 2026-06-17 | 2026-09-11 | 98 |
| GLD | 4680 | 2026-06-17 | 2026-09-11 | 104 |
| AAPL | 4680 | 2026-06-17 | 2026-09-11 | 104 |
| MSFT | 4680 | 2026-06-17 | 2026-09-11 | 138 |
| NVDA | 4680 | 2026-06-17 | 2026-09-11 | 89 |
| AMZN | 4680 | 2026-06-17 | 2026-09-11 | 97 |
| GOOGL | 4680 | 2026-06-17 | 2026-09-11 | 92 |
| META | 4680 | 2026-06-17 | 2026-09-11 | 96 |

Crypto: Coinbase public candles (volume zeroed to match Robinhood). Equities: Yahoo Finance 5m (max 60 days available). Single stocks are current survivors (survivorship bias); ETFs are not affected.

## trend_pullback

**Hypothesis:** In an established intraday uptrend (SMA20>SMA50, rising SMA50) a shallow pullback to EMA20 with RSI 40-55 and an up-close resumes the trend. **Intended regime:** up.

### crypto

| metric | all proposals (one position at a time) | risk-engine approved only |
|---|---|---|
| trades | 970 | — |
| gross mean % | -0.030 | — |
| est. cost % | 0.399 | — |
| net mean % (expectancy) | -0.430 | — |
| win rate | 0.141 | — |
| avg winner % | 0.451 | — |
| avg loser % | -0.575 | — |
| profit factor | 0.129 | — |
| max drawdown % (sum of returns) | 417.707 | — |
| avg holding (5m bars) | 14.829 | — |
| avg MFE % | 0.323 | — |
| avg MAE % | -0.255 | — |
| t-stat | -32.396 | — |

Cost sensitivity (net mean % at 0x/1x/2x/3x costs): {'0x': -0.030464462258356837, '1x': -0.4298044661260496, '2x': -0.8272904768043715, '3x': -1.2231897541099959}

**Why it fails / attribution**

- Predictive content, 6 bars: signal fwd return +0.004% vs unconditional +0.002% → edge +0.002% (t=0.57, n=2068)
- Predictive content, 12 bars: signal fwd return -0.002% vs unconditional +0.003% → edge -0.005% (t=-0.24, n=2068)
- Predictive content, 48 bars: signal fwd return -0.029% vs unconditional +0.013% → edge -0.042% (t=-1.41, n=2068)
- Costs: gross -0.030% → net -0.430% per trade; costs 0.399% (gross edge itself is negative)
- Exits: 31% of trades moved ≥1R in favour at some point; 16% of all trades reached +1R and still lost money. Exit mix: {'stop': 0.78, 'target': 0.12, 'time': 0.1, 'stop_gap': 0.0}
- Entries: 29% of trades stopped out within 3 bars; planned R:R 2.00 needs win rate ≥ 33% before costs, actual 14%; realized mean R -1.14
- Regime: intended 'up' net -0.448% (n=526) vs other -0.408% (n=444)
- Noise: 95% bootstrap CI of mean net return [-0.455%, -0.404%], P(mean>0)=0.00

By regime:

| regime | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| down | 14.000 | 0.286 | -0.333 | -0.554 | -4.665 |
| range | 430.000 | 0.128 | -0.410 | -0.491 | -176.381 |
| up | 526.000 | 0.148 | -0.448 | -0.546 | -235.865 |

By hour (ET):

| hour_et | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| 0 | 31.000 | 0.097 | -0.481 | -0.535 | -14.913 |
| 1 | 33.000 | 0.121 | -0.480 | -0.519 | -15.840 |
| 2 | 34.000 | 0.088 | -0.451 | -0.505 | -15.340 |
| 3 | 43.000 | 0.140 | -0.395 | -0.497 | -16.994 |
| 4 | 49.000 | 0.184 | -0.381 | -0.536 | -18.649 |
| 5 | 37.000 | 0.081 | -0.518 | -0.566 | -19.180 |
| 6 | 36.000 | 0.167 | -0.416 | -0.498 | -14.970 |
| 7 | 33.000 | 0.212 | -0.307 | -0.471 | -10.145 |
| 8 | 44.000 | 0.182 | -0.411 | -0.494 | -18.066 |
| 9 | 22.000 | 0.182 | -0.439 | -0.561 | -9.667 |
| 10 | 44.000 | 0.159 | -0.460 | -0.521 | -20.262 |
| 11 | 42.000 | 0.238 | -0.287 | -0.502 | -12.037 |
| 12 | 61.000 | 0.180 | -0.381 | -0.523 | -23.255 |
| 13 | 35.000 | 0.229 | -0.320 | -0.452 | -11.201 |
| 14 | 55.000 | 0.127 | -0.459 | -0.543 | -25.265 |
| 15 | 38.000 | 0.105 | -0.465 | -0.561 | -17.660 |
| 16 | 49.000 | 0.143 | -0.442 | -0.521 | -21.668 |
| 17 | 36.000 | 0.028 | -0.535 | -0.529 | -19.257 |
| 18 | 44.000 | 0.159 | -0.394 | -0.549 | -17.354 |
| 19 | 39.000 | 0.103 | -0.487 | -0.542 | -18.999 |
| 20 | 37.000 | 0.081 | -0.487 | -0.490 | -18.031 |
| 21 | 44.000 | 0.091 | -0.543 | -0.535 | -23.872 |
| 22 | 43.000 | 0.163 | -0.425 | -0.540 | -18.254 |
| 23 | 41.000 | 0.098 | -0.391 | -0.519 | -16.032 |

By symbol:

| symbol | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| BTC-USD | 486.000 | 0.132 | -0.421 | -0.503 | -204.364 |
| ETH-USD | 484.000 | 0.151 | -0.439 | -0.549 | -212.546 |

By exit reason:

| exit_reason | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| stop | 757.000 | 0.000 | -0.601 | -0.555 | -454.770 |
| stop_gap | 1.000 | 0.000 | -0.438 | -0.438 | -0.438 |
| target | 116.000 | 1.000 | 0.488 | 0.407 | 56.563 |
| time | 96.000 | 0.219 | -0.190 | -0.241 | -18.265 |

By volatility tercile (ATR% of price):

| vol_bucket | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| low vol | 324.000 | 0.114 | -0.389 | -0.465 | -126.118 |
| mid vol | 322.000 | 0.106 | -0.468 | -0.555 | -150.584 |
| high vol | 324.000 | 0.204 | -0.433 | -0.617 | -140.209 |

### equity

| metric | all proposals (one position at a time) | risk-engine approved only |
|---|---|---|
| trades | 546 | 86 |
| gross mean % | -0.006 | -0.008 |
| est. cost % | 0.078 | 0.075 |
| net mean % (expectancy) | -0.084 | -0.084 |
| win rate | 0.321 | 0.372 |
| avg winner % | 0.364 | 0.505 |
| avg loser % | -0.296 | -0.433 |
| profit factor | 0.581 | 0.692 |
| max drawdown % (sum of returns) | 46.103 | 8.198 |
| avg holding (5m bars) | 16.722 | 18.756 |
| avg MFE % | 0.283 | 0.384 |
| avg MAE % | -0.232 | -0.321 |
| t-stat | -4.994 | -1.272 |

Cost sensitivity (net mean % at 0x/1x/2x/3x costs): {'0x': -0.005964377584794139, '1x': -0.08429973167117966, '2x': -0.1572715713770358, '3x': -0.22993364834600602}

**Why it fails / attribution**

- Predictive content, 6 bars: signal fwd return -0.001% vs unconditional +0.000% → edge -0.001% (t=-0.11, n=1171)
- Predictive content, 12 bars: signal fwd return -0.004% vs unconditional +0.008% → edge -0.012% (t=-0.29, n=1171)
- Predictive content, 48 bars: signal fwd return +0.027% vs unconditional +0.066% → edge -0.039% (t=0.73, n=1171)
- Costs: gross -0.006% → net -0.084% per trade; costs 0.078% (gross edge itself is negative)
- Exits: 45% of trades moved ≥1R in favour at some point; 15% of all trades reached +1R and still lost money. Exit mix: {'stop': 0.58, 'target': 0.19, 'session_end': 0.13, 'time': 0.1, 'stop_gap': 0.0}
- Entries: 19% of trades stopped out within 3 bars; planned R:R 2.00 needs win rate ≥ 33% before costs, actual 32%; realized mean R -0.40
- Regime: intended 'up' net -0.088% (n=209) vs other -0.082% (n=337)
- Noise: 95% bootstrap CI of mean net return [-0.116%, -0.050%], P(mean>0)=0.00

By regime:

| regime | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| down | 85.000 | 0.294 | -0.135 | -0.248 | -11.508 |
| range | 252.000 | 0.329 | -0.064 | -0.173 | -16.125 |
| up | 209.000 | 0.321 | -0.088 | -0.169 | -18.395 |

By hour (ET):

| hour_et | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| 9 | 18.000 | 0.333 | -0.050 | -0.299 | -0.899 |
| 10 | 115.000 | 0.357 | -0.095 | -0.254 | -10.929 |
| 11 | 102.000 | 0.304 | -0.094 | -0.227 | -9.566 |
| 12 | 116.000 | 0.302 | -0.083 | -0.186 | -9.656 |
| 13 | 68.000 | 0.250 | -0.110 | -0.156 | -7.455 |
| 14 | 86.000 | 0.337 | -0.066 | -0.125 | -5.633 |
| 15 | 41.000 | 0.390 | -0.046 | -0.093 | -1.889 |

By symbol:

| symbol | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| AAPL | 31.000 | 0.387 | -0.065 | -0.225 | -2.017 |
| AMZN | 34.000 | 0.235 | -0.264 | -0.321 | -8.982 |
| DIA | 39.000 | 0.256 | -0.067 | -0.124 | -2.602 |
| GLD | 35.000 | 0.286 | -0.103 | -0.171 | -3.601 |
| GOOGL | 32.000 | 0.344 | -0.098 | -0.280 | -3.129 |
| IWM | 34.000 | 0.382 | -0.022 | -0.103 | -0.749 |
| META | 37.000 | 0.297 | -0.104 | -0.317 | -3.859 |
| MSFT | 47.000 | 0.404 | -0.019 | -0.218 | -0.889 |
| NVDA | 39.000 | 0.359 | -0.043 | -0.295 | -1.690 |
| QQQ | 26.000 | 0.346 | -0.043 | -0.113 | -1.110 |
| SPY | 28.000 | 0.286 | -0.053 | -0.129 | -1.495 |
| TLT | 30.000 | 0.267 | -0.098 | -0.137 | -2.953 |
| XLE | 38.000 | 0.316 | -0.106 | -0.253 | -4.012 |
| XLF | 27.000 | 0.222 | -0.140 | -0.207 | -3.778 |
| XLK | 33.000 | 0.303 | -0.068 | -0.152 | -2.239 |
| XLV | 36.000 | 0.389 | -0.081 | -0.169 | -2.924 |

By exit reason:

| exit_reason | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| session_end | 69.000 | 0.522 | 0.024 | 0.016 | 1.649 |
| stop | 317.000 | 0.000 | -0.321 | -0.288 | -101.659 |
| stop_gap | 2.000 | 0.000 | -0.286 | -0.286 | -0.572 |
| target | 105.000 | 1.000 | 0.444 | 0.345 | 46.668 |
| time | 53.000 | 0.642 | 0.149 | 0.105 | 7.887 |

By volatility tercile (ATR% of price):

| vol_bucket | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| low vol | 182.000 | 0.280 | -0.083 | -0.135 | -15.017 |
| mid vol | 182.000 | 0.357 | -0.059 | -0.211 | -10.786 |
| high vol | 182.000 | 0.324 | -0.111 | -0.330 | -20.225 |

By relative volume:

| rv_bucket | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| <0.8x | 393.000 | 0.300 | -0.101 | -0.198 | -39.818 |
| 0.8-1.5x | 121.000 | 0.397 | -0.027 | -0.128 | -3.268 |
| >1.5x | 32.000 | 0.281 | -0.092 | -0.145 | -2.942 |

## breakout

**Hypothesis:** A close above the prior 2-hour high on range expansion (and volume, when available) starts a continuation move. **Intended regime:** up.

### crypto

| metric | all proposals (one position at a time) | risk-engine approved only |
|---|---|---|
| trades | 1044 | — |
| gross mean % | -0.005 | — |
| est. cost % | 0.399 | — |
| net mean % (expectancy) | -0.404 | — |
| win rate | 0.144 | — |
| avg winner % | 0.446 | — |
| avg loser % | -0.547 | — |
| profit factor | 0.137 | — |
| max drawdown % (sum of returns) | 422.897 | — |
| avg holding (5m bars) | 7.559 | — |
| avg MFE % | 0.308 | — |
| avg MAE % | -0.209 | — |
| t-stat | -34.589 | — |

Cost sensitivity (net mean % at 0x/1x/2x/3x costs): {'0x': -0.004534478831230332, '1x': -0.4039659615007489, '2x': -0.8015639255506638, '3x': -1.1975700676454324}

**Why it fails / attribution**

- Predictive content, 6 bars: signal fwd return -0.014% vs unconditional +0.002% → edge -0.015% (t=-1.10, n=1476)
- Predictive content, 12 bars: signal fwd return -0.006% vs unconditional +0.003% → edge -0.009% (t=-0.33, n=1476)
- Predictive content, 48 bars: signal fwd return -0.007% vs unconditional +0.013% → edge -0.020% (t=-0.24, n=1476)
- Costs: gross -0.005% → net -0.404% per trade; costs 0.399% (gross edge itself is negative)
- Exits: 31% of trades moved ≥1R in favour at some point; 17% of all trades reached +1R and still lost money. Exit mix: {'stop': 0.83, 'target': 0.14, 'time': 0.03}
- Entries: 50% of trades stopped out within 3 bars; planned R:R 2.00 needs win rate ≥ 33% before costs, actual 14%; realized mean R -1.20
- Regime: intended 'up' net -0.401% (n=583) vs other -0.408% (n=461)
- Noise: 95% bootstrap CI of mean net return [-0.426%, -0.381%], P(mean>0)=0.00

By regime:

| regime | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| down | 7.000 | 0.143 | -0.461 | -0.546 | -3.227 |
| range | 454.000 | 0.112 | -0.407 | -0.482 | -184.924 |
| up | 583.000 | 0.168 | -0.401 | -0.535 | -233.590 |

By hour (ET):

| hour_et | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| 0 | 32.000 | 0.000 | -0.533 | -0.529 | -17.072 |
| 1 | 45.000 | 0.133 | -0.413 | -0.514 | -18.603 |
| 2 | 43.000 | 0.093 | -0.440 | -0.501 | -18.912 |
| 3 | 59.000 | 0.119 | -0.420 | -0.490 | -24.791 |
| 4 | 46.000 | 0.196 | -0.306 | -0.491 | -14.072 |
| 5 | 33.000 | 0.182 | -0.374 | -0.477 | -12.352 |
| 6 | 31.000 | 0.097 | -0.435 | -0.510 | -13.498 |
| 7 | 50.000 | 0.160 | -0.381 | -0.485 | -19.039 |
| 8 | 69.000 | 0.174 | -0.369 | -0.500 | -25.454 |
| 9 | 53.000 | 0.208 | -0.338 | -0.535 | -17.928 |
| 10 | 52.000 | 0.231 | -0.342 | -0.487 | -17.803 |
| 11 | 50.000 | 0.140 | -0.414 | -0.579 | -20.700 |
| 12 | 39.000 | 0.179 | -0.385 | -0.561 | -15.014 |
| 13 | 32.000 | 0.094 | -0.491 | -0.550 | -15.719 |
| 14 | 30.000 | 0.167 | -0.376 | -0.527 | -11.288 |
| 15 | 55.000 | 0.145 | -0.411 | -0.505 | -22.607 |
| 16 | 22.000 | 0.136 | -0.408 | -0.500 | -8.970 |
| 17 | 45.000 | 0.222 | -0.363 | -0.522 | -16.347 |
| 18 | 49.000 | 0.163 | -0.361 | -0.514 | -17.675 |
| 19 | 33.000 | 0.091 | -0.469 | -0.513 | -15.493 |
| 20 | 59.000 | 0.085 | -0.455 | -0.537 | -26.848 |
| 21 | 48.000 | 0.083 | -0.462 | -0.503 | -22.183 |
| 22 | 29.000 | 0.172 | -0.392 | -0.512 | -11.364 |
| 23 | 40.000 | 0.100 | -0.450 | -0.503 | -18.011 |

By symbol:

| symbol | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| BTC-USD | 525.000 | 0.118 | -0.417 | -0.496 | -218.922 |
| ETH-USD | 519.000 | 0.170 | -0.391 | -0.527 | -202.818 |

By exit reason:

| exit_reason | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| stop | 870.000 | 0.000 | -0.555 | -0.529 | -482.809 |
| target | 143.000 | 1.000 | 0.463 | 0.419 | 66.205 |
| time | 31.000 | 0.226 | -0.166 | -0.174 | -5.136 |

By volatility tercile (ATR% of price):

| vol_bucket | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| low vol | 348.000 | 0.080 | -0.408 | -0.462 | -141.840 |
| mid vol | 348.000 | 0.132 | -0.416 | -0.522 | -144.744 |
| high vol | 348.000 | 0.218 | -0.388 | -0.610 | -135.156 |

### equity

| metric | all proposals (one position at a time) | risk-engine approved only |
|---|---|---|
| trades | 185 | 18 |
| gross mean % | 0.020 | -0.124 |
| est. cost % | 0.079 | 0.078 |
| net mean % (expectancy) | -0.059 | -0.202 |
| win rate | 0.330 | 0.167 |
| avg winner % | 0.307 | 0.578 |
| avg loser % | -0.239 | -0.358 |
| profit factor | 0.631 | 0.323 |
| max drawdown % (sum of returns) | 12.838 | 4.372 |
| avg holding (5m bars) | 6.535 | 12.611 |
| avg MFE % | 0.233 | 0.326 |
| avg MAE % | -0.192 | -0.388 |
| t-stat | -2.473 | -2.241 |

Cost sensitivity (net mean % at 0x/1x/2x/3x costs): {'0x': 0.01958375973171707, '1x': -0.05926472100135815, '2x': -0.1337373082031747, '3x': -0.20746149182964044}

**Why it fails / attribution**

- Predictive content, 6 bars: signal fwd return -0.032% vs unconditional +0.000% → edge -0.032% (t=-1.43, n=215)
- Predictive content, 12 bars: signal fwd return +0.039% vs unconditional +0.008% → edge +0.031% (t=0.53, n=215)
- Predictive content, 48 bars: signal fwd return +0.087% vs unconditional +0.066% → edge +0.021% (t=0.64, n=215)
- Costs: gross +0.020% → net -0.059% per trade; costs 0.079% (costs exceed the entire gross edge)
- Exits: 50% of trades moved ≥1R in favour at some point; 17% of all trades reached +1R and still lost money. Exit mix: {'stop': 0.63, 'target': 0.3, 'session_end': 0.04, 'time': 0.02, 'stop_gap': 0.01}
- Entries: 31% of trades stopped out within 3 bars; planned R:R 2.00 needs win rate ≥ 33% before costs, actual 33%; realized mean R -0.45
- Regime: intended 'up' net -0.120% (n=72) vs other -0.021% (n=113)
- Noise: 95% bootstrap CI of mean net return [-0.106%, -0.012%], P(mean>0)=0.01

By regime:

| regime | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| down | 19.000 | 0.316 | -0.075 | -0.191 | -1.424 |
| range | 94.000 | 0.415 | -0.010 | -0.134 | -0.923 |
| up | 72.000 | 0.222 | -0.120 | -0.160 | -8.617 |

By hour (ET):

| hour_et | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| 9 | 26.000 | 0.423 | 0.050 | -0.156 | 1.304 |
| 10 | 13.000 | 0.462 | 0.104 | -0.132 | 1.348 |
| 11 | 13.000 | 0.308 | -0.101 | -0.190 | -1.307 |
| 12 | 17.000 | 0.235 | -0.108 | -0.184 | -1.842 |
| 13 | 33.000 | 0.242 | -0.108 | -0.158 | -3.560 |
| 14 | 45.000 | 0.311 | -0.107 | -0.151 | -4.805 |
| 15 | 38.000 | 0.368 | -0.055 | -0.100 | -2.103 |

By symbol:

| symbol | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| AAPL | 22.000 | 0.455 | 0.034 | -0.167 | 0.745 |
| AMZN | 8.000 | 0.500 | 0.012 | -0.006 | 0.097 |
| DIA | 12.000 | 0.333 | -0.045 | -0.095 | -0.541 |
| GLD | 15.000 | 0.200 | -0.109 | -0.152 | -1.638 |
| GOOGL | 8.000 | 0.375 | 0.021 | -0.107 | 0.165 |
| IWM | 10.000 | 0.500 | -0.034 | -0.020 | -0.336 |
| META | 17.000 | 0.471 | 0.041 | -0.212 | 0.705 |
| MSFT | 17.000 | 0.059 | -0.266 | -0.284 | -4.518 |
| NVDA | 16.000 | 0.375 | -0.082 | -0.222 | -1.314 |
| QQQ | 7.000 | 0.143 | -0.090 | -0.105 | -0.632 |
| SPY | 8.000 | 0.125 | -0.126 | -0.119 | -1.008 |
| TLT | 7.000 | 0.286 | -0.076 | -0.134 | -0.530 |
| XLE | 16.000 | 0.438 | -0.044 | -0.167 | -0.708 |
| XLF | 8.000 | 0.250 | -0.085 | -0.140 | -0.679 |
| XLK | 6.000 | 0.167 | -0.198 | -0.244 | -1.187 |
| XLV | 8.000 | 0.375 | 0.052 | -0.141 | 0.414 |

By exit reason:

| exit_reason | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| session_end | 8.000 | 0.375 | -0.039 | -0.046 | -0.315 |
| stop | 117.000 | 0.000 | -0.249 | -0.204 | -29.076 |
| stop_gap | 1.000 | 0.000 | -0.093 | -0.093 | -0.093 |
| target | 55.000 | 1.000 | 0.302 | 0.207 | 16.603 |
| time | 4.000 | 0.750 | 0.479 | 0.477 | 1.917 |

By volatility tercile (ATR% of price):

| vol_bucket | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| low vol | 62.000 | 0.323 | -0.062 | -0.107 | -3.864 |
| mid vol | 61.000 | 0.344 | -0.067 | -0.172 | -4.062 |
| high vol | 62.000 | 0.323 | -0.049 | -0.302 | -3.038 |

By relative volume:

| rv_bucket | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| >1.5x | 185.000 | 0.330 | -0.059 | -0.151 | -10.964 |

## mean_reversion

**Hypothesis:** In a flat regime a close below the lower Bollinger band with RSI<35 and a reversal bar reverts to SMA20. **Intended regime:** range.

### crypto

| metric | all proposals (one position at a time) | risk-engine approved only |
|---|---|---|
| trades | 452 | — |
| gross mean % | -0.028 | — |
| est. cost % | 0.399 | — |
| net mean % (expectancy) | -0.427 | — |
| win rate | 0.146 | — |
| avg winner % | 0.272 | — |
| avg loser % | -0.547 | — |
| profit factor | 0.085 | — |
| max drawdown % (sum of returns) | 193.187 | — |
| avg holding (5m bars) | 11.086 | — |
| avg MFE % | 0.280 | — |
| avg MAE % | -0.295 | — |
| t-stat | -23.734 | — |

Cost sensitivity (net mean % at 0x/1x/2x/3x costs): {'0x': -0.02808284426123963, '1x': -0.42740567205795926, '2x': -0.8249084769028626, '3x': -1.2208268955753074}

**Why it fails / attribution**

- Predictive content, 6 bars: signal fwd return -0.003% vs unconditional +0.002% → edge -0.004% (t=-0.17, n=492)
- Predictive content, 12 bars: signal fwd return -0.012% vs unconditional +0.003% → edge -0.015% (t=-0.58, n=492)
- Predictive content, 48 bars: signal fwd return -0.012% vs unconditional +0.013% → edge -0.025% (t=-0.26, n=492)
- Costs: gross -0.028% → net -0.427% per trade; costs 0.399% (gross edge itself is negative)
- Exits: 25% of trades moved ≥1R in favour at some point; 11% of all trades reached +1R and still lost money. Exit mix: {'stop': 0.69, 'target': 0.26, 'time': 0.05}
- Entries: 32% of trades stopped out within 3 bars; planned R:R 0.83 needs win rate ≥ 55% before costs, actual 15%; realized mean R -1.03
- Regime: intended 'range' net -0.443% (n=244) vs other -0.409% (n=208)
- Noise: 95% bootstrap CI of mean net return [-0.462%, -0.393%], P(mean>0)=0.00

By regime:

| regime | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| down | 207.000 | 0.164 | -0.408 | -0.552 | -84.532 |
| range | 244.000 | 0.131 | -0.443 | -0.540 | -108.166 |
| up | 1.000 | 0.000 | -0.489 | -0.489 | -0.489 |

By hour (ET):

| hour_et | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| 0 | 15.000 | 0.267 | -0.369 | -0.520 | -5.534 |
| 1 | 20.000 | 0.050 | -0.461 | -0.513 | -9.224 |
| 2 | 30.000 | 0.200 | -0.355 | -0.470 | -10.650 |
| 3 | 30.000 | 0.100 | -0.385 | -0.483 | -11.558 |
| 4 | 30.000 | 0.033 | -0.586 | -0.638 | -17.592 |
| 5 | 13.000 | 0.077 | -0.362 | -0.444 | -4.703 |
| 6 | 18.000 | 0.000 | -0.484 | -0.556 | -8.713 |
| 7 | 8.000 | 0.000 | -0.344 | -0.182 | -2.750 |
| 8 | 32.000 | 0.125 | -0.585 | -0.623 | -18.711 |
| 9 | 43.000 | 0.140 | -0.519 | -0.603 | -22.325 |
| 10 | 26.000 | 0.154 | -0.412 | -0.531 | -10.713 |
| 11 | 10.000 | 0.200 | -0.426 | -0.608 | -4.264 |
| 12 | 10.000 | 0.200 | -0.368 | -0.562 | -3.681 |
| 13 | 13.000 | 0.154 | -0.356 | -0.544 | -4.634 |
| 14 | 16.000 | 0.125 | -0.523 | -0.585 | -8.371 |
| 15 | 10.000 | 0.100 | -0.547 | -0.568 | -5.471 |
| 16 | 7.000 | 0.571 | -0.051 | 0.152 | -0.354 |
| 17 | 14.000 | 0.357 | -0.278 | -0.501 | -3.888 |
| 18 | 26.000 | 0.231 | -0.288 | -0.534 | -7.481 |
| 19 | 20.000 | 0.200 | -0.340 | -0.469 | -6.791 |
| 20 | 8.000 | 0.000 | -0.639 | -0.599 | -5.112 |
| 21 | 19.000 | 0.053 | -0.434 | -0.517 | -8.239 |
| 22 | 18.000 | 0.222 | -0.345 | -0.531 | -6.215 |
| 23 | 16.000 | 0.188 | -0.388 | -0.493 | -6.214 |

By symbol:

| symbol | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| BTC-USD | 236.000 | 0.102 | -0.434 | -0.523 | -102.452 |
| ETH-USD | 216.000 | 0.194 | -0.420 | -0.561 | -90.735 |

By exit reason:

| exit_reason | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| stop | 312.000 | 0.000 | -0.641 | -0.598 | -199.885 |
| target | 118.000 | 0.517 | 0.088 | 0.009 | 10.437 |
| time | 22.000 | 0.227 | -0.170 | -0.160 | -3.740 |

By volatility tercile (ATR% of price):

| vol_bucket | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| low vol | 151.000 | 0.040 | -0.402 | -0.484 | -60.667 |
| mid vol | 150.000 | 0.147 | -0.434 | -0.569 | -65.057 |
| high vol | 151.000 | 0.252 | -0.447 | -0.647 | -67.464 |

### equity

| metric | all proposals (one position at a time) | risk-engine approved only |
|---|---|---|
| trades | 186 | 40 |
| gross mean % | -0.033 | -0.072 |
| est. cost % | 0.076 | 0.072 |
| net mean % (expectancy) | -0.109 | -0.144 |
| win rate | 0.220 | 0.175 |
| avg winner % | 0.351 | 0.747 |
| avg loser % | -0.239 | -0.333 |
| profit factor | 0.415 | 0.476 |
| max drawdown % (sum of returns) | 20.452 | 5.762 |
| avg holding (5m bars) | 11.075 | 17.050 |
| avg MFE % | 0.235 | 0.437 |
| avg MAE % | -0.204 | -0.345 |
| t-stat | -4.703 | -1.930 |

Cost sensitivity (net mean % at 0x/1x/2x/3x costs): {'0x': -0.03336748101518256, '1x': -0.10901448196016895, '2x': -0.1788654508394208, '3x': -0.24816167585443535}

**Why it fails / attribution**

- Predictive content, 6 bars: signal fwd return -0.014% vs unconditional +0.000% → edge -0.014% (t=-0.62, n=192)
- Predictive content, 12 bars: signal fwd return +0.048% vs unconditional +0.008% → edge +0.040% (t=1.28, n=192)
- Predictive content, 48 bars: signal fwd return +0.082% vs unconditional +0.066% → edge +0.016% (t=1.05, n=192)
- Costs: gross -0.033% → net -0.109% per trade; costs 0.076% (gross edge itself is negative)
- Exits: 44% of trades moved ≥1R in favour at some point; 22% of all trades reached +1R and still lost money. Exit mix: {'stop': 0.67, 'target': 0.18, 'time': 0.09, 'session_end': 0.06}
- Entries: 38% of trades stopped out within 3 bars; planned R:R 2.71 needs win rate ≥ 27% before costs, actual 22%; realized mean R -0.52
- Regime: intended 'range' net -0.125% (n=121) vs other -0.080% (n=65)
- Noise: 95% bootstrap CI of mean net return [-0.151%, -0.063%], P(mean>0)=0.00

By regime:

| regime | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| down | 55.000 | 0.291 | -0.092 | -0.160 | -5.050 |
| range | 121.000 | 0.182 | -0.125 | -0.164 | -15.067 |
| up | 10.000 | 0.300 | -0.016 | -0.145 | -0.159 |

By hour (ET):

| hour_et | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| 9 | 69.000 | 0.174 | -0.149 | -0.219 | -10.250 |
| 10 | 28.000 | 0.214 | -0.118 | -0.247 | -3.303 |
| 11 | 9.000 | 0.222 | -0.071 | -0.146 | -0.636 |
| 12 | 10.000 | 0.100 | -0.136 | -0.155 | -1.356 |
| 13 | 12.000 | 0.083 | -0.104 | -0.124 | -1.243 |
| 14 | 43.000 | 0.349 | -0.056 | -0.104 | -2.390 |
| 15 | 15.000 | 0.267 | -0.073 | -0.103 | -1.100 |

By symbol:

| symbol | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| AAPL | 10.000 | 0.300 | -0.084 | -0.199 | -0.842 |
| AMZN | 8.000 | 0.250 | -0.149 | -0.401 | -1.192 |
| DIA | 12.000 | 0.083 | -0.126 | -0.149 | -1.507 |
| GLD | 17.000 | 0.235 | -0.128 | -0.156 | -2.169 |
| GOOGL | 10.000 | 0.300 | -0.167 | -0.343 | -1.669 |
| IWM | 19.000 | 0.105 | -0.142 | -0.211 | -2.707 |
| META | 1.000 | 0.000 | -0.211 | -0.211 | -0.211 |
| MSFT | 4.000 | 0.000 | -0.352 | -0.266 | -1.409 |
| NVDA | 6.000 | 0.333 | 0.006 | -0.294 | 0.036 |
| QQQ | 12.000 | 0.333 | -0.015 | -0.118 | -0.184 |
| SPY | 20.000 | 0.100 | -0.119 | -0.134 | -2.386 |
| TLT | 29.000 | 0.207 | -0.073 | -0.134 | -2.114 |
| XLE | 9.000 | 0.444 | 0.018 | -0.257 | 0.160 |
| XLF | 9.000 | 0.333 | -0.073 | -0.142 | -0.656 |
| XLK | 9.000 | 0.111 | -0.357 | -0.420 | -3.217 |
| XLV | 11.000 | 0.364 | -0.019 | -0.147 | -0.209 |

By exit reason:

| exit_reason | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| session_end | 12.000 | 0.500 | 0.033 | 0.003 | 0.400 |
| stop | 125.000 | 0.000 | -0.259 | -0.212 | -32.430 |
| target | 33.000 | 0.939 | 0.347 | 0.228 | 11.467 |
| time | 16.000 | 0.250 | 0.018 | -0.041 | 0.286 |

By volatility tercile (ATR% of price):

| vol_bucket | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| low vol | 62.000 | 0.226 | -0.068 | -0.124 | -4.219 |
| mid vol | 62.000 | 0.242 | -0.098 | -0.165 | -6.083 |
| high vol | 62.000 | 0.194 | -0.161 | -0.313 | -9.975 |

By relative volume:

| rv_bucket | n | win_rate | mean_pct | median_pct | total_pct |
|---|---|---|---|---|---|
| <0.8x | 50.000 | 0.240 | -0.090 | -0.142 | -4.504 |
| 0.8-1.5x | 77.000 | 0.143 | -0.158 | -0.201 | -12.149 |
| >1.5x | 59.000 | 0.305 | -0.061 | -0.155 | -3.624 |

## Score calibration (every proposal evaluated standalone)

| bucket | n | win_rate | mean_net_pct | median_net_pct | mean_gross_pct | mfe_pct | mae_pct |
|---|---|---|---|---|---|---|---|
| 0-20 | 0.000 | nan | nan | nan | nan | nan | nan |
| 20-40 | 512.000 | 0.113 | -0.410 | -0.466 | -0.015 | 0.236 | -0.213 |
| 40-60 | 3846.000 | 0.166 | -0.368 | -0.500 | -0.024 | 0.295 | -0.236 |
| 60-80 | 1106.000 | 0.289 | -0.160 | -0.204 | -0.009 | 0.321 | -0.250 |
| 80-100 | 53.000 | 0.245 | -0.121 | -0.226 | -0.043 | 0.298 | -0.271 |

Spearman rank correlation score vs net return: +0.140 (n=5517); vs 12-bar forward return: +0.010

- trend_pullback: Spearman +0.098 (n=3142)
- breakout: Spearman +0.018 (n=1691)
- mean_reversion: Spearman +0.253 (n=684)
