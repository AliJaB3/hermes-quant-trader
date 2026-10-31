"""Strictly reduce external market data to structured numeric fields."""
import math
import re


class MarketDataQuarantine:
    _symbol = re.compile(r'[A-Z0-9]{2,12}', re.ASCII)
    _delimiters = re.compile(
        r'<\|im_start\|>|<\|im_end\|>|\[SYSTEM\]|system\s*:|ignore\s+previous\s+instructions',
        re.IGNORECASE,
    )

    def validate_symbol(self, symbol: str) -> str:
        if not isinstance(symbol, str) or self._symbol.fullmatch(symbol) is None:
            raise ValueError('invalid market symbol')
        return symbol

    def sanitize_text(self, text: str) -> str:
        text = ''.join(char for char in text if char.isprintable())
        # Repeat so removing one delimiter cannot expose another.
        while True:
            cleaned = self._delimiters.sub('', text)
            if cleaned == text:
                return cleaned
            text = cleaned

    def sanitize_market_input(self, data: dict) -> dict:
        result = {'symbol': self.validate_symbol(data['symbol'])}
        for key, value in data.items():
            if key == 'symbol' or isinstance(value, bool):
                continue
            if not isinstance(key, str) or re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', key, re.ASCII) is None:
                continue
            try:
                number = float(value)
            except (TypeError, ValueError, OverflowError):
                continue
            if math.isfinite(number):
                result[key] = number
        return result
