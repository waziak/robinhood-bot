#!/usr/bin/env python3
"""
Robinhood Multi-Indicator Trading Bot with Riskfolio-Lib Position Sizing.
$50 account — PDT-compliant, 3-of-5 scoring, runner exits, VWAP + volume gate.
"""

import time
import signal
import logging
import traceback
import pytz
from contextlib import contextmanager
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests
import robin_stocks.robinhood as rh

import config
import session_auth
import state
import forecast
from indicators import score_entry, check_volume_confirmation
from risk import calculate_hrp_weights, calculate_position_size, calculate_dynamic_stop, portfolio_drawdown_check

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

ET = pytz.timezone('America/New_York')  # [Opt6]


# ─── API call timeouts ────────────────────────────────────────────────────────
# robin_stocks calls have no built-in timeout, so a single hung HTTP request
# can otherwise wedge the whole session indefinitely — an open position with
# no exits if it happens in LIVE mode. signal.alarm only fires in the main
# thread, which covers every robin_stocks call in this file EXCEPT the ones in
# fetch_price_history(): scan_for_entries() runs that inside a
# ThreadPoolExecutor worker thread, where signal.signal() would raise
# "signal only works in main thread of the main interpreter". That path is
# timed out at future.result() instead, further down.

@contextmanager
def timeout(seconds, error_message="API call timed out"):
    def handler(signum, frame):
        raise TimeoutError(error_message)

    signal.signal(signal.SIGALRM, handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)


def safe_api_call(func, *args, timeout_secs=10, **kwargs):
    """Call a robin_stocks function with a hard timeout. Returns None on a
    timeout or any other error instead of raising — every call site in this
    file already null-checks robin_stocks' return values."""
    try:
        with timeout(timeout_secs, f"{func.__name__} timed out after {timeout_secs}s"):
            return func(*args, **kwargs)
    except TimeoutError:
        log.error(f"API timeout on {func.__name__} after {timeout_secs}s")
        return None
    except Exception as e:
        log.warning(f"API error on {func.__name__}: {e}")
        return None


def send_telegram_alert(message: str):
    """Best-effort only — no Telegram creds configured means this is a no-op,
    not a failure. Never let alerting itself become another way to hang."""
    if not (config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID):
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": config.TELEGRAM_CHAT_ID, "text": message},
            timeout=5,
        )
    except Exception as e:
        log.warning(f"Telegram alert failed: {e}")


# ─── [Opt1] PDT tracker ──────────────────────────────────────────────────────

class PDTTracker:
    """
    Tracks intraday round-trips against the 3-per-5-day PDT limit.
    A day trade = buy + sell same symbol same calendar day.
    Hitting 3 on a margin account triggers a 90-day lockout.
    """
    def __init__(self):
        self.day_trades = []  # list of (datetime, symbol)

    def record_day_trade(self, symbol: str):
        self.day_trades.append((datetime.now(), symbol))
        cutoff = datetime.now() - timedelta(days=5)
        self.day_trades = [(dt, sym) for dt, sym in self.day_trades if dt > cutoff]

    def day_trades_used(self) -> int:
        return len(self.day_trades)

    def can_day_trade(self) -> bool:
        return self.day_trades_used() < config.MAX_DAY_TRADES_PER_WEEK

    def trades_remaining(self) -> int:
        return max(0, config.MAX_DAY_TRADES_PER_WEEK - self.day_trades_used())


# ─── [Opt7] Daily risk gate ───────────────────────────────────────────────────

