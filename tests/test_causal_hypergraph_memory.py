import json
import pytest

from hermes_trader.cli import main
from hermes_trader.guardian import RiskGuardian
from hermes_trader.memory.causal_shadow import CausalShadowTracker
from hermes_trader.memory.episodic import EpisodicStore
from hermes_trader.memory.fencing import FencingTokenManager
from hermes_trader.memory.hypergraph import HypergraphView
from hermes_trader.memory.procedural import ProceduralRule, ProceduralRuleEngine, RuleType
from hermes_trader.memory.synaptic_sleep import SynapticSleepCycle
from hermes_trader.proposer import StrategyProposer


def test_shadow_records_and_isolation(tmp_path):
    path = tmp_path / 'memory.db'
    episodic = EpisodicStore(path)
    tracker = CausalShadowTracker(path)
    buy = tracker.record_blocked('BTC', 'BUY', 'r', 100)
    sell = tracker.record_blocked('BTC', 'SELL', 'r', 100)
    assert tracker.resolve_counterfactual(buy, 110) == pytest.approx(9.896)
    assert tracker.resolve_counterfactual(sell, 110) == pytest.approx(-10.104)
    assert tracker.get_shadow_stats('BTC')['wins'] == 1
    assert tracker.get_shadow_stats('BTC')['losses'] == 1
    assert tracker.get_shadow_stats('ETH')['total'] == 0
    assert episodic.count() == 0
    with pytest.raises(ValueError):
        tracker.resolve_counterfactual(buy, 120)
    tracker.close()
    episodic.close()


def test_procedural_block_records_proposal_price(tmp_path):
    path = tmp_path / 'memory.db'
    rules = ProceduralRuleEngine(path)
    rules.register_rule(ProceduralRule('r', 'h', RuleType.NEGATIVE_CONSTRAINT, 'BTC', 'True', 'BLOCK'))
    proposal = StrategyProposer().propose('BTC', 'BUY', 1, 100, stop_loss=90)
    assert not RiskGuardian(procedural=rules).validate_proposal(proposal, {})[0]
    row = rules.connection.execute('SELECT record_id, hypothetical_price FROM shadow_counterfactuals').fetchone()
    assert row[1] == 100
    assert rules.shadow_tracker.resolve_counterfactual(row[0], 105) == pytest.approx(4.898)
    rules.close()


def test_sleep_and_cli_persist_graph(tmp_path, capsys):
    path = tmp_path / 'memory.db'
    graph = HypergraphView(path)
    low = graph.add_hyperedge(['a', 'b'], weight=.1)
    normal = graph.add_hyperedge(['b', 'c'])
    immune = graph.add_hyperedge(['rare'], weight=.01, z_score=-3, impact_score=1)
    assert immune.is_immune
    assert graph.add_hyperedge(['other'], z_score=3, impact_score=1).is_immune
    assert SynapticSleepCycle().prune_hypergraph(graph) == 1
    assert graph.get_hyperedge(low.edge_id) is None
    assert graph.get_hyperedge(normal.edge_id).weight == pytest.approx(.95)
    assert graph.get_hyperedge(immune.edge_id).weight == .01
    graph.close()
    assert main(['hypergraph-summary', '--db', str(path)]) == 0
    assert json.loads(capsys.readouterr().out)['immune_edges'] == 2
    assert main(['sleep-cycle', '--db', str(path)]) == 0
    assert json.loads(capsys.readouterr().out)['pruned_edges'] == 0


def test_fencing_across_managers(tmp_path):
    path = tmp_path / 'memory.db'
    first, second = FencingTokenManager(path), FencingTokenManager(path)
    old = first.acquire_token('one')
    new = second.acquire_token('two')
    assert new.epoch == old.epoch + 1
    assert not first.validate_token(old)
    assert first.validate_token(new)
    first.close()
    second.close()
