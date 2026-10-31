# Phase 4: Production Hardening & Execution Engine (Decision 6a305c35)
## Technical Specification for Codex Autonomous Implementation

### Objective
Implement the 4 operational pillars approved in Council Decision `6a305c35`:
1. Atomic Capacity Reservation & Single-Use Execution Tokens.
2. Crash-Durable Portfolio & State Store with SQLite WAL (`synchronous=FULL`).
3. Non-linear Orderbook Depth Slippage Model.
4. Live Binance Market WebSocket / REST stream with 2000ms watchdog.
5. Comprehensive Chaos & Fault-Injection test suite.

---

### 1. New & Enhanced Modules in `hermes_trader/`:

#### A. Atomic Capacity Reservation (`hermes_trader/guardian/reservation.py`):
- `ExecutionToken`:
  - `token_id: str`, `proposal_id: str`, `reserved_usd: float`, `reserved_cvar: float`, `created_at: float`, `ttl_ms: float = 2000.0`, `is_consumed: bool = False`.
- `CapacityReservationManager`:
  - Thread-safe tracking of active reservations.
  - `reserve(proposal_id: str, amount_usd: float, cvar: float, current_available_usd: float, current_available_cvar: float) -> ExecutionToken | None`:
    - Atomically checks available limits. If sufficient, creates token and adds to reserved tally.
    - If insufficient (would breach limits), returns None.
  - `consume(token_id: str) -> bool`: marks token consumed.
  - `release(token_id: str)`: frees reserved capacity.
  - `purge_expired()`: releases tokens whose age > ttl_ms.

#### B. Crash-Durable SQLite WAL Store (`hermes_trader/paper/store.py`):
- `PortfolioStore`:
  - Path: `~/.hermes/trader_portfolio.sqlite` (or `:memory:` / configurable).
  - Schema:
    - `portfolio_state (key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP)`
    - `positions (symbol TEXT PRIMARY KEY, side TEXT, size REAL, entry_price REAL, leverage REAL, updated_at TIMESTAMP)`
    - `orders (order_id TEXT PRIMARY KEY, proposal_id TEXT, symbol TEXT, side TEXT, qty REAL, price REAL, status TEXT, created_at TIMESTAMP)`
  - PRAGMAs:
    - `PRAGMA journal_mode = WAL;`
    - `PRAGMA synchronous = FULL;`
  - `save_state(state: dict)`
  - `load_state() -> dict | None`

#### C. Non-Linear Depth Slippage (`hermes_trader/paper/slippage.py`):
- `DepthSlippageModel`:
  - `base_slippage: float = 0.0001` (0.01%)
  - `impact_factor: float = 0.0005` (5 bps base coefficient)
  - `default_depth_usd: float = 100_000.0`
  - `compute_slippage(order_size_usd: float, book_depth_usd: float | None = None) -> float`:
    - depth = max(1000.0, book_depth_usd or default_depth_usd)
    - ratio = order_size_usd / depth
    - slippage = base_slippage + impact_factor * math.sqrt(ratio)
    - return min(0.05, max(base_slippage, slippage)) # capped at 5% max slippage

#### D. Live Binance WebSocket Streamer (`hermes_trader/feed/binance_ws.py`):
- `BinanceFeedClient`:
  - `symbol: str` (e.g. `BTCUSDT`)
  - `watchdog: FeedWatchdog` (max_stale_ms = 2000.0)
  - `parse_stream_message(msg: dict) -> MarketTick | None`:
    - Parses Binance bookTicker payload (`b`: best bid, `a`: best ask, `B`: bid qty, `A`: ask qty).
    - Computes spread in bps: `(ask - bid) / ((ask + bid) / 2) * 10000`.
    - Updates watchdog.

---

### 2. Integration with `PaperEngine` & `RiskGuardian`:
- In `RiskGuardian`:
  - Use `CapacityReservationManager` to guard against concurrent capacity breaches.
- In `PaperEngine`:
  - Use `DepthSlippageModel` instead of fixed slippage.
  - Wire `PortfolioStore` to auto-persist state after every trade and reload on initialization.

---

### 3. Tests in `tests/test_chaos_fault_injection.py`:
- Test concurrent reservations: two orders competing for remaining capacity — only one gets token, second is blocked.
- Test token TTL expiry auto-releases capacity.
- Test crash recovery: save state, re-instantiate `PaperEngine`, verify cash, equity, and positions match exactly.
- Test non-linear slippage scales with order size.
- Test Binance stream message parsing and watchdog freshness.
- Run `/root/kaggle-llm-orchestrator/.venv/bin/pytest tests/` to confirm 100% pass rate.
