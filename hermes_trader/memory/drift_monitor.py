import math
import statistics
import time


class MarketDriftMonitor:
    def __init__(self, falsification_window_hours=4.0, max_falsification_burst=5):
        self.falsification_window_hours = falsification_window_hours
        self.max_falsification_burst = max_falsification_burst
        self.falsifications = []

    def record_falsification(self, rule_id, timestamp):
        self.falsifications.append((rule_id, float(timestamp)))

    def is_burst_triggered(self):
        now = time.time()
        cutoff = now - self.falsification_window_hours * 3600
        self.falsifications = [(rule, ts) for rule, ts in self.falsifications if ts >= cutoff]
        return sum(cutoff <= ts <= now for _, ts in self.falsifications) >= self.max_falsification_burst

    def check_distribution_drift(self, recent_values, historical_values, threshold_sigma=3.5):
        if len(recent_values) < 2 or len(historical_values) < 2 or threshold_sigma <= 0:
            raise ValueError('Two samples per distribution and a positive threshold are required')
        if not all(math.isfinite(x) for x in [*recent_values, *historical_values, threshold_sigma]):
            raise ValueError('Distribution values must be finite')
        old_std = statistics.stdev(historical_values)
        new_std = statistics.stdev(recent_values)
        mean_shift = abs(statistics.mean(recent_values) - statistics.mean(historical_values))
        if old_std == 0:
            return mean_shift > 0 or new_std > 0
        return mean_shift / old_std > threshold_sigma or abs(new_std - old_std) / old_std > threshold_sigma
