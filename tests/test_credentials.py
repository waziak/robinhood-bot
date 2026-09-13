import io
import logging
import re
import subprocess
from pathlib import Path

import pytest

from trader import credentials as cr

JWT = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0dXNlcjEyMzQ1Njc4OSJ9.c2lnbmF0dXJlc2lnbmF0dXJlc2ln'
SESSION = {'token_type': 'Bearer', 'access_token': JWT, 'refresh_token': 'R' * 40, 'device_token': 'D' * 36}


class Resp:
    def __init__(self, status, body):
        self.status_code, self.body = status, body

    def json(self):
        return self.body


@pytest.fixture(autouse=True)
def no_legacy(monkeypatch, tmp_path):
    monkeypatch.setattr(cr, 'LEGACY_PICKLE_GLOB', str(tmp_path / 'none' / '*.pickle'))


def test_session_requires_all_fields():
    with pytest.raises(cr.CredentialError):
        cr.save_session(cr.MemoryStore(), {**SESSION, 'device_token': None})


def test_resume_valid_session():
    store = cr.MemoryStore()
    cr.save_session(store, SESSION)
    assert cr.resume(store, apply=lambda s: None, verify=lambda: True, clear=lambda: None)


def test_refresh_updates_keychain_and_never_logs_tokens(caplog):
    store = cr.MemoryStore()
    cr.save_session(store, SESSION)
    calls = iter([False, True])
    new_token = 'N' * 48
    post = lambda url, data, timeout: Resp(200, {'access_token': new_token, 'token_type': 'Bearer'})
    with caplog.at_level(logging.DEBUG):
        assert cr.resume(store, apply=lambda s: None, verify=lambda: next(calls), clear=lambda: None, post=post)
    assert cr.load_session(store)['access_token'] == new_token
    assert new_token not in caplog.text and JWT not in caplog.text and 'R' * 40 not in caplog.text


def test_rejected_refresh_does_not_log_response_body(caplog):
    store = cr.MemoryStore()
    cr.save_session(store, SESSION)
    leaked = 'S' * 40
    post = lambda url, data, timeout: Resp(401, {'detail': leaked, 'refresh_token': leaked})
    cleared = []
    with caplog.at_level(logging.DEBUG):
        assert not cr.resume(store, apply=lambda s: None, verify=lambda: False, clear=lambda: cleared.append(1), post=post)
    assert leaked not in caplog.text and cleared


def test_no_session_means_no_login_attempt():
    assert cr.resume(cr.MemoryStore(), apply=pytest.fail, verify=pytest.fail, clear=pytest.fail) is False


def test_legacy_plaintext_session_refused(monkeypatch, tmp_path):
    (tmp_path / 't').mkdir()
    (tmp_path / 't' / 'robinhood.pickle').write_bytes(b'x')
    monkeypatch.setattr(cr, 'LEGACY_PICKLE_GLOB', str(tmp_path / 't' / '*.pickle'))
    with pytest.raises(cr.CredentialError):
        cr.resume(cr.MemoryStore())


def test_redacting_stream_scrubs_tokens():
    buf = io.StringIO()
    cr.RedactingStream(buf).write(f'Authorization: Bearer {JWT} refresh={"x" * 40} ok')
    out = buf.getvalue()
    assert JWT not in out and 'x' * 40 not in out and 'ok' in out


def test_status_never_contains_values():
    store = cr.MemoryStore()
    store.set(cr.KEY_PASSWORD, 'hunter2-secret')
    cr.save_session(store, SESSION)
    text = str(cr.status(store))
    assert 'hunter2' not in text and JWT not in text


TOKEN_VALUE_PATTERNS = [
    re.compile(r'eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}'),
    re.compile(r'Bearer\s+[A-Za-z0-9._-]{30,}'),
    re.compile(r'(access|refresh|device)_token["\']?\s*[:=]\s*["\'][A-Za-z0-9._-]{20,}'),
    re.compile(r'gAS[A-Za-z0-9+/=]{60,}'),  # base64 pickle
    re.compile(r'gh[pousr]_[A-Za-z0-9]{30,}'),
]


def test_no_workflow_caches_a_credential_path():
    """Regression test for the actual incident mechanism: a GitHub Actions workflow using actions/cache (or
    upload-artifact) to persist a Robinhood session/token file. Session state must never leave the local Keychain."""
    root = Path(__file__).resolve().parents[1]
    wf_dir = root / '.github' / 'workflows'
    if not wf_dir.is_dir():
        return
    forbidden_path_fragments = ('.tokens', 'robinhood.pickle', 'rh-session', 'RH_SESSION_SEED')
    offenders = []
    for wf in wf_dir.glob('*.y*ml'):
        text = wf.read_text()
        if 'actions/cache' in text or 'upload-artifact' in text:
            if any(frag in text for frag in forbidden_path_fragments):
                offenders.append(wf.name)
    assert offenders == [], f'workflow(s) cache/upload a credential-shaped path: {offenders}'


def test_repository_contains_no_credential_values():
    root = Path(__file__).resolve().parents[1]
    files = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard'], cwd=root,
                           capture_output=True, text=True, check=True).stdout.split()
    offenders = []
    for rel in files:
        p = root / rel
        if rel == 'tests/test_credentials.py' or not p.is_file() or p.stat().st_size > 2_000_000:
            continue
        try:
            text = p.read_text(errors='ignore')
        except OSError:
            continue
        if any(pat.search(text) for pat in TOKEN_VALUE_PATTERNS):
            offenders.append(rel)
    assert offenders == []
