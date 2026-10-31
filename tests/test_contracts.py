from dataclasses import asdict
import json
from hermes_trader.contracts import OrderSide, Position, PositionSide

def test_serialization(proposal):
    data = json.loads(json.dumps(asdict(proposal)))
    assert data['side'] == 'BUY'
    assert OrderSide(data['side']) == OrderSide.BUY
    assert Position('BTC', PositionSide.LONG, 1, 10, 11, 1, 0, 1).unrealized_pnl == 1