class DailyRiskGate:
    """
    Halts new entries if daily loss exceeds 6% or $3.
    Also pauses 30 min after 3 consecutive losses.
    Tighter than the old -8% portfolio gate — right-sized for $50.
    """
    def __init__(self, starting_value: float):
        self.starting_value = starting_value
        self.peak_value = starting_value
        self.trades_today = 0
        self.losses_today = 0
        self.consecutive_losses = 0

    def update(self, current_value: float, trade_result: float):
        self.trades_today += 1
        if trade_result < 0:
            self.losses_today += 1
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        if current_value > self.peak_value:
            self.peak_value = current_value

    def should_halt(self, current_value: float) -> bool:
        daily_loss_pct = (self.starting_value - current_value) / self.starting_value
        daily_loss_dollars = self.starting_value - current_value

        if daily_loss_pct >= config.MAX_DAILY_DRAWDOWN:
            log.warning(f"HALT — daily drawdown {daily_loss_pct*100:.1f}% "
                        f"exceeds {config.MAX_DAILY_DRAWDOWN*100}% limit")
            return True

        if daily_loss_dollars >= config.MAX_DAILY_LOSS_DOLLARS:
            log.warning(f"HALT — daily loss ${daily_loss_dollars:.2f} "
                        f"exceeds ${config.MAX_DAILY_LOSS_DOLLARS} hard floor")
            return True

        if self.consecutive_losses >= config.CONSECUTIVE_LOSS_PAUSE:
            log.warning("3 consecutive losses — pausing 30 minutes")
            time.sleep(1800)
            self.consecutive_losses = 0

        return False


# ─── [Opt6] ET time helpers ───────────────────────────────────────────────────

def get_et_time():
    return datetime.now(ET).time()

def is_valid_entry_time() -> bool:
    current = get_et_time()
    if current < config.NO_ENTRY_BEFORE:
        log.info(f"Entry blocked — pre-{config.NO_ENTRY_BEFORE} ET fakeout period")
        return False
    if current >= config.NO_NEW_ENTRIES_AFTER:
        log.info(f"Entry blocked — after {config.NO_NEW_ENTRIES_AFTER} ET cutoff")
        return False
    return True

def should_close_all_positions() -> bool:
    return get_et_time() >= config.FORCE_CLOSE_TIME


# ─── [Opt8] Daily compound tracker ───────────────────────────────────────────

def generate_daily_report(starting_balance: float, current_balance: float,
                           trades: list, pdt_tracker: PDTTracker):
    gain = current_balance - starting_balance
    gain_pct = (gain / starting_balance * 100) if starting_balance > 0 else 0
    wins = [t for t in trades if t['pnl'] > 0]
    losses = [t for t in trades if t['pnl'] < 0]
    win_rate = len(wins) / len(trades) * 100 if trades else 0
    avg_win = sum(t['pnl'] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t['pnl'] for t in losses) / len(losses) if losses else 0

    log.info(f"""
╔══════════════════════════════════════╗
║         DAILY TRADING REPORT         ║
╠══════════════════════════════════════╣
║ Starting balance:  ${starting_balance:.2f}
║ Ending balance:    ${current_balance:.2f}
║ Daily P&L:         ${gain:+.2f} ({gain_pct:+.1f}%)
╠══════════════════════════════════════╣
║ Total trades:      {len(trades)}
║ Win rate:          {win_rate:.0f}%
║ Avg win:           ${avg_win:.2f}
║ Avg loss:          ${avg_loss:.2f}
║ Day trades used:   {pdt_tracker.day_trades_used()}/3
╠══════════════════════════════════════╣
║ COMPOUND TRACKER
║ Day 7  target (+10%): ${starting_balance * 1.10:.2f}
║ Day 14 target (+25%): ${starting_balance * 1.25:.2f}
║ Day 30 target (+50%): ${starting_balance * 1.50:.2f}
╚══════════════════════════════════════╝""")


# ─── Main bot ─────────────────────────────────────────────────────────────────

