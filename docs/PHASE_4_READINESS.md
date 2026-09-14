# Phase 4 Readiness Report — Can We Find a Genuinely Repeatable Edge?

Date: 2026-09-14 · Branch: `hardening/week1-validation` (all Phase 3 work pushed to `origin`; Phase 4 commits below, not yet pushed) · No live order was placed, no credential rotated, no strategy approved.

## Direct conclusion: **(C) No credible edge discovered — with one candidate close enough to keep watching, not close enough to act on.**

Nineteen hypotheses have now been tested across Phases 3–4 (the pre-registered validation/test gate, a random-entry
reality check, and — new this phase — a Bonferroni multiple-testing correction that raises the bar every hypothesis
must clear as more are tried). **Zero clear the corrected bar.** One (`weekly_rsi2`) clears the *uncorrected*
single-test 95th-percentile bar in every split — the first and only candidate in this entire program to do so — but
fails the bar that actually applies given how many hypotheses have been searched, and its economic magnitude (once
properly capital-constrained for a small account) is weak enough that even an uncorrected pass would not justify
acting on it yet. This is not a forced or hedged answer: nothing here is being read generously.

## Four readiness scores, kept separate

| Dimension | Score | Basis |
|---|---|---|
| ENGINEERING READINESS | 8/10 | Unchanged from Phase 3 in substance. Two new real bugs were found and fixed this phase (see below) — the process of catching them is itself evidence the engineering is being held to a real bar, not just "nothing broke." |
| BROKER READINESS | 6/10 | Unchanged — no broker-facing work this phase. Credential rotation still pending (your action). |
| STRATEGY READINESS | 1/10 | Lower than Phase 3's 2/10. More searching happened, more rigor was applied, and the result is *more* certain there's no edge yet, not less — that's what a lower number should mean here. |
| LIVE CAPITAL READINESS | 0/10 | Unchanged. `RiskConfig.approved_strategies` remains empty. |

## What was done this phase

**RSI2 diagnostic attribution** (`research/rsi2_diagnostics.py`, `research/RSI2_DIAGNOSTICS.md`) — read-only, no
parameters touched. Broke down the already-sealed `rsi2_mean_reversion` trades by instrument, trend regime,
volatility regime, entry severity (RSI value), holding period, and exit reason. Two honest findings:
- The validation-vs-test volatility-regime *mix* is nearly identical (43/32/24% vs. 47/30/22% low/mid/high) — my own
  hypothesis that "a quieter validation window explains the weaker result" does **not** hold up quantitatively.
- **Holding period** is the one clean, cross-split-consistent pattern: trades resolved within 1–4 days were
  strongly profitable in train, validation, *and* test alike; trades still open at 7–10 days were a net loss in
  all three splits independently. That's a legitimate basis for a new, separately-tested hypothesis (below) —
  not for retroactively shortening `rsi2_mean_reversion`'s own already-sealed exit rule.

**Five new pre-registered candidates**, each with a stated hypothesis fixed before evaluation:
- `rsi2_early_exit` — same entry, but a hard 4-day time-stop instead of the existing 10-day/5-day-SMA-reclaim exit,
  testing the holding-period finding above. **Rejected at validation** (validation mean net −0.03%) — the pattern
  seen in train did not generalize. This is a real, useful negative result: it disconfirms a hypothesis that looked
  promising from a single split, exactly what the pre-registration discipline is for.
- `pullback_from_high` — the same broad "oversold pullback in an uptrend" idea via a plain %-off-high measure
  instead of RSI, to check whether the effect is RSI-specific. Passed validation, but reality check: 47th
  percentile — market drift, not skill.
- `weekly_rsi2` — the same idea sampled weekly instead of daily. See below — the one interesting result.
- `combined_trend_vol_rsi2` — RSI2 entries filtered to exclude the "high" volatility tercile (motivated by the
  diagnostic finding that bucket was flat-to-negative in 2 of 3 rsi2_mean_reversion splits). 95th percentile in
  test, but only 46th in validation — inconsistent, stays `RESEARCHING`.
