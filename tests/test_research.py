import ast
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research import backtest, baselines, candidates, portfolio, splits, stats
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


def test_summarize_and_consistency_are_row_order_independent():
    """Regression test: multi-symbol trades arrive concatenated symbol-block by symbol-block (all of SPY's
    trades, then all of QQQ's, ...), not chronologically. Sequence-dependent stats must sort by entry_ts first,
    or a shuffled input produces a different (wrong) drawdown/streak than the chronologically correct one."""
    ts = pd.date_range('2026-01-01', periods=8, freq='3D', tz='UTC')
    chrono = pd.DataFrame({'entry_ts': ts, 'exit_ts': ts, 'net_ret': [0.02, -0.01, -0.03, 0.01, -0.02, -0.01, 0.05, -0.01]})
    shuffled = chrono.sample(frac=1, random_state=3).reset_index(drop=True)  # e.g. symbol-block concatenation order
    a, b = stats.summarize(chrono), stats.summarize(shuffled)
    assert a['max_dd_pct'] == pytest.approx(b['max_dd_pct'])
    ca, cb = stats.consistency_metrics(chrono), stats.consistency_metrics(shuffled)
    assert ca['longest_losing_streak'] == cb['longest_losing_streak'] == 2  # the 3-in-a-row loss run, correctly found either way


def test_consistency_metrics_smoothness():
    # two losses, two wins, one big loss last -> exercise streaks, downside deviation, drawdown together
    ts = pd.date_range('2026-01-05', periods=5, freq='7D', tz='UTC')  # separate weeks
    t = pd.DataFrame({'entry_ts': ts, 'exit_ts': ts, 'net_ret': [0.01, -0.02, -0.01, 0.03, -0.05]})
    assert stats.longest_losing_streak(t['net_ret']) == 2  # the trailing single loss doesn't chain to the earlier pair
    assert stats.longest_winning_streak(t['net_ret']) == 1
    dd = stats.downside_deviation(t['net_ret'])
    assert dd > 0 and dd < t['net_ret'].std(ddof=1)  # only counts the downside half
    cm = stats.consistency_metrics(t, years=5 / 365.25)
    assert cm['weeks_active'] == 5 and 0 <= cm['pct_profitable_weeks'] <= 1
    assert cm['calmar_like'] == pytest.approx(t['net_ret'].sum() / stats.max_drawdown(t['net_ret']))


def test_period_returns_resamples_by_exit_week():
    ts = pd.to_datetime(['2026-01-01', '2026-01-02', '2026-01-10'], utc=True)  # first two share a week
    t = pd.DataFrame({'exit_ts': ts, 'net_ret': [0.01, 0.02, -0.01]})
    p = stats.period_returns(t, 'W')
    assert len(p) == 2 and abs(p.iloc[0] - 0.03) < 1e-12


def regime_switch_bars(n1, drift1, n2, drift2, seed=1, freq='1D'):
    """Two concatenated trend regimes with a genuine drift change, so trend-following rules actually flip at
    least once — a pure random walk with constant drift almost never triggers a real exit before data ends."""
    a, b = bars(n1, freq=freq, seed=seed, drift=drift1), bars(n1 + n2, freq=freq, seed=seed + 1, drift=drift2).iloc[n1:]
    scale = a['close'].iloc[-1] / b['open'].iloc[0]
    b = b[['open', 'high', 'low', 'close']] * scale
    b['volume'] = 1e5
    out = pd.concat([a, b])
    out.index = pd.date_range(a.index[0], periods=len(out), freq=freq, tz='UTC')
    return out


def test_monthly_sma_timing_no_lookahead_and_shape():
    # A trade still open when the series ends is force-closed with exit_reason='data_end' — that closing date is
    # an artifact of where the data happens to stop, not a lookahead violation, so it's excluded from comparison.
    df = regime_switch_bars(400, 0.003, 500, -0.004, seed=21)
    cut = 600
    closed = lambda rows: [r for r in rows if r['exit_reason'] != 'data_end' and r['exit_ts'] <= df.index[cut - 1]]
    full = closed(candidates.monthly_sma_timing(df, {'sma_months': 10}))
    trunc = closed(candidates.monthly_sma_timing(df.iloc[:cut], {'sma_months': 10}))
    key = lambda rows: [(r['entry_ts'], r['exit_ts']) for r in rows]
    assert key(full) == key(trunc) and len(full) > 0
    for r in full:
        assert r['entry_ts'] < r['exit_ts'] and r['exit_raw'] > 0


