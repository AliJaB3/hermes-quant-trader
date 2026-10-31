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
    text = j.extract_negative_constraints(report, t)
    j.close()
    j = EvoMemJournal(path)
    assert j.get_negative_constraints('BTC') == [text]
    assert not j.get_negative_constraints('ETH')
    j.close()
