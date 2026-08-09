"""
Robinhood session persistence.

Robinhood no longer offers TOTP/authenticator-app 2FA — the only unattended-login
option is a device-approval push, which requires a human tap and is a bad fit for
an ephemeral CI runner that looks like a brand-new device every run. This module
avoids re-triggering that approval on every run by resuming a saved access token,
or silently refreshing it via Robinhood's OAuth refresh grant, before ever falling
back to a full password login.

Only the full-login fallback (bottom of authenticate()) needs a human to approve
the device push. Resume and refresh are both fully headless.
"""
import os
import pickle
import logging

import requests
import robin_stocks.robinhood as rh
from robin_stocks.robinhood.authentication import set_login_state
from robin_stocks.robinhood.helper import update_session

log = logging.getLogger(__name__)

TOKEN_URL = 'https://api.robinhood.com/oauth2/token/'
CLIENT_ID = 'c82SH0WZOsabOXGP2sxqcj34FxkvfnWRZBKlBjFS'  # public client_id robin_stocks itself uses
PICKLE_PATH = os.path.expanduser('~/.tokens/robinhood.pickle')


def _load_pickle():
    if not os.path.isfile(PICKLE_PATH):
        return None
    try:
        with open(PICKLE_PATH, 'rb') as f:
            return pickle.load(f)
    except Exception as e:
        log.warning(f"Could not read saved session ({PICKLE_PATH}): {e}")
        return None


def _save_pickle(data):
    os.makedirs(os.path.dirname(PICKLE_PATH), exist_ok=True)
    with open(PICKLE_PATH, 'wb') as f:
        pickle.dump(data, f)


def _apply(token_type, access_token):
    update_session('Authorization', f'{token_type} {access_token}')
    set_login_state(True)


def _verify() -> bool:
    """Cheap authenticated call to confirm the current session actually works."""
    try:
        profile = rh.load_account_profile()
        return bool(profile and profile.get('account_number'))
    except Exception:
        return False


def _refresh(saved: dict):
    """Mint a new access token from the stored refresh_token — no approval needed."""
    payload = {
        'grant_type': 'refresh_token',
        'refresh_token': saved['refresh_token'],
        'scope': 'internal',
        'client_id': CLIENT_ID,
        'expires_in': 86400,
        'device_token': saved['device_token'],
    }
    try:
        resp = requests.post(TOKEN_URL, data=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.warning(f"Session refresh request failed: {e}")
        return None
    if 'access_token' not in data:
        log.warning(f"Session refresh returned no access_token: {data}")
        return None
    return {
        'token_type': data.get('token_type', 'Bearer'),
        'access_token': data['access_token'],
        # Robinhood may or may not rotate the refresh_token on use — keep the old one if absent.
        'refresh_token': data.get('refresh_token', saved['refresh_token']),
        'device_token': saved['device_token'],
    }


def authenticate(username: str, password: str) -> bool:
    """Resume a saved session, refresh it, or fall back to a full login.

    Returns True only if a real authenticated call succeeded — never reports
    success on a failure it happened to swallow.
    """
    saved = _load_pickle()

    if saved:
        _apply(saved['token_type'], saved['access_token'])
        if _verify():
            log.info("✓ Session resumed from saved token — no login needed")
            return True

        log.info("Saved access token expired — refreshing...")
        refreshed = _refresh(saved)
        if refreshed:
            _apply(refreshed['token_type'], refreshed['access_token'])
            if _verify():
                _save_pickle(refreshed)
                log.info("✓ Session refreshed via refresh_token — no approval needed")
                return True

        log.warning("Saved session could not be resumed or refreshed — falling back to full login")
        set_login_state(False)

    if not username or not password:
        log.error("RH_USERNAME or RH_PASSWORD not set — cannot attempt full login")
        return False

    log.warning("No usable saved session — attempting full login "
                "(this will hang on a device-approval push until it's approved on your phone)")
    try:
        data = rh.login(username, password, store_session=True)
    except Exception as e:
        log.error(f"Full login failed: {e}")
        return False

    if not data or 'access_token' not in data:
        log.error(f"Full login did not return an access token: {data}")
        return False

    # rh.login() already persisted its own pickle to PICKLE_PATH on success.
    log.info("✓ Full login succeeded — session saved for future runs")
    return _verify()
