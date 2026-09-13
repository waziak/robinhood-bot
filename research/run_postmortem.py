"""Post-mortem of the production strategies over the widest intraday history available.

  venv/bin/python -m research.run_postmortem   ->  research/CURRENT_STRATEGY_POSTMORTEM.md
"""
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from research import backtest, costs, current, data, stats

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'CURRENT_STRATEGY_POSTMORTEM.md')
HYPOTHESES = {
    'trend_pullback': ('In an established intraday uptrend (SMA20>SMA50, rising SMA50) a shallow pullback to EMA20 with RSI 40-55 '
                       'and an up-close resumes the trend.', 'up'),
    'breakout': ('A close above the prior 2-hour high on range expansion (and volume, when available) starts a continuation move.', 'up'),
    'mean_reversion': ('In a flat regime a close below the lower Bollinger band with RSI<35 and a reversal bar reverts to SMA20.', 'range'),
}


def align(ref_index, ref_values, target_index):
    pos = np.searchsorted(ref_index.asi8, target_index.asi8, side='right') - 1
    out = np.where(pos >= 0, ref_values[np.clip(pos, 0, None)], 'unknown')
    return out


def build():
    frames = []
    universes = [('cb', data.CRYPTO, True), ('yf', data.ETFS + data.STOCKS, False)]
    refs = {}
    for source, ref in (('cb', 'BTC-USD'), ('yf', 'SPY')):
        df = data.load(source, ref, '5m')
        refs[source] = (df.index, current.regime_series(df))
    coverage, proposals = [], []
    for source, symbols, crypto in universes:
        for sym in symbols:
            try:
                df = data.load(source, sym, '5m')
            except FileNotFoundError:
                continue
            cost = costs.for_symbol(sym)
            sigs = current.signals(sym, df, cost, align(*refs[source], df.index), crypto)
            coverage.append((sym, len(df), df.index[0], df.index[-1], len(sigs)))
            fwd = current.forward_returns(df, [s.i for s in sigs])
            meta = pd.DataFrame([s.meta for s in sigs])
            if len(meta):
                proposals.append(pd.concat([meta.reset_index(drop=True), fwd.reset_index(drop=True)], axis=1))
            allowed = np.flatnonzero(current.entry_window_mask(df.index, crypto)[current.WINDOW:-1]) + current.WINDOW
            base = current.forward_returns(df, list(allowed[::3])).mean()
            base['symbol'] = sym
            frames.append(('baseline', base))
            for strat in HYPOTHESES:
                ss = [s for s in sigs if s.meta['strategy'] == strat]
                for label, subset, overlap in (('sequential', ss, False), ('standalone', ss, True),
                                               ('gated', [s for s in ss if s.meta['gated']], False)):
                    t = backtest.run(df, subset, cost, flatten_daily=not crypto, overlap=overlap)
                    if len(t):
                        t['asset'], t['book'] = 'crypto' if crypto else 'equity', label
                        frames.append(('trades', t))
    trades = pd.concat([f for k, f in frames if k == 'trades'], ignore_index=True) if frames else pd.DataFrame()
    baseline = pd.DataFrame([f for k, f in frames if k == 'baseline'])
    return trades, pd.concat(proposals, ignore_index=True) if proposals else pd.DataFrame(), baseline, coverage


def cost_multiples(t: pd.DataFrame, ks=(0, 1, 2, 3)) -> dict:
    out = {}
    for k in ks:
        net = [costs.for_symbol(s).scaled(k).net_return(a, b) if k else b / a - 1
               for s, a, b in zip(t['symbol'], t['entry_raw'], t['exit_raw'])]
        out[f'{k}x'] = 100 * float(np.mean(net)) if net else np.nan
    return out


