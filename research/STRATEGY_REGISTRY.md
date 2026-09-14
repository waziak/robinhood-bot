# Strategy Registry

Generated 2026-09-14 00:23 UTC by `python -m research.registry`. States: IDEA, RESEARCHING, FAILED, SHADOW_CANDIDATE, SHADOW_VALIDATED, LIVE_ELIGIBLE, RETIRED.

Summary: RESEARCHING=4, FAILED=12, RETIRED=3

| strategy | family | status | trades | rationale |
|---|---|---|---|---|
| rsi2_mean_reversion | daily/monthly | **RESEARCHING** | 893 | weak/inconclusive edge vs. random-entry null (test 85th percentile, validation 46th) — passed the formal gate but not the reality check; needs more evidence |
| monthly_sma10_timing_spy | daily/monthly | **RESEARCHING** | 25 | too few trades in train/validation to evaluate the gate — needs more data or a broader universe |
| weekly_rsi2 | daily/monthly | **RESEARCHING** | 169 | clears the nominal single-test 95th-percentile bar (test 97th) but NOT the multiple-testing-adjusted 99.74th-percentile bar required given 19 hypotheses tested (validation 100th) — promising but not yet promotable; see research/multiple_testing.py |
| combined_trend_vol_rsi2 | daily/monthly | **RESEARCHING** | 708 | weak/inconclusive edge vs. random-entry null (test 95th percentile, validation 46th) — passed the formal gate but not the reality check; needs more evidence |
| orb_continuation | intraday | **FAILED** | 103 | rejected at validation |
| vwap_pullback | intraday | **FAILED** | 379 | rejected at validation |
| intraday_momentum_last_hour | multi-hour | **FAILED** | 1488 | rejected at validation |
| crypto_tsmom | multi-hour | **FAILED** | 809 | rejected at validation |
| overnight_drift | daily/monthly | **FAILED** | 29196 | rejected at validation |
| overnight_drift_trend | daily/monthly | **FAILED** | 21158 | rejected at validation |
| trend_sma200 | daily/monthly | **FAILED** | 870 | reality check: test-window gains are explained by market drift/exposure (47th percentile vs. random-entry null), not timing skill |
| monthly_sma10_timing_multi | daily/monthly | **FAILED** | 443 | reality check: test-window gains are explained by market drift/exposure (62th percentile vs. random-entry null), not timing skill |
| sector_rotation_momentum | daily/monthly (cross-sectional rotation) | **FAILED** | 175 | rejected at validation |
| rsi2_early_exit | daily/monthly | **FAILED** | 928 | rejected at validation |
| pullback_from_high | daily/monthly | **FAILED** | 459 | reality check: test-window gains are explained by market drift/exposure (47th percentile vs. random-entry null), not timing skill |
| low_volatility_rotation | daily/monthly (cross-sectional rotation) | **FAILED** | 708 | reality check: test-window gains are explained by market drift/exposure (34th percentile vs. random-entry null), not timing skill |
| trend_pullback | legacy production | **RETIRED** | — | Production strategy (bot.py). No predictive signal after costs on 180d crypto + 60d equity 5-min bars (gross ≈0%, net −0.03% to −0.43%/trade). See research/CURRENT_STRATEGY_POSTMORTEM.md. |
| breakout | legacy production | **RETIRED** | — | Production strategy (bot.py). Same postmortem: no signal after costs. |
| mean_reversion | legacy production | **RETIRED** | — | Production strategy (bot.py). Same postmortem: no signal after costs. |

## Promotion rules

- **SHADOW_CANDIDATE** (automatic, this script): passed the pre-registered validation gate AND beats a random-entry null at or above the multiple-testing-adjusted 99.74th percentile (Bonferroni, 19 hypotheses tested — see `research/multiple_testing.py`) in BOTH the validation and test windows, so it is neither a one-window fluke nor a false positive expected from testing this many hypotheses. The bar rises automatically as more hypotheses are added.
- **SHADOW_VALIDATED** (manual, requires evidence this script cannot produce): a SHADOW_CANDIDATE run for real in `trader.agent --mode shadow` for enough calendar time to accumulate a meaningful trade count, with results consistent with the research-stage numbers.
- **LIVE_ELIGIBLE** (manual): a SHADOW_VALIDATED strategy with a completed Week-1-style review showing positive expectancy, acceptable drawdown, and no execution anomalies — see `trader/reporting.py`.
- Nothing may be added to `RiskConfig.approved_strategies` below LIVE_ELIGIBLE.

**Current state: no strategy is above RESEARCHING/FAILED/RETIRED.** `RiskConfig.approved_strategies` remains empty by design.
