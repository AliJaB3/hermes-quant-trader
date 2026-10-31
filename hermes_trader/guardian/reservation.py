"""Atomic, expiring capacity reservations for proposed executions."""
from dataclasses import dataclass
import math
import threading
import time
from uuid import uuid4


@dataclass
class ExecutionToken:
    token_id: str
    proposal_id: str
    reserved_usd: float
    reserved_cvar: float
    created_at: float
    ttl_ms: float = 2000.0
    is_consumed: bool = False


class CapacityReservationManager:
    def __init__(self, ttl_ms=2000.0):
        if not math.isfinite(ttl_ms) or ttl_ms <= 0:
            raise ValueError('ttl_ms must be positive and finite')
        self.ttl_ms = ttl_ms
        self._lock = threading.RLock()
        self._tokens = {}

    def purge_expired(self):
        with self._lock:
            now = time.monotonic()
            for key, token in list(self._tokens.items()):
                if (now - token.created_at) * 1000 > token.ttl_ms:
                    del self._tokens[key]

    def reserve(self, proposal_id, amount_usd, cvar, current_available_usd, current_available_cvar):
        values = (amount_usd, cvar, current_available_usd, current_available_cvar)
        if not all(math.isfinite(x) and x >= 0 for x in values):
            return None
        with self._lock:
            self.purge_expired()
            if (sum(t.reserved_usd for t in self._tokens.values()) + amount_usd > current_available_usd or
                    sum(t.reserved_cvar for t in self._tokens.values()) + cvar > current_available_cvar):
                return None
            token = ExecutionToken(str(uuid4()), proposal_id, amount_usd, cvar, time.monotonic(), self.ttl_ms)
            self._tokens[token.token_id] = token
            return token

    def consume(self, token_id):
        with self._lock:
            self.purge_expired()
            token = self._tokens.get(token_id)
            if token is None or token.is_consumed:
                return False
            token.is_consumed = True
            return True

    def release(self, token_id):
        with self._lock:
            self._tokens.pop(token_id, None)
