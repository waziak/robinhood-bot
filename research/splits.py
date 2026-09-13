"""Chronological TRAIN / VALIDATION / TEST separation and walk-forward folds.

The final TEST window is sealed: `research/TEST_SET_LOG.md` records every evaluation on it. A strategy may be
evaluated on TEST only once, only after it passed VALIDATION, and with parameters frozen beforehand.
"""
import hashlib
import json
import os
from datetime import datetime, timezone

import pandas as pd

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'TEST_SET_LOG.md')


def bounds(index: pd.DatetimeIndex, train: float = 0.6, validation: float = 0.2) -> dict:
    """Split points on time (not row count per symbol), so every symbol shares the same calendar windows."""
    t0, t1 = index.min(), index.max()
    span = t1 - t0
    return {'train': (t0, t0 + span * train), 'validation': (t0 + span * train, t0 + span * (train + validation)),
            'test': (t0 + span * (train + validation), t1 + pd.Timedelta(seconds=1))}


def in_window(ts: pd.Series, window: tuple) -> pd.Series:
    return (ts >= window[0]) & (ts < window[1])


def walk_forward(index: pd.DatetimeIndex, folds: int = 4, min_train: float = 0.4) -> list:
    """Expanding-window folds over the pre-test period: train on [start, cut_k), evaluate on [cut_k, cut_k+1)."""
    t0, t1 = index.min(), index.max()
    span = t1 - t0
    step = span * (1 - min_train) / folds
    return [((t0, t0 + span * min_train + step * k), (t0 + span * min_train + step * k, t0 + span * min_train + step * (k + 1)))
            for k in range(folds)]


def spec_hash(name: str, params: dict) -> str:
    return hashlib.sha256(json.dumps({'name': name, 'params': params}, sort_keys=True).encode()).hexdigest()[:12]


def test_already_used(name: str, params: dict) -> bool:
    return os.path.exists(LOG) and spec_hash(name, params) in open(LOG).read()


def record_test_use(name: str, params: dict, result_line: str):
    new = not os.path.exists(LOG)
    with open(LOG, 'a') as f:
        if new:
            f.write('# Sealed TEST set evaluations (append-only)\n\n| when (UTC) | strategy | spec hash | params | result |\n|---|---|---|---|---|\n')
        f.write(f"| {datetime.now(timezone.utc):%Y-%m-%d %H:%M} | {name} | {spec_hash(name, params)} | "
                f"`{json.dumps(params, sort_keys=True)}` | {result_line} |\n")
