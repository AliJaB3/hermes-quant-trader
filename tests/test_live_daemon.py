import json
import time

from hermes_trader.cli import main
from hermes_trader.daemon import TradingDaemon
from hermes_trader.feed import FeedWatchdog, MarketTick
from hermes_trader.reconciliation import StateReconciler
from hermes_trader.strategy import StrategyLoader


def strategy():
    return StrategyLoader().load_from_dict({'strategy_id': 'test', 'version': '1',
        'target_universe': ['BTCUSDT'], 'alpha_rules': [{'condition': 'last_price > 90 and spread_bps < 5'}],
        'execution_parameters': {'quantity': 0.1}})


def tick(timestamp=None):
    return MarketTick('BTCUSDT', 100, 100, 100, 0, time.time() if timestamp is None else timestamp)


def test_watchdog(monkeypatch):
    monkeypatch.setattr('hermes_trader.feed.ticker.time.time', lambda: 100.0)
    watchdog = FeedWatchdog(max_stale_ms=1000)
    assert not watchdog.is_healthy()
    watchdog.record_tick(tick(99.0))
    assert watchdog.is_healthy()
    watchdog.record_tick(tick(98.9))
    assert not watchdog.is_healthy()


def test_reconciliation():
    local = {'BTC': {'size': 1, 'side': 'LONG'}, 'ETH': {'size': 2, 'side': 'LONG'},
             'SOL': {'size': 1, 'side': 'LONG'}}
    remote = {'BTC': {'size': 2, 'side': 'LONG'}, 'ETH': {'size': 2, 'side': 'SHORT'},
              'DOGE': {'size': 3, 'side': 'LONG'}}
    found = {(d.symbol, d.discrepancy_type) for d in StateReconciler().reconcile(local, remote)}
    assert found == {('BTC', 'SIZE_MISMATCH'), ('ETH', 'SIZE_MISMATCH'),
                     ('SOL', 'GHOST_LOCAL'), ('DOGE', 'ORPHAN_REMOTE')}


def test_daemon_execution_and_stale():
    daemon = TradingDaemon([strategy()])
    assert daemon.process_tick(tick(time.time() - 10)) == []
    reports = daemon.process_tick(tick())
    assert len(reports) == 1 and reports[0].symbol == 'BTCUSDT'
    status = daemon.get_status()
    assert status['watchdog_healthy'] and status['guardian_state'] == 'NORMAL'
    assert status['positions']['BTCUSDT'].size == 0.1
    assert status['equity'] < 10000


def test_run_cli(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('HERMES_TRADER_STATE', str(tmp_path / 'state.json'))
    path = tmp_path / 'strategy.json'
    path.write_text(json.dumps({'strategy_id': 'test', 'version': '1', 'target_universe': ['BTCUSDT'],
        'alpha_rules': [{'condition': 'last_price > 90'}], 'execution_parameters': {'quantity': 0.1}}))
    assert main(['run', '--strategy', str(path), '--max-ticks', '1']) == 0
    assert json.loads(capsys.readouterr().out)['symbol'] == 'BTCUSDT'


def test_daemon_rejects_wide_spread_and_halted_guardian():
    from hermes_trader.contracts import GuardianState
    daemon = TradingDaemon([strategy()])
    assert daemon.process_tick(MarketTick('BTCUSDT', 99, 101, 100, 1, time.time())) == []
    daemon.guardian.state = GuardianState.HALTED
    assert daemon.process_tick(tick()) == []
    assert daemon.get_status()['guardian_state'] == 'HALTED'


def test_binance_tick(monkeypatch):
    from hermes_trader.feed.ticker import binance_tick
    import urllib.request

    class Response:
        def __init__(self, data):
            self.data = json.dumps(data).encode()
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self):
            return self.data

    def open_url(url, timeout):
        assert timeout == 5.0
        if 'bookTicker' in url:
            return Response({'bidPrice': '99.99', 'askPrice': '100.01'})
        return Response({'price': '100'})

    monkeypatch.setattr(urllib.request, 'urlopen', open_url)
    result = binance_tick('BTCUSDT')
    assert result.symbol == 'BTCUSDT' and result.last_price == 100
    assert abs(result.spread_bps - 2) < 1e-8
