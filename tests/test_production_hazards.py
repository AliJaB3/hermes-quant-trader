from dataclasses import replace

import pytest

from hermes_trader.daemon.shutdown import GracefulShutdownManager, ShutdownState
from hermes_trader.feed.clock_sync import ClockSynchronizer
from hermes_trader.feed.rate_governor import RateGovernor
from hermes_trader.guardian.adl_watchdog import ADLWatchdog
from hermes_trader.memory.fencing import FencingTokenManager
from hermes_trader.paper import PaperEngine
from hermes_trader.paper.store import PortfolioStore


def test_clock_sync(monkeypatch):
    clock = ClockSynchronizer()
    clock.update_offset(1000, 1150, 1100)
    assert clock.clock_offset_ms == pytest.approx(20)
    clock.update_offset(1000, 1150, 1100)
    assert clock.clock_offset_ms == pytest.approx(36)
    monkeypatch.setattr('hermes_trader.feed.clock_sync.time.time', lambda: 10)
    assert clock.get_calibrated_timestamp_ms() == 10036


def test_monotonic_fencing(monkeypatch):
    now = [100.0]
    monkeypatch.setattr('hermes_trader.memory.fencing.time.monotonic', lambda: now[0])
    manager = FencingTokenManager()
    token = manager.acquire_token('leader', 5)
    assert token.issued_at == 100
    monkeypatch.setattr('hermes_trader.memory.fencing.time.time', lambda: -100000)
    now[0] = 105
    assert manager.validate_token(token)
    now[0] = 105.01
    assert not manager.validate_token(token)
    assert not manager.validate_token(replace(token, issued_at=200))
    manager.close()


def test_rate_governor(monkeypatch):
    now = [10.0]
    monkeypatch.setattr('hermes_trader.feed.rate_governor.time.monotonic', lambda: now[0])
    governor = RateGovernor()
    governor.record_weight(900)
    assert not governor.can_request()
    assert governor.can_request(300, is_emergency=True)
    assert not governor.can_request(301, is_emergency=True)
    governor.trip_429(5)
    assert not governor.can_request(is_emergency=True)
    now[0] = 15
    assert governor.can_request(is_emergency=True)


def test_wal_guard_and_checkpoint(tmp_path):
    store = PortfolioStore(tmp_path / 'portfolio.db', max_wal_bytes=10**8)
    store.save_state({'positions': {}, 'reports': []})
    size = store.check_wal_size()
    assert size > 0
    store.max_wal_bytes = size - 1
    assert store.check_wal_size() == size
    assert store.check_wal_size() == 0
    assert store.checkpoint_wal()
    assert store.load_state() == {'positions': {}, 'reports': []}
    store.close()


def test_adl_quantiles():
    watchdog = ADLWatchdog()
    assert not watchdog.is_high_risk('BTC')
    watchdog.update_quantile('BTC', 4)
    assert watchdog.is_high_risk('BTC') and not watchdog.should_derisk('BTC')
    watchdog.update_quantile('BTC', 5)
    assert watchdog.should_derisk('BTC')
    with pytest.raises(ValueError):
        watchdog.update_quantile('BTC', 6)


def test_shutdown_preserves_stops_and_rejects_proposals(tmp_path):
    engine = PaperEngine(store_path=tmp_path / 'portfolio.db')
    manager = GracefulShutdownManager()
    orders = {'entry': 'entry', 'stop': 'stop-loss'}
    states = []

    def cancel_entries():
        states.append(manager.state)
        assert engine.execute_proposal(None) == (False, 'Engine is shutting down')
        del orders['entry']

    original_save = engine._save
    def save():
        states.append(manager.state)
        original_save()

    engine._save = save
    manager.initiate_shutdown(engine, cancel_entries)
    assert states == [ShutdownState.CANCEL_ENTRY_ONLY, ShutdownState.CANCEL_ENTRY_ONLY]
    assert manager.state is ShutdownState.STOPPED
    assert orders == {'stop': 'stop-loss'}
    assert engine.store.load_state() is not None
    engine.store.close()


def test_shutdown_failure_does_not_claim_stopped(tmp_path):
    engine = PaperEngine(store_path=tmp_path / 'portfolio.db')
    manager = GracefulShutdownManager()
    def fail():
        raise RuntimeError('cancellation failed')
    with pytest.raises(RuntimeError, match='cancellation failed'):
        manager.initiate_shutdown(engine, fail)
    assert manager.state is ShutdownState.CANCEL_ENTRY_ONLY
    assert engine.execute_proposal(None)[0] is False
    engine.store.close()
