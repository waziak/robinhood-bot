# Robinhood Multi-Indicator Trading Bot

A Python trading bot with dynamic position sizing using Riskfolio-Lib. Implements a medium-risk strategy on a $100 portfolio with RSI, MACD, and SMA20/50 pullback signals.

## Features

- **Multi-indicator entry scoring** (RSI, MACD, SMA trend, pullback) — requires 3 of 4 signals
- **Hierarchical Risk Parity (HRP)** position sizing via Riskfolio-Lib — prevents over-concentration
- **Fractional share support** (robin_stocks) — buy $5 of a $500 stock (critical for $100 budget)
- **Buying power checks** (robin_stocks) — verify sufficient cash before orders
- **Dynamic stop loss** adjusted by per-symbol CVaR (volatility-aware)
- **Portfolio-level drawdown gate** — halts new entries if portfolio is down >8%
- **Paper trading mode** for testing before live trading
- **Live quote-based exits** (no stale historical price)
- **MFA support** (robin_stocks handles seamlessly)
- **Market hours check** — only trades 9:30–16:00 ET, Mon–Fri

## Setup

### 1. Install Dependencies

```bash
cd /Users/akselkukkonen/robinhood-bot
pip install -r requirements.txt
```

### 2. Configure Credentials

Edit `.env` and add your Robinhood username and password:

```
RH_USERNAME=your_email@example.com
RH_PASSWORD=your_password
PAPER_MODE=true
```

### 3. Run in Paper Mode

```bash
python bot.py
```

Watch the logs — each scan cycle will:
- Fetch 5-minute candle data for all 8 watchlist symbols
- Calculate HRP weights (optimal allocation per symbol)
- Score each symbol on 4 entry signals (0–4 score)
- Place paper buy/sell orders
- Track stats (win rate, profit, open positions)

## Configuration

Edit `config.py` to adjust:

- **Watchlist**: `WATCHLIST = ['AAPL', 'MSFT', ...]`
- **Entry thresholds**: `MIN_ENTRY_SCORE`, `RSI_MIN`/`RSI_MAX`
- **Exit levels**: `PROFIT_TARGET_PCT`, `STOP_LOSS_PCT`, `TRAILING_STOP_PCT`
- **Risk limits**: `MAX_POSITION_PCT`, `MAX_PORTFOLIO_DRAWDOWN`
- **Scan timing**: `SCAN_INTERVAL_SECONDS`

## Entry Signals (3-of-4 Required)

1. **SMA Trend**: SMA20 > SMA50 (uptrend on 5-min candles)
2. **RSI Zone**: RSI(14) between 40–58 (momentum confirmation)
3. **MACD Cross**: MACD line crossed above signal in last 3 bars (bullish momentum)
4. **Pullback**: Price within ±2% of SMA20 (entry on support)

## Exit Triggers (In Priority Order)

1. **Profit Target**: +4% from entry
2. **Hard Stop Loss**: -2% from entry (dynamic per-symbol)
3. **Trailing Stop**: -1.5% from peak (only arms after +2% profit)

## Tech Stack: Gold Standard Libraries

### Robin Stocks — Most Actively Maintained Robinhood Library

**Repository:** [jmfernandez/robin_stocks](https://github.com/jmfernandez/robin_stocks)

Why it's the gold standard:
- ✅ **Seamless MFA support** — handles mandatory two-factor authentication automatically
- ✅ **Fractional shares** — buy $5 of a $500 stock (enables small-budget trading)
- ✅ **Real-time quotes** — live prices for accurate exits (not stale historical data)
- ✅ **Buying power checks** — verify sufficient cash before placing orders
- ✅ **Active maintenance** — kept current with Robinhood API changes
- ✅ **Large community** — battle-tested in production

**Example (Fractional Shares for $100 Budget):**
```
Portfolio: $100
Entry signal: AAPL @ $192.50

Traditional broker: Can't buy (need $192.50 minimum)
Robin Stocks: Buy 0.5194 shares for exactly $100 ✓
```

**Used in bot.py:**
- `rh.login()` — MFA-aware authentication
- `rh.get_historicals()` — fetch 5-min candles for indicators
- `rh.get_quotes()` — live prices for exit decisions
- `rh.get_account()` — buying power & portfolio value
- `rh.order_buy_market() / order_sell_market()` — fractional share orders

See [robin_stocks_integration.md](robin_stocks_integration.md) for detailed integration guide.

### Riskfolio-Lib — Portfolio Optimization

**Repository:** [dcguba/Riskfolio-Lib](https://github.com/dcguba/Riskfolio-Lib)

Why it's critical for small accounts:
- **HRP (Hierarchical Risk Parity)** — optimal allocation avoiding sector concentration
- **CVaR (Conditional Value-at-Risk)** — dynamic stops based on volatility
- **No matrix inversion required** — stable with 8-symbol watchlist (MV optimization unstable)

## Risk Management

### HRP (Hierarchical Risk Parity)

Instead of flat $15/position, the bot uses HRP to calculate optimal allocation:
- Clusters correlated assets (reduces sector concentration)
- Allocates more capital to uncorrelated diversifiers
- Caps any single position at 25% of portfolio

### CVaR-Adjusted Stops

High-volatility symbols get tighter stops; low-volatility symbols get more room.

### Portfolio Drawdown Gate

If portfolio is down >8% from initial value, new entries halt until recovered.

## Logs

All activity logged to console with timestamps:

```
[2026-06-18 09:30:15] [INFO] 🤖 Bot started in PAPER mode
[2026-06-18 09:30:16] [INFO] Scanning for entries...
[2026-06-18 09:30:17] [INFO] AAPL @ $192.50 | score=3/4 | SMA20(192.10) > SMA50(190.05) | RSI=42.3 (in zone 40-58) | Pullback to SMA20 (-0.21%)
[2026-06-18 09:30:17] [INFO] ✓ [ENTRY] AAPL: 0.0778 shares @ $192.50 | stop=-2.00%
...
```

## Going Live

**Before trading with real money:**

1. Run in paper mode for a full trading day
2. Verify entry/exit logic and position sizing in logs
3. Set `PAPER_MODE=false` in `.env`
4. Test with a small account first

## Files

- `bot.py` — Main trading loop
- `config.py` — All constants and environment variables
- `indicators.py` — RSI, MACD, SMA, entry scoring
- `risk.py` — Riskfolio-Lib wrapper (HRP, CVaR, drawdown gate)
- `requirements.txt` — Python dependencies
- `.env` — Credentials (gitignored)

## Notes

- Market hours: 9:30–16:00 ET, Mon–Fri only
- Uses 5-minute candles (~16 hours of history per week span)
- Thread pool fetches price data in parallel for speed
- Robin Stocks library handles Robinhood authentication (includes MFA support)
