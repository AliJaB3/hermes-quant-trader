"""Square-root market impact approximation."""
import math


class DepthSlippageModel:
    def __init__(self, base_slippage=0.0001, impact_factor=0.0005, default_depth_usd=100_000.0):
        if not all(math.isfinite(x) and x >= 0 for x in (base_slippage, impact_factor)) or base_slippage > 0.05 or not math.isfinite(default_depth_usd) or default_depth_usd <= 0:
            raise ValueError('invalid slippage parameters')
        self.base_slippage = base_slippage
        self.impact_factor = impact_factor
        self.default_depth_usd = default_depth_usd

    def compute_slippage(self, order_size_usd, book_depth_usd=None):
        if not math.isfinite(order_size_usd) or order_size_usd < 0 or (book_depth_usd is not None and (not math.isfinite(book_depth_usd) or book_depth_usd < 0)):
            raise ValueError('invalid order size or book depth')
        depth = max(1000.0, book_depth_usd or self.default_depth_usd)
        return min(0.05, max(self.base_slippage, self.base_slippage + self.impact_factor * math.sqrt(order_size_usd / depth)))