- `low_volatility_rotation` — the well-documented low-volatility anomaly (Ang/Hodges/Xing/Zhang 2006), monthly
  rotation into the lowest-realized-volatility instruments across the 18-ETF universe. Passed validation; reality
  check: 34th percentile — drift, not skill.

**Two real bugs found and fixed** (the kind of thing this rigor exists to catch):
1. `low_volatility_rotation` crashed on shorter-history ETFs (EEM/VNQ/GLD launched years after the calendar start)
   — a symbol with insufficient trailing data could still be "selected" as lowest-volatility, producing an
   undefined price. Fixed to only rank symbols with enough real history; regression test added.
2. **`weekly_rsi2`'s `bars_held` field was recorded in weeks, but the random-entry null (`research/reality_check.py`)
   interprets `bars_held` as a daily-bar offset.** This made the null draw ~4-*day* random holds against the
   strategy's real ~4-*week* holds — a unit mismatch that artificially shrank the null's return and inflated the
   strategy's apparent percentile to a false 100% in every split. Fixed to record actual trading-day counts;
   regression test added. **The corrected number (97th percentile in test, still notable) is what's reported below
   — the number is real, but it is honestly about 3 percentage points less impressive than the bug initially made
   it look, and that gap between the buggy and corrected result is exactly why this kind of unit-consistency check
   matters.**

**Multiple-testing accounting** (`research/multiple_testing.py`, `research/MULTIPLE_TESTING.md`) — new this phase,
tracks all 19 hypotheses tested to date (16 pre-registered candidates + 3 legacy production strategies) and computes
the Bonferroni-adjusted significance bar: **99.74th percentile**, not the nominal 95th. `research/registry.py`'s
automatic promotion rule now checks candidates against this adjusted bar, not the nominal one — this is why
`weekly_rsi2` is `RESEARCHING`, not `SHADOW_CANDIDATE`, despite clearing 95% in every split.

## The one interesting result: `weekly_rsi2` — reported in full, not oversold

**Hypothesis:** the same RSI(2)-pullback-in-an-uptrend idea, sampled at weekly resolution — a lower-turnover
variant and a check for whether the effect is a daily-bar artifact.

| Metric | Value |
|---|---|
| Net expectancy per trade (test) | +2.24% (train +1.84%, validation +3.35%) |
| Independent trades | 41 in test (79 train, 49 validation) across 4 symbols — but see caveat below |
| Statistical evidence (t-stat, test) | 2.69 |
| Random-entry percentile | **Test 97th, validation 100th, train 99th** — clears the nominal 95% bar in all three splits |
| Multiple-testing-adjusted requirement | 99.74th (19 hypotheses tested) — **not cleared in test or train** |
| Profit factor | not separately computed at the trade level for this table; win rate 63–77% by symbol in test |
| Max drawdown (capital-constrained) | 18.6% |
| Worst drawdown duration | **908 calendar days (~2.5 years)** to fully recover |
| Average holding period | ~14 trading days (~3 calendar weeks) |
| Trades/month | ≈0.5 across all 4 symbols combined |
| Profitable months | 21% of 350 test-window months — most months have no position open at all |
| Worst month | not separately isolated; worst week in test was −11.25% |
| Performance by year (test) | positive 2020/2021/2023/2024/2025, **negative 2026** (n=10, −0.73% mean, 20% win rate — the most recent stretch) |
| Performance by instrument | consistent across SPY/QQQ/IWM/DIA (win rate 60–77%, all net positive) — not one symbol carrying the result |
| Sensitivity to costs | mild: mean net falls from +2.24% to +2.04% at 5× assumed costs — cost-robust, because holds are long relative to the spread |
| Dependence on a few trades | **Yes, materially**: 2021 and 2024 alone contribute ~75% of the test window's cumulative return (24 of 41 trades sit in the other five partial years, contributing the remaining ~25%) |

