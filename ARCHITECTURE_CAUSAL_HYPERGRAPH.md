# Hypergraph & Causal Memory Frontiers (HCMF) Specification (Decision d1dfd65b)
## Architecture for Codex Autonomous Implementation

### Objective
Implement the 4 cutting-edge memory frontiers approved in Council Decision `d1dfd65b`:
1. `causal_shadow.py`: Causal Shadow Lab tracking blocked proposals without polluting empirical episodic store.
2. `hypergraph.py`: Epistemic Hypergraph View connecting multi-dimensional concepts with Black Swan ($|z| \ge 3.0$) immunity.
3. `synaptic_sleep.py`: Synaptic Sleep Cycle decaying stale edges while preserving immune rare-event structures.
4. `fencing.py`: Monotonic Fencing Token Manager preventing distributed split-brain mutations.

---

### 1. New Modules in `hermes_trader/memory/`:

#### A. `hermes_trader/memory/causal_shadow.py`:
- `ShadowRecord`:
  - `record_id: str`, `timestamp: str`, `symbol: str`, `side: str`, `blocked_by_rule: str`, `hypothetical_price: float`, `resolution_price: float | None = None`, `counterfactual_pnl: float = 0.0`.
- `CausalShadowTracker`:
  - SQLite WAL table `shadow_counterfactuals`.
  - `record_blocked(symbol: str, side: str, rule_id: str, current_price: float) -> str`
  - `resolve_counterfactual(record_id: str, current_price: float) -> float`
  - `get_shadow_stats(symbol: str | None = None) -> dict`:
    - Tracks whether blocked trades would have won or lost, measuring rule censorship bias.

#### B. `hermes_trader/memory/hypergraph.py`:
- `HyperEdge`:
  - `edge_id: str`, `nodes: list[str]`, `weight: float = 1.0`, `z_score: float = 0.0`, `is_immune: bool = False`, `metadata: dict = field(default_factory=dict)`.
- `HypergraphView`:
  - `add_hyperedge(nodes: list[str], weight: float = 1.0, z_score: float = 0.0, metadata: dict | None = None) -> HyperEdge`:
    - If `abs(z_score) >= 3.0`, marks `is_immune = True`.
  - `get_hyperedge(edge_id: str) -> HyperEdge | None`
  - `decay_edges(decay_factor: float = 0.95)`:
    - Multiplies weight by decay_factor for all NON-immune edges. Immune edges remain untouched.
  - `get_summary() -> dict`:
    - `total_edges`, `immune_edges`, `active_nodes`.

#### C. `hermes_trader/memory/synaptic_sleep.py`:
- `SynapticSleepCycle`:
  - `prune_hypergraph(hypergraph: HypergraphView, min_weight: float = 0.1) -> int`:
    - Runs edge decay.
    - Prunes non-immune edges whose weight < min_weight.
    - Never prunes immune edges (`is_immune == True`).
    - Returns count of pruned edges.

#### D. `hermes_trader/memory/fencing.py`:
- `FencingToken`:
  - `epoch: int`, `leader_id: str`, `issued_at: float`.
- `FencingTokenManager`:
  - `acquire_token(leader_id: str) -> FencingToken`:
    - Increments global monotonic epoch and returns new token.
  - `validate_token(token: FencingToken) -> bool`:
    - Returns True if `token.epoch >= current_epoch`.
    - Returns False if token has an expired/stale epoch.

---

### 2. Integration with `ProceduralRuleEngine` and `hermes_trader/cli.py`:
- In `ProceduralRuleEngine`:
  - When `validate_proposal` blocks an order, automatically record it to `CausalShadowTracker`!
- In `hermes_trader/cli.py`:
  - Add `hermes-trader hypergraph-summary`: prints hypergraph statistics.
  - Add `hermes-trader sleep-cycle`: triggers synaptic sleep pruning.

---

### 3. Tests in `tests/test_causal_hypergraph_memory.py`:
- Test `CausalShadowTracker` records blocked trades and computes counterfactual PnL without affecting episodic store.
- Test `HypergraphView` sets `is_immune = True` for $|z| \ge 3.0$.
- Test `SynapticSleepCycle` decays non-immune edges, prunes below threshold, and protects immune edges.
- Test `FencingTokenManager` monotonic increments and stale epoch rejection.
- Run `/root/kaggle-llm-orchestrator/.venv/bin/pytest tests/` to confirm 100% pass rate.
