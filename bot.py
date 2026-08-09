#!/usr/bin/env python3
"""
Robinhood Multi-Indicator Trading Bot with Riskfolio-Lib Position Sizing.
$50 account — PDT-compliant, 3-of-5 scoring, runner exits, VWAP + volume gate.
"""

import time
import logging
import traceback
import pytz
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import robin_stocks.robinhood as rh

import config
import session_auth
from indicators import score_entry, check_volume_confirmation
from risk import calculate_hrp_weights, calculate_position_size, calculate_dynamic_stop, portfolio_drawdown_check

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

ET = pytz.timezone('America/New_York')  # [Opt6]


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
        self.initial_portfolio_value = config.PORTFOLIO_SIZE
        self.is_active = False
        self.pdt_tracker = PDTTracker()                    # [Opt1]
        self.daily_risk_gate = DailyRiskGate(config.PORTFOLIO_SIZE)  # [Opt7]
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
            try:
                profile = rh.load_account_profile()
                log.info(f"✓ Authenticated — account {profile.get('account_number')} | "
                         f"buying power ${float(profile.get('buying_power') or 0):.2f}")
            except Exception:
                pass
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
        try:
            if config.IS_CRYPTO(symbol):
                quote = rh.get_crypto_quote(symbol)
                if quote and quote.get('mark_price'):
                    return float(quote['mark_price'])
            else:
                quote = rh.get_quotes(symbol)
                if quote and len(quote) > 0 and quote[0]:
                    return float(quote[0]['last_trade_price'])
        except Exception as e:
            log.warning(f"Failed to get quote for {symbol}: {e}")
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

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(self.fetch_price_history, s): s for s in scan_symbols}
            for future in futures:
                symbol = futures[future]
                try:
                    series, historicals = future.result()
                    if series is not None and len(series) >= config.MIN_CANDLES:
                        self.price_histories[symbol] = series
                        self.raw_historicals[symbol] = historicals
                except Exception as e:
                    log.warning(f"Error fetching {symbol}: {e}")

        if not self.price_histories:
            log.warning("No price histories available")
            return

        hrp_weights = calculate_hrp_weights({s: h.values for s, h in self.price_histories.items()})
        log.info(f"HRP weights: {', '.join(f'{s}={w:.3f}' for s, w in sorted(hrp_weights.items()))}")

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

            weight = hrp_weights.get(symbol, 1.0 / len(config.WATCHLIST))
            position_dollars = calculate_position_size(symbol, weight, current_portfolio_value, current_price)

            if not self.check_buying_power(position_dollars):
                log.info(f"Skipping {symbol} — insufficient buying power")
                continue

            quantity = position_dollars / current_price
            dynamic_stop = calculate_dynamic_stop(symbol, prices)

            order = self.place_buy_order(symbol, position_dollars)
            if order:
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
                    self._record_exit(symbol, position, current_price, remaining_qty, is_win=True)
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

            if config.IS_CRYPTO(symbol):
                order = rh.order_buy_crypto_by_price(symbol, round(dollar_amount, 2))
            else:
                order = rh.order_buy_fractional_by_price(symbol, round(dollar_amount, 2))
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

            if config.IS_CRYPTO(symbol):
                order = rh.order_sell_crypto_by_quantity(symbol, round(quantity, 8))
            else:
                order = rh.order_sell_fractional_by_quantity(symbol, round(quantity, 6))
            if order and order.get('id'):
                log.info(f"✓ [LIVE] SELL {quantity:.6f} {symbol} | order {order['id']}")
                return order
            log.error(f"[LIVE] Sell REJECTED for {symbol}: {order} — POSITION MAY STILL BE OPEN")
            return None
        except Exception as e:
            log.error(f"Sell order failed for {symbol}: {e}")
            return None

    def get_current_portfolio_value(self) -> float:
        try:
            portfolio = rh.load_portfolio_profile()
            if portfolio and portfolio.get('equity'):
                return float(portfolio['equity'])
        except Exception as e:
            log.warning(f"Could not fetch portfolio value: {e}")
        portfolio_value = config.PORTFOLIO_SIZE
        for symbol, position in self.positions.items():
            price = self.get_current_price(symbol)
            if price:
                portfolio_value += price * position['remaining_qty']
        return portfolio_value

    def check_buying_power(self, position_dollars: float) -> bool:
        try:
            account = rh.load_account_profile()
            buying_power = float(account.get('buying_power') or 0)
            if position_dollars > buying_power:
                log.warning(f"Insufficient buying power: ${buying_power:.2f} < ${position_dollars:.2f}")
                return False
            return True
        except Exception as e:
            log.warning(f"Could not check buying power: {e}")
            return True

    def print_stats(self):
        if self.stats['total_trades'] == 0:
            return
        win_rate = self.stats['winning_trades'] / self.stats['total_trades'] * 100
        roi = self.stats['total_profit'] / config.PORTFOLIO_SIZE * 100
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
        log.info(f"Portfolio: ${config.PORTFOLIO_SIZE} | Max positions: {config.MAX_POSITIONS} | "
                 f"Watchlist: {', '.join(config.WATCHLIST)}")
        log.info(f"Session window: {config.MAX_SESSION_SECONDS/3600:.1f}h — "
                 f"all positions close at window end (crypto 24/7, stocks market hours)")

        try:
            while self.is_active:
                # Session window end — close everything, report, exit clean
                if time.time() >= session_end:
                    log.info("Session window ending — closing all positions")
                    self.close_all_positions()
                    generate_daily_report(config.PORTFOLIO_SIZE,
                                          self.get_current_portfolio_value(),
                                          self.trade_log, self.pdt_tracker)
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
            generate_daily_report(config.PORTFOLIO_SIZE,
                                   self.get_current_portfolio_value(),
                                   self.trade_log, self.pdt_tracker)
            self.is_active = False


if __name__ == '__main__':
    bot = TradingBot()
    bot.run()
