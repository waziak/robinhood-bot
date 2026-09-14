# Test-Set Addendum (post-hoc, bug-fix-only recomputation of already-sealed results)

Generated 2026-09-14 00:24 UTC. See module docstring: this recomputes DISPLAY statistics only (drawdown, consistency, capital-constrained view) for test windows already sealed in TEST_SET_LOG.md before those metrics existed or were fixed. No decision is re-made.

## trend_sma200

Test window: 2019-12-21 → 2026-09-11, n=221
- Mean net %/trade: +2.630 (matches the sealed record — unchanged)
- Max drawdown (per-trade, one-unit-per-signal convention): 79.6%
- Downside deviation: 1.878%, Sortino-like: nan, longest losing streak: 19 trades

**Capital-constrained portfolio view (test window):**
- Total return: +103.1% · Annualized: +11.1% · Max drawdown: 28.9% (duration 658d)
- Sharpe-like: 0.72 · Sortino-like: 0.95 · Annualized volatility: 16.8% · Annualized downside deviation: 12.6%
- Concurrent positions: median 6, average 5.7, max 9
- 58% of 350 weeks profitable (worst week -16.45%), 62% of months profitable

## rsi2_mean_reversion

Test window: 2019-12-21 → 2026-09-11, n=236
- Mean net %/trade: +0.402 (matches the sealed record — unchanged)
- Max drawdown (per-trade, one-unit-per-signal convention): 40.0%
- Downside deviation: 1.749%, Sortino-like: nan, longest losing streak: 4 trades

**Capital-constrained portfolio view (test window):**
- Total return: +66.4% · Annualized: +7.9% · Max drawdown: 9.4% (duration 401d)
- Sharpe-like: 0.89 · Sortino-like: 1.32 · Annualized volatility: 9.0% · Annualized downside deviation: 6.1%
- Concurrent positions: median 2, average 2.1, max 4
- 23% of 350 weeks profitable (worst week -8.40%), 54% of months profitable

## monthly_sma10_timing_multi

Test window: 2019-12-21 → 2026-09-11, n=124
- Mean net %/trade: +9.835 (matches the sealed record — unchanged)
- Max drawdown (per-trade, one-unit-per-signal convention): 128.1%
- Downside deviation: 4.419%, Sortino-like: nan, longest losing streak: 17 trades

**Capital-constrained portfolio view (test window):**
- Total return: +106.6% · Annualized: +11.4% · Max drawdown: 15.4% (duration 681d)
- Sharpe-like: 0.89 · Sortino-like: 1.25 · Annualized volatility: 13.1% · Annualized downside deviation: 9.4%
- Concurrent positions: median 16, average 13.5, max 19
- 55% of 350 weeks profitable (worst week -8.22%), 62% of months profitable

## pullback_from_high

Test window: 2019-12-21 → 2026-09-11, n=113
- Mean net %/trade: +0.152 (matches the sealed record — unchanged)
- Max drawdown (per-trade, one-unit-per-signal convention): 28.0%
- Downside deviation: 1.860%, Sortino-like: nan, longest losing streak: 5 trades

**Capital-constrained portfolio view (test window):**
- Total return: +19.2% · Annualized: +2.6% · Max drawdown: 19.7% (duration 1723d)
- Sharpe-like: 0.33 · Sortino-like: 0.44 · Annualized volatility: 9.4% · Annualized downside deviation: 7.0%
- Concurrent positions: median 1, average 1.5, max 4
- 14% of 350 weeks profitable (worst week -15.86%), 33% of months profitable

## weekly_rsi2

Test window: 2019-12-21 → 2026-09-11, n=41
- Mean net %/trade: +2.242 (matches the sealed record — unchanged)
- Max drawdown (per-trade, one-unit-per-signal convention): 18.0%
- Downside deviation: 3.067%, Sortino-like: nan, longest losing streak: 7 trades

**Capital-constrained portfolio view (test window):**
- Total return: +18.7% · Annualized: +2.6% · Max drawdown: 18.6% (duration 908d)
- Sharpe-like: 0.28 · Sortino-like: 0.38 · Annualized volatility: 11.8% · Annualized downside deviation: 8.7%
- Concurrent positions: median 1, average 1.5, max 4
- 12% of 350 weeks profitable (worst week -11.25%), 21% of months profitable

## combined_trend_vol_rsi2

Test window: 2019-12-21 → 2026-09-11, n=186
- Mean net %/trade: +0.519 (matches the sealed record — unchanged)
- Max drawdown (per-trade, one-unit-per-signal convention): 15.9%
- Downside deviation: 1.172%, Sortino-like: nan, longest losing streak: 4 trades

**Capital-constrained portfolio view (test window):**
- Total return: +54.7% · Annualized: +6.7% · Max drawdown: 9.4% (duration 457d)
- Sharpe-like: 0.87 · Sortino-like: 1.32 · Annualized volatility: 7.8% · Annualized downside deviation: 5.2%
- Concurrent positions: median 2, average 1.9, max 4
- 21% of 350 weeks profitable (worst week -3.96%), 48% of months profitable

## low_volatility_rotation

Test window: 2019-12-21 → 2026-09-11, n=175
- Mean net %/trade: +1.604 (matches the sealed record — unchanged)
- Max drawdown (per-trade, one-unit-per-signal convention): 98.5%
- Downside deviation: 3.837%, Sortino-like: nan, longest losing streak: 9 trades

**Capital-constrained portfolio view (test window):**
- Total return: +73.5% · Annualized: +8.6% · Max drawdown: 26.4% (duration 455d)
- Sharpe-like: 0.68 · Sortino-like: 0.96 · Annualized volatility: 13.3% · Annualized downside deviation: 9.5%
- Concurrent positions: median 5, average 5.0, max 5
- 57% of 350 weeks profitable (worst week -11.09%), 62% of months profitable

