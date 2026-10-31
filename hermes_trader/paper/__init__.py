from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import math
import time
from uuid import uuid4
from hermes_trader.contracts import ExecutionReport, OrderSide, OrderType, Position, PositionSide
from hermes_trader.guardian import RiskGuardian, KillSwitchManager
from .store import PortfolioStore
from .slippage import DepthSlippageModel

class PaperEngine:
    def __init__(self, initial_balance=10000.0, guardian=None, store=None, store_path=None, slippage_model=None):
        if not math.isfinite(initial_balance) or initial_balance <= 0:
            raise ValueError('initial balance must be positive and finite')
        self.initial_balance = float(initial_balance)
        self.cash = float(initial_balance)
        self.guardian = guardian or RiskGuardian()
        self.kill_switch = KillSwitchManager(self.guardian)
        self.tickers = {}
        self.positions = {}
        self.reports = []
        self.peak_equity = self.initial_balance
        self._history = [(time.monotonic(), 0.0)]
        self.store = store if store is not None else PortfolioStore(store_path)
        self.slippage_model = slippage_model or DepthSlippageModel()
        saved = self.store.load_state()
        if saved is not None:
            self.initial_balance = saved['initial_balance']
            self.cash = saved['cash']
            self.peak_equity = saved['peak_equity']
            self.tickers = {s: tuple(v) for s, v in saved['tickers'].items()}
            self.positions = {s: Position(**{**p, 'side': PositionSide(p['side'])}) for s, p in saved['positions'].items()}
            self.reports = [ExecutionReport(**{**r, 'side': OrderSide(r['side'])}) for r in saved['reports']]

    def _save(self):
        self.store.save_state({'initial_balance': self.initial_balance, 'cash': self.cash,
                               'peak_equity': self.peak_equity, 'tickers': self.tickers,
                               'positions': {s: asdict(p) for s, p in self.positions.items()},
                               'reports': [asdict(r) for r in self.reports]})

    def update_ticker(self, symbol, bid, ask):
        if not symbol or not all(math.isfinite(x) and x > 0 for x in (bid, ask)) or bid > ask:
            raise ValueError('invalid ticker')
        self.tickers[symbol] = (float(bid), float(ask))
        self._mark()

    def _mark(self):
        for symbol, p in self.positions.items():
            bid, ask = self.tickers[symbol]
            p.current_price = (bid + ask) / 2
            sign = 1 if p.side == PositionSide.LONG else -1
            p.unrealized_pnl = sign * p.size * (p.current_price - p.entry_price)
        equity = self.cash + sum(p.unrealized_pnl for p in self.positions.values())
        self.peak_equity = max(self.peak_equity, equity)
        dd = max(0.0, (self.peak_equity - equity) / self.peak_equity * 100)
        now = time.monotonic()
        self._history.append((now, dd))
        self._history = [x for x in self._history if x[0] >= now - 3600]
        # Compare against the oldest observation in the rolling hour, normalized to one hour.
        elapsed = now - self._history[0][0]
        velocity = max(0.0, (dd - self._history[0][1]) * 3600 / max(elapsed, 60))
        self.kill_switch.monitor(dd, velocity)
        return equity, dd, velocity

    def get_portfolio(self):
        equity, dd, velocity = self._mark()
        closed = [r for r in self.reports if r.realized_pnl != 0]
        return {'cash': self.cash, 'equity': equity, 'initial_balance': self.initial_balance,
                'drawdown_pct': dd, 'drawdown_velocity': velocity, 'positions': dict(self.positions),
                'cvar_99': 0.0, 'trade_count': len(self.reports),
                'win_rate': sum(r.realized_pnl > 0 for r in closed) / len(closed) if closed else 0.0,
                'prices': {s: (b + a) / 2 for s, (b, a) in self.tickers.items()}}

    def execute_proposal(self, proposal):
        with self.guardian.execution_lock:
            return self._execute_proposal(proposal)

    def _execute_proposal(self, proposal):
        if proposal.symbol not in self.tickers:
            return False, 'No ticker available'
        try:
            side = OrderSide(proposal.side)
            order_type = OrderType(proposal.order_type)
        except ValueError:
            return False, 'Invalid order side or type'
        if order_type not in (OrderType.MARKET, OrderType.LIMIT):
            return False, 'Conditional orders are not supported by the paper engine'
        bid, ask = self.tickers[proposal.symbol]
        market = ask if side == OrderSide.BUY else bid
        slip_rate = self.slippage_model.compute_slippage(abs(proposal.quantity) * market)
        fill = market * (1 + slip_rate if side == OrderSide.BUY else 1 - slip_rate)
        if order_type == OrderType.LIMIT and (proposal.price is None or (side == OrderSide.BUY and fill > proposal.price) or (side == OrderSide.SELL and fill < proposal.price)):
            return False, 'Limit price is not executable'
        from dataclasses import replace
        risk_proposal = replace(proposal, price=fill)
        portfolio = self.get_portfolio()
        approved, reason = self.guardian.validate_proposal(risk_proposal, portfolio)
        if not approved:
            return False, reason
        token = self.guardian.reserve_proposal(risk_proposal, portfolio)
        if token is None:
            return False, 'Insufficient reserved capacity'
        try:
            if not self.guardian.reservations.consume(token.token_id):
                return False, 'Execution token expired or consumed'
            snapshot = (self.cash, deepcopy(self.positions), list(self.reports), self.peak_equity, list(self._history), self.guardian.state)
            try:
                return self._fill(proposal, side, market, fill)
            except Exception:
                self.cash, self.positions, self.reports, self.peak_equity, self._history, self.guardian.state = snapshot
                raise
        finally:
            self.guardian.reservations.release(token.token_id)

    def _fill(self, proposal, side, market, fill):
        qty = proposal.quantity
        existing = self.positions.get(proposal.symbol)
        old = (existing.size if existing.side == PositionSide.LONG else -existing.size) if existing else 0.0
        delta = qty if side == OrderSide.BUY else -qty
        new = old + delta
        realized = 0.0
        if old and old * delta < 0:
            realized = min(abs(old), qty) * (fill - existing.entry_price) * (1 if old > 0 else -1)
        fee = qty * fill * self.guardian.limits.taker_fee_rate
        self.cash += realized - fee
        if abs(new) < 1e-12:
            self.positions.pop(proposal.symbol, None)
        else:
            entry = fill if old == 0 or old * new < 0 else ((abs(old) * existing.entry_price + qty * fill) / abs(new) if old * delta > 0 else existing.entry_price)
            self.positions[proposal.symbol] = Position(proposal.symbol, PositionSide.LONG if new > 0 else PositionSide.SHORT, abs(new), entry, fill, 0.0, 0.0, 1.0)
        report = ExecutionReport(str(uuid4()), proposal.proposal_id, proposal.symbol, side, qty, fill, fee, abs(fill - market), realized, datetime.now(timezone.utc).isoformat())
        self.reports.append(report)
        self._mark()
        self._save()
        return True, report