def test_sector_rotation_no_lookahead_and_single_holding_at_a_time():
    # Leadership switches partway (A leads, then B takes over) so the strategy actually rotates before the cutoff —
    # constant relative drift would just buy-and-hold the permanent leader and never produce a comparable "closed" trade.
    data = {'A': regime_switch_bars(300, 0.0025, 400, -0.0015, seed=1),
           'B': regime_switch_bars(300, 0.0002, 400, 0.0025, seed=2),
           'C': regime_switch_bars(300, -0.0005, 400, -0.0010, seed=3)}
    cut = 500
    cutoff_ts = list(data.values())[0].index[cut - 1]
    closed = lambda rows: [r for r in rows if r['exit_reason'] != 'data_end' and r['exit_ts'] <= cutoff_ts]
    full = closed(candidates.sector_rotation_monthly(data, {'lookback_months': 6}))
    trunc = closed(candidates.sector_rotation_monthly({s: d.iloc[:cut] for s, d in data.items()}, {'lookback_months': 6}))
    key = lambda rows: [(r['entry_ts'], r['exit_ts'], r['symbol']) for r in rows]
    assert key(full) == key(trunc) and len(full) > 0
    for a, b in zip(full, full[1:]):
        assert a['exit_ts'] <= b['entry_ts']  # never two positions open at once


def test_baselines_buy_and_hold_matches_total_return():
    df = bars(60, freq='1D', seed=2, drift=0.001)
    window = (df.index[0], df.index[-1] + pd.Timedelta(days=1))
    bh = baselines.buy_and_hold(df, window, CostModel(0, 0, tick=1e-9))
    assert abs((1 + bh['net_ret']).prod() - df['close'].iloc[-1] / df['close'].iloc[0]) < 1e-6


def test_baselines_random_entry_uses_matched_holding_periods():
    df = bars(300, freq='1D', seed=4)
    window = (df.index[0], df.index[-1] + pd.Timedelta(days=1))
    rng = np.random.default_rng(0)
    r = baselines.random_entries(df, window, 20, np.array([5, 5, 10]), CostModel(0, 0, tick=1e-9), rng)
    assert len(r) == 20 and set(r['bars_held']) <= {5, 10}


def test_capital_constrained_curve_splits_capital_across_concurrent_positions():
    cal = pd.date_range('2026-01-01', periods=10, freq='D', tz='UTC')
    # A: open the whole window, flat throughout. B: opens on day index 4, jumps +100% in one day (index 4->5) while
    # A is also open. On that one day both hold 50% of capital, so the portfolio should gain exactly half of B's
    # +100% jump = +50% that day, and nothing on any other day (both flat elsewhere) -> total return = +50%.
    b_close = [100.0] * 5 + [200.0] * 5
    price = {'A': pd.DataFrame({'close': [100.0] * 10}, index=cal), 'B': pd.DataFrame({'close': b_close}, index=cal)}
    trades = pd.DataFrame({'entry_ts': [cal[0], cal[4]], 'exit_ts': [cal[9], cal[9]], 'symbol': ['A', 'B']})
    r = portfolio.build(trades, price, cal)
    # day 0 itself has no attributable return yet (you buy AT that day's open); invested from day 1 onward = 9/10.
    assert r['max_concurrent_positions'] == 2 and r['pct_days_invested'] == pytest.approx(0.9)
    assert r['total_return_pct'] == pytest.approx(50.0, abs=1e-6)


def test_capital_constrained_curve_flat_when_nothing_open():
    cal = pd.date_range('2026-01-01', periods=5, freq='D', tz='UTC')
    price = {'A': pd.DataFrame({'close': [100.0, 110.0, 90.0, 80.0, 120.0]}, index=cal)}
    trades = pd.DataFrame({'entry_ts': [cal[0]], 'exit_ts': [cal[0]], 'symbol': ['A']})  # closes same day it opens
    r = portfolio.build(trades, price, cal)
    assert r['total_return_pct'] == pytest.approx(0.0, abs=1e-6) and r['pct_days_invested'] == 0.0


def test_portfolio_candidate_declared_correctly():
    names = {c['name']: c for c in candidates.CANDIDATES}
    assert names['sector_rotation_momentum']['kind'] == 'portfolio'
    assert len(names['sector_rotation_momentum']['universe']) >= 5


def test_research_never_imports_execution_or_broker():
    for path in (ROOT / 'research').glob('*.py'):
        tree = ast.parse(path.read_text())
        names = [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        names += [n.module or '' for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        assert not any(m.startswith(('trader.broker', 'trader.execution', 'trader.agent', 'trader.credentials', 'robin_stocks'))
                       for m in names), path.name