class TradingBot:
    def __init__(self):
        # positions: {symbol: {entry_price, quantity, remaining_qty, orderId,
        #                       dynamic_stop, peak_price, entry_time,
        #                       scaled_out, runner_stop}}
        self.positions = {}
        self.stats = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_profit': 0.0,
        }
        self.price_histories = {}
        self.raw_historicals = {}                          # for volume + VWAP
        # Paper mode compounds across sessions via state.json; live mode always
        # starts from the broker's real equity, so config.PORTFOLIO_SIZE is just
        # a label there, never a balance override.
        self.initial_portfolio_value = (
            state.load_balance(config.PORTFOLIO_SIZE) if config.PAPER_MODE else config.PORTFOLIO_SIZE
        )
        self.cash = self.initial_portfolio_value            # paper-mode ledger; unused in LIVE
        self.is_active = False
        self.pdt_tracker = PDTTracker()                    # [Opt1]
        self.daily_risk_gate = DailyRiskGate(self.initial_portfolio_value)  # [Opt7]
        self.trade_log = []                                # [Opt8]

    def authenticate(self):
        if not config.RH_USERNAME or not config.RH_PASSWORD:
            log.error("RH_USERNAME or RH_PASSWORD not set in .env")
            return False
        try:
            log.info("Authenticating with Robinhood...")
            if not session_auth.authenticate(config.RH_USERNAME, config.RH_PASSWORD):
                log.error("Authentication failed — see warnings above")
                return False
            profile = safe_api_call(rh.load_account_profile, account_number=config.ACCOUNT_NUMBER,
                                     timeout_secs=config.API_TIMEOUT_PROFILE)
            if profile:
                log.info(f"✓ Authenticated — account {profile.get('account_number')} | "
                         f"buying power ${float(profile.get('buying_power') or 0):.2f}")
            return True
        except Exception as e:
            log.error(f"Authentication failed: {e}")
            traceback.print_exc()
            return False

    def is_market_open(self) -> bool:
        """Check if US stock market is open (ET 9:30-16:00, Mon-Fri)."""
        now = datetime.now(ET)          # [Opt6] proper ET timezone
        if now.weekday() >= 5:
            return False
        total_min = now.hour * 60 + now.minute
        return 570 <= total_min < 960

    def fetch_price_history(self, symbol: str):
        """
        Fetch 5-min candles. Returns (pd.Series of closes, raw historicals list).
        Raw historicals are stored for volume confirmation and VWAP.
        """
        try:
            if config.IS_CRYPTO(symbol):
                # 24h of 5-min candles; '24_7' bounds — crypto never sleeps
                historicals = rh.get_crypto_historicals(
                    symbol, interval=config.CANDLE_INTERVAL, span='day', bounds='24_7'
                )
            else:
                historicals = rh.get_stock_historicals(
                    symbol, interval=config.CANDLE_INTERVAL, span=config.CANDLE_SPAN
                )
            if not historicals:
                log.warning(f"No historical data for {symbol}")
                return None, None
            closes = [float(h['close_price']) for h in historicals]
            return pd.Series(closes, name=symbol), historicals
        except Exception as e:
            log.warning(f"Failed to fetch {symbol}: {e}")
            return None, None

    def get_current_price(self, symbol: str) -> float:
        # Always called from the main thread (scan/exit loops), so safe_api_call's
        # signal-based timeout applies cleanly here.
        if config.IS_CRYPTO(symbol):
            quote = safe_api_call(rh.get_crypto_quote, symbol, timeout_secs=config.API_TIMEOUT_QUOTE)
            if quote and quote.get('mark_price'):
                return float(quote['mark_price'])
        else:
            quote = safe_api_call(rh.get_quotes, symbol, timeout_secs=config.API_TIMEOUT_QUOTE)
            if quote and len(quote) > 0 and quote[0]:
                return float(quote[0]['last_trade_price'])
        return None

    def scan_for_entries(self):
        """Scan watchlist for entry signals and place buy orders."""
        # [Opt6] Time gates apply to stocks only — crypto trades 24/7
        market_open = self.is_market_open()
        stock_entries_ok = market_open and is_valid_entry_time()

        # [Opt1] Log PDT status on every scan
        log.info(f"Day trades used this week: {self.pdt_tracker.day_trades_used()}/3 "
                 f"({self.pdt_tracker.trades_remaining()} remaining)")

        log.info("Scanning for entries...")
        self.price_histories = {}
        self.raw_historicals = {}

        scan_symbols = [s for s in config.WATCHLIST
                        if config.IS_CRYPTO(s) or stock_entries_ok]
        if not scan_symbols:
            return

        # fetch_price_history() runs rh.get_stock_historicals/get_crypto_historicals
        # inside these worker threads, where signal-based safe_api_call can't be
        # used (SIGALRM only fires in the main thread) — so the timeout is
        # enforced here instead, at future.result(), which does work across
        # threads. A future that times out leaves its thread running in the
        # background (Python can't force-kill a thread), which is why this uses
        # shutdown(wait=False) below instead of the `with` form — otherwise exiting
        # the executor would itself block on that same hung thread.
        executor = ThreadPoolExecutor(max_workers=4)
        try:
            futures = {executor.submit(self.fetch_price_history, s): s for s in scan_symbols}
            for future in futures:
                symbol = futures[future]
                try:
                    series, historicals = future.result(timeout=config.API_TIMEOUT_HISTORICALS)
                    if series is not None and len(series) >= config.MIN_CANDLES:
                        self.price_histories[symbol] = series
                        self.raw_historicals[symbol] = historicals
                except TimeoutError:
                    log.warning(f"API timeout fetching {symbol} historicals "
                                f"after {config.API_TIMEOUT_HISTORICALS}s")
                except Exception as e:
                    log.warning(f"Error fetching {symbol}: {e}")
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        if not self.price_histories:
            log.warning("No price histories available")
            return

        hrp_weights = calculate_hrp_weights({s: h.values for s, h in self.price_histories.items()})
        log.info(f"HRP weights: {', '.join(f'{s}={w:.3f}' for s, w in sorted(hrp_weights.items()))}")

        # [TimesFM] One batched forecast call for the whole watchlist per scan
        # cycle — see forecast.py. Missing entries mean "no opinion", not bearish.
        forecast_bullish = forecast.forecast_direction(self.price_histories)

        current_portfolio_value = self.get_current_portfolio_value()
        # [Opt7] Use updated 6% drawdown gate instead of old 8%
        if not portfolio_drawdown_check(self.initial_portfolio_value,
                                        current_portfolio_value,
                                        config.MAX_PORTFOLIO_DRAWDOWN):
            log.warning(f"Portfolio drawdown exceeded — halting new entries")
            return

        for symbol in config.WATCHLIST:
            if symbol in self.positions:
                continue
            if len(self.positions) >= config.MAX_POSITIONS:
                log.info(f"Max positions ({config.MAX_POSITIONS}) reached; skipping {symbol}")
                break
            if symbol not in self.price_histories:
                continue

            # [Opt1] PDT check — equities only; crypto trades freely
            if not self.pdt_tracker.can_day_trade() and not config.IS_CRYPTO(symbol):
                log.info(f"PDT limit reached ({self.pdt_tracker.day_trades_used()}/3) "
                         f"— skipping {symbol} (crypto-only mode)")
                continue

            historicals = self.raw_historicals.get(symbol, [])

            # [Opt4] Volume gate — required before scoring
            vol_ok, vol_ratio = check_volume_confirmation(historicals)
            if not vol_ok and config.IS_CRYPTO(symbol) and vol_ratio == 0.0:
                vol_ok = True  # RH crypto candles often report zero volume — gate not applicable
            log.info(f"{symbol} volume ratio: {vol_ratio:.2f}x average")
            if not vol_ok:
                log.info(f"{symbol} SKIP — volume {vol_ratio:.2f}x < {config.MIN_VOLUME_RATIO}x required")
                continue

            prices = self.price_histories[symbol]
            current_price = self.get_current_price(symbol)
            if current_price is None:
                continue

            # [Opt5] Score entry — now 3-of-5 including VWAP
            entry_score = score_entry(prices, current_price, historicals)
            log.info(f"{symbol} @ ${current_price:.2f} | score={entry_score['score']}/{config.TOTAL_SIGNALS} "
                     f"| {' | '.join(entry_score['reasons'])}")

            if entry_score['score'] < config.MIN_ENTRY_SCORE:
                continue

            # [TimesFM] Veto only — a bearish forecast blocks an otherwise-good
            # entry, but no opinion (model disabled/unavailable/insufficient
            # history) never blocks one.
            if symbol in forecast_bullish and not forecast_bullish[symbol]:
                log.info(f"{symbol} SKIP — TimesFM forecasts lower prices over "
                         f"the next {config.FORECAST_HORIZON} bars")
                continue

            weight = hrp_weights.get(symbol, 1.0 / len(config.WATCHLIST))
            position_dollars = calculate_position_size(symbol, weight, current_portfolio_value, current_price)

            if not self.check_buying_power(position_dollars):
                log.info(f"Skipping {symbol} — insufficient buying power")
                continue

            quantity = position_dollars / current_price
            dynamic_stop = calculate_dynamic_stop(symbol, prices)

            order = self.place_buy_order(symbol, position_dollars)
            if order:
                self.cash -= position_dollars
                self.positions[symbol] = {
                    'entry_price': current_price,
                    'quantity': quantity,
                    'remaining_qty': quantity,      # [Opt3] tracks partial sells
                    'orderId': order.get('id', f'paper-{int(time.time())}'),
                    'dynamic_stop': dynamic_stop,
                    'peak_price': current_price,
                    'entry_time': time.time(),
                    'scaled_out': False,            # [Opt3] runner system
                    'runner_stop': None,            # [Opt3] absolute price, set at scale-out
                }
                self.stats['total_trades'] += 1
                log.info(f"✓ [ENTRY] {symbol}: {quantity:.4f} shares @ ${current_price:.2f} | "
                         f"stop={dynamic_stop*100:.2f}%")

    def _record_exit(self, symbol: str, position: dict, current_price: float,
                     quantity: float, is_win: bool):
        """Update stats, trade log, PDT tracker, and daily risk gate after an exit."""
        self.cash += current_price * quantity
        pnl = (current_price - position['entry_price']) * quantity
        self.stats['total_profit'] += pnl
        if is_win:
            self.stats['winning_trades'] += 1
        else:
            self.stats['losing_trades'] += 1
        self.trade_log.append({'symbol': symbol, 'pnl': pnl})

        # [Opt1] Count as day trade if opened and closed the same calendar day
        entry_date = datetime.fromtimestamp(position['entry_time']).date()
        if entry_date == datetime.now().date():
            self.pdt_tracker.record_day_trade(symbol)
            log.info(f"Day trade recorded: {symbol} | PDT: "
                     f"{self.pdt_tracker.day_trades_used()}/3 "
                     f"({self.pdt_tracker.trades_remaining()} remaining)")

        # [Opt7] Update daily risk gate with trade result
        self.daily_risk_gate.update(self.get_current_portfolio_value(), pnl)

    def manage_exits(self):
        """Check open positions for exit conditions."""
        # [Opt6] Force close stock positions at 3:45pm ET — crypto trades on 24/7
        if should_close_all_positions():
            stock_syms = [s for s in self.positions if not config.IS_CRYPTO(s)]
            if stock_syms:
                log.info("3:45pm ET — closing stock positions (crypto keeps running)")
                for s in stock_syms:
                    pos = self.positions.pop(s)
                    price = self.get_current_price(s) or pos['entry_price']
                    self.place_sell_order(s, pos['remaining_qty'])
                    self._record_exit(s, pos, price, pos['remaining_qty'],
                                      is_win=price > pos['entry_price'])

        symbols_to_exit = []

        for symbol, position in self.positions.items():
            current_price = self.get_current_price(symbol)
            if current_price is None:
                continue

            entry_price = position['entry_price']
            remaining_qty = position['remaining_qty']
            profit_pct = (current_price - entry_price) / entry_price

            if current_price > position['peak_price']:
                position['peak_price'] = current_price

            # [Opt3] Runner system ────────────────────────────────────────────
            if not position['scaled_out']:
                # Hard stop (always checked first)
                if profit_pct <= position['dynamic_stop']:
                    log.warning(f"✗ [STOP LOSS] {symbol} @ ${current_price:.2f} ({profit_pct*100:.2f}%)")
                    self.place_sell_order(symbol, remaining_qty)
                    symbols_to_exit.append(symbol)
                    self._record_exit(symbol, position, current_price, remaining_qty, is_win=False)
                    continue

                # Scale out 50% at +4% — start running the rest
                if profit_pct >= config.PROFIT_TARGET_SCALE:
                    half_qty = remaining_qty / 2
                    self.place_sell_order(symbol, half_qty)
                    self.cash += current_price * half_qty
                    position['scaled_out'] = True
                    position['remaining_qty'] = remaining_qty - half_qty
                    position['runner_stop'] = current_price * (1 + config.TRAILING_STOP_PCT)
                    log.info(f"[SCALE OUT] {symbol} 50% @ ${current_price:.2f} "
                             f"(+{profit_pct*100:.1f}%) — trailing rest to +8%")
                    continue

                # Trailing stop arms after +2% (prevents whipsaw)
                if profit_pct >= config.TRAILING_ACTIVATE_PCT:
                    drop_from_peak = (position['peak_price'] - current_price) / position['peak_price']
                    if drop_from_peak >= abs(config.TRAILING_STOP_PCT):
                        log.warning(f"📉 [TRAILING STOP] {symbol} @ ${current_price:.2f} "
                                    f"(dropped {drop_from_peak*100:.2f}% from peak)")
                        self.place_sell_order(symbol, remaining_qty)
                        symbols_to_exit.append(symbol)
                        self._record_exit(symbol, position, current_price, remaining_qty, is_win=False)
                        continue

            else:
                # Runner mode — trail remaining shares ────────────────────────
                if current_price > position['peak_price']:
                    position['peak_price'] = current_price
                    position['runner_stop'] = current_price * (1 + config.TRAILING_STOP_PCT)

                # Hard stop on runner
                if profit_pct <= position['dynamic_stop']:
                    log.warning(f"✗ [RUNNER HARD STOP] {symbol} @ ${current_price:.2f} ({profit_pct*100:.2f}%)")
                    self.place_sell_order(symbol, remaining_qty)
                    symbols_to_exit.append(symbol)
                    # Was hardcoded is_win=True — this branch only fires when price has
                    # fallen back through the stop relative to entry, i.e. a loss on this
                    # parcel, so it was inflating win-rate stats. Derive it from price instead.
                    self._record_exit(symbol, position, current_price, remaining_qty,
                                      is_win=current_price > position['entry_price'])
                    continue

                # Runner trailing stop hit
                if position['runner_stop'] and current_price <= position['runner_stop']:
                    log.info(f"[RUNNER EXIT] {symbol} @ ${current_price:.2f} "
                             f"({profit_pct*100:.1f}%) — avg winner now +6%")
                    self.place_sell_order(symbol, remaining_qty)
                    symbols_to_exit.append(symbol)
                    self._record_exit(symbol, position, current_price, remaining_qty, is_win=True)
                    continue

        for symbol in symbols_to_exit:
            del self.positions[symbol]

    def close_all_positions(self):
        """Force close all open positions (end-of-session or shutdown)."""
        for symbol, position in list(self.positions.items()):
            current_price = self.get_current_price(symbol) or position['entry_price']
            self.place_sell_order(symbol, position['remaining_qty'])
            self._record_exit(symbol, position, current_price, position['remaining_qty'],
                              is_win=current_price > position['entry_price'])
        self.positions.clear()

    def place_buy_order(self, symbol: str, dollar_amount: float):
        try:
            current_price = self.get_current_price(symbol)
            quantity = dollar_amount / current_price
            if config.PAPER_MODE:
                log.info(f"[PAPER] BUY {quantity:.4f} {symbol} @ ${current_price:.2f} = ${dollar_amount:.2f}")
                return {'id': f'paper-{int(time.time())}', 'status': 'filled'}

            action_desc = f"BUY {symbol} ${dollar_amount:.2f}"
            try:
                with timeout(config.API_TIMEOUT_ORDER):
                    if config.IS_CRYPTO(symbol):
                        # robin_stocks crypto orders have no account_number param — always executes
                        # against the login's default account, not config.ACCOUNT_NUMBER.
                        order = rh.order_buy_crypto_by_price(symbol, round(dollar_amount, 2))
                    else:
                        order = rh.order_buy_fractional_by_price(
                            symbol, round(dollar_amount, 2), account_number=config.ACCOUNT_NUMBER)
            except TimeoutError:
                # Order state is genuinely unknown here — the request may have
                # reached Robinhood and filled even though we never got a response.
                # Never assume filled or unfilled; a human needs to check the account.
                log.error(f"⚠️ ORDER TIMEOUT — {action_desc} after {config.API_TIMEOUT_ORDER}s. "
                          f"Order status UNKNOWN — verify against the account before assuming "
                          f"filled or unfilled.")
                send_telegram_alert(f"⚠️ Order timeout — verify manually: {action_desc}")
                return None

            if order and order.get('id'):
                log.info(f"✓ [LIVE] BUY {symbol} ${dollar_amount:.2f} @ ~${current_price:.2f} "
                         f"| order {order['id']}")
                return order
            log.error(f"[LIVE] Buy REJECTED for {symbol}: {order}")
            return None
        except Exception as e:
            log.error(f"Buy order failed for {symbol}: {e}")
            return None

    def place_sell_order(self, symbol: str, quantity: float):
        try:
            if config.PAPER_MODE:
                log.info(f"[PAPER] SELL {quantity:.4f} {symbol}")
                return {'id': f'paper-{int(time.time())}', 'status': 'filled'}

            action_desc = f"SELL {quantity:.6f} {symbol}"
            try:
                with timeout(config.API_TIMEOUT_ORDER):
                    if config.IS_CRYPTO(symbol):
                        order = rh.order_sell_crypto_by_quantity(symbol, round(quantity, 8))
                    else:
                        order = rh.order_sell_fractional_by_quantity(
                            symbol, round(quantity, 6), account_number=config.ACCOUNT_NUMBER)
            except TimeoutError:
                log.error(f"⚠️ ORDER TIMEOUT — {action_desc} after {config.API_TIMEOUT_ORDER}s. "
                          f"Order status UNKNOWN — POSITION MAY STILL BE OPEN — verify against "
                          f"the account before assuming filled or unfilled.")
                send_telegram_alert(f"⚠️ Order timeout — verify manually: {action_desc}")
                return None

            if order and order.get('id'):
                log.info(f"✓ [LIVE] SELL {quantity:.6f} {symbol} | order {order['id']}")
                return order
            log.error(f"[LIVE] Sell REJECTED for {symbol}: {order} — POSITION MAY STILL BE OPEN")
            return None
        except Exception as e:
            log.error(f"Sell order failed for {symbol}: {e}")
            return None

    def get_current_portfolio_value(self) -> float:
        # PAPER_MODE never touches the real account — it was previously calling
        # rh.load_portfolio_profile() unconditionally, which (after account_number
        # routing was added) returned the real funded account's real, unmoving
        # equity instead of the simulated one, permanently tripping the daily
        # drawdown gate. Cash + open-position mark-to-market is the correct paper
        # equity (the old fallback here double-counted: it added position market
        # value on top of the full starting balance instead of the cash actually
        # spent on it).
        if config.PAPER_MODE:
            value = self.cash
            for symbol, position in self.positions.items():
                price = self.get_current_price(symbol)
                if price:
                    value += price * position['remaining_qty']
            return value
        portfolio = safe_api_call(rh.load_portfolio_profile, account_number=config.ACCOUNT_NUMBER,
                                   timeout_secs=config.API_TIMEOUT_PROFILE)
        if portfolio and portfolio.get('equity'):
            return float(portfolio['equity'])
        return self.initial_portfolio_value

    def check_buying_power(self, position_dollars: float) -> bool:
        if config.PAPER_MODE:
            # Real cash check against the simulated ledger — MAX_POSITIONS(5) x
            # MAX_POSITION_PCT(25%) can size up to 125% of portfolio value, so
            # without this a paper account could "buy" more than it has.
            if position_dollars > self.cash:
                log.info(f"[PAPER] Insufficient simulated cash: ${self.cash:.2f} < ${position_dollars:.2f}")
                return False
            return True
        account = safe_api_call(rh.load_account_profile, account_number=config.ACCOUNT_NUMBER,
                                 timeout_secs=config.API_TIMEOUT_PROFILE)
        if account is None:
            return True  # can't verify — fail open, same as the prior any-error behavior
        buying_power = float(account.get('buying_power') or 0)
        if position_dollars > buying_power:
            log.warning(f"Insufficient buying power: ${buying_power:.2f} < ${position_dollars:.2f}")
            return False
        return True

    def print_stats(self):
        if self.stats['total_trades'] == 0:
            return
        win_rate = self.stats['winning_trades'] / self.stats['total_trades'] * 100
        roi = self.stats['total_profit'] / self.initial_portfolio_value * 100
        log.info(f"STATS: {self.stats['total_trades']} trades | "
                 f"{self.stats['winning_trades']} wins ({win_rate:.1f}%) | "
                 f"Profit: ${self.stats['total_profit']:.2f} ({roi:.1f}% ROI) | "
                 f"Open: {len(self.positions)}")

    def run(self):
        if not self.authenticate():
            return

        self.is_active = True
        session_end = time.time() + config.MAX_SESSION_SECONDS
        log.info(f"🤖 Bot started in {'PAPER' if config.PAPER_MODE else 'LIVE'} mode")
        log.info(f"Portfolio: ${self.initial_portfolio_value:.2f} | Max positions: {config.MAX_POSITIONS} | "
                 f"Watchlist: {', '.join(config.WATCHLIST)}")
        log.info(f"Session window: {config.MAX_SESSION_SECONDS/3600:.1f}h — "
                 f"all positions close at window end (crypto 24/7, stocks market hours)")

        try:
            while self.is_active:
                # Session window end — close everything, report, exit clean
                if time.time() >= session_end:
                    log.info("Session window ending — closing all positions")
                    self.close_all_positions()
                    ending_value = self.get_current_portfolio_value()
                    generate_daily_report(self.initial_portfolio_value, ending_value,
                                          self.trade_log, self.pdt_tracker)
                    if config.PAPER_MODE:
                        state.save_balance(ending_value)
                    log.info("Session complete — shutting down.")
                    break

                # [Opt7] Daily risk gate — halt NEW entries if loss limits hit,
                # but keep managing exits so open positions are never stranded
                current_value = self.get_current_portfolio_value()
                halted = self.daily_risk_gate.should_halt(current_value)
                if halted:
                    log.warning("Daily risk gate triggered — no new entries this session")

                try:
                    if not halted:
                        self.scan_for_entries()
                    self.manage_exits()
                    self.print_stats()
                except Exception as e:
                    log.error(f"Scan cycle error: {e}")
                    traceback.print_exc()

                time.sleep(config.SCAN_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            log.info("Shutting down — closing all positions...")
            self.close_all_positions()
            ending_value = self.get_current_portfolio_value()
            generate_daily_report(self.initial_portfolio_value, ending_value,
                                   self.trade_log, self.pdt_tracker)
            if config.PAPER_MODE:
                state.save_balance(ending_value)
            self.is_active = False


if __name__ == '__main__':
    bot = TradingBot()
    bot.run()
