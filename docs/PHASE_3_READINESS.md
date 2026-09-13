# Phase 3 Readiness Report — Strategy Discovery for Smooth, Low-Drawdown Returns

Date: 2026-09-13 · Branch: `hardening/week1-validation` (pushed to `origin` as a new branch; `main` untouched) · No live order was placed at any point.

Per instruction, four readiness dimensions are kept **separate** rather than blended into one number — excellent engineering does not imply a trading edge exists, and a good research process does not imply one was found.

| Dimension | Score | What it measures |
|---|---|---|
| **ENGINEERING READINESS** | 8/10 | Order safety, restart recovery, account isolation, testing, observability |
| **BROKER READINESS** | 6/10 | Whether the system can safely talk to the real Robinhood API |
| **STRATEGY READINESS** | 2/10 | Whether a demonstrated, credible trading edge exists |
| **LIVE CAPITAL READINESS** | 0/10 | Whether real money should be risked right now |

**Live capital readiness is 0/10 and stays there until both (a) you complete credential rotation and (b) a strategy is promoted past `RESEARCHING`.** Neither happened this phase, and neither was attempted.

---

## 1. ENGINEERING READINESS — 8/10

Unchanged in substance from the Phase 2 report, plus one real bug found and fixed this phase: `research/stats.py`'s
sequence-dependent statistics (max drawdown, longest losing streak) were computing over trades in **symbol-concatenation
order** (all of SPY's trades, then all of QQQ's, ...) instead of chronological order for any multi-symbol strategy —
silently wrong for exactly the metrics this phase cares about most (drawdown, streaks). Fixed (`chronological()` sort
before every sequence-dependent calculation), covered by a new regression test
(`test_summarize_and_consistency_are_row_order_independent`), and all affected reports were regenerated.

Also added: `research/portfolio.py`, a proper capital-constrained equity curve (splits ONE pool of capital across
whatever positions are open each day, instead of assuming unlimited capital / one fresh unit per signal) — this
matters specifically because the account is small enough that "one full unit per signal" is not a real option.
141 → 143 tests, all passing; `pyflakes` clean.

Not 10/10: the credential-rotation gap from Phase 2 is still open (see Broker Readiness), and the new portfolio/stats
code, while tested, hasn't been cross-checked by a second independent implementation.

## 2. BROKER READINESS — 6/10

No change since Phase 2 — this phase did no broker-facing work by design. `trader/accounts.py`, `trader/execution.py`,
and `trader/broker_test.py` remain code-complete and unit-tested against a faithful fake of the Robinhood API, but:
- **Credential rotation is still pending** (you said you'll do this yourself — change the Robinhood password, then
  `venv/bin/python -m trader.credentials setup` and `... login`, which will send a device-approval push to your phone).
- The live broker path has still never touched the real API.
- Crypto remains permanently `UNSUPPORTED_FOR_LIVE_AUTOMATION` — robin_stocks cannot pin a crypto order to account
  ••••4508, and nothing about that has changed. No crypto strategy has been proposed for live use anyway.

`trader/broker_test.py` is prepared exactly as specified (verifies auth, account ••••4508, cash-account type, buying
power, no emergency halt, no conflicting order, exact ticker/side/notional/estimated quantity, requires the literal
confirmation phrase, submits at most one $1 order, reconciles, and exits) — **it was not run.**

## 3. STRATEGY READINESS — 2/10

This is deliberately the sharpest number in this report. A large amount of legitimate research happened; **it found
essentially no edge.**

### What was tested
11 pre-registered candidates (3 carried over + 8 new this phase — intraday breakout/pullback, hourly momentum,
crypto time-series momentum, overnight drift, 10-month SMA timing on SPY alone and across 19 ETFs, and cross-sectional
sector/asset-class momentum rotation), each with a stated economic hypothesis, fixed parameters, and a chronological
60/20/20 train/validation/test split, walk-forward folds, realistic spread/slippage/fee costs (`research/costs.py`),
and — new this phase — a Monte Carlo random-entry null and buy-and-hold/trend-filter/cash baselines
(`research/baselines.py`), plus consistency metrics (downside deviation, longest losing streak, weekly/monthly hit
rate, Sortino-/Calmar-like ratios) and a capital-constrained portfolio view for every multi-symbol candidate.

