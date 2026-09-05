import json
import requests
import uuid
import sys

import os

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Default to localhost, or allow target URL via CLI arg or env var
DEFAULT_HOST = os.getenv("API_HOST", "http://127.0.0.1:8000")
if len(sys.argv) > 1:
    target_arg = sys.argv[1].rstrip("/")
    if target_arg.endswith("/webhook/razorpay"):
        API_URL = target_arg
    else:
        API_URL = f"{target_arg}/webhook/razorpay"
else:
    API_URL = f"{DEFAULT_HOST.rstrip('/')}/webhook/razorpay"

settlement_payload = {
    "event": "payment.captured",
    "payload": {
        "payment": {
            "entity": {
                "id": "pay_" + uuid.uuid4().hex[:10],
                "amount": 1950000, # ₹19,500.00
                "status": "captured",
                "notes": {
                    "order_id": "ORD-LIVE-" + uuid.uuid4().hex[:6].upper(),
                    "sku_id": "SKU_SPICE_PREMIUM",
                    "quantity_kg": "150"
                }
            }
        }
    }
}

def run_settlement_test():
    print("=" * 70)
    print("💳 DISPATCHING RAZORPAY POST-PAYMENT SETTLEMENT WEBHOOK...")
    print(f"Target URL: {API_URL}")
    print("=" * 70)

    try:
        res = requests.post(API_URL, json=settlement_payload, timeout=10)
        response = res.json()
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Connection Error: Could not reach {API_URL}")
        print("💡 Make sure your server is running (e.g. uvicorn main:app --reload) or pass your live Render URL:")
        print("   python test_settlement.py https://omni-commerce-gatekeeper.onrender.com\n")
        return
    except Exception as e:
        print(f"\n❌ Request failed: {e}\n")
        return

    print("\n--- SYSTEM SETTLEMENT LOGS ---")
    for log in response.get("logs", []):
        print(f"  {log}")

    print("\n" + "=" * 70)
    print(f"✅ ORDER RECONCILED & DISPATCHED")
    print(f"Order ID: {response.get('order_id')}")
    print(f"Waybill ID: {response.get('waybill_id')}")
    print(f"Remaining Inventory Stock: {response.get('remaining_stock_kg')} kg")
    print(f"Platform 5% Commission: ₹{response.get('platform_commission_inr'):,.2f}")
    print(f"Merchant 95% Payout: ₹{response.get('merchant_payout_inr'):,.2f}")
    print("=" * 70)

if __name__ == "__main__":
    run_settlement_test()
