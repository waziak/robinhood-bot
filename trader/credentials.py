"""Local credential storage in the macOS Keychain (via `keyring`). Tokens never touch disk, logs, reports or stdout.

  venv/bin/python -m trader.credentials setup    # store username + password (getpass, no echo)
  venv/bin/python -m trader.credentials login    # fresh login; Robinhood sends a device-approval push to your phone
  venv/bin/python -m trader.credentials status   # shows which items exist — never their values
  venv/bin/python -m trader.credentials forget   # delete the stored session
"""
import argparse
import contextlib
import getpass
import glob
import json
import logging
import os
import re
import sys
import time

from trader.events import redact

log = logging.getLogger('trader.credentials')

SERVICE = 'robinhood-bot'
KEY_USERNAME, KEY_PASSWORD, KEY_SESSION = 'rh_username', 'rh_password', 'rh_session'
TOKEN_URL = 'https://api.robinhood.com/oauth2/token/'
CLIENT_ID = 'c82SH0WZOsabOXGP2sxqcj34FxkvfnWRZBKlBjFS'  # public client id used by robin_stocks itself
LEGACY_PICKLE_GLOB = os.path.expanduser('~/.tokens/*.pickle')
SESSION_FIELDS = ('token_type', 'access_token', 'refresh_token', 'device_token')

_LONG_SECRET = re.compile(r'\b[A-Za-z0-9_\-]{32,}\b')


class CredentialError(Exception):
    pass


class KeychainStore:
    def __init__(self, service: str = SERVICE, backend=None):
        if backend is None:
            import keyring as backend
        self.kr, self.service = backend, service

    def get(self, key):
        return self.kr.get_password(self.service, key)

    def set(self, key, value):
        self.kr.set_password(self.service, key, value)

    def delete(self, key):
        try:
            self.kr.delete_password(self.service, key)
        except Exception:
            pass


class MemoryStore:
    def __init__(self):
        self.d = {}

    def get(self, key):
        return self.d.get(key)

    def set(self, key, value):
        self.d[key] = value

    def delete(self, key):
        self.d.pop(key, None)


def scrub(text: str) -> str:
    return _LONG_SECRET.sub('[REDACTED]', redact(str(text)))


class RedactingStream:
    """Forwards third-party library output (robin_stocks prints during login) with anything token-like removed."""

    def __init__(self, target):
        self.target = target

    def write(self, s):
        return self.target.write(scrub(s))

    def flush(self):
        self.target.flush()


def legacy_plaintext_sessions() -> list:
    return glob.glob(LEGACY_PICKLE_GLOB)


def save_session(store, sess: dict):
    missing = [k for k in SESSION_FIELDS if not sess.get(k)]
    if missing:
        raise CredentialError(f'session incomplete: missing {missing}')
    store.set(KEY_SESSION, json.dumps({**{k: sess[k] for k in SESSION_FIELDS}, 'saved_at': time.time()}))


def load_session(store):
    raw = store.get(KEY_SESSION)
    if not raw:
        return None
    try:
        sess = json.loads(raw)
    except ValueError:
        raise CredentialError('stored session is corrupt — run `login` again')
    return sess if all(sess.get(k) for k in SESSION_FIELDS) else None


def _rh_apply(sess):
    from robin_stocks.robinhood.authentication import set_login_state
    from robin_stocks.robinhood.helper import update_session
    update_session('Authorization', f"{sess['token_type']} {sess['access_token']}")
    set_login_state(True)


def _rh_clear():
    from robin_stocks.robinhood.authentication import set_login_state
    from robin_stocks.robinhood.helper import update_session
    update_session('Authorization', None)
    set_login_state(False)


def _rh_verify() -> bool:
    import robin_stocks.robinhood as rh
    try:
        profile = rh.load_account_profile()
        return bool(profile and profile.get('account_number'))
    except Exception:
        return False


