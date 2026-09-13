# Trading System Audit — robinhood-bot

Audit date: 2026-09-13 · Branch audited: `main` @ `b5d09f3` · Auditor: Claude (automated, read-only pass before any change)

Evidence sources: full read of every tracked source file, GitHub Actions run logs (runs `34530499788` → `34718391475`),
`gh` repo/secret/cache metadata, and a **read-only** query of the Robinhood account via the Robinhood MCP.
No order was placed at any point.

---

## 0. Executive summary

The bot is a single-process, single-strategy script (`bot.py`, 749 lines) running in PAPER mode on a GitHub Actions
cron. Authentication, data fetch and the paper loop genuinely work. **It is not safe for live trading**, and the reasons
are structural, not tuning:

1. **A failed or timed-out SELL is recorded as a completed exit.** The position is deleted from memory and P&L booked
   while the shares may still be held — an unmanaged live position with no stop. (§3, E3)
2. **Nothing is persisted.** Positions, orders, PDT count and risk counters live in memory on an ephemeral runner.
   A crash, a runner timeout or GitHub's 350-min kill leaves live positions orphaned; there is no startup reconciliation.
3. **Order success = "response had an `id`".** Order state (queued/rejected/cancelled/partially filled) is never checked;
   fills are assumed at the pre-order quote.
4. **Crypto orders cannot target the funded account.** `robin_stocks` crypto order functions take no `account_number`,
   so they execute against the default **margin** account ••••1441 — which is not the account authorised for the bot.
5. **The only risk gate sleeps the whole loop for 30 minutes** after 3 losses (`time.sleep(1800)`), freezing stop
   management of open positions.
6. **Live buying-power check fails open** when the API call fails, and live equity silently falls back to a hard-coded
   `$50` constant when the equity call fails.
7. **Paper results are optimistic**: fills at mid/mark price, no spread, no fees, no slippage — while Robinhood crypto
   orders carry spread and fees. Paper "profit" of ~+$1.37 over ~9 sessions is inside the cost that was not modelled.
8. **Security: a full-access Robinhood OAuth session (access + refresh token) sits in the Actions cache of a PUBLIC
   repo**, restorable by workflows running on pull requests. Credentials are also exposed to every step, including
   `pip install` of unpinned packages, in a job with `contents: write`.

Verdict: **NOT SAFE FOR LIVE TRADING** as-is. The paper loop can continue running unchanged while the rebuild happens.

---

## 1. Live account state (read-only, 2026-09-13)

| Account | Type | Bot-authorised | Value | Positions | Orders since 2026-08-01 |
|---|---|---|---|---|---|
| ••••4508 "Agentic" | cash, individual | **yes** | $26.86 cash, $26.86 buying power | none | none (equity + crypto) |
| ••••1441 (default) | **margin**, individual | no | not queried | — | — |
| ••••5059 | cash, Roth IRA | no | not queried | — | — |

Implications: the only account the bot may use is a **cash** account (no margin, no shorting, T+1 settlement rules for
stock sales → good-faith-violation risk on round trips funded by unsettled proceeds; PDT rules do not apply to cash accounts).

## 2. Current architecture

```
GitHub Actions cron (4×/day, 35 0/6/12/18 UTC, concurrency group "trading-bot", queue depth 1)
 └─ python bot.py   (one process, 5.5 h session window, 60 s loop)
     ├─ session_auth.py   resume pickle → OAuth refresh → full login (device push)
     ├─ config.py         ~60 module constants (risk values mixed with strategy values)
     ├─ indicators.py     SMA20/50, RSI(14), MACD(12,26,9) cross, pullback±2%, VWAP, volume ratio
     ├─ risk.py           HRP weights (riskfolio), %-of-equity sizing, CVaR "dynamic stop", drawdown check
     ├─ forecast.py       TimesFM 2.5 (800 MB) veto on entries
     ├─ state.py          paper balance → state.json (committed back to main by the workflow)
     └─ bot.py            TradingBot: scan → score → size → order → manage_exits, PDTTracker, DailyRiskGate, report
```

