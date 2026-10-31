import json

import pytest

from hermes_trader.cli import main
from hermes_trader.guardian import RiskGuardian
from hermes_trader.strategy import StrategyLoader, StrategyEvaluator, WalkForwardValidator


@pytest.fixture
def definition():
    return {'strategy_id': 'test', 'version': '1', 'target_universe': ['BTC'],
            'alpha_rules': [{'indicator': 'ofi', 'condition': 'ofi < -0.5 and spread_bps <= 6'}],
            'execution_parameters': {'quantity': 1, 'stop_loss_pct': 1, 'take_profit_pct': 2}}


def test_loader(definition, tmp_path):
    loader = StrategyLoader()
    assert loader.load_from_dict(definition).strategy_id == 'test'
    path = tmp_path / 'strategy.json'
    path.write_text(json.dumps(definition))
    assert loader.load_from_yaml_or_json(str(path)).target_universe == ['BTC']
    assert loader.load_from_yaml_or_json('strategy_id: x\nversion: "1"\ntarget_universe: [BTC]').strategy_id == 'x'
    with pytest.raises(ValueError):
        loader.load_from_dict({'strategy_id': 'x'})


def test_evaluator(definition):
    strategy = StrategyLoader().load_from_dict(definition)
    evaluator = StrategyEvaluator()
    proposal = evaluator.evaluate_tick(strategy, 'BTC', 100, {'ofi': -1, 'spread_bps': 5})
    assert proposal.stop_loss == 99 and proposal.take_profit == 102
    assert RiskGuardian().validate_proposal(proposal, {'equity': 10000})[0]
    assert evaluator.evaluate_tick(strategy, 'BTC', 100, {'ofi': 0, 'spread_bps': 5}) is None
    strategy.alpha_rules[0]['condition'] = '__import__("os").system("false")'
    assert evaluator.evaluate_tick(strategy, 'BTC', 100, {}) is None


def test_walk_forward(definition):
    strategy = StrategyLoader().load_from_dict(definition)
    candles = [{'open': 100, 'high': 103, 'low': 100, 'close': 102,
                'indicators': {'ofi': -1, 'spread_bps': 5}} for _ in range(12)]
    validator = WalkForwardValidator()
    free = validator.validate(strategy, candles, fee_rate=0, slippage_rate=0)
    costly = validator.validate(strategy, candles)
    assert costly.total_trades > 0 and costly.is_admissible
    assert costly.net_pnl < free.net_pnl
    assert validator.validate(strategy, [], folds=3).is_admissible is False


def test_cli_strategy(definition, tmp_path, capsys):
    path = tmp_path / 'strategy.json'
    path.write_text(json.dumps(definition))
    assert main(['test-strategy', '--file', str(path)]) == 0
    assert json.loads(capsys.readouterr().out)['is_admissible'] is False
    path.write_text('{}')
    assert main(['test-strategy', '--file', str(path)]) == 1
    assert 'error' in json.loads(capsys.readouterr().out)
