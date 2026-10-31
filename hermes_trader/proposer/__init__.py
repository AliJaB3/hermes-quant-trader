from datetime import datetime, timezone
from uuid import uuid4
from hermes_trader.contracts import OrderProposal, OrderSide, OrderType

class StrategyProposer:
    def propose(self, symbol, side, quantity, price=None, thesis=None, negative_constraints=None, market_conditions=None, strategy_id='manual', cvar_estimate=0.0, order_type=None, stop_loss=None):
        if thesis and (thesis.symbol != symbol or thesis.status != 'OPEN'):
            raise ValueError('an open thesis for the requested symbol is required')
        # Free-form constraints cannot be reliably evaluated by a deterministic engine.
        if negative_constraints:
            raise ValueError('negative constraints require operator review before proposing')
        rationale = thesis.hypothesis if thesis else 'Manual proposal'
        if market_conditions:
            rationale += f'; market conditions: {market_conditions}'
        return OrderProposal(str(uuid4()), str(uuid4()), symbol, OrderSide(side), OrderType(order_type or ('LIMIT' if price is not None else 'MARKET')), quantity, price, stop_loss, None, strategy_id, thesis.thesis_id if thesis else '', rationale, cvar_estimate, datetime.now(timezone.utc).isoformat())
