import argparse
import json
import os
from pathlib import Path
from hermes_trader.contracts import GuardianState
from hermes_trader.paper import PaperEngine
from hermes_trader.proposer import StrategyProposer
from hermes_trader.scaffold import ProfileScaffolder

def main(argv=None):
    parser = argparse.ArgumentParser(prog='hermes-trader')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('status')
    propose = sub.add_parser('propose')
    propose.add_argument('--symbol', required=True)
    propose.add_argument('--side', choices=['BUY', 'SELL'], required=True)
    propose.add_argument('--qty', type=float, required=True)
    propose.add_argument('--price', type=float, required=True)
    sub.add_parser('emergency-stop')
    scaffold = sub.add_parser('scaffold')
    scaffold.add_argument('--path', default='~/.hermes/profiles/trader')
    args = parser.parse_args(argv)
    if args.command == 'scaffold':
        print(json.dumps(ProfileScaffolder().generate_trader_profile(args.path)))
        return 0
    engine = PaperEngine()
    state_path = Path(os.environ.get('HERMES_TRADER_STATE', '~/.hermes/trader-state.json')).expanduser()
    if state_path.exists():
        try:
            engine.guardian.state = GuardianState(json.loads(state_path.read_text())['state'])
        except (ValueError, KeyError, OSError):
            engine.guardian.state = GuardianState.HALTED
    if args.command == 'status':
        portfolio = engine.get_portfolio()
        portfolio['state'] = engine.guardian.state.value
        print(json.dumps(portfolio, default=str))
    elif args.command == 'emergency-stop':
        message = engine.kill_switch.trigger_emergency_stop()
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({'state': engine.guardian.state.value}))
        print(message)
    else:
        proposal = StrategyProposer().propose(args.symbol, args.side, args.qty, args.price)
        approved, reason = engine.guardian.validate_proposal(proposal, engine.get_portfolio())
        print(reason)
        return 0 if approved else 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
