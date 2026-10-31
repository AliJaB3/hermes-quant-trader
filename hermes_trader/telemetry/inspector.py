"""Bounded, sanitized snapshots for an inspector consumer."""
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import threading


@dataclass
class InspectorFrame:
    seq: int
    correlation_id: str
    causation_id: str
    timestamp: str
    event_type: str
    data: dict


def _sanitize(value):
    if isinstance(value, dict):
        return {k: _sanitize(v) for k, v in value.items()
                if not any(part in str(k).lower() for part in ('key', 'token', 'secret', 'password'))}
    if isinstance(value, (list, tuple)):
        return [_sanitize(v) for v in value]
    return value


class MCTSInspectorStream:
    def __init__(self, maxlen=1000):
        if maxlen <= 0:
            raise ValueError('maxlen must be positive')
        self._frames = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._seq = 0

    def emit(self, event_type: str, correlation_id: str, causation_id: str, data: dict):
        clean = _sanitize(data)
        with self._lock:
            self._seq += 1
            self._frames.append(InspectorFrame(self._seq, correlation_id, causation_id,
                                datetime.now(timezone.utc).isoformat(), event_type, clean))

    def get_recent_frames(self, limit: int = 50) -> list[InspectorFrame]:
        if limit <= 0:
            return []
        with self._lock:
            return list(self._frames)[-limit:]
