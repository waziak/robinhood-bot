import pytest

from conftest import FakeApi
from trader.accounts import AccountGuard
from trader.broker_test import CONFIRM_PHRASE, BrokerTestRefused, run_broker_test


def run(env, api=None, symbol='SPY', side='buy', dollars=1.0, answer=CONFIRM_PHRASE, auth_ok=True, session=True):
    api = api or FakeApi(env.clock, fill_on_post=True)
    out = []
    result = run_broker_test(symbol, side, dollars, cfg=env.cfg, store=env.store, events=env.events, risk=env.risk,
                             guard=AccountGuard(api.account_list, last4='4508', clock=env.clock.now), api=api,
                             data=env.data, auth_ok=auth_ok, clock=env.clock.now, sleep=env.clock.sleep,
                             input_fn=lambda prompt: answer, print_fn=out.append, session_open=lambda t: session)
    return result, api, '\n'.join(map(str, out))


@pytest.mark.parametrize('kwargs,match', [
    ({'dollars': 1.01}, r'\$1.00'),
    ({'dollars': 0}, r'\$1.00'),
    ({'symbol': 'BTC'}, 'UNSUPPORTED'),
    ({'auth_ok': False}, 'credentials'),
    ({'session': False}, 'session'),
    ({'side': 'short'}, 'side'),
])
def test_refusals_send_nothing(env, kwargs, match):
    api = FakeApi(env.clock)
    with pytest.raises(BrokerTestRefused, match=match):
        run(env, api=api, **kwargs)
    assert api.posts == []


def test_emergency_halt_refuses(env):
    env.risk.emergency_halt('manual')
    api = FakeApi(env.clock)
    with pytest.raises(BrokerTestRefused, match='halt'):
        run(env, api=api)
    assert api.posts == []


def test_wrong_confirmation_aborts(env):
    result, api, _ = run(env, answer='yes')
    assert result == {'submitted': False} and api.posts == []


def test_happy_path_submits_exactly_one_order_and_reconciles(env):
    result, api, text = run(env)
    assert len(api.posts) == 1
    assert api.posts[0]['account'].endswith('/554664508/')
    assert float(api.posts[0]['quantity']) * float(api.posts[0]['price']) <= 1.0
    assert result['state'] == 'filled' and result['broker_position_qty'] > 0
    assert '••••4508' in text and 'Est. quantity' in text and '554664508' not in text
    assert env.store.get_meta('broker_test')['submitted'] is True


def test_unfilled_order_is_cancelled_not_resent(env):
    result, api, _ = run(env, api=FakeApi(env.clock, fill_on_post=False))
    assert len(api.posts) == 1 and result['state'] == 'cancelled'


def test_second_run_refused(env):
    run(env)
    with pytest.raises(BrokerTestRefused, match='already'):
        run(env)
