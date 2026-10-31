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


class HypergraphView:
    def __init__(self, path=':memory:'):
        self.connection = sqlite3.connect(path)
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.execute('CREATE TABLE IF NOT EXISTS hyperedges (edge_id TEXT PRIMARY KEY, nodes TEXT NOT NULL, weight REAL NOT NULL, z_score REAL NOT NULL, is_immune INTEGER NOT NULL, metadata TEXT NOT NULL)')
        self.connection.commit()

    @staticmethod
    def _edge(row):
        return HyperEdge(row[0], json.loads(row[1]), row[2], row[3], bool(row[4]), json.loads(row[5]))

    def add_hyperedge(self, nodes, weight=1.0, z_score=0.0, metadata=None):
        edge = HyperEdge(str(uuid4()), list(nodes), weight, z_score, abs(z_score) >= 3.0, dict(metadata or {}))
        with self.connection:
            self.connection.execute('INSERT INTO hyperedges VALUES (?, ?, ?, ?, ?, ?)', (edge.edge_id, json.dumps(edge.nodes), edge.weight, edge.z_score, edge.is_immune, json.dumps(edge.metadata)))
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
