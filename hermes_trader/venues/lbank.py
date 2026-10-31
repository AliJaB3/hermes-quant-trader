"""LBank order preparation and conservative timeout classification."""
import math
import re
from enum import Enum

from .capability import VenueCapabilityMatrix


class LBankMarketType(str, Enum):
    SPOT = 'SPOT'
    PERPETUAL = 'PERPETUAL'


class LBankVenueAdapter:
    def __init__(self, market_type: LBankMarketType = LBankMarketType.SPOT):
        self.market_type = LBankMarketType(market_type)
        self.venue_name = f'LBANK_{self.market_type.value}'
        self.capabilities = VenueCapabilityMatrix().get(self.venue_name)
        self.pending_reconciliation = set()

    def normalize_symbol(self, symbol: str) -> str:
        if not isinstance(symbol, str):
            raise ValueError('invalid symbol')
        symbol = symbol.strip().lower().replace('/', '_').replace('-', '_')
        if '_' not in symbol:
            for quote in ('usdt', 'usdc', 'btc', 'eth', 'usd'):
                if symbol.endswith(quote) and len(symbol) > len(quote):
                    symbol = symbol[:-len(quote)] + '_' + quote
                    break
        if not re.fullmatch(r'[a-z0-9]+_[a-z0-9]+', symbol):
            raise ValueError('symbol must include a recognizable quote currency')
        return symbol

    def build_order_payload(self, symbol: str, is_buy: bool, price: float, qty: float,
                            order_type: str = 'LIMIT') -> dict:
        if type(is_buy) is not bool:
            raise ValueError('is_buy must be a boolean')
        if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x > 0 for x in (price, qty)):
            raise ValueError('price and quantity must be positive and finite')
        if order_type.upper() != 'LIMIT':
            raise ValueError('only limit orders are supported')
        if self.market_type == LBankMarketType.PERPETUAL:
            raise NotImplementedError('LBank perpetual order placement requires a verified contract API schema')
        return {'symbol': self.normalize_symbol(symbol), 'type': 'buy' if is_buy else 'sell',
                'price': format(price, '.15g'), 'amount': format(qty, '.15g')}

    def handle_timeout_discrepancy(self, order_id: str, symbol: str) -> str:
        self.pending_reconciliation.add((order_id, self.normalize_symbol(symbol)))
        return 'UNKNOWN_PENDING_RECONCILIATION'

    def validate_arbitrage_exposure(self, dollar_time_integral: float, max_allowed: float = 1500.0) -> bool:
        return (math.isfinite(dollar_time_integral) and math.isfinite(max_allowed)
                and 0 <= dollar_time_integral <= max_allowed)
