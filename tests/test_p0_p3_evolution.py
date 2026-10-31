from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from hermes_trader.contracts.v1 import OrderIntentV1
from hermes_trader.feed.rate_governor import RateGovernor
from hermes_trader.reconciliation.resolver import ReconciliationResolver
from hermes_trader.telemetry import MCTSInspectorStream
from hermes_trader.strategy.passport import StrategyPassportManager
from hermes_trader.strategy.stress_tester import SyntheticStressTester
from hermes_trader.venues import HyperliquidVenueAdapter, VenueCapabilityMatrix
from hermes_trader.cli import main


def test_atomic_reservation():
    governor = RateGovernor(100, 20)
    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(lambda _: governor.atomic_reserve(), range(300)))
    assert sum(results) == 80 and governor.current_weight == 80
    assert governor.atomic_reserve(20, True)
    assert not governor.atomic_reserve(1, True)


def test_reconciliation():
    intent = OrderIntentV1('id', 'c', 'a', 'BTC', 'BUY', 1, 10, 9, None, '', '')
    resolver = ReconciliationResolver()
    for status, expected in [('FILLED', 'FILLED'), ('CANCELED', 'FAILED'), ('NEW', 'PENDING')]:
        assert resolver.resolve_timeout(intent, [{'clientOrderId': 'id', 'status': status}], {})[0] == expected
    assert resolver.resolve_timeout(intent, [], {'BTC': {'size': 2, 'previous_size': 1}})[0] == 'FILLED_UNTRAKED'
    assert resolver.resolve_timeout(intent, [], {}) == ('NOT_FOUND_SAFE_TO_RETRY', {})


def test_inspector():
    stream = MCTSInspectorStream(maxlen=2)
    for i in range(3):
        stream.emit('tick', 'c', 'a', {'i': i, 'secret': 'x', 'nested': [{'api_key': 'y', 'value': 2}]})
    frames = stream.get_recent_frames()
    assert [f.seq for f in frames] == [2, 3]
    assert frames[0].data == {'i': 1, 'nested': [{'value': 2}]}
    assert stream.get_recent_frames(0) == []


def test_passport():
    manager = StrategyPassportManager()
    passport = manager.issue_passport('s', 'code', 'config', 1.1, 2, True)
    assert manager.validate_passport(passport, 'code', 'config')
    assert not manager.validate_passport(passport, 'tampered', 'config')
    assert not manager.validate_passport(replace(passport, expires_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat()), 'code', 'config')
    assert not manager.validate_passport(replace(passport, stress_tested=False), 'code', 'config')


def test_stress_scenarios():
    ticks = []
    result = SyntheticStressTester().run_stress_test(lambda tick: ticks.append(tick) or 1)
    crash = [t for t in ticks if t['scenario'] == 'flash_crash']
    assert len(crash) == 5 and crash[-1]['price'] == 45000 and crash[0]['depth'] == .2
    assert result['survived'] and result['max_drawdown'] > 0
    assert not SyntheticStressTester().run_stress_test(lambda tick: 100)['survived']


def test_venues_and_cli(capsys):
    matrix = VenueCapabilityMatrix()
    assert matrix.get('HYPERLIQUID').settlement_type == 'L1_APPCHAIN'
    payload = HyperliquidVenueAdapter({'BTC': 0}).build_order_payload('BTC', True, 60000, .1, post_only=True)
    assert payload['orders'][0] == {'a': 0, 'b': True, 'p': '60000', 's': '0.1', 'r': False, 't': {'limit': {'tif': 'Alo'}}}
    assert main(['venues']) == 0
    assert 'HYPERLIQUID' in capsys.readouterr().out
    assert main(['stress-test']) == 0
    assert 'survived' in capsys.readouterr().out


def test_guardian_passport_enforcement():
    from hermes_trader.guardian import RiskGuardian
    from hermes_trader.proposer import StrategyProposer
    manager = StrategyPassportManager()
    proposal = StrategyProposer().propose('BTC', 'BUY', .01, 100, stop_loss=90)
    guardian = RiskGuardian(procedural=None)
    proposal.strategy_passport_hash = 'unverifiable'
    assert not guardian.validate_proposal(proposal, {})[0]
    proposal.strategy_passport_hash = None
    proposal.passport = manager.issue_passport(proposal.strategy_id, 'code', 'config', 1.2, 2, True)
    proposal.current_code_content = 'code'
    proposal.current_config_content = 'config'
    assert guardian.validate_proposal(proposal, {})[0]
    proposal.current_code_content = 'changed'
    assert not guardian.validate_proposal(proposal, {})[0]
