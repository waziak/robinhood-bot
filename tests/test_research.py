import ast
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research import backtest, candidates, splits, stats
from research.backtest import Signal
from research.costs import CostModel, for_symbol

ROOT = Path(__file__).resolve().parents[1]


def bars(n=300, start='2026-06-01 13:30', freq='5min', seed=1, drift=0.0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=n, freq=freq, tz='UTC')
    c = 100 * np.exp(np.cumsum(rng.normal(drift, 0.002, n)))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + rng.uniform(0, 0.001, n))
    l = np.minimum(o, c) * (1 - rng.uniform(0, 0.001, n))
    return pd.DataFrame({'open': o, 'high': h, 'low': l, 'close': c, 'volume': rng.uniform(1e5, 2e5, n)}, index=idx)


def frame(rows):
    idx = pd.date_range('2026-06-01 14:00', periods=len(rows), freq='5min', tz='UTC')
    return pd.DataFrame(rows, columns=['open', 'high', 'low', 'close'], index=idx).assign(volume=1.0)


def test_costs_fill_against_us_and_scale():
    cm = CostModel(1.0, 3.0)
    assert cm.buy_fill(100.0) > 100.0 and cm.sell_fill(100.0) < 100.0
    assert cm.net_return(100, 100) < 0 and cm.scaled(2).net_return(100, 100) < cm.net_return(100, 100)
    assert for_symbol('BTC-USD').round_trip_bps() > for_symbol('SPY').round_trip_bps()


def test_entry_is_next_open_and_stop_beats_target_in_same_bar():
    df = frame([[100, 100, 100, 100], [101, 101, 101, 101], [101, 110, 90, 101], [101, 101, 101, 101]])
    t = backtest.run(df, [Signal(0, 95, 105, 10)], CostModel(0, 0, tick=1e-9))
    assert t.iloc[0]['entry_raw'] == 101 and t.iloc[0]['exit_reason'] == 'stop' and t.iloc[0]['exit_raw'] == 95


def test_gap_through_stop_fills_at_open():
    df = frame([[100, 100, 100, 100], [100, 100.5, 99.5, 100], [90, 91, 89, 90]])
    t = backtest.run(df, [Signal(0, 98, None, 5)], CostModel(0, 0, tick=1e-9))
    assert t.iloc[0]['exit_reason'] == 'stop_gap' and t.iloc[0]['exit_raw'] == 90


def test_gap_invalidating_setup_skips_entry_and_last_bar_signal_ignored():
    df = frame([[100, 100, 100, 100], [94, 95, 93, 94], [94, 94, 94, 94]])
    assert len(backtest.run(df, [Signal(0, 95, None, 5), Signal(2, 90, None, 5)], CostModel(0, 0))) == 0


def test_overlapping_signals_skipped_unless_standalone():
    df = bars(50)
    sigs = [Signal(5, 1, None, 10), Signal(8, 1, None, 10)]
    assert len(backtest.run(df, sigs, CostModel(0, 0))) == 1
    assert len(backtest.run(df, sigs, CostModel(0, 0), overlap=True)) == 2


def test_exit_rule_exits_next_open():
    df = frame([[100, 100, 100, 100]] * 3 + [[105, 106, 104, 105]] * 3)
    rule = np.array([False, False, True, False, False, False])
    t = backtest.run(df, [Signal(0, 50, None, 100)], CostModel(0, 0, tick=1e-9), exit_rule=rule)
    assert t.iloc[0]['exit_reason'] == 'rule' and t.iloc[0]['exit_raw'] == 105


def _signal_keys(sigs):
    return [(s.i, round(s.stop, 8), None if s.target is None else round(s.target, 8)) for s in sigs]


