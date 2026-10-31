import pytest
from hermes_trader.proposer import StrategyProposer

@pytest.fixture
def proposal():
    return StrategyProposer().propose('BTCUSDT', 'BUY', 0.01, 10000)
