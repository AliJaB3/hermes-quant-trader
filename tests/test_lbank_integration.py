import hashlib
import hmac
from types import SimpleNamespace

import pytest

from hermes_trader.venues import (LBankHmacSignerV2, LBankMarketType,
                                  LBankRsaSignerV2, LBankVenueAdapter,
                                  VenueCapabilityMatrix)


def test_hmac_signs_sorted_parameters_without_mutation(monkeypatch):
    monkeypatch.setattr('hermes_trader.venues.lbank_auth.time.time', lambda: 1234.5)
    monkeypatch.setattr('hermes_trader.venues.lbank_auth.uuid4', lambda: SimpleNamespace(hex='0123456789abcdef0123456789abcdef'))
    original = {'symbol': 'btc_usdt', 'amount': '1', 'sign': 'old'}
    result = LBankHmacSignerV2('key', 'secret').sign_parameters(original)
    query = 'amount=1&api_key=key&echostr=0123456789abcdef&signature_method=HmacSHA256&symbol=btc_usdt&timestamp=1234500'
    digest = hashlib.md5(query.encode()).hexdigest().upper()
    assert result['sign'] == hmac.new(b'secret', digest.encode(), hashlib.sha256).hexdigest()
    assert original['sign'] == 'old'


def test_rsa_requires_key():
    with pytest.raises(ValueError):
        LBankRsaSignerV2('key').sign_contract_payload({})


def test_rsa_signature(monkeypatch):
    crypto = pytest.importorskip('cryptography.hazmat.primitives.asymmetric.rsa')
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    import base64
    key = crypto.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    monkeypatch.setattr('hermes_trader.venues.lbank_auth.time.time', lambda: 1)
    monkeypatch.setattr('hermes_trader.venues.lbank_auth.uuid4', lambda: SimpleNamespace(hex='a' * 32))
    signed = LBankRsaSignerV2('key', pem).sign_contract_payload({'asset': 'USDT'})
    query = 'api_key=key&asset=USDT&echostr=aaaaaaaaaaaaaaaa&signature_method=RSA&timestamp=1000'
    digest = hashlib.md5(query.encode()).hexdigest().upper().encode()
    key.public_key().verify(base64.b64decode(signed['sign']), digest, padding.PKCS1v15(), hashes.SHA256())


@pytest.mark.parametrize('market', list(LBankMarketType))
def test_normalization_and_timeout(market):
    adapter = LBankVenueAdapter(market)
    assert adapter.normalize_symbol('BTCUSDT') == 'btc_usdt'
    assert adapter.normalize_symbol('ETH/USDT') == 'eth_usdt'
    assert adapter.handle_timeout_discrepancy('123', 'BTCUSDT') == 'UNKNOWN_PENDING_RECONCILIATION'
    assert ('123', 'btc_usdt') in adapter.pending_reconciliation
    assert adapter.validate_arbitrage_exposure(1500)
    assert not adapter.validate_arbitrage_exposure(1500.1)
    assert not adapter.validate_arbitrage_exposure(float('nan'))


def test_orders():
    adapter = LBankVenueAdapter()
    assert adapter.build_order_payload('BTCUSDT', True, 100, .1) == {
        'symbol': 'btc_usdt', 'type': 'buy', 'price': '100', 'amount': '0.1'}
    assert adapter.build_order_payload('BTCUSDT', False, 100, 1)['type'] == 'sell'
    with pytest.raises(ValueError):
        adapter.build_order_payload('BTCUSDT', True, -1, 1)
    with pytest.raises(NotImplementedError):
        LBankVenueAdapter(LBankMarketType.PERPETUAL).build_order_payload('BTCUSDT', True, 100, 1)


def test_capabilities():
    matrix = VenueCapabilityMatrix()
    spot = matrix.get('LBANK_SPOT')
    perp = matrix.get('LBANK_PERPETUAL')
    assert (spot.supports_post_only, spot.supports_reduce_only, spot.supports_native_stop_loss,
            spot.supports_countdown_cancel, spot.settlement_type) == (True, False, True, False, 'CENTRALIZED_OFFCHAIN')
    assert (perp.supports_post_only, perp.supports_reduce_only, perp.supports_native_stop_loss,
            perp.supports_countdown_cancel, perp.settlement_type) == (True, True, True, False, 'CENTRALIZED_OFFCHAIN')
