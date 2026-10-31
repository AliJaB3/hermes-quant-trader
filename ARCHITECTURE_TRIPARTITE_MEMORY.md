# Tripartite Autonomous Memory & Epistemic Learning Specification (Decision d9d21f61)
## Architecture for Codex Autonomous Implementation

### Objective
Implement the 3-tier memory and autonomous learning subsystem in `hermes_trader/memory/`:
1. `episodic.py`: Append-only Episodic Store in SQLite WAL tracking executed and counterfactual trades.
2. `semantic.py`: Semantic Knowledge DAG tracking hypotheses across the 6-stage lifecycle (`DRAFT` -> `CANDIDATE` -> `VALIDATED` -> `SHADOW` -> `ACTIVE` -> `STALE`).
3. `procedural.py`: Procedural Rules Engine executing validated negative constraints and guards.
4. `learning_pipeline.py`: Automated learning pipeline evaluating statistical clusters ($N \ge 30$) and managing rule graduation.
5. `drift_monitor.py`: Market distribution drift and falsification burst kill-switch monitor.

---

### 1. New Directory & Modules in `hermes_trader/memory/`:

#### A. `hermes_trader/memory/episodic.py`:
- `EpisodicTrade`:
  - `trade_id: str`, `timestamp: str`, `symbol: str`, `side: str`, `qty: float`, `price: float`, `fee: float`, `slippage: float`, `realized_pnl: float`, `regime_tag: str`, `was_simulated: bool`, `correlation_id: str`, `raw_json: str`.
- `EpisodicStore`:
  - SQLite WAL table `episodic_trades`.
  - `record_trade(trade: EpisodicTrade)`
  - `get_cluster(symbol: str, side: str, min_trades: int = 30) -> list[EpisodicTrade]`
  - `get_recent_trades(limit: int = 100) -> list[EpisodicTrade]`

#### B. `hermes_trader/memory/semantic.py`:
- `HypothesisStatus`: Enum (`DRAFT`, `CANDIDATE`, `VALIDATED`, `SHADOW`, `ACTIVE`, `STALE`).
- `SemanticHypothesis`:
  - `hypothesis_id: str`, `title: str`, `domain: str`, `premise: str`, `falsification_condition: str`, `sample_size: int = 0`, `p_value: float = 1.0`, `status: HypothesisStatus = HypothesisStatus.DRAFT`, `created_at: str = ''`, `updated_at: str = ''`.
- `SemanticKnowledgeDAG`:
  - `create_hypothesis(title: str, premise: str, falsification_condition: str, domain: str = 'FINANCE') -> SemanticHypothesis`
  - `update_status(hypothesis_id: str, new_status: HypothesisStatus, metrics: dict | None = None) -> bool`
  - `get_active_hypotheses() -> list[SemanticHypothesis]`

#### C. `hermes_trader/memory/procedural.py`:
- `RuleType`: Enum (`NEGATIVE_CONSTRAINT`, `EXECUTION_GUARD`, `REGIME_FILTER`).
- `ProceduralRule`:
  - `rule_id: str`, `hypothesis_id: str`, `rule_type: RuleType`, `symbol: str`, `condition_dsl: str`, `action: str`, `ttl_hours: float = 168.0`, `max_capital_usd: float = 1000.0`, `is_active: bool = True`, `created_at: str = ''`.
- `ProceduralRuleEngine`:
  - `register_rule(rule: ProceduralRule)`
  - `validate_proposal(symbol: str, side: str, order_type: str, indicators: dict) -> tuple[bool, str]`:
    - Checks all active rules matching the symbol.
    - If a rule condition matches and action is 'BLOCK', returns `(False, f"Blocked by procedural rule {rule.rule_id}: {rule.condition_dsl}")`.
    - Returns `(True, "All procedural rules passed")`.

#### D. `hermes_trader/memory/learning_pipeline.py`:
- `LearningPipeline`:
  - `__init__(episodic: EpisodicStore, semantic: SemanticKnowledgeDAG, procedural: ProceduralRuleEngine)`
  - `process_clusters(min_samples: int = 30) -> list[SemanticHypothesis]`:
    - Scans episodic store for clusters with $\ge 30$ samples.
    - If a cluster has a persistent loss pattern (win rate < 35% with statistical significance), promotes to a `CANDIDATE` hypothesis and generates a `NEGATIVE_CONSTRAINT` procedural rule in `SHADOW` mode.
  - `graduate_rule(hypothesis_id: str)`: promotes from `SHADOW` to `ACTIVE`.

#### E. `hermes_trader/memory/drift_monitor.py`:
- `MarketDriftMonitor`:
  - `falsification_window_hours: float = 4.0`
  - `max_falsification_burst: int = 5`
  - `record_falsification(rule_id: str, timestamp: float)`
  - `is_burst_triggered() -> bool`: returns True if $\ge 5$ falsifications within 4 hours.
  - `check_distribution_drift(recent_values: list[float], historical_values: list[float], threshold_sigma: float = 3.5) -> bool`:
    - Compares mean and variance of recent vs historical distribution; returns True if shift > threshold_sigma.

---

### 2. Integration with `RiskGuardian` & `hermes_trader/cli.py`:
- In `RiskGuardian.validate_proposal`:
  - Consult `ProceduralRuleEngine.validate_proposal` to enforce active negative constraints.
- In `hermes_trader/cli.py`:
  - Add `hermes-trader memory-status` subcommand displaying episodic trade count, semantic hypotheses, and procedural rules.

---

### 3. Tests in `tests/test_tripartite_memory.py`:
- Test `EpisodicStore` records both executed and simulated trades.
- Test `SemanticKnowledgeDAG` manages hypothesis lifecycle transitions.
- Test `ProceduralRuleEngine` validates or blocks proposals matching active negative constraints.
- Test `LearningPipeline.process_clusters` requires at least 30 samples before candidate formation.
- Test `MarketDriftMonitor` triggers kill-switch on 5 falsifications in window.
- Run `/root/kaggle-llm-orchestrator/.venv/bin/pytest tests/` to confirm 100% pass rate.
