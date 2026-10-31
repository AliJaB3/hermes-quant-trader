# P0-P3 Comprehensive Production Evolution Specification (Decision 50e32c23)
## Architecture for Codex Autonomous Implementation

### Objective
Implement the 4 progressive phases approved in Council Decision `50e32c23`:
1. **P0:** Versioned Data Contracts (v1), Atomic Rate Reservation, and Unambiguous Timeout Reconciliation Resolver.
2. **P1:** Risk Telemetry & MCTS Live Inspector Stream (async drop-frame queue, credentials stripped).
3. **P2:** Strategy Evidence Passport (Deflated Sharpe) & Synthetic Microstructure Stress Tester.
4. **P3:** Multi-Venue Capability Matrix & Hyperliquid Venue Adapter.

---

### 1. New & Enhanced Modules in `hermes_trader/`:

#### A. P0: Versioned Contracts & Atomic Rate Governor (`contracts/v1.py` & `feed/rate_governor.py`):
- `hermes_trader/contracts/v1.py`:
  - `OrderIntentV1`: `intent_id: str`, `correlation_id: str`, `causation_id: str`, `symbol: str`, `side: str`, `qty: float`, `price: float | None`, `stop_loss: float`, `take_profit: float | None`, `strategy_passport_hash: str`, `created_at: str`.
  - `ExecutionReportV1`: `execution_id: str`, `intent_id: str`, `symbol: str`, `side: str`, `filled_qty: float`, `avg_fill_price: float`, `fee_usd: float`, `slippage_bps: float`, `timestamp: str`.
  - `PositionStateV1`: `symbol: str`, `side: str`, `size: float`, `entry_price: float`, `mark_price: float`, `unrealized_pnl: float`, `leverage: float`.
  - `RiskSnapshotV1`: `equity: float`, `cash: float`, `drawdown_pct: float`, `drawdown_velocity: float`, `cvar_99_usd: float`, `open_positions_count: int`, `state: str`, `timestamp: str`.
  - `StrategyPassportV1`: `passport_id: str`, `strategy_id: str`, `code_hash: str`, `config_hash: str`, `deflated_sharpe: float`, `max_drawdown_pct: float`, `stress_tested: bool`, `issued_at: str`, `expires_at: str`.
- In `hermes_trader/feed/rate_governor.py`:
  - Add thread lock `threading.Lock()` inside `RateGovernor`.
  - `atomic_reserve(weight: int = 1, is_emergency: bool = False) -> bool`:
    - Atomically checks capacity AND increments `current_weight` in a single critical section, eliminating any TOCTOU race between concurrent threads!

#### B. P0: Unambiguous Timeout Reconciliation Resolver (`reconciliation/resolver.py`):
- `ReconciliationResolver`:
  - `resolve_timeout(intent: OrderIntentV1, exchange_orders: list[dict], remote_positions: dict) -> tuple[str, dict]`:
    - Searches `exchange_orders` for matching client order id / intent_id.
    - If found with status FILLED: returns `('FILLED', order_data)`.
    - If found with status CANCELED/REJECTED: returns `('FAILED', order_data)`.
    - If not found in orders: checks position delta. If position increased: returns `('FILLED_UNTRAKED', remote_positions)`.
    - If not found and no position change: returns `('NOT_FOUND_SAFE_TO_RETRY', {})`.

#### C. P1: Risk Telemetry & MCTS Live Inspector (`telemetry/inspector.py`):
- `InspectorFrame`:
  - `seq: int`, `correlation_id: str`, `causation_id: str`, `timestamp: str`, `event_type: str`, `data: dict`.
- `MCTSInspectorStream`:
  - Thread-safe bounded queue (`maxlen=1000`).
  - `emit(event_type: str, correlation_id: str, causation_id: str, data: dict)`:
    - Sanitizes `data` (strips `key`, `token`, `secret`, `password`, `private_key`).
    - Pushes frame. Drops oldest frame if buffer is full (guaranteeing zero latency penalty on trading engine).
  - `get_recent_frames(limit: int = 50) -> list[InspectorFrame]`

#### D. P2: Strategy Evidence Passport & Synthetic Stress Tester (`strategy/passport.py` & `strategy/stress_tester.py`):
- `StrategyPassportManager`:
  - `issue_passport(strategy_id: str, code_content: str, config_content: str, deflated_sharpe: float, max_drawdown_pct: float, stress_tested: bool) -> StrategyPassportV1`:
    - Computes SHA256 of code and config.
    - Sets 30-day expiration.
  - `validate_passport(passport: StrategyPassportV1, current_code_content: str, current_config_content: str) -> bool`:
    - Verifies hashes match current contents.
    - Verifies `not expired` and `stress_tested is True` and `deflated_sharpe >= 1.0`.
- `SyntheticStressTester`:
  - `run_stress_test(strategy_fn, initial_price: float = 60000.0) -> dict`:
    - Simulates 3 extreme market shock scenarios:
      1. Flash Crash: -25% price drop in 5 ticks with 80% depth collapse.
      2. Cascade Squeeze: +20% price surge with fee explosion.
      3. Illiquid Whipsaw: alternating wide spreads (25 bps).
    - Returns `survived: bool`, `max_drawdown: float`, `liquidation_avoided: bool`.
- In `RiskGuardian.validate_proposal`:
  - If proposal carries a passport hash or passport object, verifies it is valid; rejects uncertified strategies.

#### E. P3: Venue Capability Matrix & Hyperliquid Adapter (`venues/capability.py` & `venues/hyperliquid.py`):
- `VenueCapabilityMatrix`:
  - Venues: `BINANCE_FUTURES`, `HYPERLIQUID`, `UNISWAP_V3`.
  - Properties: `supports_post_only`, `supports_reduce_only`, `supports_native_stop_loss`, `supports_countdown_cancel`, `settlement_type` (`CENTRALIZED_OFFCHAIN`, `L1_APPCHAIN`, `ON_CHAIN_EVM`).
- `HyperliquidVenueAdapter`:
  - `venue_name = "HYPERLIQUID"`
  - `build_order_payload(symbol: str, is_buy: bool, limit_px: float, sz: float, reduce_only: bool = False, post_only: bool = False) -> dict`:
    - Formats Hyperliquid L1 wire format (order action dictionary).
    - Enforces capability validation.

---

### 2. Integration with `hermes_trader/cli.py`:
- Add subcommand: `hermes-trader stress-test`: runs synthetic stress test on sample strategy.
- Add subcommand: `hermes-trader venues`: lists venue capability matrix.

---

### 3. Tests in `tests/test_p0_p3_evolution.py`:
- Test `RateGovernor.atomic_reserve` under concurrent access.
- Test `ReconciliationResolver` handles timeout resolution cleanly.
- Test `MCTSInspectorStream` drops oldest frame when full and sanitizes secrets.
- Test `StrategyPassportManager` issues valid passport and rejects tampered code hash.
- Test `SyntheticStressTester` runs flash crash scenario.
- Test `VenueCapabilityMatrix` and `HyperliquidVenueAdapter` wire format.
- Run `/root/kaggle-llm-orchestrator/.venv/bin/pytest tests/` to confirm 100% pass rate.
