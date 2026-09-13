from dataclasses import replace

import pytest

from conftest import ACCOUNTS, FakeApi
from trader.accounts import AccountGuard, AccountVerificationError
from trader.broker import BrokerRefused, RobinhoodBroker
from trader.market_data import BrokerTimeout
from trader.models import OrderState

LIVE = None


def broker(env, api=None, budget=None, live=True, accounts=None):
    api = api or FakeApi(env.clock, accounts=accounts)
    cfg = replace(env.cfg, live_trading_enabled=live)
    return RobinhoodBroker(env.data, cfg, AccountGuard(api.account_list, last4='4508', clock=env.clock.now), api,
                           order_budget=budget), api


def test_order_payload_pinned_to_4508_with_ref_id(env):
    b, api = broker(env)
    st = b.submit_limit_order('client-123', 'SPY', 'buy', 0.012345678, 100.123)
    [p] = api.posts
    assert p['account'] == 'https://api.robinhood.com/accounts/554664508/'
    assert p['ref_id'] == 'client-123' and p['type'] == 'limit' and p['time_in_force'] == 'gfd'
    assert p['market_hours'] == 'regular_hours' and p['extended_hours'] is False
    assert p['quantity'] == '0.012346' and p['price'] == '100.12'
    assert st.state == OrderState.SUBMITTED and st.ref_id == 'client-123'


def test_account_reverified_with_broker_before_every_order(env):
    b, api = broker(env)
    b.submit_limit_order('c1', 'SPY', 'buy', 0.01, 100)
    n = api.account_list_calls
    b.submit_limit_order('c2', 'SPY', 'buy', 0.01, 100)
    assert api.account_list_calls == n + 1


@pytest.mark.parametrize('accounts', [
    [a for a in ACCOUNTS if not a['account_number'].endswith('4508')],
    [{**ACCOUNTS[2], 'type': 'margin'}],
])
def test_wrong_or_missing_account_blocks_before_anything_is_sent(env, accounts):
    b, api = broker(env, accounts=accounts)
    with pytest.raises(AccountVerificationError):
        b.submit_limit_order('c1', 'SPY', 'buy', 0.01, 100)
    assert api.posts == []


def test_crypto_is_unsupported_for_live_automation(env):
    b, api = broker(env)
    with pytest.raises(BrokerRefused, match='UNSUPPORTED_FOR_LIVE_AUTOMATION'):
        b.submit_limit_order('c1', 'BTC', 'buy', 0.0001, 60000)
    assert api.posts == []


def test_live_disabled_refuses(env):
    b, api = broker(env, live=False)
    with pytest.raises(BrokerRefused):
        b.submit_limit_order('c1', 'SPY', 'buy', 0.01, 100)
    assert api.posts == []


def test_order_budget_allows_exactly_one_even_after_timeout(env):
    api = FakeApi(env.clock)
    api.post_error = BrokerTimeout('timeout')
    b, _ = broker(env, api=api, budget=1, live=False)
    with pytest.raises(BrokerTimeout):
        b.submit_limit_order('c1', 'SPY', 'buy', 0.01, 100)
    api.post_error = None
    with pytest.raises(BrokerRefused, match='budget'):
        b.submit_limit_order('c2', 'SPY', 'buy', 0.01, 100)
    assert len(api.posts) == 1


def test_response_booked_to_other_account_raises(env):
    api = FakeApi(env.clock)
    api.response_account = 'https://api.robinhood.com/accounts/705601441/'
    b, _ = broker(env, api=api)
    with pytest.raises(AccountVerificationError):
        b.submit_limit_order('c1', 'SPY', 'buy', 0.01, 100)


def test_inactive_instrument_refused(env):
    api = FakeApi(env.clock)
    api.inst_overrides = {'tradeable': False}
    b, _ = broker(env, api=api)
    with pytest.raises(BrokerRefused):
        b.submit_limit_order('c1', 'SPY', 'buy', 0.01, 100)
    assert api.posts == []


def test_foreign_account_records_rejected(env):
    b, api = broker(env)
    b.submit_limit_order('c1', 'SPY', 'buy', 0.01, 100)
    api.orders['o1']['account'] = 'https://api.robinhood.com/accounts/705601441/'
    with pytest.raises(AccountVerificationError):
        b.get_order_status('o1')
    api.position_rows = [{'account': 'https://api.robinhood.com/accounts/705601441/', 'instrument': 'x/SPY/', 'quantity': '1'}]
    with pytest.raises(AccountVerificationError):
        b.get_positions()


def test_find_by_ref_and_positions_scoped(env):
    api = FakeApi(env.clock, fill_on_post=True)
    b, _ = broker(env, api=api)
    b.submit_limit_order('ref-1', 'SPY', 'buy', 0.01, 100)
    st = b.find_order_by_ref('ref-1', 'SPY', 'buy', env.clock.now())
    assert st and st.state == OrderState.FILLED and st.filled_qty == 0.01
    assert b.find_order_by_ref('nope', 'SPY', 'buy', env.clock.now()) is None
    assert b.get_positions() == {'SPY': 0.01}
