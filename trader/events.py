"""Structured, redacted event logging. Every money-relevant step emits one JSON line."""
import json
import logging
import re
import time

MARKET_DATA = 'MARKET_DATA'
SIGNAL = 'SIGNAL'
RISK_DECISION = 'RISK_DECISION'
ORDER_SUBMITTED = 'ORDER_SUBMITTED'
ORDER_UPDATE = 'ORDER_UPDATE'
POSITION_UPDATE = 'POSITION_UPDATE'
TRADE_EXIT = 'TRADE_EXIT'
SYSTEM_ERROR = 'SYSTEM_ERROR'
KILL_SWITCH = 'KILL_SWITCH'
LIFECYCLE = 'LIFECYCLE'

log = logging.getLogger('trader')

_SECRET_KEYS = re.compile(r'(token|password|secret|authorization|cookie|session|device_token|mfa)', re.I)
_PATTERNS = [
    (re.compile(r'(Bearer\s+)[A-Za-z0-9\-._~+/]+=*'), r'\1[REDACTED]'),
    (re.compile(r'eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}'), '[REDACTED_JWT]'),
    (re.compile(r'/accounts/[A-Z0-9]{5,}/'), '/accounts/[REDACTED]/'),
    (re.compile(r'\b\d{5,}(\d{4})\b'), r'••••\1'),
]


def redact(value):
    if isinstance(value, dict):
        return {k: ('[REDACTED]' if _SECRET_KEYS.search(str(k)) else redact(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if isinstance(value, str):
        for pat, rep in _PATTERNS:
            value = pat.sub(rep, value)
        return value
    return value


class EventLog:
    def __init__(self, store=None, clock=time.time):
        self.store, self.clock = store, clock

    def emit(self, kind: str, message: str = '', **data):
        payload = redact({'ts': round(self.clock(), 3), 'event': kind, 'msg': message, **data})
        line = json.dumps(payload, default=str, sort_keys=True)
        level = logging.ERROR if kind in (SYSTEM_ERROR, KILL_SWITCH) else logging.INFO
        log.log(level, line)
        if self.store is not None:
            try:
                self.store.add_event(kind, payload)
            except Exception:
                log.exception('failed to persist event')
        return payload
