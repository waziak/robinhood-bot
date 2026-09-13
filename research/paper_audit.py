"""Audit of the legacy paper bot: IDEALIZED paper P&L (fills at Robinhood mark/last price, no costs) versus
REALISTIC ESTIMATED P&L (same trades, minus a round trip of spread + slippage on every entry's notional).

Input: a directory of per-run log extracts (one file per GitHub Actions run).
"""
import argparse
import json
import os
import re

BUY = re.compile(r'\[PAPER\] BUY ([\d.]+) (\w+) @ \$([\d.]+) = \$([\d.]+)')
SELL = re.compile(r'\[PAPER\] SELL ([\d.]+) (\w+)')
PNL = re.compile(r'Daily P&L:\s+\$([+-][\d.]+)')

# Round-trip cost in bps of notional (full spread + slippage both sides), low / mid / high scenarios.
BANDS = {
    'crypto': (30, 60, 120),      # BTC, ETH on Robinhood
    'doge': (80, 150, 250),
    'leveraged_etf': (6, 12, 24),  # TQQQ, SQQQ
    'etf': (3, 6, 12),             # SPY, QQQ
    'stock': (5, 10, 20),          # TSLA, NVDA, AAPL
}


def bucket(sym: str) -> str:
    return {'BTC': 'crypto', 'ETH': 'crypto', 'DOGE': 'doge', 'TQQQ': 'leveraged_etf', 'SQQQ': 'leveraged_etf',
            'SPY': 'etf', 'QQQ': 'etf'}.get(sym, 'stock')


TS = re.compile(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]')
# Commit 465fef3 (2026-09-08 04:05 UTC) fixed paper valuation: before it, every session restarted at $50 and
# marked positions against the wrong equity, so pre-fix session P&L is not evidence of anything.
VALUATION_FIX_UTC = '2026-09-08 04:06:00'


def audit(log_dir: str, clean_since: str = VALUATION_FIX_UTC) -> dict:
    sessions = []
    for name in sorted(os.listdir(log_dir)):
        text = open(os.path.join(log_dir, name), errors='ignore').read()
        if 'Bot started in PAPER' not in text:
            continue
        buys = [(m.group(2), float(m.group(4))) for m in BUY.finditer(text)]
        pnl, first = PNL.search(text), TS.search(text)
        sessions.append({'run': name.split('.')[0], 'buys': buys, 'sells': len(SELL.findall(text)),
                         'started': first.group(1) if first else '', 'idealized_pnl': float(pnl.group(1)) if pnl else None})
    contaminated = [s for s in sessions if s['idealized_pnl'] is not None and s['started'] < clean_since]
    result = {'pre_fix_sessions_excluded': len(contaminated),
              'pre_fix_reported_pnl_sum_INVALID': round(sum(s['idealized_pnl'] for s in contaminated), 2),
              'clean_since_utc': clean_since}
    sessions = [s for s in sessions if s['started'] >= clean_since]
    return {**result, **_summarize(sessions)}


def _summarize(sessions: list) -> dict:
    complete = [s for s in sessions if s['idealized_pnl'] is not None]
    idealized = sum(s['idealized_pnl'] for s in complete)
    notional = {}
    for s in complete:
        for sym, usd in s['buys']:
            notional[bucket(sym)] = notional.get(bucket(sym), 0.0) + usd
    realistic = {}
    for i, label in enumerate(('low_cost', 'mid_cost', 'high_cost')):
        cost = sum(usd * BANDS[b][i] / 1e4 for b, usd in notional.items())
        realistic[label] = {'estimated_costs': round(cost, 2), 'realistic_pnl': round(idealized - cost, 2)}
    by_symbol = {}
    for s in complete:
        for sym, usd in s['buys']:
            d = by_symbol.setdefault(sym, {'entries': 0, 'notional': 0.0})
            d['entries'] += 1
            d['notional'] = round(d['notional'] + usd, 2)
    return {
        'paper_sessions_found': len(sessions), 'sessions_with_final_report': len(complete),
        'sessions_without_report_excluded': len(sessions) - len(complete),
        'entries': sum(len(s['buys']) for s in complete), 'total_entry_notional': round(sum(notional.values()), 2),
        'notional_by_bucket': {k: round(v, 2) for k, v in notional.items()}, 'by_symbol': by_symbol,
        'idealized_pnl_sum_of_sessions': round(idealized, 2),
        'positive_sessions': sum(1 for s in complete if s['idealized_pnl'] > 0),
        'negative_sessions': sum(1 for s in complete if s['idealized_pnl'] < 0),
        'realistic_estimates': realistic, 'round_trip_bps_bands': BANDS,
    }


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('log_dir')
    print(json.dumps(audit(ap.parse_args().log_dir), indent=2))
