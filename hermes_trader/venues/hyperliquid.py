"""Build unsigned Hyperliquid order actions using supplied asset metadata."""
import math
from .capability import VenueCapabilityMatrix


class HyperliquidVenueAdapter:
    venue_name = 'HYPERLIQUID'

    def __init__(self, asset_ids=None):
        # Asset indices are exchange metadata and must be supplied by the caller.
        self.asset_ids = dict(asset_ids or {})
        self.capabilities = VenueCapabilityMatrix().get(self.venue_name)

    def build_order_payload(self, symbol: str, is_buy: bool, limit_px: float, sz: float,
                            reduce_only: bool = False, post_only: bool = False) -> dict:
        if symbol not in self.asset_ids:
            raise ValueError('unknown asset: supply its exchange asset index')
        asset = self.asset_ids[symbol]
        if type(asset) is not int or asset < 0 or type(is_buy) is not bool or type(reduce_only) is not bool or type(post_only) is not bool:
            raise ValueError('invalid order flags or asset index')
        if not all(math.isfinite(x) and x > 0 for x in (limit_px, sz)):
            raise ValueError('price and size must be positive and finite')
        if (post_only and not self.capabilities.supports_post_only) or (reduce_only and not self.capabilities.supports_reduce_only):
            raise ValueError('unsupported order capability')
        order = {'a': asset, 'b': is_buy, 'p': format(limit_px, '.15g'), 's': format(sz, '.15g'),
                 'r': reduce_only, 't': {'limit': {'tif': 'Alo' if post_only else 'Gtc'}}}
        return {'type': 'order', 'orders': [order], 'grouping': 'na'}
