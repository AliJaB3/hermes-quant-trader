import json
from pathlib import Path

import yaml

from .models import StrategyDefinition


class StrategyLoader:
    def load_from_dict(self, data: dict) -> StrategyDefinition:
        if not isinstance(data, dict):
            raise ValueError('strategy must be a mapping')
        for key in ('strategy_id', 'version', 'target_universe'):
            if key not in data or not data[key]:
                raise ValueError(f'missing mandatory field: {key}')
        if not isinstance(data['strategy_id'], str) or not isinstance(data['version'], str):
            raise ValueError('strategy_id and version must be strings')
        if not isinstance(data['target_universe'], list) or not all(isinstance(x, str) and x for x in data['target_universe']):
            raise ValueError('target_universe must be a list of symbols')
        for key, kind in (('hypothesis', dict), ('alpha_rules', list), ('execution_parameters', dict)):
            if key in data and not isinstance(data[key], kind):
                raise ValueError(f'{key} must be a {kind.__name__}')
        if not all(isinstance(rule, dict) for rule in data.get('alpha_rules', [])):
            raise ValueError('alpha_rules must contain mappings')
        fields = StrategyDefinition.__dataclass_fields__
        return StrategyDefinition(**{key: value for key, value in data.items() if key in fields})

    def load_from_yaml_or_json(self, path_or_content: str) -> StrategyDefinition:
        value = str(path_or_content)
        try:
            path = Path(value)
            content = path.read_text() if '\n' not in value and len(value) < 4096 and path.is_file() else value
            data = yaml.safe_load(content)
        except (OSError, yaml.YAMLError) as exc:
            raise ValueError(f'invalid strategy: {exc}') from exc
        return self.load_from_dict(data)
