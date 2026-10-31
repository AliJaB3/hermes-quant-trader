"""Weight budget and cooldown shield for exchange requests."""
import time
import threading


class RateGovernor:
    def __init__(self, max_weight_per_min=1200, emergency_reserve_weight=300):
        if max_weight_per_min < 0 or not 0 <= emergency_reserve_weight <= max_weight_per_min:
            raise ValueError('invalid rate limit or emergency reserve')
        self._lock = threading.Lock()
        self.max_weight_per_min = max_weight_per_min
        self.emergency_reserve_weight = emergency_reserve_weight
        self.current_weight = 0
        self.is_tripped_429 = False
        self.cooldown_until = 0.0

    def can_request(self, weight=1, is_emergency=False):
        if weight < 0:
            raise ValueError('weight must be nonnegative')
        if self.is_tripped_429 and time.monotonic() < self.cooldown_until:
            return False
        limit = self.max_weight_per_min if is_emergency else self.max_weight_per_min - self.emergency_reserve_weight
        return self.current_weight + weight <= limit

    def atomic_reserve(self, weight: int = 1, is_emergency: bool = False) -> bool:
        with self._lock:
            if not self.can_request(weight, is_emergency):
                return False
            self.current_weight += weight
            return True

    def record_weight(self, used_weight_1m):
        if used_weight_1m < 0:
            raise ValueError('weight must be nonnegative')
        with self._lock:
            self.current_weight = used_weight_1m

    def trip_429(self, backoff_s=60.0):
        if backoff_s < 0:
            raise ValueError('backoff must be nonnegative')
        with self._lock:
            self.is_tripped_429 = True
            self.cooldown_until = max(self.cooldown_until, time.monotonic() + backoff_s)
