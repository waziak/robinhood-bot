"""Canonical account selection. Every live broker call goes through AccountGuard; nothing may reach another account."""
import os
import time
from dataclasses import dataclass

SUPPORTED = 'SUPPORTED'
UNSUPPORTED_FOR_LIVE_AUTOMATION = 'UNSUPPORTED_FOR_LIVE_AUTOMATION'

# Verified against robin_stocks 3.x source (2026-09-13):
#  equity orders/positions/open orders build URLs from an explicit account_number;
#  order_crypto() always uses load_crypto_profile() (the login's default crypto account) — no way to target ••••4508;
#  options are out of scope for week-1.
ASSET_CLASS_SUPPORT = {
    'equity': (SUPPORTED, 'orders, positions and open orders are addressed by explicit account_number'),
    'crypto': (UNSUPPORTED_FOR_LIVE_AUTOMATION, 'robin_stocks crypto orders use the default crypto profile; cannot be pinned to the trading account'),
    'option': (UNSUPPORTED_FOR_LIVE_AUTOMATION, 'options disabled'),
}


class AccountVerificationError(Exception):
    pass


@dataclass(frozen=True)
class VerifiedAccount:
    account_number: str
    last4: str
    type: str
    verified_at: float


def expected_last4() -> str:
    v = os.getenv('EXPECTED_ACCOUNT_LAST4', '4508').strip()
    if len(v) != 4 or not v.isdigit():
        raise AccountVerificationError('EXPECTED_ACCOUNT_LAST4 must be exactly 4 digits')
    return v


class AccountGuard:
    def __init__(self, fetch_accounts, last4: str = None, expected_type: str = 'cash', clock=time.time):
        self.fetch_accounts, self.last4, self.expected_type, self.clock = fetch_accounts, last4 or expected_last4(), expected_type, clock
        self.verified = None

    def verify(self) -> VerifiedAccount:
        self.verified = None
        accounts = self.fetch_accounts()
        if not isinstance(accounts, list) or not accounts:
            raise AccountVerificationError('broker returned no account list')
        matches = [a for a in accounts if isinstance(a, dict) and str(a.get('account_number', '')).endswith(self.last4)]
        if len(matches) != 1:
            raise AccountVerificationError(f'expected exactly one account ending {self.last4}, found {len(matches)}')
        a = matches[0]
        if a.get('deactivated') or a.get('permanently_deactivated'):
            raise AccountVerificationError(f'account ••••{self.last4} is deactivated')
        if a.get('type') != self.expected_type:
            raise AccountVerificationError(f"account ••••{self.last4} type is {a.get('type')!r}, expected {self.expected_type!r}")
        self.verified = VerifiedAccount(str(a['account_number']), self.last4, a['type'], self.clock())
        return self.verified

    def require(self, asset_class: str, max_age: float = 0.0) -> VerifiedAccount:
        """Call immediately before any live order. max_age=0 forces a fresh broker round-trip."""
        support, why = ASSET_CLASS_SUPPORT.get(asset_class, (UNSUPPORTED_FOR_LIVE_AUTOMATION, 'unknown asset class'))
        if support != SUPPORTED:
            raise AccountVerificationError(f'{asset_class}: {UNSUPPORTED_FOR_LIVE_AUTOMATION} — {why}')
        if max_age <= 0 or self.verified is None or self.clock() - self.verified.verified_at > max_age:
            self.verify()
        return self.verified

    def check_order_account(self, order_response: dict) -> None:
        """Post-submit proof that the broker booked the order to the verified account."""
        url = str((order_response or {}).get('account', ''))
        if not self.verified or f'/accounts/{self.verified.account_number}/' not in url:
            raise AccountVerificationError('order response account does not match the verified trading account')
