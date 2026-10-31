import ast
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
import json
import operator
import sqlite3
from .semantic import now


class RuleType(str, Enum):
    NEGATIVE_CONSTRAINT = 'NEGATIVE_CONSTRAINT'
    EXECUTION_GUARD = 'EXECUTION_GUARD'
    REGIME_FILTER = 'REGIME_FILTER'


@dataclass
class ProceduralRule:
    rule_id: str
    hypothesis_id: str
    rule_type: RuleType
    symbol: str
    condition_dsl: str
    action: str
    ttl_hours: float = 168.0
    max_capital_usd: float = 1000.0
    is_active: bool = True
    created_at: str = ''


def _condition(expression, context):
    """Evaluate comparisons and boolean operators without executing arbitrary code."""
    comparisons = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
                   ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
                   ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b}
    def evaluate(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return context[node.id]
        if isinstance(node, (ast.List, ast.Tuple)):
            return [evaluate(x) for x in node.elts]
        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            values = (bool(evaluate(x)) for x in node.values)
            return all(values) if isinstance(node.op, ast.And) else any(values)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not evaluate(node.operand)
        if isinstance(node, ast.Compare):
            left = evaluate(node.left)
            for op, right_node in zip(node.ops, node.comparators):
                right = evaluate(right_node)
                if type(op) not in comparisons or not comparisons[type(op)](left, right):
                    return False
                left = right
            return True
        raise ValueError('Unsupported rule expression')
    return bool(evaluate(ast.parse(expression, mode='eval').body))


class ProceduralRuleEngine:
    def __init__(self, path=':memory:'):
        self.connection = sqlite3.connect(path)
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.execute('CREATE TABLE IF NOT EXISTS procedural_rules (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
        self.connection.commit()

    def register_rule(self, rule):
        ast.parse(rule.condition_dsl, mode='eval')
        if not rule.created_at:
            rule.created_at = now()
        with self.connection:
            self.connection.execute('INSERT INTO procedural_rules VALUES (?, ?)', (rule.rule_id, json.dumps(asdict(rule))))

    def get_rules(self):
        result = []
        for (data,) in self.connection.execute('SELECT data FROM procedural_rules ORDER BY rowid'):
            fields = json.loads(data)
            fields['rule_type'] = RuleType(fields['rule_type'])
            result.append(ProceduralRule(**fields))
        return result

    def set_active(self, rule_id, active):
        rule = next((r for r in self.get_rules() if r.rule_id == rule_id), None)
        if rule is None:
            return False
        rule.is_active = active
        with self.connection:
            self.connection.execute('UPDATE procedural_rules SET data=? WHERE id=?', (json.dumps(asdict(rule)), rule_id))
        return True

    def validate_proposal(self, symbol, side, order_type, indicators):
        context = dict(indicators or {})
        context.update(symbol=symbol, side=getattr(side, 'value', side), order_type=getattr(order_type, 'value', order_type))
        for rule in self.get_rules():
            if not rule.is_active or rule.symbol not in (symbol, '*'):
                continue
            try:
                created = datetime.fromisoformat(rule.created_at.replace('Z', '+00:00'))
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) >= created + timedelta(hours=rule.ttl_hours):
                    continue
                matches = _condition(rule.condition_dsl, context)
            except (KeyError, ValueError, TypeError, SyntaxError, OverflowError):
                return False, f'Invalid procedural rule {rule.rule_id}: {rule.condition_dsl}'
            if matches and rule.action == 'BLOCK':
                return False, f'Blocked by procedural rule {rule.rule_id}: {rule.condition_dsl}'
        return True, 'All procedural rules passed'

    def close(self):
        self.connection.close()
