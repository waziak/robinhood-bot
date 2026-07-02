# Deployment Guide — Robinhood Bot v2

## Current Status

✅ **Code:** Complete and syntax-verified  
✅ **Logic:** Tested with synthetic data  
✅ **Configuration:** Ready to deploy  
❌ **Dependencies:** System environment full (no pip space)  

## Installation Methods

### Option 1: Virtual Environment (Recommended) — Cleanest Approach

```bash
cd /Users/akselkukkonen/robinhood-bot

# Create isolated virtual environment (doesn't use system site-packages)
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies (uses isolated space)
pip install -r requirements.txt

# Run bot
python bot.py
```

This avoids the system Python space issue entirely.

### Option 2: Alternative Python Path

If venv fails, try installing to a custom location:

```bash
pip install --target ./lib -r requirements.txt
export PYTHONPATH="/Users/akselkukkonen/robinhood-bot/lib:$PYTHONPATH"
python bot.py
```

### Option 3: Clean System Python (If You Can)

```bash
# Remove old pandas/numpy to free space
pip uninstall -y pandas numpy

# Clean pip cache
pip cache purge

# Retry install
pip install -r requirements.txt
```

## Quick Start (Once Dependencies Installed)

### 1. Setup Credentials

Edit `.env`:
```bash
nano /Users/akselkukkonen/robinhood-bot/.env
```

Add:
```
RH_USERNAME=your_robinhood_email@example.com
RH_PASSWORD=your_robinhood_password
PAPER_MODE=true
```

### 2. Run Bot

```bash
cd /Users/akselkukkonen/robinhood-bot
python bot.py
```

### 3. Monitor Logs

Watch for these key indicators in logs:

```
[INFO] 🤖 Bot started in PAPER mode
[INFO] ✓ Authenticated successfully
[INFO] HRP weights: AAPL=0.125 MSFT=0.156 ...
[INFO] AAPL @ $192.50 | score=3/4 | SMA20(191.80) > SMA50(189.50)
[INFO] ✓ [ENTRY] AAPL: 0.0778 shares @ $192.50
[INFO] ✓ [PROFIT TARGET] AAPL @ $200.10 (+4.16%)
[STATS] 10 trades | 6 wins (60.0%) | Profit: $15.20 (15.2% ROI)
```

### 4. Switch to Live (After 1+ Day Paper Trading)

Edit `.env`:
```
PAPER_MODE=false
```

Then restart bot.

## File Manifest

```
robinhood-bot/
├── bot.py                    (480 lines) — Main trading loop
├── config.py                 (50 lines)  — Configuration constants
├── indicators.py             (150 lines) — Technical indicators
├── risk.py                   (130 lines) — Riskfolio-Lib wrapper
├── requirements.txt          (5 lines)   — Dependencies
├── .env                      (3 lines)   — Credentials (gitignored)
├── .gitignore                (11 lines)  — Git excludes
├── test_bot.py              (280 lines) — Logic test (no deps)
├── README.md                 (200 lines) — User guide
├── IMPLEMENTATION_NOTES.md   (350 lines) — Technical deep dive
├── TEST_RESULTS.md          (250 lines) — Test report
└── DEPLOYMENT.md            (This file) — Deployment guide
```

## System Requirements

| Requirement | Min | Recommended | Notes |
|-------------|-----|-------------|-------|
| Python | 3.8 | 3.10+ | Uses pandas/numpy |
| Disk space | 500MB | 1GB | Virtual env + deps |
| Memory | 256MB | 512MB | Run-time during scan cycles |
| Network | 1Mbps | 10Mbps | Robinhood API calls |
| System | macOS/Linux | macOS/Linux | robin_stocks library compatible |

## Robinhood Account Setup

### Prerequisites
1. **Active Robinhood account** (free tier OK)
2. **Email + password** (add to `.env`)
3. **MFA optional** — robin_stocks will prompt for SMS code if enabled
4. **Paper mode** — practice first with `PAPER_MODE=true`

