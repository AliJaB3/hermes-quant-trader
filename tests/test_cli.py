import json
from hermes_trader.cli import main

def test_cli(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('HERMES_TRADER_STATE', str(tmp_path / 'state.json'))
    assert main(['status']) == 0
    assert json.loads(capsys.readouterr().out)['equity'] == 10000
    assert main(['propose', '--symbol', 'BTCUSDT', '--side', 'BUY', '--qty', '.01', '--price', '10000', '--stop-loss', '9000']) == 0
    assert main(['emergency-stop']) == 0
    assert main(['propose', '--symbol', 'BTCUSDT', '--side', 'BUY', '--qty', '.01', '--price', '10000', '--stop-loss', '9000']) == 1
    assert main(['scaffold', '--path', str(tmp_path / 'profile')]) == 0
    assert (tmp_path / 'profile/config.yaml').exists()
