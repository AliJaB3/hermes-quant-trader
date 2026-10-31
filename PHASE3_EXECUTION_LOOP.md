# Phase 3: Live Feed, Reconciliation & Autonomous Paper Daemon Specification (G4-G5)
## Technical Runbook for Codex Autonomous Implementation

### Objective
Implement the real-time execution loop connecting live market feeds, state reconciliation, and the autonomous Guardian daemon:
1. `hermes_trader/feed/`: Binance ticker/depth feed with heartbeat watchdog.
2. `hermes_trader/reconciliation/`: State reconciler matching local state with exchange/paper records.
3. `hermes_trader/daemon/`: Background autonomous paper trading daemon.
4. CLI command `hermes-trader run` to launch the live autonomous trading loop.

---

### 1. New Directory & Modules:

#### A. `hermes_trader/feed/ticker.py`:
- `MarketTick`:
  - `symbol: str`, `bid: float`, `ask: float`, `last_price: float`, `spread_bps: float`, `timestamp: float`
- `FeedWatchdog`:
  - `max_stale_ms: float = 5000.0`
  - `record_tick(tick: MarketTick)`
  - `is_healthy() -> bool`: returns False if current time - last tick > max_stale_ms.

#### B. `hermes_trader/reconciliation/engine.py`:
- `ReconciliationDiscrepancy`:
  - `symbol: str`, `discrepancy_type: str` ('ORPHAN_REMOTE', 'GHOST_LOCAL', 'SIZE_MISMATCH'), `details: str`
- `StateReconciler`:
  - `reconcile(local_positions: dict, remote_positions: dict) -> list[ReconciliationDiscrepancy]`:
    - Compares position sizes and sides.
    - Flags any orphan or mismatched positions.

#### C. `hermes_trader/daemon/runner.py`:
- `TradingDaemon`:
  - Initializes `RiskGuardian`, `PaperEngine`, `FeedWatchdog`, and active `StrategyDefinition`s.
  - `process_tick(tick: MarketTick) -> list[ExecutionReport]`:
    - Checks watchdog health. If stale, rejects proposals.
    - Evaluates active strategies on the tick.
    - Submits resulting proposals to `PaperEngine.execute_proposal`.
    - Returns executed trade reports.
  - `get_status() -> dict`:
    - Returns portfolio equity, open positions, watchdog health, and guardian state.

---

### 2. Updates to `hermes_trader/cli.py`:
- Add subcommand:
  - `hermes-trader run --strategy PATH`: starts autonomous trading loop with simulated or live ticks.

---

### 3. Tests in `tests/test_live_daemon.py`:
- Test `FeedWatchdog` marks feed stale when ticks stop.
- Test `StateReconciler` detects orphan and size mismatch positions.
- Test `TradingDaemon.process_tick` executes end-to-end paper trades from strategy triggers.
- Test CLI `run` command.
- Run `/root/kaggle-llm-orchestrator/.venv/bin/pytest tests/` to confirm 100% pass rate.
