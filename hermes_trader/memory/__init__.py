from dataclasses import dataclass, asdict
import json
import sqlite3
from hermes_trader.contracts import ExecutionReport, OrderSide

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
        self.connection.execute('CREATE TABLE IF NOT EXISTS loss_clusters (execution_id TEXT PRIMARY KEY, cluster_key TEXT NOT NULL, data TEXT NOT NULL)')
        self.connection.commit()
        self.loss_clusters = {}
        for key, data in self.connection.execute('SELECT cluster_key, data FROM loss_clusters ORDER BY rowid'):
            fields = json.loads(data)
            fields['side'] = OrderSide(fields['side'])
            self.loss_clusters.setdefault(key, []).append(ExecutionReport(**fields))

    def record_trade(self, report):
        with self.connection:
            self.connection.execute('INSERT OR REPLACE INTO trades VALUES (?, ?)', (report.execution_id, json.dumps(asdict(report))))

    def record_thesis(self, thesis):
        with self.connection:
            self.connection.execute('INSERT OR REPLACE INTO theses VALUES (?, ?)', (thesis.thesis_id, json.dumps(asdict(thesis))))

    def extract_negative_constraints(self, losing_trade, thesis):
        return self.record_loss(losing_trade.symbol, losing_trade.side, losing_trade, thesis)

    def record_loss(self, symbol, side, report, thesis=None):
        side = OrderSide(side)
        if report.realized_pnl >= 0:
            raise ValueError('trade must have negative realized PnL')
        if report.symbol != symbol or OrderSide(report.side) != side:
            raise ValueError('trade and cluster differ')
        if thesis is not None and symbol != thesis.symbol:
            raise ValueError('trade and thesis symbols differ')
        key = f'{symbol}_{side.value}'
        with self.connection:
            inserted = self.connection.execute('INSERT OR IGNORE INTO loss_clusters VALUES (?, ?, ?)', (report.execution_id, key, json.dumps(asdict(report)))).rowcount
            cluster = self.loss_clusters.setdefault(key, [])
            if inserted:
                cluster.append(report)
            if len(cluster) < 3 or sum(trade.realized_pnl for trade in cluster) >= -50.0:
                return None
            text = f"Do not open {side.value} on {symbol} during high volatility"
            self.connection.execute('INSERT OR IGNORE INTO constraints (symbol, text) VALUES (?, ?)', (symbol, text))
        return text

    def get_negative_constraints(self, symbol):
        return [row[0] for row in self.connection.execute('SELECT text FROM constraints WHERE symbol = ? ORDER BY id', (symbol,))]

    def close(self):
        self.connection.close()

from .episodic import EpisodicTrade, EpisodicStore
from .semantic import HypothesisStatus, SemanticHypothesis, SemanticKnowledgeDAG
from .procedural import RuleType, ProceduralRule, ProceduralRuleEngine
from .learning_pipeline import LearningPipeline
from .drift_monitor import MarketDriftMonitor
from .causal_shadow import ShadowRecord, CausalShadowTracker
from .hypergraph import HyperEdge, HypergraphView
from .synaptic_sleep import SynapticSleepCycle
from .fencing import FencingToken, FencingTokenManager
