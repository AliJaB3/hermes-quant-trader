"""Track exchange-provided auto-deleveraging risk quantiles."""


class ADLWatchdog:
    def __init__(self):
        self.symbol_quantiles = {}

    def update_quantile(self, symbol, quantile):
        if isinstance(quantile, bool) or not isinstance(quantile, int) or not 1 <= quantile <= 5:
            raise ValueError('quantile must be an integer from 1 to 5')
        self.symbol_quantiles[symbol] = quantile

    def is_high_risk(self, symbol):
        return self.symbol_quantiles.get(symbol, 0) >= 4

    def should_derisk(self, symbol):
        return self.symbol_quantiles.get(symbol, 0) == 5
