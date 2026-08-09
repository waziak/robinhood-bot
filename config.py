import os
from datetime import time
from dotenv import load_dotenv

load_dotenv()

# [Opt2] Watchlist updated for $50 account — MSFT/GOOGL/AMZN removed (fractional spreads too wide)
WATCHLIST = [
    'BTC', 'ETH', 'DOGE',           # no PDT, 24/7, high volatility
    'TQQQ', 'SQQQ',                  # leveraged ETFs, affordable range
    'TSLA', 'NVDA', 'AAPL', 'SPY', 'QQQ',
]

# [Opt1] PDT compliance
CRYPTO_SYMBOLS = ['BTC', 'ETH', 'DOGE']
IS_CRYPTO = lambda s: s in CRYPTO_SYMBOLS
MAX_DAY_TRADES_PER_WEEK = 3

# [Opt2] Volatility tiers — HIGH/VERY_HIGH prioritized for $50 compounding
SYMBOL_VOLATILITY = {
    'BTC': 'HIGH',      'ETH': 'HIGH',   'DOGE': 'VERY_HIGH',
    'TQQQ': 'HIGH',     'SQQQ': 'HIGH',
    'TSLA': 'HIGH',     'NVDA': 'HIGH',
    'AAPL': 'MEDIUM',   'SPY': 'LOW',    'QQQ': 'MEDIUM',
}

# Account
PORTFOLIO_SIZE = 50.00
MAX_POSITIONS = 5
MAX_POSITION_PCT = 0.25
MIN_CANDLES = 60

# Indicator periods (5-minute candles)
SMA_FAST = 20
SMA_SLOW = 50
RSI_PERIOD = 14
RSI_MIN = 40
RSI_MAX = 58
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
PULLBACK_PCT = 0.02

# [Opt5] 3-of-5 scoring (VWAP added as 5th signal)
MIN_ENTRY_SCORE = 3
TOTAL_SIGNALS = 5

# [Opt4] Volume gate — required before scoring (not a scored signal)
MIN_VOLUME_RATIO = 1.5

# [Opt3] Runner exit system — avg winner +6% vs old +4%
PROFIT_TARGET_SCALE = 0.04    # sell 50% of position here
PROFIT_TARGET_RUNNER = 0.08   # trail remaining 50% toward here
TRAILING_STOP_PCT = -0.015    # 1.5% trail on runner (also used pre-scale-out)
TRAILING_ACTIVATE_PCT = 0.02  # trailing arms after +2% profit

# Kept for risk.py compatibility
PROFIT_TARGET_PCT = PROFIT_TARGET_SCALE
STOP_LOSS_PCT = -0.02

# [Opt7] Tightened risk gate for $50 — was 8%/no dollar floor
MAX_DAILY_DRAWDOWN = 0.06
MAX_DAILY_LOSS_DOLLARS = 3.00
CONSECUTIVE_LOSS_PAUSE = 3
MAX_PORTFOLIO_DRAWDOWN = -0.06   # passed to portfolio_drawdown_check (was -0.08)

# [Opt6] Time filters (ET) — no entries before 9:45, force close at 3:45
# FORCE_CLOSE_HOUR/FORCE_CLOSE_MINUTE env vars let CI override without touching local config
NO_ENTRY_BEFORE = time(9, 45)
NO_NEW_ENTRIES_AFTER = time(15, 30)
FORCE_CLOSE_TIME = time(
    int(os.getenv('FORCE_CLOSE_HOUR', '15')),
    int(os.getenv('FORCE_CLOSE_MINUTE', '45')),
)

# API and timing
SCAN_INTERVAL_SECONDS = 60
CANDLE_INTERVAL = '5minute'
CANDLE_SPAN = 'week'
PAPER_MODE = os.getenv('PAPER_MODE', 'true').lower() != 'false'

RH_USERNAME = os.getenv('RH_USERNAME')
RH_PASSWORD = os.getenv('RH_PASSWORD')

# Session window — bot closes everything and exits after this long (CI runners cap jobs at 6h)
MAX_SESSION_SECONDS = int(os.getenv('MAX_SESSION_SECONDS', str(int(5.5 * 3600))))

CVaR_ALPHA = 0.05
DYNAMIC_STOP_SCALAR = 1.5
