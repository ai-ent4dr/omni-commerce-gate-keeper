# Omni-Commerce Gatekeeper
**Track 01: Agentic Commerce — Autonomous AP2 Gated Settlement Engine (v6.0 Enterprise)**

Omni-Commerce Gatekeeper is an interactive, user-driven transaction engine that unifies **Verified Supplier Sourcing**, **WhatsApp Negotiation Rails**, **AP2 Cryptographic Mandates**, **Deterministic Margin Gating**, **Razorpay Settlement Rails**, and **Automated Logistics Dispatch**.

```
                           ┌────────────────────────────────────────┐
                           │      OMNI-COMMERCE GATEWAY (v6.0)      │
                           └────────────────────────────────────────┘
                                               │
             ┌─────────────────────────────────┼─────────────────────────────────┐
             ▼                                 ▼                                 ▼
   [USER DIRECTIVE]                 [INTERACTIVE OUTREACH]              [POST-PAYMENT SETTLEMENT]
   • Specify Product & Qty          • Verified Supplier Directory       • Razorpay payment.captured
   • Target Wholesale Rate (₹)      • WhatsApp Channel Negotiation      • Dynamic 5% Platform Split
   • Multi-Commodity Resolution     • Two-Way Counter Offers            • Inventory Reconciliation
             │                                 │                        • Delhivery Waybill Dispatch
             ▼                                 ▼                                 │
   [GEMINI / DETERMINISTIC PARSER]   [AP2 CART MANDATE SIGNER]                   │
             │                                 │                                 │
             ▼                                 ▼                                 ▼
   [DETERMINISTIC MARGIN GATE] ────► [HMAC-SHA256 SIGNATURE] ────► [LIVE AUDIT STREAM]
```

---

### Core Capabilities

1. **User-Driven Sourcing & Negotiation**: You specify the product (e.g., Sugar, Cardamom, Turmeric, Spice Blend), required quantity, and target rate. The agent searches verified B2B suppliers and opens an interactive negotiation workspace where you review and dispatch proposals.
2. **Deterministic Margin Floor Protection**: Mathematical safety gate guaranteeing that no offer below wholesale cost floor (e.g. ₹40.32/kg for Sugar, ₹115.00/kg for Spice Blend) can trigger payment rails.
3. **AP2 Cryptographic Cart Mandates**: Generates non-repudiable HMAC-SHA256 signatures for every agreed requirement before activating checkout rails.
4. **Post-Payment Execution & Split Settlement**: Automatically handles `payment.captured` events, reconciles inventory, splits revenue (5% platform fee vs 95% merchant payout), and generates Delhivery Express waybills.

---

### Execution & Demo Commands

```powershell
# 1. Start the Interactive Command Center
uvicorn main:app --reload

# Open http://127.0.0.1:8000/ in your browser

# 2. Run Automated Test Suite
pytest -v

# 3. Test Webhook Settlement (Simulate Payment & Waybill Dispatch)
python test_settlement.py
```