def attribution(t: pd.DataFrame, props: pd.DataFrame, base: pd.DataFrame, strat: str, asset: str) -> list:
    L = []
    s = stats.summarize(t)
    if s['n'] == 0:
        return ['- no trades']
    p = props[(props['strategy'] == strat)]
    p = p[p['symbol'].str.endswith('-USD')] if asset == 'crypto' else p[~p['symbol'].str.endswith('-USD')]
    b = base[base['symbol'].str.endswith('-USD')] if asset == 'crypto' else base[~base['symbol'].str.endswith('-USD')]
    for hz in (6, 12, 48):
        col = f'fwd_{hz}'
        if col in p and len(p):
            edge = 100 * (p[col].mean() - b[col].mean())
            tstat = p[col].mean() / (p[col].std(ddof=1) / np.sqrt(len(p))) if len(p) > 1 else np.nan
            L.append(f'- Predictive content, {hz} bars: signal fwd return {100 * p[col].mean():+.3f}% vs unconditional '
                     f'{100 * b[col].mean():+.3f}% → edge {edge:+.3f}% (t={tstat:.2f}, n={len(p)})')
    gross, net = s['gross_mean_pct'], s['mean_pct']
    L.append(f"- Costs: gross {gross:+.3f}% → net {net:+.3f}% per trade; costs {s['cost_mean_pct']:.3f}% "
             f"({'costs exceed the entire gross edge' if gross > 0 > net else 'gross edge itself is negative' if gross <= 0 else 'edge survives costs'})")
    reached_1r = (t['mfe'] >= t['planned_risk_pct']) if 'planned_risk_pct' in t else pd.Series(False, index=t.index)
    L.append(f"- Exits: {100 * reached_1r.mean():.0f}% of trades moved ≥1R in favour at some point; "
             f"{100 * (reached_1r & (t['net_ret'] <= 0)).mean():.0f}% of all trades reached +1R and still lost money. "
             f"Exit mix: {t['exit_reason'].value_counts(normalize=True).round(2).to_dict()}")
    early = (t['exit_reason'].str.startswith('stop') & (t['bars_held'] <= 3)).mean()
    rr = t['planned_rr'].mean() if 'planned_rr' in t else np.nan
    need = 1 / (1 + rr) if rr == rr and rr > 0 else np.nan
    L.append(f"- Entries: {100 * early:.0f}% of trades stopped out within 3 bars; planned R:R {rr:.2f} needs win rate ≥ "
             f"{100 * need:.0f}% before costs, actual {100 * s['win_rate']:.0f}%; realized mean R {t['r_multiple'].mean():+.2f}")
    intended = HYPOTHESES[strat][1]
    if 'regime' in t:
        inr, outr = t[t['regime'] == intended]['net_ret'], t[t['regime'] != intended]['net_ret']
        L.append(f"- Regime: intended '{intended}' net {100 * inr.mean() if len(inr) else float('nan'):+.3f}% (n={len(inr)}) "
                 f"vs other {100 * outr.mean() if len(outr) else float('nan'):+.3f}% (n={len(outr)})")
    lo, hi = s['ci95_mean_pct']
    L.append(f"- Noise: 95% bootstrap CI of mean net return [{lo:+.3f}%, {hi:+.3f}%], P(mean>0)={s['p_mean_positive']:.2f}")
    return L


