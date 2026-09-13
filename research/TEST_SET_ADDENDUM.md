# Test-Set Addendum (post-hoc, bug-fix-only recomputation of already-sealed results)

Generated 2026-09-13 20:02 UTC. See module docstring: this recomputes DISPLAY statistics only (drawdown, consistency, capital-constrained view) for test windows already sealed in TEST_SET_LOG.md before those metrics existed or were fixed. No decision is re-made.

## trend_sma200

Test window: 2019-12-21 → 2026-09-11, n=221
- Mean net %/trade: +2.630 (matches the sealed record — unchanged)
- Max drawdown (per-trade, one-unit-per-signal convention): 79.6%
- Downside deviation: 1.878%, Sortino-like: nan, longest losing streak: 19 trades

**Capital-constrained portfolio view (test window):**
- Total return: +103.1% · Annualized: +11.1% · Max drawdown: 28.9% · Sharpe-like: 0.72
- Concurrent positions: median 6, average 5.7, max 9
- 58% of 350 weeks profitable (worst week -16.45%), 62% of months profitable

## rsi2_mean_reversion

Test window: 2019-12-21 → 2026-09-11, n=236
- Mean net %/trade: +0.402 (matches the sealed record — unchanged)
- Max drawdown (per-trade, one-unit-per-signal convention): 40.0%
- Downside deviation: 1.749%, Sortino-like: nan, longest losing streak: 4 trades

**Capital-constrained portfolio view (test window):**
- Total return: +66.4% · Annualized: +7.9% · Max drawdown: 9.4% · Sharpe-like: 0.89
- Concurrent positions: median 2, average 2.1, max 4
- 23% of 350 weeks profitable (worst week -8.40%), 54% of months profitable

## monthly_sma10_timing_multi

Test window: 2019-12-21 → 2026-09-11, n=124
- Mean net %/trade: +9.835 (matches the sealed record — unchanged)
- Max drawdown (per-trade, one-unit-per-signal convention): 128.1%
- Downside deviation: 4.419%, Sortino-like: nan, longest losing streak: 17 trades

**Capital-constrained portfolio view (test window):**
- Total return: +106.6% · Annualized: +11.4% · Max drawdown: 15.4% · Sharpe-like: 0.89
- Concurrent positions: median 16, average 13.5, max 19
- 55% of 350 weeks profitable (worst week -8.22%), 62% of months profitable

