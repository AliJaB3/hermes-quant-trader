from hermes_trader.bot import TelegramCommandHandler
from hermes_trader.paper import PaperEngine
from hermes_trader.guardian import KillSwitchManager

def test_commands():
    e = PaperEngine()
    bot = TelegramCommandHandler(e, kill_switch=KillSwitchManager(e.guardian, 'key'))
    assert 'Equity: 10000.00' in bot.handle('/status')
    assert 'No open positions' in bot.handle('/positions')
    assert 'No active theses' in bot.handle('/theses')
    assert 'HALTED' in bot.handle('/emergency_stop')
    assert 'denied' in bot.handle('/resume bad')
    assert bot.handle('/resume key') == 'Resumed'
    assert bot.handle('/unknown') == 'Unknown command'
