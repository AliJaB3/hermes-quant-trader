"""Compare local positions against the exchange or paper ledger."""
from dataclasses import dataclass
import math


@dataclass
class ReconciliationDiscrepancy:
    symbol: str
    discrepancy_type: str
    details: str


class StateReconciler:
    def reconcile(self, local_positions: dict, remote_positions: dict) -> list[ReconciliationDiscrepancy]:
        discrepancies = []
        for symbol in sorted(local_positions.keys() | remote_positions.keys()):
            if symbol not in local_positions:
                discrepancies.append(ReconciliationDiscrepancy(symbol, 'ORPHAN_REMOTE', 'Position exists only remotely'))
            elif symbol not in remote_positions:
                discrepancies.append(ReconciliationDiscrepancy(symbol, 'GHOST_LOCAL', 'Position exists only locally'))
            else:
                local, remote = local_positions[symbol], remote_positions[symbol]
                def field(position, name):
                    return position.get(name) if isinstance(position, dict) else getattr(position, name)
                local_size, remote_size = float(field(local, 'size')), float(field(remote, 'size'))
                local_side, remote_side = field(local, 'side'), field(remote, 'side')
                if (not math.isfinite(local_size) or not math.isfinite(remote_size)
                        or not math.isclose(local_size, remote_size, rel_tol=1e-9, abs_tol=1e-12)
                        or local_side != remote_side):
                    discrepancies.append(ReconciliationDiscrepancy(
                        symbol, 'SIZE_MISMATCH',
                        f'Local: {local_side} {local_size}; remote: {remote_side} {remote_size}'))
        return discrepancies