Language: Python 3.11. Broker library: `robin_stocks` (unofficial, reverse-engineered API). No database, no tests
(`test_bot.py` is a demo script that re-implements its own indicators and imports nothing from the bot), no LLM
components, no news/sentiment, no linter/typecheck config. Stale docs (`FINAL_SUMMARY.md`, `QUICKSTART.txt`,
`DEPLOYMENT.md`, `TEST_RESULTS.md`, …) describe June-era behaviour that no longer matches the code.

### What works (verified in logs)
- Session resume from cache: `✓ Session resumed from saved token` on every recent run, no device approvals.
- Crypto + stock data fetch, indicator scoring, paper entries/exits, clean 5.5 h self-exit (every run since 2026-08-30 `success`).
- CVaR stop fix holds (`stop=-2.11%/-2.20%/-2.26%` on 2026-09-12 entries, not the old flat −1%).
- HRP call signature fixed and pinned (`riskfolio-lib==7.3.0`).

## 3. Money path trace (signal → P&L) and software-loss points

| # | Stage | Code | What happens | Software failure that loses money | Sev |
|---|---|---|---|---|---|
| 1 | Market data | `fetch_price_history` | 5-min candles; stocks `span=week`, crypto `span=day`; no candle timestamp check | **Stale data**: last candle age never checked; a frozen feed looks like a flat market. Quote timestamp (`updated_at`) ignored. | High |
| 2 | Quote | `get_current_price` | crypto `mark_price`, stock `last_trade_price` | Mid/last, not ask → entries assume no spread. `None` on error → position silently **not managed** that cycle. | High |
| 3 | Signal | `score_entry` | 3-of-5 binary signals | Crypto volume is always 0 on RH → volume gate bypassed and VWAP never fires → crypto effectively scored 3-of-4. Correlated signals (SMA trend + pullback + VWAP). | Med |
| 4 | Forecast veto | `forecast.py` | TimesFM median 12 bars out ≥ last close | Unvalidated; no evidence of edge; 800 MB dependency + unpinned `timesfm[torch]` in a credentialed job. | Med |
| 5 | Risk | `DailyRiskGate`, `portfolio_drawdown_check` | $3 / 6 % per **session**, reset every 5.5 h | Limits reset each session → not a daily limit. `time.sleep(1800)` after 3 losses **freezes exits for 30 min**. In LIVE, `initial_portfolio_value = PORTFOLIO_SIZE = 50` while real equity is $26.86 → the gate compares against a fictional $50. | **Crit** |
| 6 | Sizing | `calculate_position_size` | `HRP weight × equity`, capped 25 % | Not risk-based (ignores stop distance). Three crypto positions opened in the same minute = 75 % of equity in one correlated bet. Leveraged ETFs (TQQQ/SQQQ) on the watchlist. | High |
| 7 | Buying power | `check_buying_power` | LIVE: `load_account_profile` | **Fails open** (`return True`) when the call fails. | High |
| 8 | Order create | `place_buy_order` | Market order by dollar amount | Re-fetches a second quote; no limit price / no slippage bound; crypto order goes to the **default margin account**, not ••••4508. | **Crit** |
| 9 | Broker ack | `place_buy_order` | success ⇔ `order.get('id')` | Queued-then-rejected/cancelled orders are recorded as positions. No client idempotency key; on `TimeoutError` returns `None` → the order may have filled but is **untracked**, and the next scan can buy again (**duplicate order**). | **Crit** |
| 10 | Fill | — | none | Partial fills never handled; quantity recorded = `dollars / pre-order quote`, not filled quantity → later SELL of wrong quantity (rejects, or leaves dust). | **Crit** |
| 11 | Position tracking | `self.positions` dict | in memory only | Process crash / runner kill / 350-min timeout → positions forgotten. No startup reconciliation with broker positions or open orders. | **Crit** |
| 12 | Exit | `manage_exits` | stop / scale-out / trailing / runner | **`place_sell_order` return value ignored**: on reject/timeout the position is removed and P&L booked while shares may still be held (E3). Force-close at 15:45 `pop`s the position **before** selling. Scale-out books cash but never records realised P&L. Pre-scale-out trailing stop always recorded as a loss. | **Crit** |
| 13 | Session end | `close_all_positions` | market-sells everything every 5.5 h | Arbitrary liquidation regardless of signal → pays spread 4×/day; same unchecked-sell bug. | High |
| 14 | P&L | `_record_exit`, `generate_daily_report` | `(mark − entry) × qty` | No fees/spread; "daily" report is per session; report prints "Day 7/14/30 targets" (+10/25/50 %) — target-chasing framing. | Med |
| 15 | Persistence | `state.py` + workflow commit | paper balance only | **Lost updates (verified)**: a queued run checks out the SHA from *trigger* time, not start time. Run `34718391475` was triggered 20:53 on `ae7ec96`, started after `47eb5d1` (22:12) was pushed, and started from $51.09 instead of $51.05. Two session results (−$0.06, −$0.02) were silently overwritten. | High |