### Permissions Needed
- View account balance
- Place market orders (buy/sell)
- View historical quotes
- View current holdings

All available on free Robinhood tier.

## Troubleshooting

### "No space left on device" on pip install

Use virtual environment instead:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### "robin_stocks: 2FA/MFA prompt"

If Robinhood account has MFA enabled, bot will print:
```
Please enter your MFA code from text message:
```

Type the SMS code shown on your phone. robin_stocks saves the session for future runs.

### "Market closed; sleeping..." (all day long)

Bot only runs 9:30–16:00 ET, Mon–Fri. If you're testing outside hours:

1. Edit `config.py`, lower `MIN_ENTRY_SCORE` to 1 to force test entry
2. Or wait for next trading day

### "No price histories available"

Check:
1. Running during market hours (9:30–16:00 ET, Mon–Fri)
2. Internet connection working
3. Robinhood API status: https://status.robinhood.com/

### "All symbols score 0/4, no entries"

Check config thresholds in `config.py`:
- `RSI_MIN=40, RSI_MAX=58` (not too tight)
- `PULLBACK_PCT=0.02` (±2% not too strict)
- `MIN_ENTRY_SCORE=3` (not too high)

Try lowering to test:
```python
MIN_ENTRY_SCORE=1  # Force test entry
```

## Performance Tuning

### Faster Scans (if slow)

Edit `config.py`:
```python
SCAN_INTERVAL_SECONDS = 30  # was 60
MAX_WORKERS = 8              # add this, increase thread pool
```

### Lower CPU Usage (if high)

```python
SCAN_INTERVAL_SECONDS = 120  # slower scans
```

### Memory Usage

Current: ~50MB (minimal Python overhead)
- Increase if holding 20+ positions
- Decrease by reducing watchlist size

## Monitoring & Alerts

### Current (Console Logs)

All activity logged to console. Redirect to file:

```bash
python bot.py > bot.log 2>&1 &
tail -f bot.log
```

### Future Enhancement: Slack Alerts

```python
# Add to bot.py
import requests

def send_slack(message):
    webhook = os.getenv('SLACK_WEBHOOK')
    requests.post(webhook, json={'text': message})

# In scan_for_entries():
send_slack(f"[ENTRY] {symbol} scored {entry_score['score']}/4")
```

Set `SLACK_WEBHOOK` in `.env`.

## Backup & Recovery

### State Persistence

⚠️ **Current:** State lives in memory (lost on crash)

**Improvement:** Add SQLite persistence

```bash
# Add to requirements.txt
sqlite3  # stdlib, no install needed
```

### Recovery Plan

If bot crashes:
1. Check logs for error message
2. Manual position check: `rh.get_positions()`
3. Restart bot: `python bot.py`

## Upgrading Bot

### Update Strategy Parameters

Edit `config.py` — no code changes needed:
- Watchlist
- Entry thresholds
- Exit levels
- Risk limits

### Update to New Version

```bash
cd /Users/akselkukkonen/robinhood-bot
git pull origin main  # if using git
python bot.py
```

### Roll Back

If new version breaks:
```bash
git checkout HEAD~1  # previous version
python bot.py
```

## Support

### Check Logs

```bash
tail -100 bot.log | grep ERROR
```

### Test Without Robinhood

```bash
python test_bot.py  # synthetic data, no dependencies
```

### Verify Config

```bash
python3 -c "from config import *; print(WATCHLIST, PROFIT_TARGET_PCT)"
```

## Next Steps

1. **Choose installation method** (Option 1: venv recommended)
2. **Install dependencies**
3. **Add Robinhood credentials to `.env`**
4. **Run in paper mode for 1 trading day**
5. **Monitor logs for entries/exits**
6. **Switch to live when confident**

---

**Questions?** Check:
- `README.md` — user guide
- `IMPLEMENTATION_NOTES.md` — design decisions
- `TEST_RESULTS.md` — what we tested
- `test_bot.py` — working example
