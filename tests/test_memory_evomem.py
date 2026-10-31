from hermes_trader.memory import TradingThesis, ThesisTracker, EvoMemJournal
from hermes_trader.contracts import ExecutionReport, OrderSide

def test_tracking_and_persistence(tmp_path):
    t = TradingThesis('1', 'breakout', 'BTC', 'rises', 'breakout fails', {}, 'OPEN', 'now')
    tracker = ThesisTracker()
    tracker.register(t)
    assert tracker.active() == [t]
    tracker.update('1', 'FALSIFIED')
    assert not tracker.active()
    report = ExecutionReport('e', 'p', 'BTC', OrderSide.SELL, 1, 10, .1, .01, -2, 'now')
    path = str(tmp_path / 'journal.db')
    j = EvoMemJournal(path)
    j.record_trade(report); j.record_thesis(t)
    assert j.extract_negative_constraints(report, t) is None
    assert j.record_loss('BTC', OrderSide.SELL, report, t) is None
    j.close()
    j = EvoMemJournal(path)
    from dataclasses import replace
    assert j.record_loss('BTC', OrderSide.SELL, replace(report, execution_id='e2', realized_pnl=-24), t) is None
    assert not j.get_negative_constraints('BTC')
    text = j.record_loss('BTC', OrderSide.SELL, replace(report, execution_id='e3', realized_pnl=-25), t)
    assert j.get_negative_constraints('BTC') == [text]
    assert not j.get_negative_constraints('ETH')
    j.close()
