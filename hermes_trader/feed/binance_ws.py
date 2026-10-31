"""Parse Binance bookTicker stream updates into monitored market ticks."""
import math
import time
from .ticker import FeedWatchdog, MarketTick


class BinanceFeedClient:
    def __init__(self, symbol, watchdog=None):
        self.symbol = symbol.upper()
        self.watchdog = watchdog or FeedWatchdog(max_stale_ms=2000.0)

    def parse_stream_message(self, msg):
        try:
            msg = msg.get('data', msg)
            if msg.get('s', self.symbol).upper() != self.symbol:
                return None
            bid, ask, bid_qty, ask_qty = (float(msg[k]) for k in ('b', 'a', 'B', 'A'))
            if not all(math.isfinite(x) and x > 0 for x in (bid, ask)) or bid > ask or not all(math.isfinite(x) and x >= 0 for x in (bid_qty, ask_qty)):
                return None
            sequence = msg.get('u', msg.get('U'))
            if sequence is not None:
                if isinstance(sequence, bool) or not str(sequence).isdigit():
                    return None
                self.watchdog.record_sequence(int(sequence))
            mid = (bid + ask) / 2
            tick = MarketTick(self.symbol, bid, ask, mid, (ask - bid) / mid * 10000, time.time())
            self.watchdog.record_tick(tick)
            return tick
        except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
            return None
