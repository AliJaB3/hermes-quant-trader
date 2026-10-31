from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
import json
import sqlite3
from uuid import uuid4


class HypothesisStatus(str, Enum):
    DRAFT = 'DRAFT'
    CANDIDATE = 'CANDIDATE'
    VALIDATED = 'VALIDATED'
    SHADOW = 'SHADOW'
    ACTIVE = 'ACTIVE'
    STALE = 'STALE'


def now():
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SemanticHypothesis:
    hypothesis_id: str
    title: str
    domain: str
    premise: str
    falsification_condition: str
    sample_size: int = 0
    p_value: float = 1.0
    status: HypothesisStatus = HypothesisStatus.DRAFT
    created_at: str = ''
    updated_at: str = ''


class SemanticKnowledgeDAG:
    def __init__(self, path=':memory:'):
        self.connection = sqlite3.connect(path)
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.execute('CREATE TABLE IF NOT EXISTS semantic_hypotheses (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
        self.connection.commit()

    def _save(self, hypothesis):
        with self.connection:
            self.connection.execute('INSERT OR REPLACE INTO semantic_hypotheses VALUES (?, ?)', (hypothesis.hypothesis_id, json.dumps(asdict(hypothesis))))

    def create_hypothesis(self, title, premise, falsification_condition, domain='FINANCE'):
        timestamp = now()
        h = SemanticHypothesis(str(uuid4()), title, domain, premise, falsification_condition, created_at=timestamp, updated_at=timestamp)
        self._save(h)
        return h

    def get_hypotheses(self):
        result = []
        for (data,) in self.connection.execute('SELECT data FROM semantic_hypotheses ORDER BY rowid'):
            fields = json.loads(data)
            fields['status'] = HypothesisStatus(fields['status'])
            result.append(SemanticHypothesis(**fields))
        return result

    def get_hypothesis(self, hypothesis_id):
        return next ( (h for h in self.get_hypotheses() if h.hypothesis_id == hypothesis_id), None)

    def update_status(self, hypothesis_id, new_status, metrics=None):
        h = self.get_hypothesis(hypothesis_id)
        if h is None:
            return False
        new_status = HypothesisStatus(new_status)
        transitions = {HypothesisStatus.DRAFT: HypothesisStatus.CANDIDATE, HypothesisStatus.CANDIDATE: HypothesisStatus.VALIDATED, HypothesisStatus.VALIDATED: HypothesisStatus.SHADOW, HypothesisStatus.SHADOW: HypothesisStatus.ACTIVE, HypothesisStatus.ACTIVE: HypothesisStatus.STALE}
        if new_status != transitions.get(h.status) and not (new_status == HypothesisStatus.STALE and h.status != HypothesisStatus.STALE):
            return False
        for key, value in (metrics or {}).items():
            if key not in ('sample_size', 'p_value'):
                raise ValueError('Unsupported hypothesis metric')
            setattr(h, key, value)
        h.status = new_status
        h.updated_at = now()
        self._save(h)
        return True

    def get_active_hypotheses(self):
        return [h for h in self.get_hypotheses() if h.status == HypothesisStatus.ACTIVE]

    def close(self):
        self.connection.close()
