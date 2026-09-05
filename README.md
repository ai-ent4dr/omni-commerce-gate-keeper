# Omni-Commerce Gatekeeper
**Autonomous B2B Sourcing, Negotiation & Zero-Trust Settlement Engine**

[![Enterprise Ready](https://img.shields.io/badge/Enterprise-v6.0-emerald.svg)](https://github.com/ai-ent4dr/omni-commerce-gate-keeper)
[![Protocol AP2](https://img.shields.io/badge/Protocol-AP2%20Cryptographic-purple.svg)](https://github.com/ai-ent4dr/omni-commerce-gate-keeper)
[![Settlement Rails](https://img.shields.io/badge/Settlement-Razorpay%20Route-blue.svg)](https://razorpay.com)
[![Logistics Dispatch](https://img.shields.io/badge/Logistics-Delhivery%20Express-cyan.svg)](https://delhivery.com)
[![Tests Passing](https://img.shields.io/badge/Tests-7%2F7%20Passing-brightgreen.svg)](tests/)

Omni-Commerce Gatekeeper is an agentic commerce gateway designed for wholesale B2B procurement. It strictly **decouples non-deterministic AI negotiation from financial execution**. While Gemini LLM handles semantic negotiation in natural language across WhatsApp and Web channels, financial settlement is protected by a **Zero-Trust Deterministic Margin Gate**, an **AP2 HMAC-SHA256 Cryptographic Cart Mandate**, and **dynamic Razorpay payment rails**.

---

## Architecture Overview

```
                               ┌────────────────────────────────────────┐
                               │      OMNI-COMMERCE GATEKEEPER          │
                               └────────────────────────────────────────┘
                                                    │
                 ┌──────────────────────────────────┼──────────────────────────────────┐
                 ▼                                  ▼                                  ▼
      [1. USER DIRECTIVE]                 [2. MULTI-CHANNEL NEGOTIATION]      [3. ZERO-TRUST GATEWAY]
      • Commodity & Volume (kg)           • Verified Supplier Sourcing        • Deterministic Margin Floor
      • Target Wholesale Rate (₹)         • Two-Way WhatsApp Outreach         • AP2 HMAC-SHA256 Cart Mandate
      • Multi-Commodity Resolution        • Intent Parsing (Gemini + Local)   • Dynamic Razorpay Payment Link
                 │                                  │                                  │
                 └──────────────────────────────────┼──────────────────────────────────┘
                                                    │
                                                    ▼
                                     [4. FINANCIAL SETTLEMENT & DISPATCH]
                                     • payment.captured Webhook Event
                                     • 95% Merchant Warehouse Payout
                                     • 5% Platform Commission Cut
                                     • Real-Time Stock Reconciliation
                                     • Delhivery Logistics Waybill
```

---

## Key Features

1. **User-Driven Procurement**:
   - Buyers enter requirements (product, quantity, target rate).
   - Dynamically resolves verified suppliers across commodities (Refined Cane Sugar, Premium Spice Blend, Cardamom, Turmeric, Black Pepper, etc.).

2. **Decoupled Negotiation & Deterministic Margin Floor**:
   - Large Language Models can hallucinate pricing. The gatekeeper enforces strict mathematical margin floors:
     $$\text{Floor Price} = \text{Cost Price} \times \text{Min Margin Multiplier}$$
   - Offers below the floor are automatically blocked with clear counter-offer explanations. Payment rails are never generated for unprofitable offers.

3. **AP2 Cryptographic Cart Mandates**:
   - Every approved transaction is cryptographically signed using an HMAC-SHA256 hash across SKU, quantity, negotiated unit rate, and timestamp.
   - Guarantees transaction non-repudiation and prevents parameter tampering.

4. **Dynamic Razorpay Payment Rails & In-App Portal**:
   - Creates verified Razorpay payment links generated dynamically with the exact negotiated order value.
   - Built-in secure fallback checkout portal (`/checkout/{order_id}`) prevents static price distortions.

5. **Post-Payment Split Settlement & Logistics**:
   - Listens to Razorpay payment webhooks (`payment.captured` & `payment.failed`).
   - Automatically executes a **95% Merchant Payout** vs. **5% Platform Cut**.
   - Reconciles warehouse inventory and generates automated Delhivery Express shipping waybills.

---

## Project Structure

```
omni-commerce-agent/
├── main.py                  # Core application: FastAPI backend, margin engine & embedded UI
├── test_settlement.py       # CLI settlement test script (Razorpay post-payment simulation)
├── requirements.txt         # Production dependencies
├── render.yaml              # Render cloud deployment specification
├── .env.example             # Template for API credentials and secrets
├── .gitignore               # Excludes secrets, venv, and cache files
└── tests/
    └── test_main.py         # Pytest test suite covering sourcing, margin gating & webhooks
```

---

## API Reference

### 1. Procurement & Sourcing
- `GET /` — Interactive Command Center UI.
- `GET /api/suppliers/search?q={query}` — Searches directory of verified B2B suppliers.
- `GET /api/state` — Live metrics (settled revenue, platform commission cut, logs, order registry).

### 2. Negotiation & Order Creation
- `POST /api/chat` — Evaluates buyer proposals, validates margin floors, signs AP2 mandates, and generates payment links.
  ```json
  {
    "user_message": "Need 200kg of Refined Cane Sugar at ₹42/kg",
    "product": "Refined Cane Sugar",
    "quantity": 200,
    "target_rate": 42.0
  }
  ```
- `GET /api/order/{order_id}` — Retrieves live status, AP2 signature, and dispatch waybill.
- `GET /checkout/{order_id}` — Secure in-app checkout portal for order settlement.

### 3. Settlement Rails
- `POST /webhook/razorpay` — Inbound payment webhook handler (`payment.captured` / `payment.failed`).
- `POST /webhook/whatsapp` — Twilio WhatsApp webhook for inbound buyer text messages.

---

## Getting Started

### 1. Prerequisites
- Python 3.11+
- Git

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/ai-ent4dr/omni-commerce-gate-keeper.git
cd omni-commerce-gate-keeper

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate    # Windows
source venv/bin/activate  # macOS / Linux

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Variables
Copy `.env.example` to `.env` and fill in your API credentials:
```bash
cp .env.example .env
```
Key variables:
- `RAZORPAY_KEY_ID` & `RAZORPAY_KEY_SECRET` — Razorpay API credentials.
- `GEMINI_API_KEY` — Google Gemini API key for semantic intent extraction.
- `TWILIO_ACCOUNT_SID`, `TWILIO_API_KEY`, `TWILIO_API_SECRET` — Twilio WhatsApp outreach (optional in simulator mode).

### 4. Running Locally
```bash
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```
Open your browser at: `http://127.0.0.1:8000`

---

## Verification & Testing

### Automated Unit Tests
Run the test suite covering sourcing, margin validation, payment webhooks, and status polling:
```bash
pytest -v
```

### CLI Post-Payment Settlement Test
Simulate a live Razorpay settlement webhook:
```bash
python test_settlement.py
```
Outputs:
- Full Gross Settled Amount
- Platform 5% Commission Cut
- Merchant 95% Warehouse Payout
- Delhivery Logistics Tracking Waybill
- Real-Time Warehouse Inventory Reconciliation
