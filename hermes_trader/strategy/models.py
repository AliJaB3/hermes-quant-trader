from dataclasses import dataclass, field


@dataclass
class AlphaRule:
    indicator: str
    params: dict = field(default_factory=dict)
    condition: str = ''


@dataclass
class StrategyDefinition:
    strategy_id: str
    version: str
    target_universe: list[str]
    timeframe: str = '5m'
    hypothesis: dict = field(default_factory=dict)
    alpha_rules: list[dict] = field(default_factory=list)
    execution_parameters: dict = field(default_factory=dict)
