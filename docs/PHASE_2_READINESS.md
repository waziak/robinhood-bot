# Phase 2 Readiness Report

Date: 2026-09-13 · Branch: `hardening/week1-validation` (local; not pushed to `origin/main`) · No live order was placed at any point.

## Scores

| Area | Score | Basis |
|---|---|---|
| Credential Security | 6/10 | Immediate exposure contained (caches, secret, local plaintext file all deleted; workflow disabled at GitHub); Keychain-only storage implemented and tested. **Not higher**: the exposed refresh token has not actually been invalidated yet — that requires the owner to change the Robinhood password (§ owner actions). |
| Account Isolation | 9/10 | `AccountGuard` verifies account number/type/active status before every live call; crypto explicitly `UNSUPPORTED_FOR_LIVE_AUTOMATION`; order responses checked against the verified account. 16 tests. Not 10: never exercised against the real Robinhood API, only a faithful fake built from `inspect.signature` on the real library. |
| Execution Safety | 8/10 | Monotonic order state machine; timeouts produce UNKNOWN, never FILLED; UNKNOWN orders are located, never resubmitted; stale/regressed broker reports are ignored; positions change only on confirmed fills. 24 tests cover the required timeout/partial/reject/crash/duplicate/stale matrix. Not higher: same real-API caveat as above. |
| Restart Recovery | 8/10 | Full reconciliation (orders + positions) before any scan; explicit handling of all four required discrepancy categories; broker truth wins; uncertainty always resolves to `STOP_NEW_TRADES`, never to guessing. 9 tests. |
| Risk Controls | 9/10 | Entry permission and position management are separate code paths — exits, monitoring and reconciliation run unconditionally; verified by 5 parametrized tests including "account down" and "emergency halt". `approved_strategies` now gates every proposal and defaults to empty. |
| Strategy Evidence | 9/10 (rigor) / **0/10 (result)** | A real research pipeline now exists (train/validation/sealed-test splits, walk-forward, bootstrap CI, cost stress, random-entry null, score calibration) and was run to completion. The result is unambiguous: no strategy has credible edge (see below) — that is a finding, not a gap in the process. |
| Paper Simulation Quality | 8/10 | `PaperBroker` fills at bid/ask + slippage + fees, not midpoint; every closed position now records both a realistic (fill-based) and idealized (reference-price) P&L; the legacy bot's paper history was re-audited with a realistic-cost estimate. |
| Testing | 8/10 | 132 tests, all passing; `pyflakes` clean across `trader/`, `research/`, `tests/`, `scripts/`; `compileall` clean. Not higher: `mypy --strict`-style run surfaces ~50 missing-annotation/Optional-default warnings (style, not correctness — reviewed individually, none indicate a real bug) that weren't cleaned up given the time budget. |
| Observability | 8/10 | Structured, redacted JSON events; expanded status CLI now reports mode, account last4, auth status, broker connection, halt state, entry status, positions, orders, cash/equity, daily P&L and loss budget, last reconciliation/market-data/signal/rejection/execution/error — all without ever printing a secret. |
| Live Readiness | 2/10 | Zero approved strategies; credential rotation pending; live broker code never run against the real API; crypto permanently blocked for live. |

**OVERALL: 75/100** (up from 59/100 in the prior report)

## Classification: **SHADOW VALIDATION READY**

Not **SUPERVISED BROKER TEST READY**: `trader/broker_test.py` exists, is fully unit-tested against a faithful fake of the Robinhood API, and enforces every required safeguard (account 4508 verification, $1 cap, crypto refusal, emergency-halt check, credential check, market-hours check, typed confirmation, a hard one-order budget) — but it has never been run against the real API, and it cannot authenticate at all until the owner completes credential rotation. Both are prerequisites, not code gaps.

Not **LIMITED LIVE VALIDATION READY**: that requires credible positive out-of-sample evidence after realistic costs. There is none — see below.

## Strategy evidence — explicit, unambiguous

**All three production strategies (`trend_pullback`, `breakout`, `mean_reversion`) have negative expectancy after realistic costs, in every asset class tested, over the widest history available (BTC/ETH: 180 days of 5-minute bars; 16 ETFs/stocks: 60 days, the Yahoo Finance limit).** Full attribution in `research/CURRENT_STRATEGY_POSTMORTEM.md`. `RiskConfig.approved_strategies` is now empty by default — none of these three may open a position, in any mode.

Eight additional, pre-registered candidate strategies (`research/candidates.py`, hypothesis stated before any result) were evaluated on chronological 60/20/20 train/validation/test splits with a fixed pre-registered validation gate:

