"""Autonomous paper trading driven by market ticks."""
import math

from hermes_trader.feed import FeedWatchdog
from hermes_trader.guardian import RiskGuardian
from hermes_trader.paper import PaperEngine
from hermes_trader.strategy import StrategyEvaluator


class TradingDaemon:
    def __init__(self, strategies=None, guardian=None, paper_engine=None, watchdog=None):
        self.guardian = guardian or (paper_engine.guardian if paper_engine is not None else RiskGuardian())
        self.paper_engine = paper_engine or PaperEngine(guardian=self.guardian)
        if self.paper_engine.guardian is not self.guardian:
            raise ValueError('paper engine and daemon must share a guardian')
        self.watchdog = watchdog or FeedWatchdog()
        self.strategies = list(strategies or [])
        self.evaluator = StrategyEvaluator()

    def process_tick(self, tick):
        self.watchdog.record_tick(tick)
        if not self.watchdog.is_healthy():
            return []
        if (not tick.symbol or not all(math.isfinite(x) for x in
                (tick.bid, tick.ask, tick.last_price, tick.spread_bps))
                or tick.bid <= 0 or tick.ask < tick.bid or tick.last_price <= 0 or tick.spread_bps < 0):
            return []
        self.paper_engine.update_ticker(tick.symbol, tick.bid, tick.ask)
        indicators = {'bid': tick.bid, 'ask': tick.ask, 'last_price': tick.last_price,
                      'price': tick.last_price, 'spread_bps': tick.spread_bps,
                      'timestamp': tick.timestamp}
        reports = []
        for strategy in self.strategies:
            if not self.watchdog.is_healthy():
                break
            proposal = self.evaluator.evaluate_tick(strategy, tick.symbol, tick.last_price, indicators)
            # The Guardian's market spread limit must also apply to daemon trades.
            spread = max(tick.spread_bps, (tick.ask - tick.bid) / ((tick.ask + tick.bid) / 2) * 10000)
            if proposal is not None and spread <= 8:
                approved, result = self.paper_engine.execute_proposal(proposal)
                if approved:
                    reports.append(result)
        return reports

    def get_status(self):
        portfolio = self.paper_engine.get_portfolio()
        return {'equity': portfolio['equity'], 'positions': portfolio['positions'],
                'watchdog_healthy': self.watchdog.is_healthy(),
                'guardian_state': self.guardian.state.value}