The historical universe was also expanded: US equity ETFs now go back to 1993–2004 (covering the dot-com crash, 2008
GFC, 2020 COVID crash, and 2022 bear — genuine regime diversity), the ETF universe grew from 10 to 19 symbols
(sectors, bonds, gold, international, EM, REITs), and crypto hourly history extended from 3 to 5 years.

### Result: **research/STRATEGY_REGISTRY.md** — 2 RESEARCHING, 9 FAILED, 3 RETIRED. Nothing reached SHADOW_CANDIDATE.

| Holding-period family | Candidates | Outcome |
|---|---|---|
| Intraday (5-min) | orb_continuation, vwap_pullback | Rejected at validation — near-zero-to-negative gross edge before costs |
| Multi-hour (1h) | intraday_momentum_last_hour, crypto_tsmom | Rejected at validation |
| Daily / multi-day swing | overnight_drift(_trend), rsi2_mean_reversion | Overnight drift rejected; **rsi2_mean_reversion is the one lead** (below) |
| Monthly / long-hold | trend_sma200, monthly_sma10_timing_(spy/multi) | Passed the naive validation gate; **failed the harder reality check** — see below |
| Cross-sectional rotation | sector_rotation_momentum | Rejected at validation |

**Direct answer to "does a longer holding period beat frequent intraday trading here": yes, directionally — every
intraday and multi-hour candidate failed outright at the first, easiest gate, while the only candidate with even
weak positive evidence holds for ~4 days, and the monthly-hold candidates were the only ones that looked strong on
a naive read.** But "longer holding period" is not a free win either — see the monthly-hold finding just below,
which is the more important nuance.

**The monthly-hold finding, and why it's a genuine negative result, not a shortfall in effort:** `trend_sma200`
(10 ETFs, ~40-day average hold) and `monthly_sma10_timing_multi` (19 ETFs, ~175-day average hold) both cleared the
formal train/validation/test gate with large positive numbers (+2.6%/trade and +9.8%/trade net, respectively, in the
sealed test window). Both **failed the random-entry reality check**: `trend_sma200` landed at the 47th percentile of
2,000 random-entry simulations matched to the same holding periods and costs (pure chance), and
`monthly_sma10_timing_multi` at the 62nd (below the 80th-percentile floor for even "inconclusive" evidence). In plain
terms: being long an ETF for a random 40–175 day window during 1993–2026 usually made about as much money as this
specific timing rule did — the rule's positive return is mostly just the reward for being invested, not for correctly
predicting *when*. That said, the capital-constrained equity curve for `monthly_sma10_timing_multi` did show real,
structural drawdown reduction (test-window max drawdown 15.4% vs. SPY buy-and-hold's 38.2% over the same 2019–2026
window, for annualized return 11.4% vs. 15.2%) — a legitimate risk-reduction property distinct from "edge," and worth
remembering if capital preservation is ever weighted more heavily than the reality-check bar implies, but it is not
being classified as a demonstrated edge.

**The lead: `rsi2_mean_reversion`.** A 2-period RSI pullback (RSI(2) < 10) inside a long-term uptrend (price above its
200-day average) on the four core index ETFs (SPY, QQQ, IWM, DIA), held up to 10 days or until price reclaims its
5-day average. See the specific numbers requested below.

### Baselines every candidate had to beat
`research/baselines.py`: buy-and-hold, a 300-simulation random-entry null matched to the same holding-period
distribution and costs, a plain 200-day trend filter, and cash. No candidate beat all four convincingly; several
(the monthly-hold family) didn't beat random entry at all despite beating buy-and-hold's *drawdown*.

