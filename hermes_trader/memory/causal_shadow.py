"""Counterfactual records, kept separate from executed trade history."""
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from uuid import uuid4


@dataclass
class ShadowRecord:
    record_id: str
    timestamp: str
    symbol: str
    side: str
    blocked_by_rule: str
    hypothetical_price: float
    resolution_price: float | None = None
    counterfactual_pnl: float = 0.0


class CausalShadowTracker:
    def __init__(self, path=':memory:', connection=None):
        if connection is None and path and path != ':memory:':
            Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self.connection = connection if connection is not None else sqlite3.connect(path)
        self._owns_connection = connection is None
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.execute('''CREATE TABLE IF NOT EXISTS shadow_counterfactuals
            (record_id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, symbol TEXT NOT NULL,
             side TEXT NOT NULL, blocked_by_rule TEXT NOT NULL, hypothetical_price REAL NOT NULL,
             resolution_price REAL, counterfactual_pnl REAL NOT NULL DEFAULT 0)''')
        self.connection.commit()

    def record_blocked(self, symbol, side, rule_id, current_price):
        record_id = str(uuid4())
        side = str(getattr(side, 'value', side)).upper()
        with self.connection:
            self.connection.execute('INSERT INTO shadow_counterfactuals VALUES (?, ?, ?, ?, ?, ?, NULL, 0)',
                                    (record_id, datetime.now(timezone.utc).isoformat(), symbol, side, rule_id, float(current_price)))
        return record_id

    def resolve_counterfactual(self, record_id, current_price):
        with self.connection:
            row = self.connection.execute('SELECT side, hypothetical_price, resolution_price FROM shadow_counterfactuals WHERE record_id=?', (record_id,)).fetchone()
            if row is None:
                raise KeyError(record_id)
            if row[2] is not None:
                raise ValueError('counterfactual already resolved')
            if row[0] not in ('BUY', 'SELL'):
                raise ValueError('unsupported side')
            pnl = (float(current_price) - row[1]) * (1 if row[0] == 'BUY' else -1)
            self.connection.execute('UPDATE shadow_counterfactuals SET resolution_price=?, counterfactual_pnl=? WHERE record_id=?', (float(current_price), pnl, record_id))
        return pnl

    def get_shadow_stats(self, symbol=None):
        query = 'SELECT resolution_price, counterfactual_pnl FROM shadow_counterfactuals'
        rows = self.connection.execute(query + (' WHERE symbol=?' if symbol is not None else ''), (symbol,) if symbol is not None else ()).fetchall()
        resolved = [pnl for price, pnl in rows if price is not None]
        return {'total': len(rows), 'resolved': len(resolved), 'pending': len(rows) - len(resolved),
                'wins': sum(p > 0 for p in resolved), 'losses': sum(p < 0 for p in resolved),
                'breakeven': sum(p == 0 for p in resolved), 'total_counterfactual_pnl': sum(resolved)}

    def close(self):
        if self._owns_connection:
            self.connection.close()
