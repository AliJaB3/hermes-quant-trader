"""Capabilities used when constructing venue-specific orders."""
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class VenueCapabilities:
    supports_post_only: bool
    supports_reduce_only: bool
    supports_native_stop_loss: bool
    supports_countdown_cancel: bool
    settlement_type: str


class VenueCapabilityMatrix:
    def __init__(self):
        self.venues = {
            'BINANCE_FUTURES': VenueCapabilities(True, True, True, True, 'CENTRALIZED_OFFCHAIN'),
            'HYPERLIQUID': VenueCapabilities(True, True, True, True, 'L1_APPCHAIN'),
            'UNISWAP_V3': VenueCapabilities(False, False, False, False, 'ON_CHAIN_EVM'),
        }

    def get(self, venue):
        return self.venues[venue]

    def as_dict(self):
        return {name: asdict(cap) for name, cap in self.venues.items()}
