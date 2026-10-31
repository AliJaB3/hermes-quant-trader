# 📈 Hermes Quant Trader

[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)]()
[![License](https://img.shields.io/badge/license-MIT-purple.svg)]()

**Hermes Quant Trader** is an autonomous cryptocurrency trading engine engineered with the **Proposer-Guardian-Executor** architecture. It decouples high-level alpha strategy discovery from risk controls and execution, guaranteeing zero-mock execution and capital protection.

---

## 🏛️ The 3-Plane Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ 1. PROPOSER PLANE (Hermes Agent / Strategy Discovery)       │
│    • Hypothesizes trades from orderbook & liquidation data  │
│    • Formulates structured OrderProposal payloads           │
│    • ZERO execution privileges (Proposer only)              │
└──────────────────────────────┬──────────────────────────────┘
                               │ OrderProposal
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. GUARDIAN & RISK ENGINE (Independent Daemon)              │
│    • Validates 99% CVaR & Drawdown Velocity (max 1.5%/hr)   │
│    • Enforces leverage caps & negative constraints          │
│    • Evaluates Kill-Switch triggers (Halt on emergency)     │
└──────────────────────────────┬──────────────────────────────┘
                               │ Approved Orders
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. PAPER ENGINE & EVOMEM LEARNER                            │
│    • Zero-mock execution with realistic slippage & fees     │
│    • Tracks portfolio equity, margin & real-time PnL        │
│    • Journaling & negative constraints extraction (EvoMem)  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Installation & Quick Start

```bash
git clone https://github.com/AliJaB3/hermes-quant-trader.git
cd hermes-quant-trader
pip install -e .
```

### CLI Commands:

```bash
# Check portfolio & guardian status
hermes-trader status

# Propose a paper trade
hermes-trader propose --symbol BTCUSDT --side BUY --qty 0.1 --price 65000

# Emergency stop (cancels active orders and halts engine)
hermes-trader emergency-stop

# Scaffold an isolated trader profile
hermes-trader scaffold --path ~/.hermes/profiles/trader --bot-token "YOUR_TELEGRAM_BOT_TOKEN"
```

---

## 🧪 Testing

```bash
pytest -v tests/
```

Complete test suite covering contracts, risk limits, paper execution with slippage/fees, negative constraints, and telegram commands.
