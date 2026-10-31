"""Orderly shutdown that leaves protective orders intact."""
from enum import Enum, auto


class ShutdownState(Enum):
    RUNNING = auto()
    QUIESCING = auto()
    CANCEL_ENTRY_ONLY = auto()
    PERSISTED = auto()
    STOPPED = auto()


class GracefulShutdownManager:
    def __init__(self):
        self.state = ShutdownState.RUNNING

    def initiate_shutdown(self, paper_engine, cancel_entry_orders_fn=None):
        # Synchronize with executions already in progress before refusing new ones.
        with paper_engine.guardian.execution_lock:
            if self.state is not ShutdownState.RUNNING:
                raise RuntimeError('shutdown already initiated')
            self.state = ShutdownState.QUIESCING
            paper_engine._quiescing = True
        self.state = ShutdownState.CANCEL_ENTRY_ONLY
        if cancel_entry_orders_fn is not None:
            cancel_entry_orders_fn()
        paper_engine._save()
        if not paper_engine.store.checkpoint_wal():
            raise RuntimeError('portfolio WAL checkpoint was blocked')
        self.state = ShutdownState.PERSISTED
        self.state = ShutdownState.STOPPED
