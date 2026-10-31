from dataclasses import dataclass, astuple
from pathlib import Path
import sqlite3


@dataclass
class EpisodicTrade:
    trade_id: str
    timestamp: str
    symbol: str
    side: str
    qty: float
    price: float
    fee: float
    slippage: float
    realized_pnl: float
    regime_tag: str
    was_simulated: bool
    correlation_id: str
    raw_json: str


class EpisodicStore:
    def __init__(self, path=':memory:'):
        if path and path != ':memory:':
            Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.execute('''CREATE TABLE IF NOT EXISTS episodic_trades
            (trade_id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, symbol TEXT NOT NULL,
             side TEXT NOT NULL, qty REAL NOT NULL, price REAL NOT NULL, fee REAL NOT NULL,
             slippage REAL NOT NULL, realized_pnl REAL NOT NULL, regime_tag TEXT NOT NULL,
             was_simulated INTEGER NOT NULL, correlation_id TEXT NOT NULL, raw_json TEXT NOT NULL)''')
        self.connection.commit()

    def record_trade(self, trade):
        with self.connection:
            self.connection.execute('INSERT INTO episodic_trades VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', astuple(trade))

    @staticmethod
    def _trades(rows):
        return [EpisodicTrade(*row[:10], bool(row[10]), *row[11:]) for row in rows]

    def get_cluster(self, symbol, side, min_trades=30):
        rows = self.connection.execute('SELECT * FROM episodic_trades WHERE symbol=? AND side=? ORDER BY rowid', (symbol, side)).fetchall()
        return self._trades(rows) if len(rows) >= min_trades else []

    def get_recent_trades(self, limit=100):
        return self._trades(self.connection.execute('SELECT * FROM episodic_trades ORDER BY rowid DESC LIMIT ?', (limit,)))

    def clusters(self, min_trades=30):
        return self.connection.execute('SELECT symbol, side FROM episodic_trades GROUP BY symbol, side HAVING COUNT(*) >= ?', (min_trades,)).fetchall()

    def count(self):
        return self.connection.execute('SELECT COUNT(*) FROM episodic_trades').fetchone()[0]

    def close(self):
        self.connection.close()
