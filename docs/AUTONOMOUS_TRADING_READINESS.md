# Autonomous Trading Readiness Report

Date: 2026-09-13 · Branch: `hardening/week1-validation` (local, not pushed, not deployed) · Companion: `docs/TRADING_SYSTEM_AUDIT.md`

No live order was placed at any point. The production paper bot on `main` (legacy `bot.py`) was left running unchanged.

## Verdict

| Area | Score |
|---|---|
| Architecture | 7/10 |
| Execution safety | 7/10 |
| Risk management | 8/10 |
| Strategy quality | 2/10 |
| Testing | 7/10 |
| Security | 4/10 |
| Observability | 7/10 |
| Autonomous reliability | 5/10 |

**OVERALL SCORE: 59/100** (47/80 normalised)

**PAPER TRADING READY** — for the new `trader/` stack in shadow/paper mode.
**NOT SAFE FOR LIVE TRADING** — the strategies show no evidence of positive expectancy after costs, the Robinhood session token is exposed via a public repo's Actions cache, and the live broker adapter has never been exercised against real Robinhood responses.

---

## What was built

`trader/` — a layered system replacing the monolithic `bot.py` (which is untouched and still what CI runs):

| Module | Role | Key guarantees |
|---|---|---|
| `risk_config.py` | Single `RiskConfig`; `WEEK_1_VALIDATION_MODE` preset | Week-1 values are a ceiling: overrides that loosen them raise; unknown keys raise; leverage/margin/options/short/averaging-down forbidden; live requires `live_trading_enabled` **and** `LIVE_TRADING_ACK=I_ACCEPT_REAL_MONEY_RISK` |
| `market_data.py` | Quotes with bid/ask/timestamp, candles | Never defaults a price; malformed, halted, crossed or stale data raises; every API call has a thread-safe timeout |
| `strategies.py` | `trend_pullback`, `breakout`, `mean_reversion` → `Proposal` | Long-only, explicit entry/stop/target/invalidation/reasoning; no broker import |
| `scoring.py` | 0–100 score | Missing evidence scores 0, never default credit |
| `risk_engine.py` | Absolute veto + sizing | Sizing from stop distance and costs, capped by $ / % / cash / total exposure; `STOP_NEW_TRADES` (auto, daily) and `EMERGENCY_HALT` (persistent, manual clear only) |
| `execution.py` | Order state machine | Intent persisted before submit; submit once; timeout → locate at broker, never resubmit; unverifiable → `EMERGENCY_HALT`; partial fills cancel remainder; positions change only on confirmed fills; failed exits keep the position and halt after 3 attempts |
| `broker.py` | `PaperBroker`, `RobinhoodBroker` | Paper fills pay ask/receive bid + slippage + fees. Live: equities only, limit orders only, pinned to the configured cash account (verified per call); **crypto refused** (robin_stocks cannot pin crypto orders to an account) |
| `store.py` | SQLite | Candidates incl. rejections + hypothetical outcomes, orders, positions (MFE/MAE), events, equity, flags, heartbeat instance lock |
| `agent.py` | Loop + fail-safe startup | Env validate → lock → account → reconcile orders/positions vs broker → halt check → data freshness → enable. `NO_TRADE` logged every cycle |
| `events.py` | Structured JSON events | `MARKET_DATA, SIGNAL, RISK_DECISION, ORDER_SUBMITTED, ORDER_UPDATE, POSITION_UPDATE, TRADE_EXIT, SYSTEM_ERROR, KILL_SWITCH`; tokens, auth headers, account numbers redacted |
| `reporting.py` | Daily report, Week-1 review (A/B/C/D) | Never modifies risk settings |
| `status.py` | CLI dashboard + manual halt/clear | Clearing a halt requires a written review note |

Week-1 limits (for a ~$27 cash account): $0.30 max loss/trade · $1.00 max daily loss · 10 % max drawdown (→ emergency halt) · $6 / 20 % max position · 40 % total exposure · 2 open positions · 4 trades/day · score ≥ 70 · reward/risk ≥ 1.8 · spread ≤ 0.40 % · quote ≤ 20 s old · 30-min cooldown after a loss · halt after 3 consecutive losses · universe BTC, ETH, SPY, QQQ, AAPL, NVDA, MSFT (no leveraged ETFs).
At these limits a $5/day gain is not reachable and is not a target — that is intentional.

## Validation evidence

**Tests** — `python -m pytest tests -q`: **54 passed**. Covers position sizing, max-loss and daily-loss enforcement, unrealized loss counting, consecutive-loss/cooldown, stale quotes/candles, wide spreads, abnormal volatility, insufficient cash, duplicate orders, timeout-but-filled (located, not resubmitted), timeout-unverifiable (halt, no retry), partial fills, rejected-after-ack, unconfirmed cancel, rejected exits, restart recovery of pending entries and in-flight exits, broker/local position mismatch, untracked broker orders, duplicate instance, malformed/invalid/halted quotes, live-broker crypto refusal, redaction, reports, config loosening. `pyflakes`: clean.

**Replay on real data** — `scripts/shadow_replay.py` drives the real agent loop on a simulated clock over public 5-min candles
(Coinbase BTC/ETH 2026-09-05 → 09-13, 2,250 bars; Robinhood SPY/QQQ/AAPL/NVDA/MSFT 09-08 → 09-11, 852 bars), paper fills with assumed spread (crypto 0.10 % and 0.25 %, stocks 0.05 %) and 0.10 % slippage per side. Robinhood's authenticated session was deliberately **not** used, so the running bot's token could not be disturbed.

