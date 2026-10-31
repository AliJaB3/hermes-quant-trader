from dataclasses import replace
from hermes_trader.contracts import GuardianState, OrderSide, Position, PositionSide, OrderType
from hermes_trader.guardian import RiskGuardian, RiskLimits, KillSwitchManager

def test_limits(proposal):
    proposal = replace(proposal, stop_loss=9000)
    g = RiskGuardian()
    assert g.validate_proposal(proposal, {})[0]
    for p, portfolio in [(replace(proposal, quantity=1), {}), (proposal, {'leverage': 6}), (proposal, {'drawdown_pct': 5}), (proposal, {'drawdown_velocity': 2}), (replace(proposal, quantity=float('nan')), {})]:
        assert not g.validate_proposal(p, portfolio)[0]

def test_reduce_only_and_halt(proposal):
    g = RiskGuardian(state=GuardianState.REDUCE_ONLY)
    p = Position('BTCUSDT', PositionSide.LONG, .02, 10000, 10000, 0, 0, 1)
    portfolio = {'positions': {'BTCUSDT': p}}
    assert not g.validate_proposal(proposal, portfolio)[0]
    assert g.validate_proposal(replace(proposal, side=OrderSide.SELL), portfolio)[0]
    assert not g.validate_proposal(replace(proposal, side=OrderSide.SELL, quantity=.05), portfolio)[0]
    calls = []
    k = KillSwitchManager(g, 'secret', lambda: calls.append(1))
    assert k.monitor(0, 2)
    assert calls == [1] and g.state == GuardianState.HALTED
    assert not k.resume('wrong') and k.resume('secret')


def test_independent_cvar_and_spread(proposal):
    proposal = replace(proposal, stop_loss=9000, cvar_estimate=0)
    g = RiskGuardian(RiskLimits(max_cvar_99_usd=3))
    assert g.validate_proposal(proposal, {}) == (False, "Independent CVaR limit exceeded")
    market = replace(proposal, order_type=OrderType.MARKET)
    g = RiskGuardian()
    for spread in (9, {'BTCUSDT': 9}):
        assert g.validate_proposal(market, {'spread_bps': spread}) == (False, "Market order rejected: spread exceeds 8 bps limit")
    assert g.validate_proposal(market, {'spread_bps': 8})[0]


def test_opening_stop_loss(proposal):
    g = RiskGuardian()
    assert g.validate_proposal(proposal, {}) == (False, "Missing mandatory stop-loss on position opening")
    for side, stop in ((OrderSide.BUY, 10001), (OrderSide.SELL, 9999)):
        assert g.validate_proposal(replace(proposal, side=side, stop_loss=stop), {}) == (False, "Invalid stop-loss level relative to entry price")
    assert g.validate_proposal(replace(proposal, side=OrderSide.SELL, stop_loss=11000), {})[0]
