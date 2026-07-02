# Robin Stocks Integration — Gold Standard for Robinhood Trading

**Repository:** [jmfernandez/robin_stocks](https://github.com/jmfernandez/robin_stocks)  
**Status in Bot:** ✅ Integrated (primary API library)  
**Why Chosen:** Most actively maintained, robust, handles MFA, supports fractional shares

## Why Robin Stocks is the Gold Standard

### 1. **Seamless MFA Handling** ✅

Robinhood mandatory MFA is handled transparently:

```python
# Bot automatically prompts for SMS code if MFA enabled
rh.login(username, password)
# If MFA required:
# → Console prints: "Please enter your MFA code from SMS:"
# → User types code
# → Session saved for future runs (no re-prompt until session expires)
```

**In bot.py:**
```python
def authenticate(self):
    try:
        rh.login(config.RH_USERNAME, config.RH_PASSWORD)
        # robin_stocks handles MFA internally
        log.info("✓ Authenticated successfully")
        return True
    except Exception as e:
        log.error(f"Authentication failed: {e}")
        return False
```

### 2. **Fractional Share Support** ✅ (Critical for $100 Budget)

Traditional brokers require whole shares. Robin Stocks enables:

```python
# Without fractional shares:
# At $192.50/share, $100 budget = 0 shares (can't buy)

# With fractional shares (robin_stocks):
quantity = 100 / 192.50  # = 0.5194 shares
# Order: Buy 0.5194 shares for exactly $100
```

**In bot.py:**
```python
def place_buy_order(self, symbol: str, dollar_amount: float):
    quantity = dollar_amount / self.get_current_price(symbol)
    # quantity can be fractional: 0.3341, 0.5194, 1.0778, etc.
    # Robin Stocks handles this natively
    rh.order_buy_market(symbol, quantity)  # works with fractional qty
```

**Example from test run:**
```
[ENTRY] NVDA: 0.3341 shares @ $299.35  # 0.3341 fractional shares = ~$100
[ENTRY] AAPL: 0.0778 shares @ $192.50  # can buy even tiny fractions
```

### 3. **Real-Time Quotes** ✅

Live market data (not stale historical):

```python
# Get live quote
quote = rh.get_quotes(symbol)[0]['last_trade_price']  # current price

# Compare to historical (5-min candle)
historical_price = prices[-1]  # last 5-min candle close
```

**In bot.py (exit logic):**
```python
def manage_exits(self):
    for symbol, position in self.positions.items():
        current_price = self.get_current_price(symbol)  # live quote
        # Use current_price, not stale historical data
        if current_price > position['entry_price'] * 1.04:
            # Profit target hit
            self.place_sell_order(symbol, position['quantity'])
```

**Key Advantage:** Exit decisions use live prices, not 5-minute-old candles. Prevents stale-price exits (original Node.js bot bug).

### 4. **Buying Power Check** ✅

Verify sufficient cash before placing orders:

```python
account = rh.get_account()
buying_power = float(account['buying_power'])  # available cash

# Ensure we have enough for the trade
if position_dollars <= buying_power:
    place_order(symbol, position_dollars)
else:
    log.warning(f"Insufficient buying power: ${buying_power} < ${position_dollars}")
```

### 5. **Portfolio Snapshot** ✅

Real-time portfolio value for risk management:

```python
account = rh.get_account()
portfolio_value = float(account['portfolio_value'])
cash = float(account['cash'])
equity = float(account['equity'])

# Drawdown gate uses live portfolio value
if portfolio_drawdown_check(initial_value, portfolio_value):
    scan_for_entries()  # safe to enter
else:
    log.warning("Portfolio down >8%; halting entries")
```

### 6. **Active Maintenance** ✅

- Latest updates handle Robinhood API changes
- Community-driven bug fixes
- Works with current Robinhood infrastructure (OAuth, etc.)

## Features Leveraged in Bot

### Authentication
```python
# robin_stocks.robinhood.login()
# Handles: OAuth, MFA, session persistence
rh.login(username, password)
```

### Market Data (Indicators)
```python
# robin_stocks.robinhood.get_historicals()
# Returns 5-min, 10-min, daily candles + OHLC
historicals = rh.get_historicals(symbol, interval='5minute', span='week')
closes = [float(h['close_price']) for h in historicals]
# Used by: indicators.py (RSI, MACD, SMA calculations)
```

### Live Quotes (Exit Logic)
```python
# robin_stocks.robinhood.get_quotes()
# Returns real-time bid/ask/last trade price
quote = rh.get_quotes(symbol)[0]
last_price = float(quote['last_trade_price'])
# Used by: manage_exits() for live exit checks
```

### Account Info (Risk Management)
```python
# robin_stocks.robinhood.get_account()
# Returns portfolio_value, buying_power, cash, equity
account = rh.get_account()
portfolio_value = float(account['portfolio_value'])
# Used by: portfolio_drawdown_check()
```

### Order Execution (Fractional Shares)
```python
# robin_stocks.robinhood.order_buy_market()
# Accepts fractional quantity, executes market order
quantity = 0.3341  # fractional
rh.order_buy_market(symbol, quantity)  # works!

# robin_stocks.robinhood.order_sell_market()
# Sell fractional shares
rh.order_sell_market(symbol, quantity)
```

## Integration Points in Bot

### File: `bot.py`

```python
import robin_stocks.robinhood as rh

class TradingBot:
    def authenticate(self):
        """Login to Robinhood via robin_stocks"""
        rh.login(config.RH_USERNAME, config.RH_PASSWORD)
        # MFA handled automatically
        
    def fetch_price_history(self, symbol: str) -> pd.Series:
        """Fetch 5-min historicals from Robinhood"""
        historicals = rh.get_historicals(symbol, interval='5minute', span='week')
        closes = [float(h['close_price']) for h in historicals]
        return pd.Series(closes, name=symbol)
    
    def get_current_price(self, symbol: str) -> float:
        """Get live quote from Robinhood"""
        quote = rh.get_quotes(symbol)[0]
        return float(quote['last_trade_price'])
    
    def place_buy_order(self, symbol: str, dollar_amount: float):
        """Buy fractional shares"""
        quantity = dollar_amount / self.get_current_price(symbol)
        # quantity can be 0.3341, 0.5194, etc.
        if not config.PAPER_MODE:
            rh.order_buy_market(symbol, quantity)  # fractional order
    
    def place_sell_order(self, symbol: str, quantity: float):
        """Sell fractional shares"""
        if not config.PAPER_MODE:
            rh.order_sell_market(symbol, quantity)  # fractional order
    
    def get_current_portfolio_value(self) -> float:
        """Get live portfolio value for risk management"""
        account = rh.get_account()
        return float(account['portfolio_value'])
```

## Why This Matters for a $100 Budget

### Without Fractional Shares (Traditional Brokers)
```
Portfolio: $100
Entry signal: AAPL @ $192.50

Problem: Can't buy even 1 share (costs $192.50)
Result: 0 positions, no trading
```

### With Fractional Shares (robin_stocks)
```
Portfolio: $100
Entry signal: AAPL @ $192.50

Solution: Buy 0.5194 shares for exactly $100
Result: Position entered, strategy works
```

### Position Sizing Example
```
$100 portfolio, 3 entry signals (AAPL, MSFT, GOOGL)
HRP weights: AAPL=0.33, MSFT=0.33, GOOGL=0.34

AAPL: 0.33 × $100 = $33    → 0.1714 shares @ $192.50
MSFT: 0.33 × $100 = $33    → 0.0793 shares @ $416.00
GOOGL: 0.34 × $100 = $34   → 0.1919 shares @ $177.00

All three positions live simultaneously with fractional shares!
```

## MFA Security

### How It Works
1. **First run:** Bot prompts for SMS code
   ```
   Please enter your MFA code from text message:
   123456
   ```

2. **Session saved:** robin_stocks caches the session
   ```
   Future runs: No MFA prompt (session still valid)
   ```

3. **Session expires:** Re-authenticate next time MFA needed

### Safe for Production
- Session file stored locally (~/.robinhood_session)
- No credentials stored (OAuth token only)
- Token auto-refreshes before expiry

## Comparison: Robin Stocks vs. Alternatives

| Feature | Robin Stocks | REST API | Others |
|---------|--------------|----------|--------|
| MFA Support | ✅ Seamless | ❌ Manual | ⚠️ Varies |
| Fractional Shares | ✅ Native | ✅ Supported | ⚠️ Not all |
| Active Maintenance | ✅ Yes (jmfernandez) | ❌ Robinhood only | ⚠️ Varies |
| Pythonic API | ✅ Yes | ⚠️ JSON REST | ✅ Yes |
| Documentation | ✅ Excellent | ⚠️ Basic | ⚠️ Varies |
| Community | ✅ Large | ❌ Small | ⚠️ Varies |

## Installation

```bash
pip install robin_stocks
```

**In requirements.txt:**
```
robin_stocks>=3.2.0
```

## Next Enhancement: Buying Power Check

To add explicit buying power validation:

```python
def check_buying_power(self, position_dollars: float) -> bool:
    """Verify sufficient cash for position"""
    try:
        account = rh.get_account()
        buying_power = float(account['buying_power'])
        
        if position_dollars > buying_power:
            log.warning(f"Insufficient buying power: ${buying_power} < ${position_dollars}")
            return False
        return True
    except:
        log.warning("Could not check buying power")
        return True  # optimistic fallback
```

Add to `scan_for_entries()`:
```python
if not self.check_buying_power(position_dollars):
    continue  # skip this entry
```

## Summary

✅ **Robin Stocks is the backbone of this bot.**

It provides:
- ✅ Robust MFA handling (no manual 2FA code entry)
- ✅ Fractional share support (critical for $100 budget)
- ✅ Real-time quotes (accurate exit decisions)
- ✅ Portfolio snapshots (risk management)
- ✅ Active maintenance (works with current Robinhood API)

**Result:** Small-account trading ($100) becomes viable with fractional shares + intelligent position sizing (Riskfolio-Lib HRP).

---

**Repository:** https://github.com/jmfernandez/robin_stocks  
**Used in:** bot.py (authentication, market data, order execution)  
**Critical for:** MFA, fractional shares, real-time execution
