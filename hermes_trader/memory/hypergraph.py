"""Persistent hyperedges connecting arbitrary sets of concepts."""
from dataclasses import dataclass, field
import json
import sqlite3
from uuid import uuid4


@dataclass
class HyperEdge:
    edge_id: str
    nodes: list[str]
    weight: float = 1.0
    z_score: float = 0.0
    is_immune: bool = False
    metadata: dict = field(default_factory=dict)
    impact_score: float = 0.0


class HypergraphView:
    def __init__(self, path=':memory:', max_edges=1000):
        if not isinstance(max_edges, int) or isinstance(max_edges, bool) or max_edges <= 0:
            raise ValueError('max_edges must be a positive integer')
        self.max_edges = max_edges
        self.connection = sqlite3.connect(path)
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.execute('CREATE TABLE IF NOT EXISTS hyperedges (edge_id TEXT PRIMARY KEY, nodes TEXT NOT NULL, weight REAL NOT NULL, z_score REAL NOT NULL, is_immune INTEGER NOT NULL, metadata TEXT NOT NULL)')
        columns = {row[1] for row in self.connection.execute('PRAGMA table_info(hyperedges)')}
        if 'impact_score' not in columns:
            self.connection.execute('ALTER TABLE hyperedges ADD COLUMN impact_score REAL NOT NULL DEFAULT 0')
            self.connection.execute('UPDATE hyperedges SET is_immune=0')
        self.connection.commit()

    @staticmethod
    def _edge(row):
        return HyperEdge(row[0], json.loads(row[1]), row[2], row[3], bool(row[4]), json.loads(row[5]), row[6])

    def add_hyperedge(self, nodes, weight=1.0, z_score=0.0, impact_score=0.0, metadata=None):
        edge = HyperEdge(str(uuid4()), list(nodes), weight, z_score,
                         abs(z_score) >= 3.0 and impact_score >= 1.0,
                         dict(metadata or {}), impact_score)
        try:
            self.connection.execute('BEGIN IMMEDIATE')
            while self.connection.execute('SELECT COUNT(*) FROM hyperedges').fetchone()[0] >= self.max_edges:
                victim = self.connection.execute(
                    'SELECT edge_id FROM hyperedges WHERE is_immune=0 ORDER BY weight, rowid LIMIT 1'
                ).fetchone()
                if victim is None:
                    victim = self.connection.execute(
                        'SELECT edge_id FROM hyperedges ORDER BY impact_score, rowid LIMIT 1'
                    ).fetchone()
                self.connection.execute('DELETE FROM hyperedges WHERE edge_id=?', victim)
            self.connection.execute(
                'INSERT INTO hyperedges (edge_id, nodes, weight, z_score, is_immune, metadata, impact_score) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (edge.edge_id, json.dumps(edge.nodes), edge.weight, edge.z_score,
                 edge.is_immune, json.dumps(edge.metadata), edge.impact_score))
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        return edge

    def get_hyperedge(self, edge_id):
        row = self.connection.execute('SELECT * FROM hyperedges WHERE edge_id=?', (edge_id,)).fetchone()
        return self._edge(row) if row else None

    def decay_edges(self, decay_factor=0.95):
        with self.connection:
            self.connection.execute('UPDATE hyperedges SET weight=weight * ? WHERE is_immune=0', (decay_factor,))

    def get_summary(self):
        edges = [self._edge(row) for row in self.connection.execute('SELECT * FROM hyperedges')]
        return {'total_edges': len(edges), 'immune_edges': sum(e.is_immune for e in edges), 'active_nodes': len({node for edge in edges for node in edge.nodes})}

    def close(self):
        self.connection.close()
