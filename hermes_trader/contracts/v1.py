"""Versioned, serializable messages exchanged by trading components."""
from dataclasses import dataclass


@dataclass
class OrderIntentV1:
    intent_id: str
    correlation_id: str
    causation_id: str
    symbol: str
    side: str
    qty: float
    price: float | None
    stop_loss: float
    take_profit: float | None
    strategy_passport_hash: str
    created_at: str


@dataclass
class ExecutionReportV1:
    execution_id: str
    intent_id: str
    symbol: str
    side: str
    filled_qty: float
    avg_fill_price: float
    fee_usd: float
    slippage_bps: float
    timestamp: str


@dataclass
class PositionStateV1:
    symbol: str
    side: str
    size: float
    entry_price: float
    mark_price: float
    unrealized_pnl: float
    leverage: float


@dataclass
class RiskSnapshotV1:
    equity: float
    cash: float
    drawdown_pct: float
    drawdown_velocity: float
    cvar_99_usd: float
    open_positions_count: int
    state: str
    timestamp: str


@dataclass
class StrategyPassportV1:
    passport_id: str
    strategy_id: str
    code_hash: str
    config_hash: str
    deflated_sharpe: float
    max_drawdown_pct: float
    stress_tested: bool
    issued_at: str
    expires_at: str
