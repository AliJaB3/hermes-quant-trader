"""LBank V2 request signing. Authentication fields also belong in HTTP headers."""
import base64
import hashlib
import hmac
import time
from uuid import uuid4


def _prepare(params, api_key, method):
    signed = dict(params)
    signed.pop('sign', None)
    signed.update(api_key=api_key, timestamp=int(time.time() * 1000),
                  echostr=uuid4().hex[:16], signature_method=method)
    query = '&'.join(f'{key}={signed[key]}' for key in sorted(signed))
    digest = hashlib.md5(query.encode('utf-8')).hexdigest().upper().encode('ascii')
    return signed, digest


class LBankHmacSignerV2:
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    def sign_parameters(self, params: dict) -> dict:
        signed, digest = _prepare(params, self.api_key, 'HmacSHA256')
        signed['sign'] = hmac.new(self.secret_key.encode('utf-8'), digest, hashlib.sha256).hexdigest()
        return signed


class LBankRsaSignerV2:
    def __init__(self, api_key: str, private_key_pem: str | None = None):
        self.api_key = api_key
        self.private_key_pem = private_key_pem

    def sign_contract_payload(self, payload: dict) -> dict:
        if not self.private_key_pem:
            raise ValueError('an RSA private key is required')
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa

        key = serialization.load_pem_private_key(self.private_key_pem.encode('utf-8'), password=None)
        if not isinstance(key, rsa.RSAPrivateKey):
            raise ValueError('private key must be RSA')
        signed, digest = _prepare(payload, self.api_key, 'RSA')
        signature = key.sign(digest, padding.PKCS1v15(), hashes.SHA256())
        signed['sign'] = base64.b64encode(signature).decode('ascii')
        return signed
