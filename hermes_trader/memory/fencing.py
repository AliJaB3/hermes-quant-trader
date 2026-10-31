"""SQLite-backed monotonic fencing epochs shared by managers using a database."""
from dataclasses import dataclass
import sqlite3
import time


@dataclass(frozen=True)
class FencingToken:
    epoch: int
    leader_id: str
    issued_at: float
    lease_ttl_s: float = 5.0


class FencingTokenManager:
    def __init__(self, path=':memory:'):
        self.connection = sqlite3.connect(path, timeout=30)
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.execute('CREATE TABLE IF NOT EXISTS fencing_epoch (id INTEGER PRIMARY KEY CHECK(id=1), epoch INTEGER NOT NULL)')
        self.connection.execute('INSERT OR IGNORE INTO fencing_epoch (id, epoch) VALUES (1, 0)')
        columns = {row[1] for row in self.connection.execute('PRAGMA table_info(fencing_epoch)')}
        if 'leader_id' not in columns:
            self.connection.execute("ALTER TABLE fencing_epoch ADD COLUMN leader_id TEXT NOT NULL DEFAULT ''")
        self.connection.commit()

    @property
    def current_epoch(self):
        return self.connection.execute('SELECT epoch FROM fencing_epoch WHERE id=1').fetchone()[0]

    @property
    def current_leader(self):
        return self.connection.execute('SELECT leader_id FROM fencing_epoch WHERE id=1').fetchone()[0]

    def acquire_token(self, leader_id, lease_ttl_s=5.0):
        with self.connection:
            self.connection.execute('UPDATE fencing_epoch SET epoch=epoch+1, leader_id=? WHERE id=1', (leader_id,))
            epoch = self.connection.execute('SELECT epoch FROM fencing_epoch WHERE id=1').fetchone()[0]
        return FencingToken(epoch, leader_id, time.monotonic(), lease_ttl_s)

    def validate_token(self, token):
        epoch, leader = self.connection.execute('SELECT epoch, leader_id FROM fencing_epoch WHERE id=1').fetchone()
        age = time.monotonic() - token.issued_at
        return token.epoch == epoch and token.leader_id == leader and 0 <= age <= token.lease_ttl_s

    def close(self):
        self.connection.close()
