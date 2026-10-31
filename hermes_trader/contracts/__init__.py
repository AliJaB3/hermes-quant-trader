from dataclasses import dataclass
from enum import Enum

class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderType(str, Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"

class PositionSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"

class OrderStatus(str, Enum):
    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"

class GuardianState(str, Enum):
    NORMAL = "NORMAL"
    REDUCE_ONLY = "REDUCE_ONLY"
    HALTED = "HALTED"

@dataclass
class OrderProposal:
    proposal_id: str
    correlation_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: float | None
    stop_loss: float | None
    take_profit: float | None
    strategy_id: str
    thesis_id: str
    rationale: str
    cvar_estimate: float
    created_at: str

@dataclass
class ExecutionReport:
    execution_id: str
    proposal_id: str
    symbol: str
    side: OrderSide
    filled_quantity: float
    avg_fill_price: float
    fee_paid: float
    slippage: float
    realized_pnl: float
    timestamp: str

@dataclass
class Position:
    symbol: str
    side: PositionSide
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    liquidation_price: float
    leverage: float