## 4. LIVE CAPITAL READINESS — 0/10

Zero strategies above `RESEARCHING`. `RiskConfig.approved_strategies` remains empty — unchanged and correctly so.
Credential rotation still pending. This is the honest, unforced result of the process above, not a conservative
default chosen to be safe: the evidence genuinely isn't there yet.

---

## Direct answers to your questions

**Best strategy found:** `rsi2_mean_reversion` (2-period RSI pullback within a long-term uptrend, index ETFs, ~4-day holds). It is a **lead worth continuing to research, not a validated edge.**

**How many independent trades/tests support it:** 893 total across train/validation/test; 236 in the sealed test window (2019-12-21 → 2026-09-11, one look, logged in `research/TEST_SET_LOG.md`) across 4 symbols (SPY, QQQ, IWM, DIA).

**Out-of-sample expectancy:** +0.402% net per trade in the test window (t = 2.82, 95% bootstrap CI [+0.122%, +0.674%], excludes zero) — but the harder random-entry check puts this at only the **85th percentile** of the null distribution (95th is the bar for "strong"), and the *validation* window separately showed only the **46th percentile** — inconsistent between windows, which is why this is "weak/inconclusive," not confirmed.

**Maximum drawdown:** 9.4% (capital-constrained: one account, capital split evenly across whatever positions are open), vs. 38.2% for simply buying and holding SPY over the identical test window. This is the strategy's best-looking property.

**Expected number of trades per week:** ≈0.67 new position entries per week across all four ETFs combined (236 trades over ≈351 weeks) — roughly 2–3 per month. Low turnover, consistent with the "smooth, minimal intervention" goal.

**Percentage of profitable weeks:** 23% of the 350 weeks in the test window were net profitable. This number is lower than it looks because most weeks have no trade open at all (average concurrent positions ≈2.1 of 4, and a flat week counts as "not profitable" here, not as a loss) — 54% of *months* were profitable, which is a fairer read of a low-frequency strategy's cadence, but by no measure is this yet a "usually wins" strategy.

**Is the evidence strong enough for shadow validation?** **No.** It fails this phase's own pre-registered bar (95th percentile, consistent across validation and test) for promotion to `SHADOW_CANDIDATE`. It remains `RESEARCHING`.

**What additional evidence would be required before risking real money:**
1. Resolve the validation/test inconsistency (46th vs. 85th percentile) — likely needs either a longer sample, a broader universe of similar ETFs to see if the effect generalizes, or accepting that the 2013–2019 validation window (a near-uninterrupted bull market with few sharp pullbacks) is simply not representative of what a mean-reversion strategy needs to prove itself on, and re-weighting how much a single validation window should count.
2. A completed `trader.agent --mode shadow` run (not simulated — using real, current market data) accumulating enough new, genuinely out-of-sample trades to move the percentile estimate, since every number above comes from historical replay.
3. Reaching the 95th-percentile bar in that shadow run, consistently, before this strategy could even be proposed for `RiskConfig.approved_strategies` — and even then, only inside `WEEK_1_VALIDATION_MODE`'s existing size limits, with a full live-Week-1 review afterward.
4. Independent of (1)–(3): credential rotation, since nothing can trade at all — shadow or live — until that's done.

## What changed in the repository this phase
`research/stats.py` (chronological-sort fix + consistency/period metrics), `research/portfolio.py` (new, capital-constrained equity curve), `research/baselines.py` (new), `research/candidates.py` (+3 strategies), `research/run_candidates.py` (baseline/consistency/portfolio integration, `portfolio`-kind support), `research/reality_check.py` (auto-detects targets instead of a hand-written list), `research/registry.py` + `research/STRATEGY_REGISTRY.md` (new), `research/test_set_addendum.py` (one narrowly-scoped, fully-audited display-only recomputation of already-sealed results — see that file's docstring for exactly why it does not constitute a second look at the test set), expanded `research/data.py` universe, 15 new tests. All committed to `hardening/week1-validation`.
