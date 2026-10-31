import pytest
from hermes_trader.proposer import StrategyProposer

@pytest.fixture
def proposal():
    return StrategyProposer().propose('BTCUSDT', 'BUY', 0.01, 10000)

@pytest.fixture(autouse=True)
def isolated_portfolio(tmp_path, monkeypatch):
    monkeypatch.setenv('HERMES_TRADER_PORTFOLIO', str(tmp_path / 'portfolio.sqlite'))
