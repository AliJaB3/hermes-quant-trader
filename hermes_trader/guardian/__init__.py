from dataclasses import dataclass
import hmac
import math
from hermes_trader.contracts import GuardianState, OrderSide, PositionSide

@dataclass
class RiskLimits:
    max_drawdown_pct: float = 5.0
    max_drawdown_velocity_pct_per_hr: float = 1.5
    max_cvar_99_usd: float = 500.0
    max_leverage: float = 5.0
    max_position_size_usd: float = 2000.0
    maker_fee_rate: float = 0.0002
    taker_fee_rate: float = 0.0004

class RiskGuardian:
    def __init__(self, limits=None, state=GuardianState.NORMAL):
        self.limits = limits or RiskLimits()
        self.state = GuardianState(state)

    def validate_proposal(self, proposal, current_portfolio):
        if self.state == GuardianState.HALTED:
            return False, "Guardian is halted"
        try:
            side = OrderSide(proposal.side)
            qty = float(proposal.quantity)
            price = float(proposal.price if proposal.price is not None else current_portfolio.get('prices', {}).get(proposal.symbol, 0))
            cvar = float(proposal.cvar_estimate)
            drawdown = float(current_portfolio.get('drawdown_pct', 0))
            velocity = float(current_portfolio.get('drawdown_velocity', 0))
            portfolio_cvar = float(current_portfolio.get('cvar_99', 0))
            leverage = float(current_portfolio.get('leverage', 1))
            if not all(math.isfinite(x) for x in (qty, price, cvar, drawdown, velocity, portfolio_cvar, leverage)) or qty <= 0 or price <= 0 or cvar < 0 or portfolio_cvar < 0 or leverage < 0:
                return False, "Invalid risk inputs"
            positions = current_portfolio.get('positions', {})
            pos = positions.get(proposal.symbol) if isinstance(positions, dict) else next((p for p in positions if (p.get('symbol') if isinstance(p, dict) else p.symbol) == proposal.symbol), None)
            def field(obj, name, default):
                return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)
            size = float(field(pos, 'size', 0)) if pos else 0
            position_side = field(pos, 'side', PositionSide.FLAT) if pos else PositionSide.FLAT
            signed = -abs(size) if position_side == PositionSide.SHORT else abs(size) if position_side == PositionSide.LONG else 0
            result = signed + (qty if side == OrderSide.BUY else -qty)
            if self.state == GuardianState.REDUCE_ONLY and (signed == 0 or signed * result < 0 or abs(result) >= abs(signed)):
                return False, "Reduce-only order must reduce the existing position"
            if drawdown >= self.limits.max_drawdown_pct or velocity >= self.limits.max_drawdown_velocity_pct_per_hr:
                return False, "Drawdown risk limit exceeded"
            if max(cvar, portfolio_cvar) > self.limits.max_cvar_99_usd:
                return False, "CVaR limit exceeded"
            if leverage > self.limits.max_leverage:
                return False, "Leverage limit exceeded"
            if abs(result) * price > self.limits.max_position_size_usd:
                return False, "Position size limit exceeded"
            equity = current_portfolio.get('equity')
            other_positions = positions.values() if isinstance(positions, dict) else positions
            other_exposure = sum(abs(float(field(p, 'size', 0))) * float(field(p, 'current_price', 0)) for p in other_positions if field(p, 'symbol', '') != proposal.symbol)
            total_exposure = other_exposure + abs(result) * price
            if not math.isfinite(total_exposure) or other_exposure < 0:
                return False, 'Invalid portfolio exposure'
            if equity is not None and (not math.isfinite(float(equity)) or float(equity) <= 0 or total_exposure > float(equity) * self.limits.max_leverage):
                return False, "Leverage limit exceeded"
        except (ValueError, TypeError, AttributeError, OverflowError):
            return False, "Invalid proposal or portfolio"
        return True, "Approved"

class KillSwitchManager:
    def __init__(self, guardian, operator_key=None, cancel_orders=None):
        self.guardian = guardian
        self.operator_key = operator_key
        self.cancel_orders = cancel_orders

    def trigger_emergency_stop(self):
        self.guardian.state = GuardianState.HALTED
        if self.cancel_orders:
            self.cancel_orders()
        return "HALTED: cancel all active orders"

    def monitor(self, drawdown_pct, drawdown_velocity):
        limits = self.guardian.limits
        if drawdown_pct >= limits.max_drawdown_pct or drawdown_velocity >= limits.max_drawdown_velocity_pct_per_hr:
            self.trigger_emergency_stop()
            return True
        return False

    def resume(self, operator_key):
        if not self.operator_key or not isinstance(operator_key, str) or not hmac.compare_digest(operator_key, self.operator_key):
            return False
        self.guardian.state = GuardianState.NORMAL
        return True