def main():
    trades, props, base, coverage = build()
    now = datetime.now(timezone.utc)
    L = ['# Current Strategy Post-mortem', '', f'Generated {now:%Y-%m-%d %H:%M} UTC by `python -m research.run_postmortem`. '
         'Runs the production `trader.strategies` + `trader.scoring` code bar-by-bar with no lookahead; entries at the next bar open; '
         'stops assumed to hit before targets inside a bar; costs per `research/costs.py`.', '', '## Data', '',
         '| symbol | 5m bars | from | to | proposals |', '|---|---|---|---|---|']
    L += [f'| {s} | {n} | {a:%Y-%m-%d} | {b:%Y-%m-%d} | {k} |' for s, n, a, b, k in coverage]
    L += ['', 'Crypto: Coinbase public candles (volume zeroed to match Robinhood). Equities: Yahoo Finance 5m (max 60 days available). '
          'Single stocks are current survivors (survivorship bias); ETFs are not affected.', '']
    for strat, (hyp, reg) in HYPOTHESES.items():
        L += [f'## {strat}', '', f'**Hypothesis:** {hyp} **Intended regime:** {reg}.', '']
        for asset in ('crypto', 'equity'):
            seq = trades[(trades['strategy'] == strat) & (trades['asset'] == asset) & (trades['book'] == 'sequential')] if len(trades) else pd.DataFrame()
            gated = trades[(trades['strategy'] == strat) & (trades['asset'] == asset) & (trades['book'] == 'gated')] if len(trades) else pd.DataFrame()
            L += [f'### {asset}', '']
            if len(seq) == 0:
                L += ['_no proposals_', '']
                continue
            s = stats.summarize(seq)
            L += ['| metric | all proposals (one position at a time) | risk-engine approved only |', '|---|---|---|']
            g = stats.summarize(gated)
            for key, label in (('n', 'trades'), ('gross_mean_pct', 'gross mean %'), ('cost_mean_pct', 'est. cost %'),
                               ('mean_pct', 'net mean % (expectancy)'), ('win_rate', 'win rate'), ('avg_win_pct', 'avg winner %'),
                               ('avg_loss_pct', 'avg loser %'), ('profit_factor', 'profit factor'), ('max_dd_pct', 'max drawdown % (sum of returns)'),
                               ('avg_bars_held', 'avg holding (5m bars)'), ('mfe_pct', 'avg MFE %'), ('mae_pct', 'avg MAE %'), ('t_stat', 't-stat')):
                fv = lambda d: ('—' if d.get('n', 0) == 0 else f'{d[key]:.3f}' if isinstance(d[key], float) else str(d[key]))
                L.append(f'| {label} | {fv(s)} | {fv(g)} |')
            L += ['', f"Cost sensitivity (net mean % at 0x/1x/2x/3x costs): {cost_multiples(seq)}", '', '**Why it fails / attribution**', '']
            L += attribution(seq, props, base, strat, asset) + ['']
            for col, title in (('regime', 'regime'), ('hour_et', 'hour (ET)'), ('symbol', 'symbol'), ('exit_reason', 'exit reason')):
                L += [f'By {title}:', '', stats.fmt_table(stats.breakdown(seq, col)), '']
            seq = seq.assign(vol_bucket=pd.qcut(seq['atr_pct'], 3, labels=['low vol', 'mid vol', 'high vol'], duplicates='drop'))
            L += ['By volatility tercile (ATR% of price):', '', stats.fmt_table(stats.breakdown(seq, 'vol_bucket')), '']
            if seq['rel_volume'].notna().any():
                seq = seq.assign(rv_bucket=pd.cut(seq['rel_volume'], [0, 0.8, 1.5, 1e9], labels=['<0.8x', '0.8-1.5x', '>1.5x']))
                L += ['By relative volume:', '', stats.fmt_table(stats.breakdown(seq, 'rv_bucket')), '']
    standalone = trades[trades['book'] == 'standalone'] if len(trades) else pd.DataFrame()
    L += ['## Score calibration (every proposal evaluated standalone)', '']
    if len(standalone):
        L += [stats.fmt_table(stats.calibration(standalone)), '',
              f"Spearman rank correlation score vs net return: {stats.spearman(standalone['score'], standalone['net_ret']):+.3f} "
              f"(n={len(standalone)}); vs 12-bar forward return: "
              f"{stats.spearman(props['score'], props.get('fwd_12', pd.Series(dtype=float))):+.3f}", '']
        for strat in HYPOTHESES:
            sub = standalone[standalone['strategy'] == strat]
            L.append(f"- {strat}: Spearman {stats.spearman(sub['score'], sub['net_ret']):+.3f} (n={len(sub)})")
    with open(OUT, 'w') as f:
        f.write('\n'.join(L) + '\n')
    print(f'wrote {OUT}: {len(trades)} trade rows, {len(props)} proposals')


if __name__ == '__main__':
    main()