@pytest.mark.parametrize('fn,params,freq,n', [
    (candidates.orb_continuation, {'or_bars': 6, 'rvol_min': 0.0, 'last_entry_minute': 690}, '5min', 78 * 15),
    (candidates.vwap_pullback, {'min_session_ret': -1, 'start_minute': 600, 'end_minute': 900, 'touch_tol': 0.002, 'stop_buffer': 0.001}, '5min', 78 * 15),
    (candidates.crypto_tsmom, {'lookback_h': 24, 'sma_h': 48, 'stop_pct': 0.05, 'hold_h': 24}, '1h', 600),
])
def test_candidates_have_no_lookahead(fn, params, freq, n):
    if freq == '5min':
        days = pd.bdate_range('2026-03-02', periods=n // 78, tz='America/New_York')
        idx = pd.DatetimeIndex([d + pd.Timedelta(minutes=570 + 5 * k) for d in days for k in range(78)]).tz_convert('UTC')
        df = bars(len(idx), seed=3)
        df.index = idx
    else:
        df = bars(n, freq=freq, seed=4, drift=0.0005)
    cut = int(len(df) * 0.6)
    full = [s for s in fn(df, params) if s.i < cut - 1]
    trunc = [s for s in fn(df.iloc[:cut], params) if s.i < cut - 1]
    for s in full + trunc:  # max_hold may legitimately depend on remaining session length; compare decisions only
        s.max_hold = 0
    assert _signal_keys(full) == _signal_keys(trunc)


def test_daily_rule_strategies_have_no_lookahead():
    df = bars(900, freq='1D', seed=5, drift=0.0004)
    cut = 600
    for fn, params in ((candidates.rsi2_mean_reversion, {'rsi_max': 30, 'stop_pct': 0.1, 'max_hold': 10}),
                       (candidates.trend_sma200, {'stop_pct': 0.3})):
        (full, rule_full), (trunc, rule_trunc) = fn(df, params), fn(df.iloc[:cut], params)
        assert _signal_keys([s for s in full if s.i < cut]) == _signal_keys(trunc)
        assert np.array_equal(rule_full[:cut], rule_trunc)


def test_production_strategy_adapter_has_no_lookahead():
    from research import current
    df = bars(320, seed=9, drift=0.0003)
    df.index = pd.date_range('2026-06-01', periods=len(df), freq='5min', tz='UTC')
    reg = current.regime_series(df)
    cut = 290
    full = [s for s in current.signals('BTC-USD', df, for_symbol('BTC-USD'), reg, True) if s.i < cut - 1]
    trunc = current.signals('BTC-USD', df.iloc[:cut], for_symbol('BTC-USD'), reg[:cut], True)
    assert _signal_keys(full) == _signal_keys([s for s in trunc if s.i < cut - 1])


def test_splits_are_ordered_non_overlapping_and_folds_precede_test():
    idx = pd.date_range('2020-01-01', '2025-01-01', freq='1D', tz='UTC')
    w = splits.bounds(idx)
    assert w['train'][0] < w['train'][1] == w['validation'][0] < w['validation'][1] == w['test'][0] < w['test'][1]
    for tr, te in splits.walk_forward(idx[idx < w['test'][0]]):
        assert tr[1] == te[0] and te[1] <= w['test'][0] + pd.Timedelta(days=1)


def test_test_set_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(splits, 'LOG', str(tmp_path / 'log.md'))
    assert not splits.test_already_used('s', {'a': 1})
    splits.record_test_use('s', {'a': 1}, 'result')
    assert splits.test_already_used('s', {'a': 1}) and not splits.test_already_used('s', {'a': 2})


def test_stats_basics_and_bootstrap_determinism():
    t = pd.DataFrame({'net_ret': [0.01, -0.005, 0.02, -0.01], 'gross_ret': [0.011, -0.004, 0.021, -0.009]})
    s = stats.summarize(t)
    assert s['n'] == 4 and s['win_rate'] == 0.5 and abs(s['profit_factor'] - 0.03 / 0.015) < 1e-9
    assert stats.bootstrap_mean(t['net_ret']) == stats.bootstrap_mean(t['net_ret'])
    assert abs(stats.max_drawdown([0.01, -0.02, -0.01, 0.05]) - 0.03) < 1e-12
    cal = stats.calibration(t.assign(score=[10, 30, 90, 95], mfe=0.0, mae=0.0))
    assert cal.loc['80-100', 'n'] == 2


def test_research_never_imports_execution_or_broker():
    for path in (ROOT / 'research').glob('*.py'):
        tree = ast.parse(path.read_text())
        names = [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        names += [n.module or '' for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        assert not any(m.startswith(('trader.broker', 'trader.execution', 'trader.agent', 'trader.credentials', 'robin_stocks'))
                       for m in names), path.name
