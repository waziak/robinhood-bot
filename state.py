"""Cross-session paper-trading equity persistence.

GitHub Actions runners are ephemeral — nothing in memory survives between the
4 scheduled sessions per day. Real trading naturally persists equity in the
broker's own ledger, but PAPER_MODE has no broker ledger, so without this file
every session silently reset to config.PORTFOLIO_SIZE and the "compounding"
in the daily report was fictional. Committed to the repo (not just GitHub's
cache) so it survives cache eviction and stays visible in git history.
"""
import json
import os

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'state.json')


def load_balance(default: float) -> float:
    try:
        with open(_PATH) as f:
            return float(json.load(f)['balance'])
    except Exception:
        return default


def save_balance(balance: float):
    with open(_PATH, 'w') as f:
        json.dump({'balance': round(balance, 2)}, f)
