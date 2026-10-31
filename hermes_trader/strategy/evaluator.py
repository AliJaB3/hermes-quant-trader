import ast
import math
import operator
from datetime import datetime, timezone
from uuid import uuid4

from hermes_trader.contracts import OrderProposal, OrderSide, OrderType

_COMPARISONS = {ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt,
                ast.GtE: operator.ge, ast.Eq: operator.eq, ast.NotEq: operator.ne}


def _condition(expression, indicators):
    """Evaluate comparisons and boolean combinations without executing Python code."""
    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Name):
            return indicators[node.id]
        if isinstance(node, ast.Constant) and type(node.value) in (int, float, bool):
            return node.value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = visit(node.operand)
            return -value if isinstance(node.op, ast.USub) else +value
        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            values = (bool(visit(v)) for v in node.values)
            return all(values) if isinstance(node.op, ast.And) else any(values)
        if isinstance(node, ast.Compare):
            left = visit(node.left)
            for op, right_node in zip(node.ops, node.comparators):
                if type(op) not in _COMPARISONS:
                    raise ValueError('unsupported comparison')
                right = visit(right_node)
                if not _COMPARISONS[type(op)](left, right):
                    return False
                left = right
            return True
        raise ValueError('unsupported condition')
    try:
        return bool(visit(ast.parse(expression, mode='eval')))
    except (SyntaxError, KeyError, TypeError, ValueError, ArithmeticError):
        return False


class StrategyEvaluator:
    def evaluate_tick(self, strategy, symbol, current_price, indicators):
        if symbol not in strategy.target_universe or not strategy.alpha_rules:
            return None
        if not all(isinstance(rule, dict) and rule.get('condition') and _condition(rule['condition'], indicators)
                   for rule in strategy.alpha_rules):
            return None
        params = strategy.execution_parameters
        try:
            price = float(current_price)
            stop_pct = float(params.get('stop_loss_pct', 1.0)) / 100
            take_pct = float(params.get('take_profit_pct', 2.0)) / 100
            quantity = float(params.get('quantity', 1.0))
            side = OrderSide(str(params.get('side', 'BUY')).upper())
            if not all(math.isfinite(x) for x in (price, stop_pct, take_pct, quantity)) or price <= 0 or quantity <= 0 or not 0 < stop_pct < 1 or not 0 < take_pct < 1:
                return None
        except (ValueError, TypeError):
            return None
        direction = 1 if side == OrderSide.BUY else -1
        return OrderProposal(str(uuid4()), str(uuid4()), symbol, side, OrderType.MARKET,
                             quantity, price, price * (1 - direction * stop_pct),
                             price * (1 + direction * take_pct), strategy.strategy_id, '',
                             'Strategy rules matched', 0.0, datetime.now(timezone.utc).isoformat())
