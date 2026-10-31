"""SQLite-backed monotonic fencing epochs shared by managers using a database."""
from dataclasses import dataclass
import sqlite3
import time


@dataclass(frozen=True)
class FencingToken:
    epoch: int
    leader_id: str
    issued_at: float


class FencingTokenManager:
    def __init__(self, path=':memory:'):
        self.connection = sqlite3.connect(path, timeout=30)
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.execute('CREATE TABLE IF NOT EXISTS fencing_epoch (id INTEGER PRIMARY KEY CHECK(id=1), epoch INTEGER NOT NULL)')
        self.connection.execute('INSERT OR IGNORE INTO fencing_epoch VALUES (1, 0)')
        self.connection.commit()

    def acquire_token(self, leader_id):
        with self.connection:
            self.connection.execute('UPDATE fencing_epoch SET epoch=epoch+1 WHERE id=1')
            epoch = self.connection.execute('SELECT epoch FROM fencing_epoch WHERE id=1').fetchone()[0]
        return FencingToken(epoch, leader_id, time.time())

    def validate_token(self, token):
        return token.epoch >= self.connection.execute('SELECT epoch FROM fencing_epoch WHERE id=1').fetchone()[0]

    def close(self):
        self.connection.close()
