import pytest

from trader.accounts import AccountGuard, AccountVerificationError

ACCOUNTS = [
    {'account_number': '705601441', 'type': 'margin', 'deactivated': False},
    {'account_number': '768435059', 'type': 'cash', 'deactivated': False},
    {'account_number': '554664508', 'type': 'cash', 'deactivated': False},
]


def guard(accounts=ACCOUNTS, **kw):
    return AccountGuard(lambda: accounts, **{'last4': '4508', **kw})


def test_verifies_expected_account():
    v = guard().verify()
    assert v.account_number == '554664508' and v.type == 'cash'


@pytest.mark.parametrize('accounts', [
    [],
    [a for a in ACCOUNTS if not a['account_number'].endswith('4508')],
    ACCOUNTS + [{'account_number': '999994508', 'type': 'cash'}],
    [{**ACCOUNTS[2], 'type': 'margin'}],
    [{**ACCOUNTS[2], 'deactivated': True}],
    None,
])
def test_rejects_missing_ambiguous_wrong_type_or_deactivated(accounts):
    with pytest.raises(AccountVerificationError):
        guard(accounts).verify()


def test_crypto_and_options_unsupported_for_live():
    g = guard()
    for cls in ('crypto', 'option', 'futures'):
        with pytest.raises(AccountVerificationError, match='UNSUPPORTED_FOR_LIVE_AUTOMATION'):
            g.require(cls)


def test_require_reverifies_every_time_by_default():
    calls = []
    g = AccountGuard(lambda: calls.append(1) or ACCOUNTS, last4='4508')
    g.require('equity')
    g.require('equity')
    assert len(calls) == 2


def test_order_response_must_book_to_verified_account():
    g = guard()
    g.verify()
    g.check_order_account({'account': 'https://api.robinhood.com/accounts/554664508/'})
    with pytest.raises(AccountVerificationError):
        g.check_order_account({'account': 'https://api.robinhood.com/accounts/705601441/'})
    with pytest.raises(AccountVerificationError):
        g.check_order_account({})


def test_invalid_expected_last4_env(monkeypatch):
    monkeypatch.setenv('EXPECTED_ACCOUNT_LAST4', '45')
    with pytest.raises(AccountVerificationError):
        AccountGuard(lambda: ACCOUNTS)
