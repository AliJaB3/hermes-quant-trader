from dataclasses import replace
import pytest
from hermes_trader.contracts import OrderSide, OrderType, PositionSide
from hermes_trader.paper import PaperEngine

def test_execution_and_pnl(proposal):
    e = PaperEngine()
    e.update_ticker('BTCUSDT', 9999, 10000)
    p = replace(proposal, order_type=OrderType.MARKET, price=None, stop_loss=9000)
    ok, buy = e.execute_proposal(p)
    assert ok and buy.avg_fill_price > 10000
    assert buy.fee_paid == pytest.approx(buy.avg_fill_price * .01 * .0004)
    assert e.positions['BTCUSDT'].side == PositionSide.LONG
    e.update_ticker('BTCUSDT', 10100, 10101)
    ok, sell = e.execute_proposal(replace(p, side=OrderSide.SELL))
    assert ok and sell.realized_pnl == pytest.approx((sell.avg_fill_price - buy.avg_fill_price) * .01)
    assert not e.positions
    assert e.cash == pytest.approx(10000 + sell.realized_pnl - sell.fee_paid - buy.fee_paid)

def test_reversal_and_rejections(proposal):
    e = PaperEngine()
    assert not e.execute_proposal(proposal)[0]
    e.update_ticker('BTCUSDT', 9999, 10000)
    p = replace(proposal, order_type=OrderType.MARKET, price=None, stop_loss=9000)
    assert e.execute_proposal(p)[0]
    assert e.execute_proposal(replace(p, side=OrderSide.SELL, quantity=.02, stop_loss=11000))[0]
    assert e.positions['BTCUSDT'].side == PositionSide.SHORT
    assert not e.execute_proposal(proposal)[0]  # buy limit below executable ask
    with pytest.raises(ValueError): e.update_ticker('BTCUSDT', 2, 1)