- **6 of 8 were rejected at validation**, before ever touching the sealed test set (`research/CANDIDATE_STRATEGY_RESULTS.md`).
- **2 of 8** (`trend_sma200`, `rsi2_mean_reversion`) passed validation and were evaluated once on the sealed test window (logged in `research/TEST_SET_LOG.md`, append-only, can't be re-run silently): both showed positive net returns.
- **Both failed a stricter reality check** (`research/reality_check.py`) run against a random-entry null with the same holding periods, symbols and costs:
  - `trend_sma200`: test-window return is statistically indistinguishable from a random long entry held the same number of days (47th percentile) — it earns the market's drift while invested, not a timing edge. It also holds positions ~40 days on average, which does not fit this account's model at all (Robinhood cash-account settlement, and a bot architecture built around 5.5-hour sessions).
  - `rsi2_mean_reversion`: 80–95th percentile vs. the null — weak, **not conclusive**, evidence of a real timing edge, on top of an already-thin per-trade return (+0.40% net, ~4-day holds) that would need to survive a full mean-reversion literature's known regime sensitivity before being trusted with real money.

**Conclusion: no strategy evaluated in this phase has credible, statistically robust, cost-realistic out-of-sample edge.** The honest result of Phase 2 research is "we don't have one yet," not "we found one." Do not read the two VALIDATION-passing candidates as tradeable — they are logged for the record and rejected by the reality check.

## What changed since the 59/100 report

- **Credential incident**: full scope investigation (`docs/CREDENTIAL_INCIDENT.md`) — no secret found in git history or artifacts; 29 session caches, the seed secret, and the local plaintext session file were deleted; the workflow was disabled at GitHub; `RH_USERNAME`/`RH_PASSWORD`/`PAPER_MODE` secrets (no longer used by anything) were deleted. `trader/credentials.py` replaces plaintext-pickle auth with macOS Keychain storage, output redaction during login, and a hard refusal to resume if any legacy plaintext session file exists.
- **Account isolation**: new `trader/accounts.py` (`AccountGuard`) is now the only path to a live account number; wired into `RobinhoodBroker`, which builds its own order payload (rather than trusting `robin_stocks.order()`'s separate, fallible account lookup) and verifies the response really booked to account ••••4508.
- **Execution safety**: `trader/execution.py` and `trader/models.py` rewritten with an explicit `OrderState` machine (`CREATED→SUBMITTING→SUBMITTED→ACKNOWLEDGED/PARTIALLY_FILLED→FILLED/CANCELLED/REJECTED/UNKNOWN`), broker-report staleness/regression checks, and a `resolve_unknown` path that locates rather than guesses. New `test_execution.py`/`test_live_broker.py` cover the full required matrix (timeout before/after receipt, partial, rejected, crash before/after send, duplicate exit, stale report).
- **Entry/exit separation**: `RiskEngine.entries_allowed()` vs. `exits_allowed()`; `Agent.monitor_positions()`/`reconcile()` run every cycle unconditionally; the old 30-minute `time.sleep` freeze is gone.
- **Restart recovery**: `Agent.reconcile()` now explicitly classifies `LOCAL_POSITION_NO_BROKER_POSITION`, `BROKER_POSITION_NO_LOCAL_POSITION`, `QUANTITY_MISMATCH` and `UNEXPECTED_OPEN_ORDER`, always resolving uncertainty to `STOP_NEW_TRADES` and logging it.
- **Strategy gate**: `RiskConfig.approved_strategies` (empty by default) — a strategy must earn its way onto this list with evidence; the risk engine enforces it directly.
- **Research harness**: `research/` (data, costs, backtest, stats, splits, candidates, current, run_postmortem, run_candidates, reality_check, paper_audit) — a full pipeline no-lookahead-tested against the production strategy code itself.
- **Paper simulation honesty**: idealized vs. realistic P&L tracked per position; legacy paper history re-audited excluding the 117 sessions contaminated by the now-fixed valuation bug (commit `465fef3`), with a separate realistic-cost estimate for the remaining 23 clean sessions.
- **Supervised broker test**: `trader/broker_test.py` + `test_broker_test.py` (11 tests) — the required infrastructure exists and is thoroughly tested against a fake; it is a code artifact, not yet a completed real-world test.
- **Status CLI**: expanded to every field requested, still zero secrets.

## What still blocks each next level

**To reach SUPERVISED BROKER TEST READY (infrastructure, not profitability):**
1. Owner completes credential rotation: change Robinhood password (invalidates the exposed refresh token), then `venv/bin/python -m trader.credentials setup` and `... login` — **this last step will send a device-approval push to your phone; approve it there.**
2. One supervised run of `python -m trader.broker_test --symbol SPY --side buy --dollars 1.00` during market hours, reviewed manually, to confirm the real API matches the fake's contract (payload shape, `ref_id` behavior, fill reporting).
3. Push this branch's fixes to `main` (or an equivalent private location) — deliberately **not done automatically**: it's a visible action on the repository the incident occurred in, and pushing is being left for your explicit decision. Recommendation: move future broker-connected work to a **private** repository regardless.

**To reach LIMITED LIVE VALIDATION READY:**
4. Find and validate an actual strategy — none exists yet. That means new hypotheses (this phase's 8 candidates were a start, not an exhaustive search), a longer/cleaner intraday equity history than Yahoo's 60-day window (or accepting daily-bar strategies and re-architecting execution around multi-day holds instead of 5.5-hour sessions), and passing both the pre-registered validation gate and the random-entry reality check — not just one of them.
5. Weeks of clean shadow/paper validation on whatever strategy eventually clears that bar, with realistic costs, before any live capital.

Nothing here should be read as "close to live." The system is materially safer and far more honest about itself than it was; it still has no strategy to trade.
