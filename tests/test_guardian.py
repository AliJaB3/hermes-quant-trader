from dataclasses import replace
from hermes_trader.contracts import GuardianState, OrderSide, Position, PositionSide
from hermes_trader.guardian import RiskGuardian, KillSwitchManager

def test_limits(proposal):
    g = RiskGuardian()
    assert g.validate_proposal(proposal, {})[0]
    for p, portfolio in [(replace(proposal, quantity=1), {}), (proposal, {'leverage': 6}), (proposal, {'drawdown_pct': 5}), (proposal, {'drawdown_velocity': 2}), (replace(proposal, cvar_estimate=501), {}), (replace(proposal, quantity=float('nan')), {})]:
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
