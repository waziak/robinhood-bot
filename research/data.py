"""Historical bar acquisition for research only (public/unauthenticated sources; never the Keychain session).

  venv/bin/python -m research.data --all        # fetch the research universe into research/data/
"""
import argparse
import os
import time
from datetime import datetime, timezone

import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

# ETFs dominate the universe to limit survivorship bias; the single stocks are today's survivors and are flagged as such.
ETFS = ['SPY', 'QQQ', 'IWM', 'DIA', 'XLK', 'XLF', 'XLE', 'XLV', 'TLT', 'GLD']
STOCKS = ['AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'META']
CRYPTO = ['BTC-USD', 'ETH-USD']
COLS = ['open', 'high', 'low', 'close', 'volume']


def path(source: str, symbol: str, interval: str) -> str:
    return os.path.join(DATA_DIR, f'{source}_{symbol}_{interval}.csv.gz')


def save(df: pd.DataFrame, source: str, symbol: str, interval: str) -> str:
    os.makedirs(DATA_DIR, exist_ok=True)
    p = path(source, symbol, interval)
    df[COLS].to_csv(p, index_label='ts', compression='gzip')
    return p


def load(source: str, symbol: str, interval: str) -> pd.DataFrame:
    df = pd.read_csv(path(source, symbol, interval), index_col='ts', compression='gzip')
    df.index = pd.to_datetime(df.index, utc=True)
    return df.sort_index()[COLS].astype(float)


def available() -> list:
    if not os.path.isdir(DATA_DIR):
        return []
    return sorted(f[:-7].split('_', 2) for f in os.listdir(DATA_DIR) if f.endswith('.csv.gz'))


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df[~df.index.duplicated(keep='last')].sort_index()
    df = df.dropna(subset=['open', 'high', 'low', 'close'])
    return df[(df['high'] >= df['low']) & (df['close'] > 0)]


def fetch_coinbase(product: str, granularity: int, days: int) -> pd.DataFrame:
    import requests
    end = int(time.time()) // granularity * granularity
    start_all = end - days * 86400
    rows, t_end = {}, end
    while t_end > start_all:
        t_start = max(start_all, t_end - 300 * granularity)
        iso = lambda t: datetime.fromtimestamp(t, tz=timezone.utc).isoformat()
        for attempt in range(4):
            r = requests.get(f'https://api.exchange.coinbase.com/products/{product}/candles',
                             params={'granularity': granularity, 'start': iso(t_start), 'end': iso(t_end)},
                             headers={'User-Agent': 'research'}, timeout=20)
            if r.status_code == 429:
                time.sleep(2 * (attempt + 1))
                continue
            r.raise_for_status()
            for ts, low, high, open_, close, vol in r.json():
                rows[ts] = (open_, high, low, close, vol)
            break
        t_end = t_start
        time.sleep(0.34)
    df = pd.DataFrame.from_dict(rows, orient='index', columns=COLS)
    df.index = pd.to_datetime(df.index, unit='s', utc=True)
    return _clean(df)


def fetch_yfinance(symbol: str, interval: str, period: str) -> pd.DataFrame:
    import yfinance as yf
    df = yf.download(symbol, interval=interval, period=period, auto_adjust=(interval == '1d'), prepost=False,
                     progress=False, threads=False)
    if df is None or df.empty:
        raise RuntimeError(f'no yfinance data for {symbol} {interval}')
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)
    df.index = pd.to_datetime(df.index, utc=True)
    return _clean(df[COLS])


def fetch_all():
    jobs = []
    for sym in ETFS + STOCKS:
        jobs += [('yf', sym, '1d', lambda s=sym: fetch_yfinance(s, '1d', 'max')),
                 ('yf', sym, '1h', lambda s=sym: fetch_yfinance(s, '1h', '730d')),
                 ('yf', sym, '5m', lambda s=sym: fetch_yfinance(s, '5m', '60d'))]
    for prod in CRYPTO:
        jobs += [('cb', prod, '5m', lambda p=prod: fetch_coinbase(p, 300, 180)),
                 ('cb', prod, '1h', lambda p=prod: fetch_coinbase(p, 3600, 1095))]
    for source, sym, interval, fn in jobs:
        try:
            df = fn()
            save(df, source, sym, interval)
            print(f'{source:3} {sym:8} {interval:3} {len(df):7d} bars  {df.index[0]:%Y-%m-%d} → {df.index[-1]:%Y-%m-%d}')
        except Exception as e:
            print(f'{source:3} {sym:8} {interval:3} FAILED {type(e).__name__}: {str(e)[:100]}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--all', action='store_true')
    if ap.parse_args().all:
        fetch_all()
