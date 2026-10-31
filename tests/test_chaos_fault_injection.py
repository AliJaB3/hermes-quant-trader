from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import time

import pytest

from hermes_trader.contracts import OrderType
from hermes_trader.feed.binance_ws import BinanceFeedClient
from hermes_trader.guardian.reservation import CapacityReservationManager
from hermes_trader.paper import PaperEngine
from hermes_trader.paper.slippage import DepthSlippageModel
from hermes_trader.paper.store import PortfolioStore


def test_competing_reservations_and_single_use():
    manager = CapacityReservationManager()
    with ThreadPoolExecutor(max_workers=2) as pool:
        tokens = list(pool.map(lambda n: manager.reserve(str(n), 80, 8, 100, 10), range(2)))
    token, = [t for t in tokens if t is not None]
    assert manager.consume(token.token_id)
    assert not manager.consume(token.token_id)
    assert manager.reserve('third', 30, 1, 100, 10) is None
    manager.release(token.token_id)
    assert manager.reserve('third', 30, 1, 100, 10)


def test_expired_token_releases_capacity():
    manager = CapacityReservationManager(ttl_ms=1)
    token = manager.reserve('first', 100, 10, 100, 10)
    time.sleep(.01)
    assert not manager.consume(token.token_id)
    assert manager.reserve('second', 100, 10, 100, 10)


def test_crash_recovery(tmp_path, proposal):
    path = tmp_path / 'portfolio.sqlite'
    engine = PaperEngine(store_path=path)
    engine.update_ticker('BTCUSDT', 9999, 10000)
    assert engine.execute_proposal(replace(proposal, order_type=OrderType.MARKET, price=None, stop_loss=9000))[0]
    before = engine.get_portfolio()
    engine.store.close()
    restored = PaperEngine(store_path=path)
    after = restored.get_portfolio()
    assert (after['cash'], after['equity'], after['positions']) == (before['cash'], before['equity'], before['positions'])
    assert restored.store.connection.execute('PRAGMA journal_mode').fetchone()[0] == 'wal'
    assert restored.store.connection.execute('PRAGMA synchronous').fetchone()[0] == 2
    restored.store.close()


def test_slippage_depth_and_cap():
    model = DepthSlippageModel()
    assert model.compute_slippage(100) < model.compute_slippage(10000)
    assert model.compute_slippage(10000, 1000) > model.compute_slippage(10000, 100000)
    assert model.compute_slippage(1e20) == .05


def test_book_ticker_and_watchdog():
    client = BinanceFeedClient('BTCUSDT')
    assert not client.watchdog.is_healthy()
    tick = client.parse_stream_message({'s': 'BTCUSDT', 'b': '99', 'a': '101', 'B': '2', 'A': '3'})
    assert tick.spread_bps == pytest.approx(200)
    assert client.watchdog.is_healthy()
    assert client.parse_stream_message({'b': 'bad'}) is None
    tick.timestamp -= 3
    assert not client.watchdog.is_healthy()


def test_store_failure_rolls_back_execution(monkeypatch, proposal):
    engine = PaperEngine(store_path=':memory:')
    engine.update_ticker('BTCUSDT', 9999, 10000)
    def fail(_state):
        raise OSError('injected disk failure')
    monkeypatch.setattr(engine.store, 'save_state', fail)
    with pytest.raises(OSError, match='injected disk failure'):
        engine.execute_proposal(replace(proposal, order_type=OrderType.MARKET, price=None, stop_loss=9000))
    assert engine.cash == 10000
    assert not engine.positions and not engine.reports
    assert engine.store.load_state() is None
