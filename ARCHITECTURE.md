# Hermes Quant Trader: Autonomous Proposer-Guardian Trading Architecture
## Specification for Codex Autonomous Implementation (Council Decision 0f053106)

### Objective
Build a standalone, production-grade Python package `hermes_trader` implementing the Proposer-Guardian-Executor architecture for autonomous crypto strategy learning and execution.

---

### Core Subsystems & Modules:

#### 1. Data Contracts (`hermes_trader/contracts/`):
- `OrderSide`: Enum (`BUY`, `SELL`).
- `OrderType`: Enum (`LIMIT`, `MARKET`, `STOP_LOSS`, `TAKE_PROFIT`).
- `PositionSide`: Enum (`LONG`, `SHORT`, `FLAT`).
- `OrderStatus`: Enum (`PROPOSED`, `ACCEPTED`, `REJECTED`, `FILLED`, `CANCELLED`).
- `GuardianState`: Enum (`NORMAL`, `REDUCE_ONLY`, `HALTED`).
- `OrderProposal`:
  - `proposal_id: str`, `correlation_id: str`, `symbol: str`, `side: OrderSide`, `order_type: OrderType`, `quantity: float`, `price: float | None`, `stop_loss: float | None`, `take_profit: float | None`, `strategy_id: str`, `thesis_id: str`, `rationale: str`, `cvar_estimate: float`, `created_at: str`.
- `ExecutionReport`:
  - `execution_id: str`, `proposal_id: str`, `symbol: str`, `side: OrderSide`, `filled_quantity: float`, `avg_fill_price: float`, `fee_paid: float`, `slippage: float`, `realized_pnl: float`, `timestamp: str`.
- `Position`:
  - `symbol: str`, `side: PositionSide`, `size: float`, `entry_price: float`, `current_price: float`, `unrealized_pnl: float`, `liquidation_price: float`, `leverage: float`.

#### 2. Guardian & Risk Engine (`hermes_trader/guardian/`):
- `RiskLimits`:
  - `max_drawdown_pct: float = 5.0`
  - `max_drawdown_velocity_pct_per_hr: float = 1.5`
  - `max_cvar_99_usd: float = 500.0`
  - `max_leverage: float = 5.0`
  - `max_position_size_usd: float = 2000.0`
  - `maker_fee_rate: float = 0.0002` (0.02%)
  - `taker_fee_rate: float = 0.0004` (0.04%)
- `RiskGuardian`:
  - `validate_proposal(proposal: OrderProposal, current_portfolio: dict) -> tuple[bool, str]`:
    - Checks: State must not be HALTED.
    - Checks: In REDUCE_ONLY, reject orders that increase net position.
    - Checks: Leverage must not exceed `max_leverage`.
    - Checks: Value must not exceed `max_position_size_usd`.
    - Checks: Drawdown and CVaR bounds.
    - Returns `(approved, reason)`.
- `KillSwitchManager`:
  - Monitors drawdown velocity and max drawdown.
  - `trigger_emergency_stop() -> str`: immediately sets state to `HALTED` and signals cancellation of all active orders.
  - `resume(operator_key: str) -> bool`: returns state to `NORMAL`.

#### 3. Zero-Mock Paper Trading Engine (`hermes_trader/paper/`):
- `PaperEngine`:
  - Initial balance: default $10,000 USDT.
  - `update_ticker(symbol: str, bid: float, ask: float)`
  - `execute_proposal(proposal: OrderProposal) -> tuple[bool, ExecutionReport | str]`:
    - Validates with `RiskGuardian`.
    - Computes realistic execution price with simulated market depth slippage (min 0.01%) and fees (0.04% taker).
    - Updates cash, position, and portfolio equity.
    - Returns `(True, ExecutionReport)` or `(False, rejection_reason)`.
  - `get_portfolio() -> dict`:
    - `cash`, `equity`, `initial_balance`, `drawdown_pct`, `drawdown_velocity`, `positions`, `cvar_99`, `trade_count`, `win_rate`.

#### 4. Trader Memory & Negative Constraints (`hermes_trader/memory/`):
- `TradingThesis`:
  - `thesis_id: str`, `title: str`, `symbol: str`, `hypothesis: str`, `falsification_condition: str`, `entry_plan: dict`, `status: str` ('OPEN', 'VALIDATED', 'FALSIFIED', 'ABANDONED'), `created_at: str`.
- `ThesisTracker`:
  - Registers, updates, and tracks theses across market cycles.
- `EvoMemJournal`:
  - Persists executed trades and thesis outcomes in SQLite WAL.
  - `extract_negative_constraints(losing_trade: ExecutionReport, thesis: TradingThesis) -> str`:
    - Formulates negative constraints (e.g., "Do not short when funding < -0.1% during high volume breakout").
  - `get_negative_constraints(symbol: str) -> list[str]`

#### 5. Proposer & Strategy Pipeline (`hermes_trader/proposer/`):
- `StrategyProposer`:
  - Formulates structured `OrderProposal` based on market conditions, thesis, and negative constraints.
  - Zero execution privileges (emits proposal for Guardian approval only).

#### 6. Governance & Telegram Bot Interface (`hermes_trader/bot/`):
- `TelegramCommandHandler`:
  - Implements command routing for:
    - `/status`: returns formatted dashboard (Equity, Cash, Drawdown, State, Open Positions).
    - `/positions`: lists open positions with Unrealized PnL.
    - `/theses`: lists active theses.
    - `/emergency_stop`: executes immediate Halt.
    - `/resume`: resumes normal operations.

#### 7. Profile Scaffolding (`hermes_trader/scaffold/`):
- `ProfileScaffolder`:
  - `generate_trader_profile(path: str = "~/.hermes/profiles/trader", bot_token: str = "") -> dict`:
    - Creates directory structure, `config.yaml`, and linked trading skills catalog.

#### 8. CLI Interface (`hermes_trader/cli.py`):
- `hermes-trader status`: inspects paper engine / portfolio status.
- `hermes-trader propose --symbol BTCUSDT --side BUY --qty 0.1 --price 65000`: runs proposal through guardian.
- `hermes-trader emergency-stop`: triggers immediate guardian halt.
- `hermes-trader scaffold --path PATH`: scaffolds profile directory.

---

### Tests (`tests/`):
- `test_contracts.py`: test dataclasses and serialization.
- `test_guardian.py`: test risk limits, leverage cap, drawdown velocity triggers, and emergency halt.
- `test_paper_engine.py`: test realistic slippage, fee deductions, PnL calculations, and position tracking.
- `test_memory_evomem.py`: test thesis tracking and negative constraint extraction.
- `test_bot_handlers.py`: test telegram command routing (/status, /positions, /emergency_stop).
- `test_cli.py`: test CLI commands.
- 100% test pass rate with pytest.
