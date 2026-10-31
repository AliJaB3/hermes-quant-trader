"""Transactional SQLite storage for paper portfolio snapshots."""
import json
import os
from pathlib import Path
import sqlite3
import threading


class PortfolioStore:
    def __init__(self, path=None, max_wal_bytes=50 * 1024 * 1024):
        self.max_wal_bytes = max_wal_bytes
        self.path = str(Path(path or os.environ.get('HERMES_TRADER_PORTFOLIO', '~/.hermes/trader_portfolio.sqlite')).expanduser())
        if self.path != ':memory:':
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.execute('PRAGMA synchronous=FULL')
        self.connection.executescript('''
            CREATE TABLE IF NOT EXISTS portfolio_state (key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP);
            CREATE TABLE IF NOT EXISTS positions (symbol TEXT PRIMARY KEY, side TEXT, size REAL, entry_price REAL, leverage REAL, updated_at TIMESTAMP);
            CREATE TABLE IF NOT EXISTS orders (order_id TEXT PRIMARY KEY, proposal_id TEXT, symbol TEXT, side TEXT, qty REAL, price REAL, status TEXT, created_at TIMESTAMP);
        ''')

    def save_state(self, state):
        payload = json.dumps(state, allow_nan=False)
        with self._lock, self.connection:
            self.connection.execute("INSERT OR REPLACE INTO portfolio_state VALUES ('snapshot', ?, CURRENT_TIMESTAMP)", (payload,))
            self.connection.execute('DELETE FROM positions')
            for p in state.get('positions', {}).values():
                self.connection.execute('INSERT INTO positions VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)', (p['symbol'], p['side'], p['size'], p['entry_price'], p['leverage']))
            for r in state.get('reports', []):
                self.connection.execute('INSERT OR REPLACE INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (r['execution_id'], r['proposal_id'], r['symbol'], r['side'], r['filled_quantity'], r['avg_fill_price'], 'FILLED', r['timestamp']))

        self.check_wal_size()

    def checkpoint_wal(self):
        """Truncate the WAL; return False if another connection prevents it."""
        with self._lock:
            busy, _, _ = self.connection.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()
            return busy == 0

    def check_wal_size(self):
        """Return the observed WAL size, checkpointing if it exceeds the limit."""
        with self._lock:
            try:
                size = os.path.getsize(self.path + '-wal') if self.path != ':memory:' else 0
            except FileNotFoundError:
                size = 0
            if size > self.max_wal_bytes:
                self.checkpoint_wal()
            return size

    def load_state(self):
        with self._lock:
            row = self.connection.execute("SELECT value FROM portfolio_state WHERE key='snapshot'").fetchone()
            return json.loads(row[0]) if row else None

    def close(self):
        with self._lock:
            self.connection.close()
