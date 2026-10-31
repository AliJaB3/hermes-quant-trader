"""Issue and validate strategy evidence records."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import math
from uuid import uuid4
from hermes_trader.contracts.v1 import StrategyPassportV1


def _hash(content):
    return sha256(content.encode('utf-8')).hexdigest()


class StrategyPassportManager:
    def issue_passport(self, strategy_id, code_content, config_content, deflated_sharpe, max_drawdown_pct, stress_tested):
        now = datetime.now(timezone.utc)
        return StrategyPassportV1(str(uuid4()), strategy_id, _hash(code_content), _hash(config_content),
                                  deflated_sharpe, max_drawdown_pct, stress_tested, now.isoformat(),
                                  (now + timedelta(days=30)).isoformat())

    def validate_passport(self, passport, current_code_content, current_config_content):
        try:
            expiry = datetime.fromisoformat(passport.expires_at)
            return (passport.code_hash == _hash(current_code_content)
                    and passport.config_hash == _hash(current_config_content)
                    and expiry.tzinfo is not None and expiry > datetime.now(timezone.utc)
                    and passport.stress_tested is True and math.isfinite(passport.deflated_sharpe)
                    and passport.deflated_sharpe >= 1.0)
        except (AttributeError, TypeError, ValueError, OverflowError):
            return False
