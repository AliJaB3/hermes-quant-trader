"""Resolve timed-out orders using exchange evidence."""


class ReconciliationResolver:
    def resolve_timeout(self, intent, exchange_orders: list[dict], remote_positions: dict) -> tuple[str, dict]:
        for order in exchange_orders:
            if any(order.get(key) == intent.intent_id for key in ('client_order_id', 'clientOrderId', 'client_order_id_str', 'intent_id', 'cloid')):
                status = str(order.get('status', '')).upper()
                if status == 'FILLED':
                    return 'FILLED', order
                if status in ('CANCELED', 'CANCELLED', 'REJECTED'):
                    return 'FAILED', order
                # An open or unknown order must never be retried blindly.
                return 'PENDING', order
        # A delta must be measured against a known baseline, not an absolute position.
        position = remote_positions.get(intent.symbol, remote_positions)
        if isinstance(position, dict):
            delta = position.get('delta', position.get('position_delta'))
            if delta is None and 'size' in position and 'previous_size' in position:
                delta = float(position['size']) - float(position['previous_size'])
            if delta is not None and float(delta) * (1 if str(intent.side).upper() == 'BUY' else -1) > 0:
                return 'FILLED_UNTRAKED', remote_positions
        return 'NOT_FOUND_SAFE_TO_RETRY', {}