## 4. Other findings

### Reliability / race conditions
- **R1 Duplicate instances**: protection relies solely on the Actions concurrency group; a local `python bot.py` with the same
  credentials runs a second, unaware instance against the same account. No lock / heartbeat.
- **R2 Schedule drift**: cron fires up to ~2.5 h late (18:35 → 20:53); with one pending slot, extra triggers are dropped. Session
  length (5.5 h + setup) ≈ cron spacing, so runs chain back-to-back and coverage is uneven.
- **R3 Hard kill**: `timeout-minutes: 350` vs 330-min session + install; a slow `pip install` of torch pushes the job over and it is
  killed mid-session — no close-out, no state save.
- **R4 SIGALRM timeouts** abort a request mid-flight: the HTTP request may already have reached Robinhood (unknown order state). Alert
  goes to Telegram, which is **not configured** in CI (no secrets) → silent.
- **R5 Error swallowing**: `safe_api_call` converts every error to `None`; the loop cannot tell "no data" from "broker down" → no
  escalation, no kill switch on abnormal API behaviour. 429/502 responses are only warnings.
- **R6 PDT tracker** is in-memory per session (never enforces a 5-day window), counts crypto round trips, and overshoots its own cap on
  force-close (`PDT: 5/3` in logs 2026-09-10). Irrelevant to the cash account, which instead needs settlement (GFV) awareness.
- **R7 Log noise**: `STATS` printed every 60 s (≈330 identical lines/session) buries real events; no structured event log; decisions
  (especially rejections) not recorded → expectancy cannot be evaluated.

### Security
- **S1 (Critical) Session token in a public repo's cache.** `~/.tokens/robinhood.pickle` (access + refresh token + device token) is
  saved with `actions/cache` on a **PUBLIC** repo. Workflows triggered by `pull_request` can restore caches created on the base branch;
  fork-PR workflow approval is only required for *first-time* contributors. A token grants full trading access. Fix: encrypt the
  pickle with a key held in Actions secrets (secrets are not passed to fork PRs), or move the bot to a private repo / self-hosted host.
- **S2 (High) Pickle deserialisation** of cache content (`pickle.load`) = code execution if the cache is ever poisoned.
- **S3 (High) Credentials exposed to every step.** `RH_USERNAME`/`RH_PASSWORD` are job-level env, so `pip install` of unpinned
  `timesfm[torch]`, `robin_stocks>=3.2.0`, `pandas>=…` runs with them in the environment, in a job that has `contents: write`.
  Fix: step-scoped env, pinned + hashed requirements, balance commit in a separate job.
- **S4 (Med) Public logs.** Actions logs on a public repo are world-readable. They include account number and buying power
  (`✓ Authenticated — account … | buying power $…`), and raw broker responses (`Buy REJECTED … {order}`, `Session refresh returned no
  access_token: {data}`) which can contain account URLs or token-endpoint error bodies. No redaction layer exists.
- **S5 (OK)** Git history: no `.env`, pickle, key or token file was ever committed (full `git log --all` scan). `.env` is gitignored.
  `default_workflow_permissions` is `read`; the workflow elevates itself to `contents: write`.

### Strategy weaknesses
- One long-only strategy applied to every regime; no regime filter; no reward/risk requirement at entry (target +4 % vs stop ~−2.2 %
  but the 5.5 h forced exit means the target is rarely reachable).
- 3-of-5 threshold was never validated out-of-sample. Observed paper record (9 sessions, 27 trades): session P&L
  +0.06, −0.07, +1.15, −0.06, −0.02, +0.22, +0.02, −0.02, +0.01 — one outlier session carries the total; **before costs**.
