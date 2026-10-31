from pathlib import Path
import json

class ProfileScaffolder:
    def generate_trader_profile(self, path='~/.hermes/profiles/trader', bot_token=''):
        root = Path(path).expanduser()
        root.mkdir(parents=True, exist_ok=True)
        skills = root / 'skills'
        skills.mkdir(exist_ok=True)
        config = root / 'config.yaml'
        # JSON strings are valid YAML scalars and safely escape arbitrary tokens.
        if not config.exists():
            config.write_text('mode: paper\ntelegram_bot_token: ' + json.dumps(bot_token) + '\nskills_catalog: skills/catalog.yaml\n', encoding='utf-8')
            config.chmod(0o600)
        catalog = skills / 'catalog.yaml'
        if not catalog.exists():
            catalog.write_text('skills:\n  - propose\n  - risk_guardian\n  - paper_execution\n  - thesis_memory\n', encoding='utf-8')
        return {'path': str(root), 'config': str(config), 'skills_catalog': str(catalog)}
