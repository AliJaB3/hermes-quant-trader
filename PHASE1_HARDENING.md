# Phase 1: Core Guardian & Invariant Hardening Specification (G0-G1)
## Architectural Runbook for Codex Autonomous Implementation

### Objective
Resolve the critical trust-boundary and risk vulnerabilities identified in the Council audit:
1. Remove reliance on self-reported `cvar_estimate`; calculate 99% CVaR independently inside `RiskGuardian`.
2. Enforce Spread Guard on Market orders: reject Market orders if `spread_bps > 8.0`.
3. Require mandatory stop-loss on all position-opening orders.
4. Fix EvoMemJournal: cluster losing trades (require $n \ge 3$ trades per pattern) before creating active negative constraints to avoid superstitious overfitting.

---

### 1. Updates to `hermes_trader/guardian/__init__.py`:

#### A. Independent 99% CVaR Calculation:
- Add `estimated_tail_move_pct: float = 0.035` (3.5% default daily tail move for crypto assets) to `RiskLimits`.
- In `RiskGuardian`:
  - Calculate `independent_cvar = total_exposure * self.limits.estimated_tail_move_pct`.
  - Reject order if `independent_cvar > self.limits.max_cvar_99_usd` with `"Independent CVaR limit exceeded"`.

#### B. Spread Guard:
- Check current spread from `current_portfolio.get('spread_bps', {}).get(proposal.symbol, 0.0)` or `current_portfolio.get('spread_bps', 0.0)`.
- If `proposal.order_type == OrderType.MARKET` and `spread_bps > 8.0`:
  - Reject order with `"Market order rejected: spread exceeds 8 bps limit"`.

#### C. Mandatory Stop-Loss Enforcement:
- If an order increases position size (opening or adding to a position):
  - If `proposal.stop_loss is None` or `proposal.stop_loss <= 0`:
    - Reject order with `"Missing mandatory stop-loss on position opening"`.
  - For BUY orders: require `proposal.stop_loss < price`.
  - For SELL orders: require `proposal.stop_loss > price`.
  - If stop loss is on wrong side of price:
    - Reject order with `"Invalid stop-loss level relative to entry price"`.

---

### 2. Updates to `hermes_trader/memory/__init__.py`:

#### A. Clustered Negative Constraints (Anti-Overfitting):
- Maintain losing trade clusters: `dict[str, list[ExecutionReport]]` grouped by `f"{symbol}_{side}"`.
- `record_loss(symbol: str, side: OrderSide, report: ExecutionReport, thesis: TradingThesis | None = None)`:
  - Appends to cluster.
  - Only when `len(cluster) >= 3` and total realized loss in cluster < -50.0 USDT:
    - Formulate and promote a negative constraint (e.g. `f"Do not open {side.value} on {symbol} during high volatility"`).
  - If cluster size < 3, return None or empty constraint (preventing single-trade superstition).

---

### 3. Verification & Tests:
- Update `tests/test_guardian.py`:
  - Test independent CVaR rejection even if `proposal.cvar_estimate` is 0.
  - Test market order rejection when spread > 8 bps.
  - Test rejection when stop-loss is missing on new position.
  - Test rejection when stop-loss is inverted.
- Update `tests/test_memory_evomem.py`:
  - Test negative constraint requires cluster of at least 3 losing trades before promotion.
- Run `/root/kaggle-llm-orchestrator/.venv/bin/pytest tests/` to confirm 100% pass rate.