- Crypto dominates actual activity (stocks gated to market hours, cron often misses the open), so the "stock" logic is barely exercised.
- Watchlist includes 3× leveraged ETFs (TQQQ/SQQQ) — excluded by the Week-1 mandate.

### Missing safeguards (vs. the required design)
No central risk config · no risk-engine veto layer (strategy code calls the broker directly) · no STOP_NEW_TRADES / EMERGENCY_HALT ·
no stale-data check · no spread/liquidity check · no max trades/day · no loss cooldown · no order-state machine · no idempotency ·
no reconciliation · no persistence · no candidate/rejection log · no MFE/MAE · no status interface · no tests.

### Places the bot could trade incorrectly
1. Sell rejected → position forgotten → no stop. 2. Order timeout → filled but untracked → duplicate buy next minute.
3. Crypto buy executes in margin account ••••1441. 4. Sizing against $50 constant when equity call fails.
5. Buying-power check passes when the API is down. 6. 30-min sleep while a position gaps through its stop.
7. Runner kill mid-session → positions left open indefinitely. 8. A second local instance double-trades.

---

## 5. Proposed architecture (implemented on branch `hardening/week1-validation`)

```
MarketData (quotes w/ bid/ask/timestamp, candles)  ── freshness + spread checks
   ↓
Scanner (eligible universe, liquidity/spread prefilter)
   ↓
Strategies (trend_pullback, breakout, mean_reversion) → Proposal{symbol, strategy, entry, stop, target, R:R, reasoning, invalidation}
   ↓
Scoring (0–100: setup, trend alignment, R:R, spread, volatility suitability, regime)
   ↓
RiskEngine  ← single RiskConfig (WEEK_1_VALIDATION_MODE preset), kill switches, sizing-from-stop  — ABSOLUTE VETO
   ↓ approved TradeIntent only
ExecutionEngine (persist intent → submit limit order → poll state → reconcile on unknown; never blind-retry)
   ↓
Broker interface ── PaperBroker (bid/ask fills + slippage + fees)  |  RobinhoodBroker (live, account-pinned)
   ↓
PositionMonitor (lifecycle, stops/targets/time-stop; exit only on confirmed fill)
   ↓
SQLite store (candidates incl. rejections, orders, positions, events, halts) → DailyReport / Week1Review → status CLI
```

Strategies never import the broker. The risk engine is the only producer of `TradeIntent`. Live order submission requires
`liveTradingEnabled` **and** an explicit env acknowledgement, and crypto live orders are refused while `robin_stocks` cannot pin them
to the authorised account.

## 6. Prioritised implementation plan

| P | Item | Addresses |
|---|---|---|
| P0 | Central `RiskConfig` + `WEEK_1_VALIDATION_MODE`; RiskEngine with veto, sizing-from-stop, kill switches, persisted `STOP_NEW_TRADES`/`EMERGENCY_HALT` | §3.5–7, missing safeguards |
| P0 | Execution engine: persisted intents, order state machine, reconcile-before-retry, confirmed-fill-only position changes | E3, E9–E12 |
| P0 | SQLite persistence + fail-safe startup reconciliation + single-instance lock | E11, R1 |
| P0 | Refuse live crypto orders (account pinning impossible); live stock orders pinned to ••••4508, limit orders only | E8 |
| P1 | Market-data freshness + spread checks; PaperBroker with bid/ask, slippage, fees | §3.1–2, paper optimism |
| P1 | Multi-strategy proposals + 0–100 scoring; remove leveraged ETFs | strategy weaknesses |
| P1 | Structured, redacted event log; candidate/rejection DB; daily + week-1 reports; status CLI | R7, S4 |
| P1 | Test suite (pytest) with fake broker for all failure modes | no tests |
| P2 | Workflow hardening: checkout latest `main` at job start, step-scoped secrets, encrypted session cache, split write job | E15, S1, S3 |
| P2 | Retire legacy `bot.py` path once shadow validation passes | — |

P2 workflow changes touch the running paper deployment on `main` and the live session token; they are prepared on the branch
but **not deployed** without the owner's review.
