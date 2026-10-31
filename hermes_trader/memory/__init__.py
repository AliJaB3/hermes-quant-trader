from dataclasses import dataclass, asdict
import json
import sqlite3

@dataclass
class TradingThesis:
    thesis_id: str
    title: str
    symbol: str
    hypothesis: str
    falsification_condition: str
    entry_plan: dict
    status: str
    created_at: str

class ThesisTracker:
    def __init__(self):
        self.theses = {}

    def register(self, thesis):
        if thesis.thesis_id in self.theses:
            raise ValueError('duplicate thesis')
        if thesis.status not in ('OPEN', 'VALIDATED', 'FALSIFIED', 'ABANDONED'):
            raise ValueError('invalid thesis status')
        self.theses[thesis.thesis_id] = thesis
        return thesis

    def update(self, thesis_id, status):
        if status not in ('OPEN', 'VALIDATED', 'FALSIFIED', 'ABANDONED'):
            raise ValueError('invalid thesis status')
        self.theses[thesis_id].status = status
        return self.theses[thesis_id]

    def get(self, thesis_id):
        return self.theses.get(thesis_id)

    def active(self):
        return [t for t in self.theses.values() if t.status == 'OPEN']

class EvoMemJournal:
    def __init__(self, path=':memory:'):
        self.connection = sqlite3.connect(path)
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.executescript('CREATE TABLE IF NOT EXISTS trades (execution_id TEXT PRIMARY KEY, data TEXT NOT NULL); CREATE TABLE IF NOT EXISTS theses (thesis_id TEXT PRIMARY KEY, data TEXT NOT NULL); CREATE TABLE IF NOT EXISTS constraints (id INTEGER PRIMARY KEY, symbol TEXT NOT NULL, text TEXT NOT NULL, UNIQUE(symbol, text));')
        self.connection.commit()

    def record_trade(self, report):
        with self.connection:
            self.connection.execute('INSERT OR REPLACE INTO trades VALUES (?, ?)', (report.execution_id, json.dumps(asdict(report))))

    def record_thesis(self, thesis):
        with self.connection:
            self.connection.execute('INSERT OR REPLACE INTO theses VALUES (?, ?)', (thesis.thesis_id, json.dumps(asdict(thesis))))

    def extract_negative_constraints(self, losing_trade, thesis):
        if losing_trade.realized_pnl >= 0:
            raise ValueError('trade must have negative realized PnL')
        if losing_trade.symbol != thesis.symbol:
            raise ValueError('trade and thesis symbols differ')
        text = f"Do not repeat {losing_trade.side.value if hasattr(losing_trade.side, 'value') else losing_trade.side} on {thesis.symbol} when {thesis.falsification_condition}."
        with self.connection:
            self.connection.execute('INSERT OR IGNORE INTO constraints (symbol, text) VALUES (?, ?)', (thesis.symbol, text))
        return text

    def get_negative_constraints(self, symbol):
        return [row[0] for row in self.connection.execute('SELECT text FROM constraints WHERE symbol = ? ORDER BY id', (symbol,))]

    def close(self):
        self.connection.close()
