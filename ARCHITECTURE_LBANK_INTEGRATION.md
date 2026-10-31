# LBank Integration Specification (Decision 93406787)
## Technical Architecture for Codex Autonomous Implementation

### Objective
Implement the LBank Exchange integration across Phase 0 and Phase 1 approved in Council Decision `93406787`:
1. `lbank_auth.py`: HMAC-SHA256 and RSA-SHA256 signers with parameter normalization.
2. `lbank.py`: `LBankVenueAdapter` for spot and perpetual markets with pessimistic timeout handling.
3. `capability.py`: Register `LBANK_SPOT` and `LBANK_PERPETUAL` in `VenueCapabilityMatrix`.

---

### 1. New & Enhanced Modules in `hermes_trader/venues/`:

#### A. `hermes_trader/venues/lbank_auth.py`:
- `LBankHmacSignerV2`:
  - `api_key: str`, `secret_key: str`
  - `sign_parameters(params: dict) -> dict`:
    - Injects `api_key`, `timestamp = int(time.time() * 1000)`, `echostr = uuid4().hex[:16]`.
    - Sorts parameters alphabetically by key.
    - Builds query string `key1=val1&key2=val2...`.
    - Generates uppercase MD5 hash of secret, then calculates HMAC-SHA256 hex digest (or direct HMAC-SHA256).
    - Returns updated dictionary containing `sign` and `signature_method='HmacSHA256'`.
- `LBankRsaSignerV2`:
  - `api_key: str`, `private_key_pem: str | None = None`
  - `sign_contract_payload(payload: dict) -> dict`:
    - Formats timestamp and payload hash.

#### B. `hermes_trader/venues/lbank.py`:
- `LBankMarketType`: Enum (`SPOT`, `PERPETUAL`).
- `LBankVenueAdapter`:
  - `market_type: LBankMarketType`
  - `normalize_symbol(symbol: str) -> str`:
    - For SPOT: converts `BTCUSDT` -> `btc_usdt`, `ETHUSDT` -> `eth_usdt`.
    - For PERPETUAL: converts `BTCUSDT` -> `btc_usdt`.
  - `build_order_payload(symbol: str, is_buy: bool, price: float, qty: float, order_type: str = 'LIMIT') -> dict`:
    - Formats LBank REST v2 wire payload.
  - `handle_timeout_discrepancy(order_id: str, symbol: str) -> str`:
    - Returns `'UNKNOWN_PENDING_RECONCILIATION'`, marking capacity as reserved until explicit REST query verifies outcome.
  - `validate_arbitrage_exposure(dollar_time_integral: float, max_allowed: float = 1500.0) -> bool`:
    - Returns False if unhedged exposure * duration exceeds $1500 \$ \cdot s$.

#### C. In `hermes_trader/venues/capability.py`:
- Add `LBANK_SPOT`:
  - `supports_post_only = True`
  - `supports_reduce_only = False`
  - `supports_native_stop_loss = True`
  - `supports_countdown_cancel = False`
  - `settlement_type = "CENTRALIZED_OFFCHAIN"`
- Add `LBANK_PERPETUAL`:
  - `supports_post_only = True`
  - `supports_reduce_only = True`
  - `supports_native_stop_loss = True`
  - `supports_countdown_cancel = False`
  - `settlement_type = "CENTRALIZED_OFFCHAIN"`

---

### 2. Tests in `tests/test_lbank_integration.py`:
- Test `LBankHmacSignerV2` parameter sorting and signature generation.
- Test `LBankVenueAdapter.normalize_symbol` correctly transforms symbols.
- Test `build_order_payload` constructs valid spot and perp wire payloads.
- Test `handle_timeout_discrepancy` yields `UNKNOWN_PENDING_RECONCILIATION`.
- Test `VenueCapabilityMatrix` includes `LBANK_SPOT` and `LBANK_PERPETUAL`.
- Run `/root/kaggle-llm-orchestrator/.venv/bin/pytest tests/` to confirm 100% pass rate.
