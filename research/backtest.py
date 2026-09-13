"""Bar-level, long-only, one-position-per-symbol backtester with no lookahead.

Timing contract:
- A Signal at bar i may only use data from bars <= i (verified by tests/test_research.py truncation tests).
- Entry fills at the OPEN of bar i+1 (plus costs). Nothing from bar i+1 is known at decision time.
- Exits: gap through stop -> fill at that bar's open; intrabar stop -> stop price; if a bar touches both stop and
  target, the stop is assumed first (conservative). Time and session-end exits fill at the bar close; rule exits
  (known at bar k's close) fill at bar k+1's open.
"""
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from research.costs import CostModel


@dataclass
class Signal:
    i: int
    stop: float
    target: Optional[float]
    max_hold: int
    meta: dict = field(default_factory=dict)


def session_last_bar(index: pd.DatetimeIndex, tz: str = 'America/New_York') -> np.ndarray:
    local = index.tz_convert(tz)
    d = np.asarray(local.date)
    last = np.zeros(len(d), dtype=bool)
    if len(d):
        last[:-1] = d[:-1] != d[1:]
        last[-1] = True
    return last


def run(df: pd.DataFrame, signals: list, cost: CostModel, flatten_daily: bool = False, exit_rule=None,
        overlap: bool = False) -> pd.DataFrame:
    """overlap=False: one position at a time (later signals while in a trade are skipped).
    overlap=True: every signal evaluated standalone (for calibration / signal-quality studies)."""
    o, h, l, c = (df[k].to_numpy(float) for k in ('open', 'high', 'low', 'close'))
    idx, n = df.index, len(df)
    last_bar = session_last_bar(idx) if flatten_daily else None
    trades, busy_until, skipped = [], -1, 0
    for s in sorted(signals, key=lambda s: s.i):
        j = s.i + 1
        if j >= n:
            continue
        if not overlap and s.i <= busy_until:
            skipped += 1
            continue
        if flatten_daily and last_bar[s.i]:
            continue  # would enter at the next session's open: not an intraday trade
        entry_raw = o[j]
        if not (s.stop < entry_raw) or (s.target is not None and s.target <= entry_raw):
            continue  # the opening gap already invalidated the setup
        end = min(n - 1, j + max(1, s.max_hold) - 1)
        exit_raw, reason, k = c[end], 'time', end
        for k in range(j, end + 1):
            if k > j and o[k] <= s.stop:
                exit_raw, reason = o[k], 'stop_gap'
                break
            if l[k] <= s.stop:
                exit_raw, reason = s.stop, 'stop'
                break
            if s.target is not None and k > j and o[k] >= s.target:
                exit_raw, reason = o[k], 'target_gap'
                break
            if s.target is not None and h[k] >= s.target:
                exit_raw, reason = s.target, 'target'
                break
            if flatten_daily and last_bar[k]:
                exit_raw, reason = c[k], 'session_end'
                break
            if exit_rule is not None and exit_rule[k] and k + 1 < n:
                k += 1
                exit_raw, reason = o[k], 'rule'
                break
        else:
            k = end
        entry_fill, exit_fill = cost.buy_fill(entry_raw), cost.sell_fill(exit_raw)
        net = cost.net_return(entry_raw, exit_raw)
        risk = entry_fill - s.stop
        last_path = k if reason != 'rule' else k - 1
        trades.append({
            'entry_ts': idx[j], 'exit_ts': idx[k], 'signal_i': s.i, 'bars_held': k - j + 1, 'exit_reason': reason,
            'entry_raw': entry_raw, 'exit_raw': exit_raw, 'entry_fill': entry_fill, 'exit_fill': exit_fill,
            'gross_ret': exit_raw / entry_raw - 1, 'net_ret': net, 'cost_ret': (exit_raw / entry_raw - 1) - net,
            'r_multiple': (exit_fill - entry_fill) / risk if risk > 0 else np.nan,
            'mfe': h[j:last_path + 1].max() / entry_raw - 1, 'mae': l[j:last_path + 1].min() / entry_raw - 1,
            **s.meta,
        })
        busy_until = max(busy_until, k)
    out = pd.DataFrame(trades)
    out.attrs['skipped_overlapping'] = int(skipped)
    return out
