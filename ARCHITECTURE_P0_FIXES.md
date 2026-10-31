# P0 Security & Reliability Remediation Specification (Decision 52aa8d68)
## Technical Specification for Codex Autonomous Implementation

### Objective
Remediate all P0 vulnerabilities and P1 reliability hazards identified in Council Decision `52aa8d68`:
1. `fencing.py`: Fix monotonic fencing token validation (exact epoch matching, leader identity verification, and lease TTL).
2. `binance_ws.py` & `ticker.py`: Sequence-gap desynchronization detector for Binance orderbook/ticker streams.
3. `proposer/quarantine.py`: Market data sanitizer and symbol validator preventing TradeTrap prompt injection.
4. `hypergraph.py`: Bounded capacity (`max_edges=1000`) and dual-gate economic utility for immune edges.
5. `causal_shadow.py`: Realistic fee and slippage deductions in counterfactual PnL calculations.

---

### 1. Module Upgrades in `hermes_trader/`:

#### A. `hermes_trader/memory/fencing.py`:
- `FencingToken`:
  - `epoch: int`, `leader_id: str`, `issued_at: float`, `lease_ttl_s: float = 5.0`.
- `FencingTokenManager`:
  - `current_epoch: int = 0`
  - `current_leader: str = ''`
  - `acquire_token(leader_id: str, lease_ttl_s: float = 5.0) -> FencingToken`:
    - Increments `current_epoch += 1`.
    - Updates `current_leader = leader_id`.
    - Returns token.
  - `validate_token(token: FencingToken) -> bool`:
    - Reject if `token.epoch != self.current_epoch` (rejects both past and unissued future epochs).
    - Reject if `token.leader_id != self.current_leader`.
    - Reject if `time.time() - token.issued_at > token.lease_ttl_s` (lease expired).
    - Returns True only when all checks pass.

#### B. `hermes_trader/feed/binance_ws.py` & `ticker.py`:
- In `FeedWatchdog`:
  - Add `sequence_gap_detected: bool = False`.
  - Add `last_sequence_id: int | None = None`.
  - `record_sequence(sequence_id: int) -> bool`:
    - If `last_sequence_id` is set and `sequence_id > last_sequence_id + 1`:
      - Sets `sequence_gap_detected = True`.
      - Returns False (gap detected!).
    - `last_sequence_id = sequence_id`.
    - Returns True.
  - `is_healthy() -> bool`:
    - Returns False if `sequence_gap_detected` is True or tick is stale.
  - `reset_gap()`: resets gap flag after fresh snapshot recovery.
- In `BinanceFeedClient`:
  - Parses `u` (final update ID) or `U` (first update ID).
  - Feeds sequence id into `watchdog.record_sequence(u)`.

#### C. `hermes_trader/proposer/quarantine.py`:
- `MarketDataQuarantine`:
  - `validate_symbol(symbol: str) -> str`:
    - Strictly matches `^[A-Z0-9]{2,12}$`. Rejects any invalid characters with `ValueError`.
  - `sanitize_text(text: str) -> str`:
    - Strips prompt injection delimiters (`<|im_start|>`, `<|im_end|>`, `[SYSTEM]`, `system:`, `ignore previous instructions`).
    - Strips non-printable control characters.
  - `sanitize_market_input(data: dict) -> dict`:
    - Sanitizes symbol, converts numeric values to strict floats, strips unstructured commentary.

#### D. `hermes_trader/memory/hypergraph.py`:
- `HyperEdge`:
  - Add `impact_score: float = 0.0`.
- In `HypergraphView`:
  - Add `max_edges: int = 1000`.
  - `add_hyperedge(nodes: list[str], weight: float = 1.0, z_score: float = 0.0, impact_score: float = 0.0, metadata: dict | None = None) -> HyperEdge`:
    - Dual-gate immunity: marked `is_immune = True` ONLY if `abs(z_score) >= 3.0` AND `impact_score >= 1.0`.
    - Bounded capacity enforcement: if `len(edges) >= max_edges`:
      - Evict edge with lowest weight among non-immune edges.
      - If all are immune, evict oldest edge with lowest impact_score.

#### E. `hermes_trader/memory/causal_shadow.py`:
- In `CausalShadowTracker.resolve_counterfactual(record_id, current_price)`:
  - Base gross PnL = price change * qty.
  - Deduct realistic round-trip taker fees: `fee = hypothetical_price * 0.0004 + current_price * 0.0004`.
  - Deduct minimum execution slippage: `slippage = hypothetical_price * 0.0002`.
  - Net counterfactual PnL = `gross_pnl - fee - slippage`.
  - Updates `shadow_counterfactuals` with realistic net PnL.

---

### 2. Tests in `tests/test_p0_security_fixes.py`:
- Test `FencingTokenManager`:
  - Validates active token.
  - Rejects stale past epoch and unissued future epoch.
  - Rejects wrong leader ID.
  - Rejects expired lease TTL.
- Test `FeedWatchdog` & sequence gap:
  - Sequence increments (100 -> 101) pass.
  - Sequence jump (100 -> 105) triggers `sequence_gap_detected = True` and `is_healthy() == False`.
- Test `MarketDataQuarantine`:
  - Validates `BTCUSDT`, rejects malicious symbols (e.g. `BTC<|im_start|>`).
  - Strips injection delimiters from text.
- Test `HypergraphView` bounded capacity:
  - Does not exceed `max_edges` (1000 edges cap).
  - Immune edge requires both `abs(z) >= 3.0` and `impact_score >= 1.0`.
- Test `CausalShadowTracker` deducts fees and slippage from counterfactual PnL.
- Run `/root/kaggle-llm-orchestrator/.venv/bin/pytest tests/` to confirm 100% pass rate.
