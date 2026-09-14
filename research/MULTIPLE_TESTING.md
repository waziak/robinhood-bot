# Multiple-Testing Accounting

Generated 2026-09-14 00:23 UTC.

**Total hypotheses tested to date: 19** (3 legacy production strategies + 16 pre-registered research candidates across Phases 3-4). Each is a distinct, fixed strategy specification evaluated once against its own train/validation/(sealed once) test split.

At a family-wise error rate of 5% across all 19 hypotheses, the Bonferroni-adjusted single-test significance level is 0.00263, which in percentile-vs-random-entry-null terms requires a result at or above the **99.74th percentile** — not the 95th percentile used as this codebase's nominal "strong evidence" bar elsewhere.

| n hypotheses | nominal bar | Bonferroni-adjusted bar |
|---|---|---|
| 1 (single pre-registered test) | 95th pct | 95th pct |
| 19 (actual, this program) | 95th pct | 99.74th pct |

**No candidate clears the adjusted 99.74th-percentile bar.**
Candidate(s) that clear the *nominal* single-test 95th percentile but NOT the adjusted bar (exactly the situation this correction exists for): weekly_rsi2.

## Hypotheses counted

1. trend_pullback
2. breakout
3. mean_reversion
4. orb_continuation
5. vwap_pullback
6. intraday_momentum_last_hour
7. crypto_tsmom
8. overnight_drift
9. overnight_drift_trend
10. trend_sma200
11. rsi2_mean_reversion
12. monthly_sma10_timing_spy
13. monthly_sma10_timing_multi
14. sector_rotation_momentum
15. rsi2_early_exit
16. pullback_from_high
17. weekly_rsi2
18. combined_trend_vol_rsi2
19. low_volatility_rotation

## Why this matters

If 20 independent, genuinely edge-less strategies are each tested at the 95th-percentile (one-sided 5%) bar, the expected number that pass by chance alone is 20 × 0.05 = 1 — i.e., roughly one "discovery" per 20 hypotheses tested is expected noise, not edge. Any single result that clears the nominal 95th but not the adjusted bar above should be treated with real skepticism — it is exactly the pattern expected from chance alone at this sample size, not confirmed evidence.