**Comparison to simply holding SPY, same test window (2019-12-21 → 2026-09-11), same methodology:**

| | weekly_rsi2 (capital-constrained) | Buy-and-hold SPY |
|---|---|---|
| Total return | +18.7% | **+158.8%** |
| Annualized return | +2.6% | **+15.2%** |
| Max drawdown | **18.6%** | 33.7% |
| Max drawdown duration | 908 days | 709 days |
| Annualized volatility | **11.8%** | 20.1% |
| Annualized downside deviation | **8.7%** | 14.2% |
| Sharpe-like | 0.28 | **0.81** |
| Sortino-like | 0.38 | **1.15** |
| % profitable months | 21% | **64%** |
| Capital utilization (time invested) | ~9% of days | 100% |

**This is exactly the distinction you flagged with the SMA strategies, applied to a different failure mode: lower
volatility and lower drawdown here are not evidence of skill — they are close to a mechanical consequence of being
invested only ~9% of the time.** The per-trade statistics are the most interesting in this whole program (real,
after the unit-mismatch fix, and consistent in direction across all three splits), but the resulting *portfolio*
is a worse risk-adjusted outcome than simply holding SPY on every measure except raw drawdown percentage. A
strategy can have a statistically genuine, non-drift per-trade effect and still not be worth deploying if it's
rarely invested and the effect is economically small — that is the situation here, not a contradiction.

**Verdict on this specific candidate: promising enough to keep in `RESEARCHING`, not strong enough for
`SHADOW_CANDIDATE`.** It fails the bar that actually applies (99.74th, not 95th), its "independent" trades are
substantially correlated (4 highly correlated US equity index ETFs moving through the same macro cycle — 41 nominal
trades are not 41 independent bets), three-quarters of its cumulative return sits in two of seven years, and the
most recent year is negative. None of that means it's wrong — it means it is not yet evidence, at the standard this
program has set for itself.

## Answering the core Phase 4 question directly

**"Can we find a genuinely repeatable, statistically defensible trading edge that is practical for a small cash
account?"** Not yet. Of 19 hypotheses spanning intraday, multi-hour, daily, weekly, and monthly holding periods —
liquid ETFs only, realistic costs, no leverage, no shorting — none survive the combination of (a) the pre-registered
validation/test gate, (b) a random-entry reality check, and (c) a multiple-testing correction sized to how much
searching has actually happened. Longer holding periods continue to look more promising than short ones (every
intraday/hourly candidate failed outright; the closest calls are all daily-to-weekly), but "more promising" has not
yet produced a result that clears its own bar.

## What would change this conclusion
1. `weekly_rsi2` (or a similarly-shaped idea) clearing the 99.74th-percentile bar in a **genuinely new** out-of-sample
   window — meaning real calendar time passing and a real shadow-mode run, not another historical replay of the
   same 1993–2026 data, which has now been searched enough that further replay-based "discoveries" are exactly what
   the multiple-testing correction warns about.
2. Broadening the 4-symbol test beyond highly-correlated US index ETFs (e.g., adding genuinely distinct assets) to
   address the "not 41 independent bets" caveat, without re-testing on the already-used window.
3. Continued monitoring specifically of whether 2026's negative stretch is noise or a regime change — that answer
   can only come from more time passing, not more backtesting.

## Repository changes this phase
`research/rsi2_diagnostics.py` (new), `research/regime.py` (new — trend/volatility regime classifiers, no-lookahead
tested), `research/multiple_testing.py` (new), `research/candidates.py` (+5 strategies, +1 bug fix), `research/portfolio.py`
(+drawdown duration, +annualized volatility/downside deviation/Sortino), `research/registry.py` (promotion now gated
on the Bonferroni-adjusted bar, not the nominal one), `research/test_set_addendum.py` (extended fields), 24 new tests
(159 total, all passing), `pyflakes` clean. Also fixed two flaky trader/ tests that depended on real wall-clock time
crossing a UTC-midnight edge case (unrelated to research work, noticed in passing).
