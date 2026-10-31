import json
import time
from dataclasses import replace
import pytest
from hermes_trader.memory.episodic import EpisodicStore, EpisodicTrade
from hermes_trader.memory.semantic import SemanticKnowledgeDAG, HypothesisStatus
from hermes_trader.memory.procedural import ProceduralRuleEngine, ProceduralRule, RuleType
from hermes_trader.memory.learning_pipeline import LearningPipeline
from hermes_trader.memory.drift_monitor import MarketDriftMonitor
from hermes_trader.guardian import RiskGuardian
from hermes_trader.proposer import StrategyProposer
from hermes_trader.cli import main


def trade(i, simulated=False):
    return EpisodicTrade(str(i), '2026-01-01', 'BTC', 'BUY', 1, 100, 0, 0, -1, 'bear', simulated, str(i), '{}')


def test_episodic_persistence_and_append_only(tmp_path):
    path = tmp_path / 'memory.db'
    store = EpisodicStore(path)
    store.record_trade(trade(1))
    store.record_trade(trade(2, True))
    with pytest.raises(Exception):
        store.record_trade(trade(1))
    store.close()
    store = EpisodicStore(path)
    assert [t.was_simulated for t in store.get_cluster('BTC', 'BUY', 2)] == [False, True]
    assert store.count() == 2
    store.close()


def test_lifecycle_and_persistence(tmp_path):
    path = tmp_path / 'memory.db'
    dag = SemanticKnowledgeDAG(path)
    h = dag.create_hypothesis('test', 'premise', 'failure')
    assert not dag.update_status(h.hypothesis_id, HypothesisStatus.ACTIVE)
    for status in [HypothesisStatus.CANDIDATE, HypothesisStatus.VALIDATED, HypothesisStatus.SHADOW, HypothesisStatus.ACTIVE]:
        assert dag.update_status(h.hypothesis_id, status)
    dag.close()
    dag = SemanticKnowledgeDAG(path)
    assert dag.get_active_hypotheses()[0].hypothesis_id == h.hypothesis_id
    assert dag.update_status(h.hypothesis_id, HypothesisStatus.STALE)
    assert not dag.get_active_hypotheses()


def test_rules_and_guardian():
    engine = ProceduralRuleEngine()
    rule = ProceduralRule('r', 'h', RuleType.NEGATIVE_CONSTRAINT, 'BTC', "side == 'BUY' and volatility > 2", 'BLOCK')
    engine.register_rule(rule)
    assert engine.validate_proposal('BTC', 'SELL', 'LIMIT', {'volatility': 3})[0]
    assert not engine.validate_proposal('BTC', 'BUY', 'LIMIT', {'volatility': 3})[0]
    proposal = StrategyProposer().propose('BTC', 'BUY', 1, 100, stop_loss=90)
    assert not RiskGuardian(procedural=engine).validate_proposal(proposal, {'indicators': {'volatility': 3}})[0]
    engine.set_active('r', False)
    assert RiskGuardian(procedural=engine).validate_proposal(proposal, {'indicators': {'volatility': 3}})[0]


def test_learning_shadow_and_graduation():
    episodic, semantic, procedural = EpisodicStore(), SemanticKnowledgeDAG(), ProceduralRuleEngine()
    pipeline = LearningPipeline(episodic, semantic, procedural)
    for i in range(29):
        episodic.record_trade(trade(i))
    assert pipeline.process_clusters(1) == []
    episodic.record_trade(trade(29))
    h, = pipeline.process_clusters()
    assert h.status == HypothesisStatus.CANDIDATE and h.sample_size == 30
    assert procedural.validate_proposal('BTC', 'BUY', 'LIMIT', {})[0]
    assert not pipeline.graduate_rule(h.hypothesis_id)
    assert semantic.update_status(h.hypothesis_id, HypothesisStatus.VALIDATED)
    assert semantic.update_status(h.hypothesis_id, HypothesisStatus.SHADOW)
    assert pipeline.graduate_rule(h.hypothesis_id)
    assert not procedural.validate_proposal('BTC', 'BUY', 'LIMIT', {})[0]
    assert pipeline.process_clusters() == []


def test_drift_and_burst():
    monitor = MarketDriftMonitor()
    now = time.time()
    for i in range(4):
        monitor.record_falsification(str(i), now)
    monitor.record_falsification('old', now - 5 * 3600)
    assert not monitor.is_burst_triggered()
    monitor.record_falsification('fifth', now)
    assert monitor.is_burst_triggered()
    assert monitor.check_distribution_drift([10, 11, 12], [0, 1, 2])
    assert not monitor.check_distribution_drift([0, 1, 2], [0, 1, 2])


def test_memory_status(tmp_path, capsys):
    path = tmp_path / 'memory.db'
    store = EpisodicStore(path)
    store.record_trade(trade(1))
    store.close()
    assert main(['memory-status', '--db', str(path)]) == 0
    assert json.loads(capsys.readouterr().out)['episodic_trade_count'] == 1