| Run | Proposals | Approved | Trades | Kill switches | Errors | Invariants |
|---|---|---|---|---|---|---|
| Crypto, week-1, 0.25 % spread | 162 | 0 | 0 | 0 | 0 | all pass |
| Crypto, week-1, 0.10 % spread | 162 | 0 | 0 | 0 | 0 | all pass |
| Stocks, week-1 | 25 | 0 | 0 | 0 | 0 | all pass |
| Crypto, DIAGNOSTIC score ≥ 50 | 162 | 1 | 1 (stop, −$0.10 vs $0.30 budget) | 0 | 0 | all pass; 2 orders filled, 0 unresolved, broker flat |
| Stocks, DIAGNOSTIC score ≥ 50 | 25 | 0 | 0 (19 blocked: costs vs stop distance) | 0 | 0 | all pass |

Diagnostic runs exist only to exercise the execution path; they are not a configuration proposal.

**Forward outcome of every proposal** (first-touch stop/target within 4 h, stop assumed first, net of spread + slippage):

| Set | n | Win rate | Avg net return | Avg R |
|---|---|---|---|---|
| Crypto, score ≥ 70 | 25 | 32 % | −0.12 % | −0.32 |
| Crypto, all | 162 | 18–32 % by bucket | −0.12 % … −0.27 % | −0.32 … −0.57 |
| Stocks, all | 25 | 0–14 % by bucket | −0.19 % … −0.46 % | −0.47 … −1.00 |

Every strategy and every score bucket was negative. Samples are small and one week is one regime, so this is not proof the ideas are worthless — but there is **no evidence of edge**, and the week-1 gate correctly declined all of them. Strategy parameters were deliberately **not** tuned to this data (that would be fitting noise).

**Replay found and fixed one real bug**: startup chose `crypto_symbols[0]` as the freshness reference even when the universe had no crypto, raising `IndexError` → the (correct, fail-safe) handler blocked all new trades for the day. Fixed; regression test added.

**Workflow fixes on the branch (not deployed)**: checkout of `github.ref` at job start (fixes the verified lost paper-balance updates), credentials scoped to the run step only, and a pytest gate before any trading step.

## Blockers to the next level (LIMITED LIVE VALIDATION READY)

1. **Evidence of edge.** Run the new stack in shadow/paper for ≥ 3–4 weeks; require ≥ 50 closed shadow trades per strategy you intend to enable, with positive expectancy and profit factor ≥ 1.2 **after** realistic Robinhood spread. Current evidence: negative on 187 proposals. Without this, live trading is expected to lose money slowly.
2. **Security S1 (critical).** The Robinhood access + refresh token lives unencrypted in the Actions cache of a public repo. Encrypt it with a key held in Actions secrets (or move the bot to a private repo / private host), then re-bootstrap the session (`scripts/bootstrap_session.py`) so any previously cached token is superseded. Pin `requirements.txt` with hashes; move the balance-commit to a separate job so the credentialed job has read-only contents.
3. **Live broker contract check.** `RobinhoodBroker` is written against robin_stocks signatures (verified with `inspect`) but never run against real responses. Before any live order: verify with the account owner present that Robinhood accepts fractional **limit** orders from this cash account, and that `get_stock_order_info` / `load_account_profile(type)` return the fields the adapter expects. One supervised $1 order, then reconcile it via `trader.status`.
4. **Deploy the new stack to CI in shadow mode** with a persistent SQLite DB (encrypted artifact or cache) and retire `bot.py`; today CI still runs the legacy script and paper positions do not survive ephemeral runners.
5. **Alerting.** `KILL_SWITCH` / `SYSTEM_ERROR` events are only logged; Telegram secrets are not configured in CI. An emergency halt nobody sees is only half a safeguard.
6. **Market calendar & settlement.** No holiday calendar (stale-data checks catch holidays, but noisily). Cash-account settlement/good-faith-violation tracking relies on Robinhood's buying power figure.
7. **Crypto live path.** Refused by design until orders can be pinned to the authorised account (robin_stocks limitation), or the account layout changes.

## Blockers beyond that (AUTONOMOUS LIVE READY)
A completed live Week-1 with classification **A** in `reports/WEEK_1_REVIEW.md`, zero execution-integrity kill switches, and a multi-week sample — plus all items above. Position sizes stay at week-1 levels until then regardless of P&L.

## How to run

```bash
python -m pytest tests -q                                   # safety suite
python -m trader.agent --mode shadow --db data/trader.db    # observe + decide, no orders (needs RH session)
python -m trader.agent --mode paper  --db data/trader.db    # simulated fills against real quotes
python -m trader.status --db data/trader.db                 # dashboard
python -m trader.status --halt "reason"                     # manual EMERGENCY_HALT
python -m trader.status --clear-halt "reviewed: why safe"   # manual clear (only way to clear)
python -m trader.status --week1-review 2026-09-14           # writes reports/WEEK_1_REVIEW.md
python scripts/shadow_replay.py --data-dir <candles> --symbols BTC,ETH --spread 0.001
```

Running `trader.agent` locally uses the saved Robinhood session; doing so while CI also uses it may rotate the refresh token and force a new device approval — coordinate before running both.
