from math import comb
from uuid import uuid4
from .semantic import HypothesisStatus
from .procedural import ProceduralRule, RuleType


class LearningPipeline:
    def __init__(self, episodic, semantic, procedural):
        self.episodic = episodic
        self.semantic = semantic
        self.procedural = procedural

    def process_clusters(self, min_samples=30):
        created = []
        minimum = max(30, min_samples)
        for symbol, side in self.episodic.clusters(minimum):
            trades = self.episodic.get_cluster(symbol, side, minimum)
            wins = sum(t.realized_pnl > 0 for t in trades)
            n = len(trades)
            p_value = sum(comb(n, k) for k in range(wins + 1)) / (2 ** n)
            if wins / n >= .35 or p_value >= .05:
                continue
            title = f'Persistent loss: {symbol} {side}'
            if any(h.title == title and h.status != HypothesisStatus.STALE for h in self.semantic.get_hypotheses()):
                continue
            h = self.semantic.create_hypothesis(title, f'{symbol} {side} has a low win rate', 'Win rate recovers to at least 35%')
            self.semantic.update_status(h.hypothesis_id, HypothesisStatus.CANDIDATE, {'sample_size': n, 'p_value': p_value})
            self.procedural.register_rule(ProceduralRule(str(uuid4()), h.hypothesis_id, RuleType.NEGATIVE_CONSTRAINT, symbol, f'side == {side!r}', 'BLOCK', is_active=False))
            created.append(self.semantic.get_hypothesis(h.hypothesis_id))
        return created

    def graduate_rule(self, hypothesis_id):
        h = self.semantic.get_hypothesis(hypothesis_id)
        rules = [r for r in self.procedural.get_rules() if r.hypothesis_id == hypothesis_id]
        if h is None or h.status != HypothesisStatus.SHADOW or not rules:
            return False
        if not self.semantic.update_status(hypothesis_id, HypothesisStatus.ACTIVE):
            return False
        for rule in rules:
            self.procedural.set_active(rule.rule_id, True)
        return True
