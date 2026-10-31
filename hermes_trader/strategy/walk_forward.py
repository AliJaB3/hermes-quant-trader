from dataclasses import dataclass
import math

from hermes_trader.contracts import OrderSide
from .evaluator import StrategyEvaluator


@dataclass
class WalkForwardReport:
    strategy_id: str
    total_trades: int
    win_rate: float
    profit_factor: float
    max_drawdown_pct: float
    net_pnl: float
    is_admissible: bool


class WalkForwardValidator:
    def validate(self, strategy, candles, folds=3, fee_rate=0.0004, slippage_rate=0.0002):
        """Use expanding history and disjoint forward folds; close positions at each boundary.

        Candles have open/high/low/close and may have symbol and indicators. Signals
        use the preceding close; fills occur at the next open. If both exits are
        touched in one bar the stop wins. PnL is in quote currency and drawdown
        is measured against an initial 10,000 units of equity.
        """
        if not isinstance(folds, int) or isinstance(folds, bool) or folds < 1:
            raise ValueError('folds must be a positive integer')
        if not all(math.isfinite(x) and 0 <= x < 1 for x in (fee_rate, slippage_rate)):
            raise ValueError('fee and slippage rates must be between 0 and 1')
        evaluator = StrategyEvaluator()
        pnls = []
        equity = peak = 10000.0
        drawdown = 0.0
        # The first partition is history; subsequent partitions are out of sample.
        n = len(candles)
        for fold in range(folds):
            start = n * (fold + 1) // (folds + 1)
            end = n * (fold + 2) // (folds + 1)
            position = None
            for i in range(max(1, start), end):
                candle = candles[i]
                close = float(candle['close'])
                opening = float(candle.get('open', close))
                high = float(candle.get('high', max(opening, close)))
                low = float(candle.get('low', min(opening, close)))
                if not all(math.isfinite(x) and x > 0 for x in (opening, high, low, close)) or low > min(opening, close) or high < max(opening, close):
                    raise ValueError('invalid candle prices')
                if position is None:
                    prev = candles[i - 1]
                    symbol = candle.get('symbol', strategy.target_universe[0])
                    if prev.get('symbol', symbol) != symbol:
                        continue
                    indicators = dict(prev)
                    indicators.update(prev.get('indicators', {}))
                    proposal = evaluator.evaluate_tick(strategy, symbol, float(prev['close']), indicators)
                    if proposal:
                        direction = 1 if proposal.side == OrderSide.BUY else -1
                        entry = opening * (1 + direction * slippage_rate)
                        ratio = entry / proposal.price
                        position = (direction, entry, proposal.quantity, proposal.stop_loss * ratio, proposal.take_profit * ratio)
                if position:
                    direction, entry, qty, stop, take = position
                    stop_hit = low <= stop if direction == 1 else high >= stop
                    take_hit = high >= take if direction == 1 else low <= take
                    exit_price = None
                    if stop_hit:
                        exit_price = min(opening, stop) if direction == 1 else max(opening, stop)
                    elif take_hit:
                        exit_price = max(opening, take) if direction == 1 else min(opening, take)
                    elif i == end - 1:
                        exit_price = close
                    if exit_price is not None:
                        exit_price *= 1 - direction * slippage_rate
                        pnl = direction * (exit_price - entry) * qty - (entry + exit_price) * qty * fee_rate
                        pnls.append(pnl)
                        equity += pnl
                        peak = max(peak, equity)
                        drawdown = max(drawdown, (peak - equity) / peak * 100)
                        position = None
        gains = sum(x for x in pnls if x > 0)
        losses = -sum(x for x in pnls if x < 0)
        factor = gains / losses if losses else (math.inf if gains else 0.0)
        net = sum(pnls)
        return WalkForwardReport(strategy.strategy_id, len(pnls), sum(x > 0 for x in pnls) / len(pnls) if pnls else 0.0,
                                 factor, drawdown, net, net > 0 and factor > 1.2 and drawdown < 5.0)
