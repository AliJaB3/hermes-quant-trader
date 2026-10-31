"""Decay and prune ordinary edges while preserving rare-event structures."""


class SynapticSleepCycle:
    def prune_hypergraph(self, hypergraph, min_weight=0.1):
        with hypergraph.connection:
            hypergraph.decay_edges()
            return hypergraph.connection.execute('DELETE FROM hyperedges WHERE is_immune=0 AND weight < ?', (min_weight,)).rowcount