def refresh(sess: dict, post=None):
    """OAuth refresh grant. Never logs the response body (it can contain tokens)."""
    if post is None:
        import requests
        post = requests.post
    payload = {'grant_type': 'refresh_token', 'refresh_token': sess['refresh_token'], 'scope': 'internal',
               'client_id': CLIENT_ID, 'expires_in': 86400, 'device_token': sess['device_token']}
    try:
        resp = post(TOKEN_URL, data=payload, timeout=15)
        status = getattr(resp, 'status_code', None)
        data = resp.json() if status == 200 else {}
    except Exception as e:
        log.warning('session refresh failed: %s', type(e).__name__)
        return None
    if not isinstance(data, dict) or 'access_token' not in data:
        log.warning('session refresh rejected (HTTP %s)', status)
        return None
    return {'token_type': data.get('token_type', 'Bearer'), 'access_token': data['access_token'],
            'refresh_token': data.get('refresh_token', sess['refresh_token']), 'device_token': sess['device_token']}


def resume(store, apply=_rh_apply, verify=_rh_verify, clear=_rh_clear, post=None) -> bool:
    """Resume or refresh the Keychain session. Never falls back to a password login — that must be run
    interactively so a human sees and approves the device push."""
    legacy = legacy_plaintext_sessions()
    if legacy:
        raise CredentialError(f'{len(legacy)} plaintext session file(s) under ~/.tokens — delete them; they are not trusted')
    sess = load_session(store)
    if not sess:
        return False
    apply(sess)
    if verify():
        log.info('session resumed from Keychain')
        return True
    new = refresh(sess, post)
    if new:
        apply(new)
        if verify():
            save_session(store, new)
            log.info('session refreshed; Keychain updated')
            return True
    clear()
    return False


def interactive_login(store, rh=None) -> bool:
    if rh is None:
        import robin_stocks.robinhood as rh
    import robin_stocks.robinhood.authentication as auth
    username, password = store.get(KEY_USERNAME), store.get(KEY_PASSWORD)
    if not username or not password:
        raise CredentialError('credentials not in Keychain — run `python -m trader.credentials setup` first')
    if legacy_plaintext_sessions():
        raise CredentialError('plaintext session files exist under ~/.tokens — delete them first')
    captured = {}
    original = auth.generate_device_token

    def capture():
        captured['device_token'] = original()
        return captured['device_token']

    auth.generate_device_token = capture
    print('Starting Robinhood login. Robinhood will send a device-approval request to your phone —\n'
          'open the Robinhood app and approve the new login (or enter the SMS code if prompted).', flush=True)
    try:
        with contextlib.redirect_stdout(RedactingStream(sys.__stdout__)):
            data = rh.login(username, password, store_session=False)
    finally:
        auth.generate_device_token = original
    if legacy_plaintext_sessions():
        raise CredentialError('robin_stocks wrote a plaintext session file despite store_session=False — delete it')
    if not isinstance(data, dict) or 'access_token' not in data:
        raise CredentialError('login did not complete (approval not given, wrong password, or rate limited)')
    save_session(store, {'token_type': data.get('token_type', 'Bearer'), 'access_token': data['access_token'],
                         'refresh_token': data.get('refresh_token'), 'device_token': captured.get('device_token')})
    return _rh_verify()


def status(store) -> dict:
    sess = None
    try:
        sess = load_session(store)
    except CredentialError:
        pass
    return {'username_stored': bool(store.get(KEY_USERNAME)), 'password_stored': bool(store.get(KEY_PASSWORD)),
            'session_stored': bool(sess), 'session_age_hours': round((time.time() - sess['saved_at']) / 3600, 1) if sess else None,
            'legacy_plaintext_session_files': len(legacy_plaintext_sessions())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('command', choices=('setup', 'login', 'status', 'forget'))
    a = ap.parse_args()
    store = KeychainStore()
    if a.command == 'setup':
        user = input('Robinhood username (email): ').strip()
        pw = getpass.getpass('Robinhood password (hidden): ')
        if pw != getpass.getpass('Repeat password: ') or not user or not pw:
            raise SystemExit('Passwords did not match or were empty; nothing stored.')
        store.set(KEY_USERNAME, user)
        store.set(KEY_PASSWORD, pw)
        store.delete(KEY_SESSION)
        print('Stored in macOS Keychain (service "robinhood-bot"). Any previous session was discarded.')
    elif a.command == 'login':
        ok = interactive_login(store)
        print('Login verified; session stored in Keychain.' if ok else 'Login completed but verification failed.')
    elif a.command == 'forget':
        store.delete(KEY_SESSION)
        print('Stored session deleted.')
    print(json.dumps(status(store), indent=2))


if __name__ == '__main__':
    main()
