# Phase 2: Strategy Teaching DSL & Walk-Forward Validator (G2-G3)
## Technical Runbook for Codex Autonomous Implementation

### Objective
Implement the Declarative Strategy DSL and Purged Walk-Forward Backtest Engine in `hermes_trader/strategy/`:
1. Strategy DSL parser supporting YAML and JSON strategy definitions.
2. Rule evaluator generating `OrderProposal`s from market candles/indicators.
3. Purged Walk-Forward backtest validator calculating out-of-sample metrics with realistic fees & slippage.

---

### 1. New Directory & Modules: `hermes_trader/strategy/`:

#### A. `hermes_trader/strategy/models.py`:
- `AlphaRule`:
  - `indicator: str`, `params: dict = field(default_factory=dict)`, `condition: str = ''`
- `StrategyDefinition`:
  - `strategy_id: str`
  - `version: str`
  - `target_universe: list[str]`
  - `timeframe: str = '5m'`
  - `hypothesis: dict = field(default_factory=dict)`
  - `alpha_rules: list[dict] = field(default_factory=list)`
  - `execution_parameters: dict = field(default_factory=dict)` (e.g. `max_leverage`, `stop_loss_pct`, `take_profit_pct`)

#### B. `hermes_trader/strategy/loader.py`:
- `StrategyLoader`:
  - `load_from_dict(data: dict) -> StrategyDefinition`
  - `load_from_yaml_or_json(path_or_content: str) -> StrategyDefinition`
  - Validates that mandatory fields (`strategy_id`, `version`, `target_universe`) exist.

#### C. `hermes_trader/strategy/evaluator.py`:
- `StrategyEvaluator`:
  - `evaluate_tick(strategy: StrategyDefinition, symbol: str, current_price: float, indicators: dict) -> OrderProposal | None`:
    - Evaluates conditions (e.g. `ofi < -0.5`, `spread_bps <= 6`).
    - If entry trigger fires, computes `stop_loss` and `take_profit` from strategy `execution_parameters`.
    - Returns structured `OrderProposal` with mandatory `stop_loss` set (conforming to Phase 1 Guardian requirements).

#### D. `hermes_trader/strategy/walk_forward.py`:
- `WalkForwardReport`:
  - `strategy_id: str`, `total_trades: int`, `win_rate: float`, `profit_factor: float`, `max_drawdown_pct: float`, `net_pnl: float`, `is_admissible: bool`.
- `WalkForwardValidator`:
  - `validate(strategy: StrategyDefinition, candles: list[dict], folds: int = 3, fee_rate: float = 0.0004, slippage_rate: float = 0.0002) -> WalkForwardReport`:
    - Simulates strategy across rolling folds with fee deduction and slippage.
    - Sets `is_admissible = True` only if `net_pnl > 0`, `profit_factor > 1.2`, and `max_drawdown_pct < 5.0`.

---

### 2. Updates to `hermes_trader/cli.py`:
- Add subcommand:
  - `hermes-trader test-strategy --file PATH`: loads strategy, validates schema, and reports admissibility.

---

### 3. Tests in `tests/test_strategy_dsl.py`:
- Test `StrategyLoader` parses valid strategy and rejects missing fields.
- Test `StrategyEvaluator` generates compliant `OrderProposal` with mandatory `stop_loss`.
- Test `WalkForwardValidator` evaluates candles, deducts fees/slippage, and determines admissibility.
- Test CLI `test-strategy` command.
- Run `/root/kaggle-llm-orchestrator/.venv/bin/pytest tests/` to confirm 100% pass rate.
