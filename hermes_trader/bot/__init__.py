class TelegramCommandHandler:
    def __init__(self, engine, thesis_tracker=None, kill_switch=None):
        self.engine = engine
        self.thesis_tracker = thesis_tracker
        self.kill_switch = kill_switch or engine.kill_switch

    def handle(self, command):
        parts = command.strip().split(maxsplit=1)
        if not parts:
            return 'Unknown command'
        action = parts[0].split('@')[0].lower()
        if action == '/status':
            p = self.engine.get_portfolio()
            return f"Equity: {p['equity']:.2f}\nCash: {p['cash']:.2f}\nDrawdown: {p['drawdown_pct']:.2f}%\nState: {self.engine.guardian.state.value}\nOpen Positions: {len(p['positions'])}"
        if action == '/positions':
            positions = self.engine.get_portfolio()['positions']
            return '\n'.join(f'{p.symbol} {p.side.value} {p.size:g} Unrealized PnL: {p.unrealized_pnl:.2f}' for p in positions.values()) or 'No open positions'
        if action == '/theses':
            return '\n'.join(f'{t.symbol}: {t.title}' for t in self.thesis_tracker.active()) if self.thesis_tracker and self.thesis_tracker.active() else 'No active theses'
        if action == '/emergency_stop':
            return self.kill_switch.trigger_emergency_stop()
        if action == '/resume':
            return 'Resumed' if self.kill_switch.resume(parts[1] if len(parts) > 1 else '') else 'Resume denied'
        return 'Unknown command'

    handle_command = handle
