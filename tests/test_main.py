import asyncio
import pytest
from fastapi.testclient import TestClient
import main

client = TestClient(main.app)

def test_app_and_ui_route_load():
    assert hasattr(main, "app")
    assert callable(main.serve_ui)
    html = asyncio.run(main.serve_ui())
    assert isinstance(html, str)
    assert "Omni-Commerce Gatekeeper" in html
    assert "Find Verified Sellers" in html
    assert "Specify Your Procurement Requirement" in html

def test_supplier_search():
    # Search for sugar
    res_sugar = client.get("/api/suppliers/search?q=sugar")
    assert res_sugar.status_code == 200
    data_sugar = res_sugar.json()
    assert len(data_sugar["results"]) > 0
    assert any("Sugar" in s["name"] or "sugar" in str(s["categories"]).lower() for s in data_sugar["results"])

    # Search for spice
    res_spice = client.get("/api/suppliers/search?q=spice")
    assert res_spice.status_code == 200
    data_spice = res_spice.json()
    assert len(data_spice["results"]) > 0

def test_margin_gate_approval():
    # 200kg of Sugar at ₹42/kg (Cost: ₹36, min margin 1.12 -> floor ₹40.32/kg) -> Should PASS
    payload = {
        "user_message": "Requirement for 200kg of Refined Cane Sugar at ₹42/kg",
        "product": "Refined Cane Sugar",
        "quantity": 200,
        "target_rate": 42.0
    }
    res = client.post("/api/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "APPROVED"
    assert "ap2_signature" in data
    assert data["payment_link_url"] is not None
    assert data["amount_inr"] == 8400.0

def test_margin_gate_rejection():
    # 200kg of Sugar at ₹25/kg (Below wholesale floor of ₹40.32/kg) -> Should BLOCK
    payload = {
        "user_message": "Requirement for 200kg of Refined Cane Sugar at ₹25/kg",
        "product": "Refined Cane Sugar",
        "quantity": 200,
        "target_rate": 25.0
    }
    res = client.post("/api/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "BLOCKED"
    assert data["floor_price"] > 25.0
    assert "Margin Violation" in data["reply"] or "breaches" in data["reply"]

def test_razorpay_settlement_webhook_success():
    payload = {
        "event": "payment.captured",
        "entity": {
            "amount": 840000, # ₹8,400.00
            "notes": {
                "order_id": "ORD-TEST-SUCCESS-1",
                "sku_id": "SKU_REFINED_SUGAR",
                "quantity_kg": "200"
            }
        }
    }
    res = client.post("/webhook/razorpay", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ["PAYMENT_SUCCESSFUL", "SETTLED_AND_DISPATCHED"]
    assert "DLV-" in data["waybill_id"]
    assert data["platform_commission_inr"] == 420.0 # 5% of 8400
    assert data["merchant_payout_inr"] == 7980.0   # 95% of 8400

def test_razorpay_settlement_webhook_failure():
    payload = {
        "event": "payment.failed",
        "entity": {
            "amount": 840000,
            "error_code": "BAD_REQUEST_ERROR",
            "error_description": "Card authorization failed: Insufficient funds",
            "notes": {
                "order_id": "ORD-TEST-FAIL-1",
                "sku_id": "SKU_REFINED_SUGAR",
                "quantity_kg": "200"
            }
        }
    }
    res = client.post("/webhook/razorpay", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "PAYMENT_FAILED"
    assert "Insufficient funds" in data["failure_reason"]
    assert data["order_id"] == "ORD-TEST-FAIL-1"

def test_order_status_tracking():
    # 1. Create order through negotiation
    chat_payload = {
        "user_message": "Need 100kg of Refined Cane Sugar at ₹42/kg",
        "product": "Refined Cane Sugar",
        "quantity": 100,
        "target_rate": 42.0
    }
    chat_res = client.post("/api/chat", json=chat_payload)
    assert chat_res.status_code == 200
    order_id = chat_res.json()["order_id"]

    # 2. Check initial order status
    status_res = client.get(f"/api/order/{order_id}")
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "AWAITING_PAYMENT"

    # 3. Simulate failure
    fail_payload = {
        "event": "payment.failed",
        "entity": {
            "amount": 420000,
            "error_description": "Customer 3DS Authentication Timeout",
            "notes": {"order_id": order_id}
        }
    }
    client.post("/webhook/razorpay", json=fail_payload)
    fail_check = client.get(f"/api/order/{order_id}").json()
    assert fail_check["status"] == "PAYMENT_FAILED"
    assert "Timeout" in fail_check["failure_reason"]

    # 4. Simulate retry / success
    success_payload = {
        "event": "payment.captured",
        "entity": {
            "amount": 420000,
            "notes": {"order_id": order_id, "sku_id": "SKU_REFINED_SUGAR", "quantity_kg": "100"}
        }
    }
    client.post("/webhook/razorpay", json=success_payload)
    success_check = client.get(f"/api/order/{order_id}").json()
    assert success_check["status"] == "PAYMENT_SUCCESSFUL"
    assert "DLV-" in success_check["waybill"]

