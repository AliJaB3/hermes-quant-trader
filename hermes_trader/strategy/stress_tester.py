"""Deterministic microstructure shocks for a simple position-based strategy.

The callback receives a tick dict and returns signed units held until the next
 tick. Equity starts at initial_price; changes in position incur tick fees.
"""
import math


class SyntheticStressTester:
    def run_stress_test(self, strategy_fn, initial_price: float = 60000.0) -> dict:
        if not math.isfinite(initial_price) or initial_price <= 0:
            raise ValueError('initial_price must be positive and finite')
        scenarios = {
            'flash_crash': [(1 - .25 * i / 5, .2, 0.0004, 2) for i in range(1, 6)],
            'cascade_squeeze': [(1 + .20 * i / 5, 1, .01, 2) for i in range(1, 6)],
            'illiquid_whipsaw': [(1 + (.03 if i % 2 else -.03), .2, .0004, 25) for i in range(1, 7)],
        }
        worst = 0.0
        liquidated = False
        for name, ticks in scenarios.items():
            equity = peak = initial_price
            previous_price = initial_price
            position = 0.0
            for factor, depth, fee, spread in ticks:
                price = initial_price * factor
                equity += position * (price - previous_price)
                if equity <= 0 or not math.isfinite(equity):
                    liquidated = True
                    worst = max(worst, 1.0)
                    break
                peak = max(peak, equity)
                worst = max(worst, (peak - equity) / peak)
                tick = {'scenario': name, 'price': price, 'depth': depth, 'fee_rate': fee, 'spread_bps': spread}
                new_position = float(strategy_fn(tick))
                if not math.isfinite(new_position):
                    raise ValueError('strategy position must be finite')
                equity -= abs(new_position - position) * price * (fee + spread / 20000)
                if equity <= 0:
                    liquidated = True
                    worst = max(worst, 1.0)
                    break
                worst = max(worst, (peak - equity) / peak)
                position, previous_price = new_position, price
        return {'survived': not liquidated, 'max_drawdown': worst, 'liquidation_avoided': not liquidated}
