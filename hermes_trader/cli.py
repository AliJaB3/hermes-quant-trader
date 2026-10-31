import argparse
import json
import os
import time
from urllib.error import URLError
from dataclasses import asdict
import yaml
from pathlib import Path
from hermes_trader.contracts import GuardianState
from hermes_trader.daemon import TradingDaemon
from hermes_trader.feed.ticker import MarketTick, binance_tick
from hermes_trader.paper import PaperEngine
from hermes_trader.proposer import StrategyProposer
from hermes_trader.scaffold import ProfileScaffolder
from hermes_trader.strategy import StrategyLoader, WalkForwardValidator

def main(argv=None):
    parser = argparse.ArgumentParser(prog='hermes-trader')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('status')
    run = sub.add_parser('run')
    run.add_argument('--strategy', required=True)
    run.add_argument('--live', action='store_true', help='poll public Binance prices')
    run.add_argument('--price', type=float, default=100.0, help='simulated price')
    run.add_argument('--interval', type=float, default=1.0)
    run.add_argument('--max-ticks', type=int, default=None, help='stop after this many cycles')
    test_strategy = sub.add_parser('test-strategy')
    test_strategy.add_argument('--file', required=True)
    propose = sub.add_parser('propose')
    propose.add_argument('--symbol', required=True)
    propose.add_argument('--side', choices=['BUY', 'SELL'], required=True)
    propose.add_argument('--qty', type=float, required=True)
    propose.add_argument('--price', type=float, required=True)
    propose.add_argument('--stop-loss', type=float)
    sub.add_parser('emergency-stop')
    scaffold = sub.add_parser('scaffold')
    scaffold.add_argument('--path', default='~/.hermes/profiles/trader')
    args = parser.parse_args(argv)
    if args.command == 'test-strategy':
        try:
            data = yaml.safe_load(Path(args.file).read_text())
            strategy = StrategyLoader().load_from_dict(data)
            candles = data.get('candles', [])
            if not isinstance(candles, list):
                raise ValueError('candles must be a list')
            report = WalkForwardValidator().validate(strategy, candles)
        except (OSError, ValueError, TypeError, KeyError, yaml.YAMLError) as exc:
            print(json.dumps({'error': str(exc)}))
            return 1
        print(json.dumps(asdict(report)))
        return 0
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
    if args.command == 'run':
        try:
            import math
            if not math.isfinite(args.interval) or args.interval <= 0 or not math.isfinite(args.price) or args.price <= 0 or (args.max_ticks is not None and args.max_ticks <= 0):
                raise ValueError('price, interval and max-ticks must be positive')
            strategy = StrategyLoader().load_from_yaml_or_json(Path(args.strategy).read_text())
            daemon = TradingDaemon([strategy], paper_engine=engine)
            cycles = 0
            while args.max_ticks is None or cycles < args.max_ticks:
                for symbol in strategy.target_universe:
                    tick = (binance_tick(symbol) if args.live else
                            MarketTick(symbol, args.price, args.price, args.price, 0.0, time.time()))
                    for report in daemon.process_tick(tick):
                        print(json.dumps(asdict(report), default=str), flush=True)
                cycles += 1
                if args.max_ticks is None or cycles < args.max_ticks:
                    time.sleep(args.interval)
        except KeyboardInterrupt:
            return 0
        except (OSError, ValueError, TypeError, KeyError, URLError) as exc:
            print(json.dumps({'error': str(exc)}))
            return 1
        return 0
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
        proposal = StrategyProposer().propose(args.symbol, args.side, args.qty, args.price, stop_loss=args.stop_loss)
        approved, reason = engine.guardian.validate_proposal(proposal, engine.get_portfolio())
        print(reason)
        return 0 if approved else 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
