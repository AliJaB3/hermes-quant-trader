# Production Hazard Remediation Specification (Decision a8943e5f)
## Architecture for Codex Autonomous Implementation

### Objective
Remediate the 5 production hazards identified in Council Decision `a8943e5f`:
1. `clock_sync.py`: Dynamic Exchange Clock Calibration with RTT correction; use `time.monotonic()` in `fencing.py`.
2. `rate_governor.py`: Centralized IP Rate-Governor with 25% emergency reserve and HTTP 429/418 circuit breaker.
3. `store.py`: WAL Storage Sentinel with periodic checkpoints and 50MB size guard to prevent disk starvation.
4. `adl_watchdog.py`: Binance Futures ADL Quantile Watchdog detecting forced deleveraging risk.
5. `shutdown.py`: Two-phase deterministic graceful shutdown state machine protecting resting stop-losses.

---

### 1. New & Enhanced Modules in `hermes_trader/`:

#### A. Clock Synchronization (`hermes_trader/feed/clock_sync.py`):
- `ClockSynchronizer`:
  - `clock_offset_ms: float = 0.0`
  - `update_offset(client_send_ts_ms: float, server_ts_ms: float, client_recv_ts_ms: float)`:
    - $RTT = client\_recv\_ts\_ms - client\_send\_ts\_ms$
    - $offset = server\_ts\_ms - (client\_send\_ts\_ms + RTT / 2.0)$
    - Updates `clock_offset_ms = 0.8 * clock_offset_ms + 0.2 * offset` (EWMA).
  - `get_calibrated_timestamp_ms() -> int`:
    - returns `int(time.time() * 1000 + self.clock_offset_ms)`.
- In `hermes_trader/memory/fencing.py`:
  - In `FencingTokenManager`:
    - Record `issued_at = time.monotonic()` (instead of `time.time()`).
    - Validate with `time.monotonic() - token.issued_at <= token.lease_ttl_s`.
    - This provides 100% immunity to system wall-clock jumps or NTP step calibrations!

#### B. Rate Governor & IP Ban Shield (`hermes_trader/feed/rate_governor.py`):
- `RateGovernor`:
  - `max_weight_per_min: int = 1200`
  - `emergency_reserve_weight: int = 300` (25% reserved for cancel/reconcile)
  - `current_weight: int = 0`
  - `is_tripped_429: bool = False`
  - `cooldown_until: float = 0.0`
  - `can_request(weight: int = 1, is_emergency: bool = False) -> bool`:
    - If `is_tripped_429` and `time.monotonic() < self.cooldown_until`: return False.
    - If not `is_emergency` and `current_weight + weight > (max_weight_per_min - emergency_reserve_weight)`: return False (reserves 25% buffer).
    - If `current_weight + weight > max_weight_per_min`: return False.
    - return True.
  - `record_weight(used_weight_1m: int)`: updates current weight.
  - `trip_429(backoff_s: float = 60.0)`: immediately trips shield, preventing 418 IP ban.

#### C. WAL Storage Sentinel (`hermes_trader/paper/store.py`):
- In `PortfolioStore`:
  - Add `max_wal_bytes: int = 50 * 1024 * 1024` (50MB threshold).
  - `checkpoint_wal() -> bool`:
    - Executes `PRAGMA wal_checkpoint(TRUNCATE);`.
  - `check_wal_size() -> int`:
    - Checks `-wal` file size on disk. If $> max_wal_bytes$, executes `checkpoint_wal()`.
    - Returns current WAL size in bytes.

#### D. ADL Quantile Watchdog (`hermes_trader/guardian/adl_watchdog.py`):
- `ADLWatchdog`:
  - `symbol_quantiles: dict[str, int]` (1 to 5)
  - `update_quantile(symbol: str, quantile: int)`:
    - Stores quantile (1 = lowest risk, 5 = highest risk of being auto-deleveraged by Binance).
  - `is_high_risk(symbol: str) -> bool`:
    - Returns True if `quantile >= 4`.
  - `should_derisk(symbol: str) -> bool`:
    - Returns True if `quantile == 5`.

#### E. Two-Phase Graceful Shutdown (`hermes_trader/daemon/shutdown.py`):
- `ShutdownState`: Enum (`RUNNING`, `QUIESCING`, `CANCEL_ENTRY_ONLY`, `PERSISTED`, `STOPPED`).
- `GracefulShutdownManager`:
  - `state: ShutdownState = ShutdownState.RUNNING`
  - `initiate_shutdown(paper_engine, cancel_entry_orders_fn = None)`:
    - Phase 1: sets `state = QUIESCING` (rejects all new trade proposals).
    - Phase 2: sets `state = CANCEL_ENTRY_ONLY` (cancels open entry orders while PRESERVING stop-losses).
    - Phase 3: sets `state = PERSISTED` (flushes portfolio store to disk).
    - Phase 4: sets `state = STOPPED`.

---

### 2. Tests in `tests/test_production_hazards.py`:
- Test `ClockSynchronizer` EWMA offset computation and calibrated timestamp.
- Test `FencingTokenManager` monotonic lease validation.
- Test `RateGovernor` blocks non-emergency orders at 75% capacity, allows emergency orders up to 100%, and trips on 429.
- Test `PortfolioStore` WAL checkpoint truncation and size check.
- Test `ADLWatchdog` flags high risk on quantile 4 and derisk on quantile 5.
- Test `GracefulShutdownManager` executes 4-phase shutdown without removing stop-loss orders.
- Run `/root/kaggle-llm-orchestrator/.venv/bin/pytest tests/` to confirm 100% pass rate.
