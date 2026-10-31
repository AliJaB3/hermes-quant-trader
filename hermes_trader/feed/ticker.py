"""Market ticks and a timestamp-based feed heartbeat."""
from dataclasses import dataclass
import math
import time


@dataclass
class MarketTick:
    symbol: str
    bid: float
    ask: float
    last_price: float
    spread_bps: float
    timestamp: float


class FeedWatchdog:
    def __init__(self, max_stale_ms: float = 5000.0):
        if not math.isfinite(max_stale_ms) or max_stale_ms <= 0:
            raise ValueError('max_stale_ms must be positive and finite')
        self.max_stale_ms = max_stale_ms
        self.last_tick = None
        self.sequence_gap_detected = False
        self.last_sequence_id = None

    def record_tick(self, tick: MarketTick):
        self.last_tick = tick

    def record_sequence(self, sequence_id: int) -> bool:
        if self.last_sequence_id is not None and sequence_id > self.last_sequence_id + 1:
            self.sequence_gap_detected = True
            return False
        self.last_sequence_id = sequence_id
        return True

    def reset_gap(self):
        self.sequence_gap_detected = False
        self.last_sequence_id = None

    def is_healthy(self) -> bool:
        if self.sequence_gap_detected:
            return False
        if self.last_tick is None or not math.isfinite(self.last_tick.timestamp):
            return False
        age = time.time() - self.last_tick.timestamp
        return 0 <= age <= self.max_stale_ms / 1000


def binance_tick(symbol: str, timeout: float = 5.0) -> MarketTick:
    """Fetch Binance's best bid/ask and latest trade price using public REST data."""
    import json
    from urllib.parse import urlencode
    from urllib.request import urlopen

    def fetch(endpoint):
        url = 'https://api.binance.com/api/v3/' + endpoint + '?' + urlencode({'symbol': symbol})
        with urlopen(url, timeout=timeout) as response:
            return json.load(response)

    book = fetch('ticker/bookTicker')
    trade = fetch('ticker/price')
    bid, ask, price = float(book['bidPrice']), float(book['askPrice']), float(trade['price'])
    if not all(math.isfinite(x) and x > 0 for x in (bid, ask, price)) or bid > ask:
        raise ValueError('invalid Binance ticker')
    return MarketTick(symbol, bid, ask, price, (ask - bid) / ((ask + bid) / 2) * 10000, time.time())
