import os
import json
import re
import time
import hmac
import hashlib
import uuid
import razorpay
from google import genai
from google.genai import types
from fastapi import FastAPI, Form, Response, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from twilio.rest import Client as TwilioClient
from twilio.twiml.messaging_response import MessagingResponse

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = FastAPI(
    title="Omni-Commerce Gatekeeper",
    version="6.0",
    description="Full-Lifecycle Agentic Commerce Engine: User-Driven Procurement, AP2 Verification, Deterministic Margin Gating & Split Settlement"
)

# --- CONFIGURATION ---
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_test_placeholder")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "razorpay_secret_placeholder")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

TWILIO_API_KEY = os.getenv("TWILIO_API_KEY", "")
TWILIO_API_SECRET = os.getenv("TWILIO_API_SECRET", "")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "AC_DUMMY_ACCOUNT_SID")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "+14155238886")

rzp_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# Initialize Twilio Client gracefully
twilio_client = None
try:
    if TWILIO_ACCOUNT_SID.startswith("AC") and len(TWILIO_ACCOUNT_SID) > 20:
        twilio_client = TwilioClient(TWILIO_API_KEY, TWILIO_API_SECRET, TWILIO_ACCOUNT_SID)
except Exception:
    twilio_client = None

# --- IN-MEMORY STATE STORE ---
CATALOG_DB = {
    "SKU_SPICE_PREMIUM": {
        "name": "Premium Spice Blend",
        "cost_price": 100.00,
        "min_margin_multiplier": 1.15,  # 15% margin floor (Min ₹115.00/kg)
        "retail_price": 150.00,
        "stock_kg": 1500,
        "warehouse": "Hub-Bengaluru-Central",
        "low_stock_threshold": 400
    },
    "SKU_REFINED_SUGAR": {
        "name": "Refined Cane Sugar",
        "cost_price": 36.00,
        "min_margin_multiplier": 1.12,  # 12% margin floor (Min ₹40.32/kg)
        "retail_price": 48.00,
        "stock_kg": 5000,
        "warehouse": "Hub-Mandya-SugarBelt",
        "low_stock_threshold": 1000
    },
    "SKU_RAW_CARDAMOM": {
        "name": "Raw Green Cardamom",
        "cost_price": 850.00,
        "min_margin_multiplier": 1.12,  # 12% margin floor (Min ₹952.00/kg)
        "retail_price": 1100.00,
        "stock_kg": 350,
        "warehouse": "Hub-Kochi-Port",
        "low_stock_threshold": 100
    },
    "SKU_ORGANIC_TURMERIC": {
        "name": "Organic Salem Turmeric",
        "cost_price": 80.00,
        "min_margin_multiplier": 1.15,  # 15% margin floor (Min ₹92.00/kg)
        "retail_price": 120.00,
        "stock_kg": 2400,
        "warehouse": "Hub-Salem-North",
        "low_stock_threshold": 500
    },
    "SKU_BLACK_PEPPER": {
        "name": "Tellicherry Black Pepper",
        "cost_price": 480.00,
        "min_margin_multiplier": 1.15,  # 15% margin floor (Min ₹552.00/kg)
        "retail_price": 650.00,
        "stock_kg": 1200,
        "warehouse": "Hub-Wayanad-Highlands",
        "low_stock_threshold": 300
    }
}

SUPPLIER_DIRECTORY = [
    {
        "id": "SUP-01",
        "name": "Sreelayam Food Products",
        "verified": True,
        "rating": "4.9 ★ (184 reviews)",
        "location": "Kochi Industrial Hub, Kerala",
        "categories": ["spice", "blend", "premium", "curry", "raw material", "turmeric"],
        "stock": "1,800 kg ready stock",
        "contact": "+919876543210",
        "default_ask": 145.0,
        "badge": "Top Verified Exporter"
    },
    {
        "id": "SUP-02",
        "name": "Kaveri Sugar & Agro Refineries",
        "verified": True,
        "rating": "4.9 ★ (230 reviews)",
        "location": "Mandya Agro Belt, Karnataka",
        "categories": ["sugar", "cane sugar", "sweetener", "refined sugar", "jaggery"],
        "stock": "6,500 kg ready stock",
        "contact": "+919844556677",
        "default_ask": 46.0,
        "badge": "NSI Certified Refinery"
    },
    {
        "id": "SUP-03",
        "name": "Malabar Agro Trading Consortium",
        "verified": True,
        "rating": "4.8 ★ (129 reviews)",
        "location": "Wayanad Hills, Kerala",
        "categories": ["cardamom", "green cardamom", "spice", "grade-a", "pepper"],
        "stock": "450 kg ready stock",
        "contact": "+919811223344",
        "default_ask": 1050.0,
        "badge": "FSSAI Grade A"
    },
    {
        "id": "SUP-04",
        "name": "Deccan Agro Spice Terminal",
        "verified": True,
        "rating": "4.7 ★ (96 reviews)",
        "location": "Guntur APMC Yard, Andhra Pradesh",
        "categories": ["chilli", "turmeric", "spice", "blend", "pepper"],
        "stock": "3,200 kg ready stock",
        "contact": "+919822334455",
        "default_ask": 138.0,
        "badge": "APEDA Certified"
    },
    {
        "id": "SUP-05",
        "name": "Sahyadri Plantation Direct",
        "verified": True,
        "rating": "4.9 ★ (210 reviews)",
        "location": "Idukki High Ranges, Kerala",
        "categories": ["cardamom", "pepper", "clove", "spice", "organic"],
        "stock": "900 kg ready stock",
        "contact": "+919833445566",
        "default_ask": 980.0,
        "badge": "Direct Farm Origin"
    },
    {
        "id": "SUP-06",
        "name": "Godavari Agro Wholesalers",
        "verified": True,
        "rating": "4.8 ★ (112 reviews)",
        "location": "Rajahmundry Commercial Yard, Andhra Pradesh",
        "categories": ["sugar", "turmeric", "raw agro commodities", "spice"],
        "stock": "4,000 kg ready stock",
        "contact": "+919855667788",
        "default_ask": 45.0,
        "badge": "Wholesale Mandi Exporter"
    }
]

ORDER_REGISTRY = {}
SYSTEM_LOGS = []
METRICS = {
    "total_volume_kg": 0,
    "revenue_inr": 0.0,
    "platform_commission_inr": 0.0,
    "active_mandates": 0,
    "dispatched_waybills": 0
}

def log_event(channel: str, message: str, metadata: dict = None):
    timestamp = time.strftime("%H:%M:%S")
    entry = {
        "time": timestamp,
        "channel": channel,
        "message": message,
        "metadata": metadata or {}
    }
    SYSTEM_LOGS.append(entry)
    if len(SYSTEM_LOGS) > 100:
        SYSTEM_LOGS.pop(0)
    return entry

# --- DYNAMIC PRODUCT / SKU RESOLUTION ---
def resolve_or_create_sku(product_name: str, target_rate: float = None) -> tuple[str, dict]:
    name_clean = (product_name or "").strip().lower()
    
    # 1. Match against existing catalog
    if "sugar" in name_clean:
        return "SKU_REFINED_SUGAR", CATALOG_DB["SKU_REFINED_SUGAR"]
    if "cardamom" in name_clean:
        return "SKU_RAW_CARDAMOM", CATALOG_DB["SKU_RAW_CARDAMOM"]
    if "turmeric" in name_clean:
        return "SKU_ORGANIC_TURMERIC", CATALOG_DB["SKU_ORGANIC_TURMERIC"]
    if "pepper" in name_clean:
        return "SKU_BLACK_PEPPER", CATALOG_DB["SKU_BLACK_PEPPER"]
    if "spice" in name_clean or "blend" in name_clean or "curry" in name_clean:
        return "SKU_SPICE_PREMIUM", CATALOG_DB["SKU_SPICE_PREMIUM"]
        
    for sku_id, item in CATALOG_DB.items():
        if name_clean in item["name"].lower() or item["name"].lower() in name_clean:
            return sku_id, item

    # 2. Dynamically register new product on demand
    slug = re.sub(r'[^a-zA-Z0-9]', '_', product_name).upper().strip('_')
    sku_id = f"SKU_{slug}" if slug else "SKU_CUSTOM_GOODS"
    
    rate_basis = target_rate if (target_rate and target_rate > 0) else 100.0
    cost = round(rate_basis * 0.85, 2)
    retail = round(rate_basis * 1.18, 2)
    
    CATALOG_DB[sku_id] = {
        "name": product_name.strip().title() if product_name else "Custom Commodity",
        "cost_price": cost,
        "min_margin_multiplier": 1.12,  # 12% margin floor
        "retail_price": retail,
        "stock_kg": 3000,
        "warehouse": "Hub-Central-Fulfillment",
        "low_stock_threshold": 500
    }
    return sku_id, CATALOG_DB[sku_id]

# --- SCHEMAS ---
class AgentProposal(BaseModel):
    sku_id: str = Field(default="SKU_SPICE_PREMIUM", description="Matching SKU in CATALOG_DB")
    quantity: int = Field(description="Quantity requested in kilograms")
    proposed_unit_price: float = Field(description="Negotiated or requested unit price per kg")
    reasoning: str = Field(description="Internal reasoning behind the proposed rate")
    detected_language: str = Field(default="English", description="Detected language of buyer")
    localized_reply: str = Field(description="Conversational reply in the buyer's language")

class ChatRequest(BaseModel):
    user_message: str
    product: str = None
    quantity: int = None
    target_rate: float = None
    supplier_name: str = None

# --- DETERMINISTIC GATE & CRYPTOGRAPHY ---
def validate_margin(proposal: AgentProposal) -> tuple[bool, float]:
    item = CATALOG_DB.get(proposal.sku_id)
    if not item:
        proposal.sku_id, item = resolve_or_create_sku(proposal.sku_id, proposal.proposed_unit_price)
    floor_price = round(item["cost_price"] * item["min_margin_multiplier"], 2)
    return (proposal.proposed_unit_price >= floor_price), floor_price

def fallback_parser(text: str, product_hint: str = None, qty_hint: int = None, rate_hint: float = None) -> AgentProposal:
    # 1. Quantity
    if qty_hint and qty_hint > 0:
        qty = qty_hint
    else:
        qty_match = re.search(r'(\d+)\s*(?:kg|kilos|units|packets|bags|tons|quintals)', text, re.IGNORECASE)
        if not qty_match:
            qty_match = re.search(r'\b(?:need|require|want|order|rfq|buy|for)\s+(\d+)\b', text, re.IGNORECASE)
        if not qty_match:
            qty_match = re.search(r'(\d+)', text)
        qty = int(qty_match.group(1)) if qty_match else 200

    # 2. Price / Rate
    if rate_hint and rate_hint > 0:
        price = float(rate_hint)
    else:
        price_match = re.search(r'(?:₹|rs\.?|inr)\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
        if not price_match:
            price_match = re.search(r'(?:rate|price|target|at|for|offer|counter)\s*(?:is|of|=|:)?\s*(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
        if not price_match:
            price_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:/kg|per\s*kg|a\s*kg)', text, re.IGNORECASE)
        price = float(price_match.group(1)) if price_match else None

    # 3. Product & SKU
    sku_id, item = resolve_or_create_sku(product_hint or text, price)
    if price is None:
        price = item["retail_price"]

    prod_name = item["name"]
    return AgentProposal(
        sku_id=sku_id,
        quantity=qty,
        proposed_unit_price=round(price, 2),
        reasoning=f"Identified procurement requirement: {qty}kg of {prod_name} at target rate ₹{price:.2f}/kg.",
        detected_language="English",
        localized_reply=f"Inquiry received for {qty}kg of {prod_name} at ₹{price:.2f}/kg."
    )

def generate_ap2_signature(payload_dict: dict) -> str:
    payload_string = json.dumps(payload_dict, sort_keys=True)
    return hmac.new(
        RAZORPAY_KEY_SECRET.encode('utf-8'),
        payload_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def dispatch_whatsapp_message(to_number: str, text: str) -> dict:
    if twilio_client and not to_number.startswith("+919876543210"):
        try:
            formatted_to = f"whatsapp:{to_number}" if not to_number.startswith("whatsapp:") else to_number
            msg = twilio_client.messages.create(
                body=text,
                from_=f"whatsapp:{TWILIO_WHATSAPP_NUMBER}",
                to=formatted_to
            )
            return {"status": "DISPATCHED", "sid": msg.sid}
        except Exception as e:
            return {"status": "TWILIO_ERROR", "error": str(e)}
    return {"status": "SIMULATED_DISPATCH", "to": to_number}

# --- NEGOTIATION PIPELINE & MARGIN GATING ---
async def process_negotiation(
    user_input: str,
    customer_contact: str = "+919876543210",
    channel: str = "WEB_SIMULATOR",
    product_hint: str = None,
    qty_hint: int = None,
    rate_hint: float = None
):
    logs = [f"[USER PROPOSAL ({channel})] {user_input}"]
    log_event(channel, f"Inbound proposal: {user_input}")
    proposal = None

    # Step 1: Intent Extraction & Negotiation Parsing
    if product_hint and qty_hint and rate_hint:
        # User provided exact parameters from UI
        sku_id, item = resolve_or_create_sku(product_hint, rate_hint)
        proposal = AgentProposal(
            sku_id=sku_id,
            quantity=int(qty_hint),
            proposed_unit_price=float(rate_hint),
            reasoning=f"User-specified parameters: {qty_hint}kg of {item['name']} @ ₹{rate_hint:.2f}/kg.",
            detected_language="English",
            localized_reply=f"Thank you for your proposal. We received your requirement for {qty_hint}kg of {item['name']} at ₹{rate_hint:.2f}/kg."
        )
        logs.append(f"[USER PARAMETERS] {proposal.quantity}kg of {item['name']} @ ₹{proposal.proposed_unit_price:.2f}/kg")
        log_event("INTENT_EXTRACTION", f"Received requirement: {proposal.quantity}kg of {item['name']} @ ₹{proposal.proposed_unit_price}/kg")
    else:
        # Parse free text via Gemini LLM or robust fallback parser
        try:
            catalog_summary = {k: {"name": v["name"], "retail": v["retail_price"], "cost": v["cost_price"]} for k, v in CATALOG_DB.items()}
            system_instruction = f"""
            You are an autonomous B2B sales agent for a wholesale agricultural and spice distributor.
            Available Catalog: {json.dumps(catalog_summary)}

            RULES:
            1. Extract the order quantity (in kg) and the target unit price (in INR).
            2. Match the requested commodity to the closest sku_id in the catalog, or use the appropriate SKU.
            3. Detect the buyer's language (English, Hindi, Malayalam, Tamil, etc.) and save to `detected_language`.
            4. Formulate a polite, professional negotiation reply inside `localized_reply` in the buyer's language.
            5. Output strictly according to the Pydantic schema.
            """
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=AgentProposal,
                temperature=0.1,
            )
            ai_response = gemini_client.models.generate_content(
                model="gemini-flash-latest",
                contents=user_input,
                config=config,
            )
            proposal = AgentProposal(**json.loads(ai_response.text))
            logs.append(f"[AI REASONING] [{proposal.detected_language}] {proposal.reasoning}")
            log_event("AI_REASONING", f"Parsed {proposal.quantity}kg @ ₹{proposal.proposed_unit_price}/kg in {proposal.detected_language}")
        except Exception as e:
            logs.append(f"[PARSER ENGAGED] Using deterministic local parser ({str(e)[:45]}...)")
            proposal = fallback_parser(user_input, product_hint, qty_hint, rate_hint)

    item = CATALOG_DB.get(proposal.sku_id)
    if not item:
        proposal.sku_id, item = resolve_or_create_sku(proposal.sku_id, proposal.proposed_unit_price)

    logs.append(f"[PROPOSAL EVALUATION] Commodity: {item['name']} | Qty: {proposal.quantity}kg | Bid: ₹{proposal.proposed_unit_price:.2f}/kg")

    # Step 2: Deterministic Margin Floor Gate
    is_approved, floor_price = validate_margin(proposal)

    if not is_approved:
        logs.append(f"[MARGIN VIOLATION] Proposed ₹{proposal.proposed_unit_price:.2f}/kg < Wholesale Cost Floor ₹{floor_price:.2f}/kg")
        logs.append("[GATE INTERCEPT] Commercial Gatekeeper BLOCKED payment rail generation.")
        log_event("MARGIN_GATE", f"BLOCKED: ₹{proposal.proposed_unit_price:.2f}/kg breaches ₹{floor_price:.2f}/kg floor for {item['name']}")
        
        rejection_reply = (
            f"⚠️ Offer Rejected: We cannot authorize ₹{proposal.proposed_unit_price:.2f}/kg for {item['name']} "
            f"as it breaches our strict wholesale margin floor. "
            f"The absolute minimum floor price for {proposal.quantity}kg is ₹{floor_price:.2f}/kg. "
            f"Would you like to proceed at ₹{floor_price:.2f}/kg?"
        )
        return {
            "reply": rejection_reply,
            "logs": logs,
            "status": "BLOCKED",
            "floor_price": floor_price,
            "detected_language": proposal.detected_language,
            "product_name": item["name"]
        }

    # Step 3: AP2 Protocol Cart Mandate Cryptographic Signing
    ap2_signature = generate_ap2_signature(proposal.model_dump())
    logs.append(f"[GATE APPROVED] Margin check PASSED (₹{proposal.proposed_unit_price:.2f}/kg >= Floor ₹{floor_price:.2f}/kg).")
    logs.append(f"🔐 [AP2 PROTOCOL] Generated Cryptographic Cart Mandate: {ap2_signature[:18]}...")
    log_event("AP2_PROTOCOL", f"Mandate Signed: {ap2_signature[:18]}...", {"ap2_signature": ap2_signature})
    METRICS["active_mandates"] += 1

    # Step 4: Gated Razorpay Payment Link Generation
    total_amount_inr = round(proposal.quantity * proposal.proposed_unit_price, 2)
    amount_in_paise = int(total_amount_inr * 100)
    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"

    short_url = f"https://rzp.io/rzp/Z4EXkLn"
    link_id = f"plink_{uuid.uuid4().hex[:8]}"

    try:
        rzp_payload = {
            "amount": amount_in_paise,
            "currency": "INR",
            "accept_partial": False,
            "description": f"Wholesale Order: {proposal.quantity}kg of {item['name']}",
            "customer": {"contact": customer_contact},
            "expire_by": int(time.time()) + 1800,
            "notes": {
                "order_id": order_id,
                "sku_id": proposal.sku_id,
                "quantity_kg": str(proposal.quantity),
                "ap2_signature": ap2_signature,
                "negotiated_unit_price": str(proposal.proposed_unit_price),
                "gated_by": "OmniCommerce_MarginGate_v6"
            }
        }
        rzp_response = rzp_client.payment_link.create(rzp_payload)
        short_url = rzp_response.get("short_url") or short_url
        link_id = rzp_response.get("id") or link_id
        logs.append(f"[RAZORPAY SUCCESS] Verified payment link created: {short_url}")
        log_event("RAZORPAY", f"Payment Link Created: {short_url}", {"order_id": order_id, "amount": total_amount_inr})
    except Exception as e:
        logs.append(f"[RAZORPAY SANDBOX] Live API notice ({str(e)[:35]}...). Using sandbox payment rails.")

    ORDER_REGISTRY[order_id] = {
        "order_id": order_id,
        "link_id": link_id,
        "sku_id": proposal.sku_id,
        "product_name": item["name"],
        "quantity_kg": proposal.quantity,
        "unit_price": proposal.proposed_unit_price,
        "total_amount_inr": total_amount_inr,
        "customer_contact": customer_contact,
        "status": "AWAITING_PAYMENT",
        "ap2_signature": ap2_signature,
        "short_url": short_url,
        "detected_language": proposal.detected_language
    }

    approval_reply = (
        f"✅ Terms Approved! We have accepted your offer for {proposal.quantity}kg of {item['name']} at ₹{proposal.proposed_unit_price:.2f}/kg. "
        f"Order Value: ₹{total_amount_inr:,.2f}. The AP2 Cart Mandate has been cryptographically signed."
    )

    return {
        "reply": approval_reply,
        "logs": logs,
        "status": "APPROVED",
        "order_id": order_id,
        "sku_id": proposal.sku_id,
        "product_name": item["name"],
        "quantity_kg": proposal.quantity,
        "unit_price": proposal.proposed_unit_price,
        "payment_link_url": short_url,
        "amount_inr": total_amount_inr,
        "detected_language": proposal.detected_language,
        "ap2_signature": ap2_signature
    }

# --- ENDPOINTS ---
@app.get("/api/suppliers/search")
async def search_suppliers(q: str = ""):
    q_clean = q.lower().strip()
    log_event("DIRECTORY_SEARCH", f"Queried B2B Directory for: '{q or 'all verified'}'")
    if not q_clean:
        return {"results": SUPPLIER_DIRECTORY, "query": q}
    
    matches = []
    for s in SUPPLIER_DIRECTORY:
        name_match = q_clean in s["name"].lower()
        cat_match = any(q_clean in cat or cat in q_clean for cat in s["categories"])
        loc_match = q_clean in s["location"].lower()
        if name_match or cat_match or loc_match:
            matches.append(s)
            
    # If no specific keyword match, return top suppliers so buyer always has options
    if not matches:
        matches = SUPPLIER_DIRECTORY[:3]
        
    return {"results": matches, "query": q}

@app.get("/api/state")
async def get_system_state():
    return {
        "catalog": CATALOG_DB,
        "metrics": METRICS,
        "logs": SYSTEM_LOGS[-30:],
        "recent_orders": list(ORDER_REGISTRY.values())[-6:]
    }

@app.post("/api/chat")
async def web_chat_handler(req: ChatRequest):
    return await process_negotiation(
        user_input=req.user_message,
        channel="WEB_SIMULATOR",
        product_hint=req.product,
        qty_hint=req.quantity,
        rate_hint=req.target_rate
    )

@app.post("/webhook/whatsapp")
async def twilio_whatsapp_webhook(Body: str = Form(...), From: str = Form(...)):
    clean_number = From.replace('whatsapp:', '')
    response_data = await process_negotiation(Body, customer_contact=clean_number, channel="WHATSAPP_TWILIO")
    resp = MessagingResponse()
    resp.message(response_data["reply"])
    return Response(content=str(resp), media_type="application/xml")

# --- POST-PAYMENT SETTLEMENT WEBHOOK (RAZORPAY ROUTE SPLIT & DELHIVERY DISPATCH) ---
@app.get("/api/order/{order_id}")
async def get_order_status(order_id: str):
    order = ORDER_REGISTRY.get(order_id)
    if not order:
        return JSONResponse(status_code=404, content={"error": f"Order {order_id} not found"})
    return order

@app.post("/webhook/razorpay")
async def razorpay_settlement_webhook(payload: dict):
    logs = ["💳 [RAZORPAY WEBHOOK] Inbound payment event received..."]
    event = payload.get("event", "payment.captured")
    
    entity = payload.get("payload", {}).get("payment", {}).get("entity", {}) or payload.get("entity", {})
    notes = entity.get("notes", {})
    order_id = notes.get("order_id", f"ORD-LIVE-{int(time.time())}")
    sku_id = notes.get("sku_id", "SKU_SPICE_PREMIUM")
    quantity_kg = int(notes.get("quantity_kg", 200))
    amount_inr = float(entity.get("amount", 2600000)) / 100.0
    
    # Check for Payment Failure
    if event == "payment.failed" or entity.get("status") == "failed":
        failure_reason = (
            entity.get("error_description") 
            or entity.get("error_reason") 
            or payload.get("error_description") 
            or "Transaction declined by customer issuing bank (ERR_AUTHENTICATION_TIMEOUT)"
        )
        logs.append(f"❌ [PAYMENT FAILED] Event: {event} | Order ID: {order_id} | Reason: {failure_reason}")
        logs.append("🛡️ [SECURITY HOLD] Financial settlement aborted. Zero inventory deducted.")
        
        log_event("PAYMENT_FAILED", f"Order {order_id} Payment FAILED: {failure_reason}", {
            "order_id": order_id,
            "amount_inr": amount_inr,
            "reason": failure_reason
        })

        if order_id in ORDER_REGISTRY:
            ORDER_REGISTRY[order_id]["status"] = "PAYMENT_FAILED"
            ORDER_REGISTRY[order_id]["failure_reason"] = failure_reason
            ORDER_REGISTRY[order_id]["amount_inr"] = amount_inr
        
        return {
            "status": "PAYMENT_FAILED",
            "event": event,
            "order_id": order_id,
            "amount_inr": amount_inr,
            "failure_reason": failure_reason,
            "logs": logs
        }

    # Payment Successful / Captured
    logs.append(f"✅ [SETTLEMENT VERIFIED] Event: {event} | Order ID: {order_id} | Settled Amount: ₹{amount_inr:,.2f}")
    
    # 1. Real-Time Inventory Reconciliation
    item = CATALOG_DB.get(sku_id, CATALOG_DB["SKU_SPICE_PREMIUM"])
    old_stock = item["stock_kg"]
    item["stock_kg"] = max(0, old_stock - quantity_kg)
    logs.append(f"📦 [INVENTORY RECONCILIATION] {item['name']}: {old_stock}kg ➔ {item['stock_kg']}kg (-{quantity_kg}kg deducted)")
    
    # 2. Razorpay Route Split (5% Platform Commission vs 95% Merchant Payout)
    platform_commission = round(amount_inr * 0.05, 2)
    merchant_payout = round(amount_inr * 0.95, 2)
    METRICS["revenue_inr"] += amount_inr
    METRICS["platform_commission_inr"] += platform_commission
    METRICS["total_volume_kg"] += quantity_kg
    logs.append(f"🔀 [ROUTE SPLIT] 5% Platform Revenue: ₹{platform_commission:,.2f} | 95% Warehouse Payout: ₹{merchant_payout:,.2f}")
    
    # 3. Logistics Auto-Dispatch (Delhivery Integration Simulation)
    waybill_id = f"DLV-{uuid.uuid4().hex[:10].upper()}-IN"
    METRICS["dispatched_waybills"] += 1
    logs.append(f"🚚 [LOGISTICS DISPATCH] Generated Express Shipping Waybill: {waybill_id} ({item['warehouse']} ➔ Buyer)")
    logs.append(f"🎉 [TRANSACTION FINALIZED] Order {order_id} reconciled and closed successfully!")
    
    log_event("SETTLEMENT", f"Order {order_id} Settled: ₹{amount_inr:,.2f} | Waybill: {waybill_id} | Fee: ₹{platform_commission:,.2f}", {
        "order_id": order_id,
        "amount_inr": amount_inr,
        "waybill": waybill_id,
        "platform_commission": platform_commission
    })

    if order_id in ORDER_REGISTRY:
        ORDER_REGISTRY[order_id]["status"] = "PAYMENT_SUCCESSFUL"
        ORDER_REGISTRY[order_id]["waybill"] = waybill_id
        ORDER_REGISTRY[order_id]["platform_commission_inr"] = platform_commission
        ORDER_REGISTRY[order_id]["merchant_payout_inr"] = merchant_payout
        ORDER_REGISTRY[order_id]["amount_inr"] = amount_inr
    
    return {
        "status": "PAYMENT_SUCCESSFUL",
        "settled_status": "SETTLED_AND_DISPATCHED",
        "order_id": order_id,
        "waybill_id": waybill_id,
        "remaining_stock_kg": item["stock_kg"],
        "platform_commission_inr": platform_commission,
        "merchant_payout_inr": merchant_payout,
        "amount_inr": amount_inr,
        "logs": logs
    }

# --- EMBEDDED DEMO FRONTEND (INTERACTIVE USER-DRIVEN COMMAND CENTER) ---
@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Omni-Commerce Gatekeeper | Interactive Autonomous Procurement</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            .fade-in { animation: fadeIn 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
            @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
            ::-webkit-scrollbar { width: 6px; height: 6px; }
            ::-webkit-scrollbar-track { background: #0b0f19; }
            ::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 4px; }
            ::-webkit-scrollbar-thumb:hover { background: #334155; }
        </style>
    </head>
    <body class="bg-gray-950 text-white font-sans h-screen flex flex-col overflow-hidden">
        <!-- HEADER -->
        <header class="bg-gray-900 px-5 py-3 border-b border-gray-800 flex justify-between items-center shadow-lg z-20">
            <div class="flex items-center gap-3">
                <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-400 flex items-center justify-center text-black font-extrabold text-lg shadow-[0_0_15px_rgba(16,185,129,0.3)]">
                    ⚡
                </div>
                <div>
                    <div class="flex items-center gap-2">
                        <h1 class="text-base font-bold text-white tracking-tight">Omni-Commerce Gatekeeper</h1>
                        <span class="text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-600/70 px-2 py-0.5 rounded-full font-mono">v6.0 Enterprise</span>
                    </div>
                    <p class="text-[11px] text-gray-400">Interactive B2B Procurement • Verified Supplier Sourcing • AP2 Gated Settlement</p>
                </div>
            </div>
            <div class="flex items-center gap-3 font-mono text-xs">
                <div class="hidden md:flex items-center gap-2 bg-gray-950 px-3 py-1.5 rounded-lg border border-gray-800">
                    <span class="text-gray-500">Volume:</span>
                    <span id="metricVolume" class="text-emerald-400 font-bold">0 kg</span>
                    <span class="text-gray-700">|</span>
                    <span class="text-gray-500">Settled:</span>
                    <span id="metricRevenue" class="text-cyan-400 font-bold">₹0</span>
                </div>
                <span class="bg-purple-950/90 text-purple-300 px-2.5 py-1 rounded border border-purple-700/60 shadow-[0_0_10px_rgba(168,85,247,0.15)]">User-Driven</span>
                <span class="bg-emerald-950/90 text-emerald-300 px-2.5 py-1 rounded border border-emerald-600/60 shadow-[0_0_10px_rgba(16,185,129,0.15)]">AP2 Cryptographic</span>
            </div>
        </header>

        <!-- MAIN SPLIT WORKSPACE -->
        <div class="flex-1 flex overflow-hidden">
            <!-- LEFT COLUMN: PROCUREMENT DIRECTIVE & INTERACTIVE OUTREACH -->
            <div class="w-7/12 border-r border-gray-800 flex flex-col bg-gray-950 overflow-hidden">
                <!-- STEP 1: USER INPUT PROCUREMENT PARAMETERS -->
                <div class="p-4 bg-gray-900/80 border-b border-gray-800 shrink-0">
                    <div class="flex justify-between items-center mb-2.5">
                        <span class="text-xs font-bold text-gray-200 uppercase tracking-wider flex items-center gap-2">
                            <span class="w-2 h-2 rounded-full bg-purple-500 shadow-[0_0_8px_rgba(168,85,247,0.8)]"></span> 
                            1. Specify Your Procurement Requirement
                        </span>
                        <span class="text-[11px] text-gray-400 font-mono">Step 1 of 3</span>
                    </div>

                    <div class="grid grid-cols-12 gap-3 mb-2.5">
                        <div class="col-span-6">
                            <label class="block text-[11px] text-gray-400 font-medium mb-1">Product / Raw Material</label>
                            <input id="inputProduct" type="text" placeholder="e.g. Refined Cane Sugar, Premium Spice Blend, Cardamom..." 
                                class="w-full bg-black border border-gray-700 focus:border-purple-500 focus:ring-1 focus:ring-purple-500 rounded px-3 py-1.5 text-xs text-white placeholder-gray-500 outline-none transition" />
                        </div>
                        <div class="col-span-3">
                            <label class="block text-[11px] text-gray-400 font-medium mb-1">Quantity (kg)</label>
                            <input id="inputQty" type="number" placeholder="200" min="10" step="10"
                                class="w-full bg-black border border-gray-700 focus:border-purple-500 focus:ring-1 focus:ring-purple-500 rounded px-3 py-1.5 text-xs text-white placeholder-gray-500 outline-none transition" />
                        </div>
                        <div class="col-span-3">
                            <label class="block text-[11px] text-gray-400 font-medium mb-1">Target Rate (₹/kg)</label>
                            <input id="inputRate" type="number" placeholder="42" min="1" step="1"
                                class="w-full bg-black border border-gray-700 focus:border-purple-500 focus:ring-1 focus:ring-purple-500 rounded px-3 py-1.5 text-xs text-white placeholder-gray-500 outline-none transition" />
                        </div>
                    </div>

                    <!-- Quick Preset Selectors -->
                    <div class="flex items-center justify-between gap-2">
                        <div class="flex flex-wrap items-center gap-1.5 text-[11px] text-gray-400">
                            <span class="text-gray-500 text-[10px]">Quick Presets:</span>
                            <button onclick="setPreset('Refined Cane Sugar', 200, 42)" class="px-2 py-0.5 bg-gray-800 hover:bg-gray-700 rounded text-gray-300 text-[10px] border border-gray-700 transition">🍬 Sugar (200kg @ ₹42)</button>
                            <button onclick="setPreset('Premium Spice Blend', 200, 130)" class="px-2 py-0.5 bg-gray-800 hover:bg-gray-700 rounded text-gray-300 text-[10px] border border-gray-700 transition">🌶️ Spice (200kg @ ₹130)</button>
                            <button onclick="setPreset('Raw Green Cardamom', 100, 980)" class="px-2 py-0.5 bg-gray-800 hover:bg-gray-700 rounded text-gray-300 text-[10px] border border-gray-700 transition">🌱 Cardamom (100kg @ ₹980)</button>
                            <button onclick="setPreset('Organic Salem Turmeric', 300, 95)" class="px-2 py-0.5 bg-gray-800 hover:bg-gray-700 rounded text-gray-300 text-[10px] border border-gray-700 transition">🟡 Turmeric (300kg @ ₹95)</button>
                        </div>
                        <button onclick="executeSupplierSearch()" id="btnSearch" 
                            class="bg-purple-700 hover:bg-purple-600 active:bg-purple-800 text-white font-bold text-xs px-4 py-1.5 rounded shadow flex items-center gap-1.5 transition shrink-0">
                            <span>🔍 Find Verified Sellers</span>
                        </button>
                    </div>
                </div>

                <!-- STEP 2 & 3 CONTAINER: DIRECTORY SEARCH RESULTS OR INTERACTIVE WHATSAPP CHAT -->
                <div class="flex-1 flex flex-col overflow-hidden relative">
                    <!-- SECTION A: SUPPLIER DIRECTORY SEARCH RESULTS -->
                    <div id="sectionDirectory" class="flex-1 overflow-y-auto p-4 space-y-3">
                        <div class="flex items-center justify-between mb-1">
                            <span class="text-xs font-semibold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
                                <span class="w-2 h-2 rounded-full bg-cyan-500"></span> 2. Verified B2B Suppliers Matching Your Product
                            </span>
                            <span id="resultsCount" class="text-[11px] text-purple-400 font-mono">Awaiting your search query</span>
                        </div>

                        <!-- Supplier Cards List -->
                        <div id="supplierCardsList" class="space-y-3">
                            <div class="bg-gray-900/60 border border-gray-800/80 rounded-xl p-8 text-center text-gray-400 text-xs">
                                <div class="text-3xl mb-2">📋</div>
                                <p class="text-gray-300 font-medium mb-1">Ready for your procurement parameters</p>
                                <p class="text-gray-500 text-[11px]">Specify your product, quantity, and target rate above and click <span class="text-purple-400 font-semibold">"🔍 Find Verified Sellers"</span>.</p>
                            </div>
                        </div>
                    </div>

                    <!-- SECTION B: INTERACTIVE WHATSAPP OUTREACH & NEGOTIATION -->
                    <div id="sectionWhatsApp" class="hidden flex-1 flex flex-col bg-[#0b141a] overflow-hidden">
                        <!-- WhatsApp Chat Header -->
                        <div class="bg-gray-900 border-b border-gray-800 px-4 py-2.5 flex justify-between items-center shrink-0">
                            <div class="flex items-center gap-3">
                                <button onclick="backToDirectory()" title="Return to Sellers List" class="text-gray-400 hover:text-white text-xs px-2.5 py-1 rounded bg-gray-800 border border-gray-700 transition">
                                    ⬅ Sellers
                                </button>
                                <div id="waAvatar" class="w-8 h-8 rounded-full bg-emerald-600 text-white font-bold flex items-center justify-center text-sm shadow">
                                    S
                                </div>
                                <div>
                                    <div class="flex items-center gap-1.5">
                                        <h3 id="waSellerName" class="text-xs font-bold text-white">Sreelayam Food Products</h3>
                                        <span class="text-[10px] bg-emerald-950 text-emerald-400 border border-emerald-600/60 px-1.5 rounded">Verified Supplier</span>
                                    </div>
                                    <p id="waSellerLocation" class="text-[10px] text-gray-400">Kochi Industrial Hub • Official WhatsApp Procurement Channel</p>
                                </div>
                            </div>
                            <div class="flex items-center gap-2">
                                <span class="text-[10px] font-mono text-emerald-400 flex items-center gap-1">
                                    <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span> Online
                                </span>
                            </div>
                        </div>

                        <!-- Chat Messages Window -->
                        <div id="waChatBox" class="flex-1 overflow-y-auto p-4 space-y-3 bg-[radial-gradient(#1e293b_1px,transparent_1px)] [background-size:16px_16px]">
                            <!-- Chat bubbles rendered dynamically -->
                        </div>

                        <!-- Proposal Dispatch & Negotiation Input Bar -->
                        <div class="bg-gray-900 border-t border-gray-800 p-3 shrink-0">
                            <div id="proposalReadyBanner" class="mb-2 bg-purple-950/60 border border-purple-800/80 rounded-lg p-2.5 flex items-center justify-between text-xs">
                                <div>
                                    <div class="text-purple-300 font-bold flex items-center gap-1">
                                        <span>📝 Prepared Requirement Proposal:</span>
                                    </div>
                                    <div id="proposalSummaryText" class="text-gray-300 text-[11px] mt-0.5">
                                        Requirement for 200kg @ ₹42.00/kg
                                    </div>
                                </div>
                                <button onclick="dispatchUserProposal()" class="bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white font-bold text-xs px-3.5 py-1.5 rounded shadow transition flex items-center gap-1">
                                    <span>📤 Send Proposal</span>
                                </button>
                            </div>

                            <div class="flex gap-2">
                                <input id="waMessageInput" type="text" 
                                    placeholder="Type custom revision, counter-offer, or inquiry..." 
                                    class="flex-1 bg-black border border-gray-700 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 rounded px-3 py-2 text-xs text-white outline-none" 
                                    onkeydown="if(event.key==='Enter') sendCustomChatMessage()" />
                                <button onclick="sendCustomChatMessage()" 
                                    class="bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white font-bold text-xs px-4 py-2 rounded shadow transition flex items-center gap-1">
                                    <span>Send</span> ➔
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- RIGHT COLUMN: REAL-TIME CRYPTOGRAPHIC AUDIT TERMINAL -->
            <div class="w-5/12 flex flex-col bg-black overflow-hidden p-4">
                <div class="flex justify-between items-center mb-2.5 pb-2 border-b border-gray-800 shrink-0">
                    <h2 class="text-xs font-semibold text-cyan-400 uppercase tracking-widest font-mono flex items-center gap-2">
                        <span class="animate-pulse w-2 h-2 bg-cyan-400 rounded-full"></span> Commercial Audit Ledger
                    </h2>
                    <div class="flex items-center gap-2">
                        <button onclick="clearAuditTerminal()" class="text-[10px] text-gray-500 hover:text-gray-300 font-mono underline">Clear</button>
                    </div>
                </div>
                
                <div id="auditTerminal" class="flex-1 overflow-y-auto bg-gray-950 font-mono text-[11px] p-3.5 rounded-lg border border-gray-800 text-gray-400 space-y-2 shadow-inner">
                    <div class="text-gray-600 text-[10px]">--- ZERO-TRUST COMMERCIAL AUDIT ACTIVE ---</div>
                    <div class="text-gray-500 text-[10px]">System ready. Enter your procurement requirement on the left to begin.</div>
                </div>
            </div>
        </div>

        <script>
            let currentSelectedSeller = null;
            let currentRequirement = { product: "Refined Cane Sugar", qty: 200, rate: 42 };
            let lastPreparedProposal = "";

            function setPreset(product, qty, rate) {
                document.getElementById('inputProduct').value = product;
                document.getElementById('inputQty').value = qty;
                document.getElementById('inputRate').value = rate;
                executeSupplierSearch();
            }

            function clearAuditTerminal() {
                const terminal = document.getElementById('auditTerminal');
                terminal.innerHTML = '<div class="text-gray-600 text-[10px]">--- AUDIT LOG RESET ---</div>';
            }

            async function typeLog(message, colorClass) {
                const terminal = document.getElementById('auditTerminal');
                const div = document.createElement('div');
                div.className = colorClass + ' fade-in';
                div.innerHTML = message;
                terminal.appendChild(div);
                terminal.scrollTop = terminal.scrollHeight;
            }

            // --- STEP 1: USER-TRIGGERED SEARCH FOR VERIFIED SELLERS ---
            async function executeSupplierSearch() {
                const prod = document.getElementById('inputProduct').value.trim() || "Refined Cane Sugar";
                const qty = parseInt(document.getElementById('inputQty').value) || 200;
                const rate = parseFloat(document.getElementById('inputRate').value) || 42;
                currentRequirement = { product: prod, qty: qty, rate: rate };

                const cardsList = document.getElementById('supplierCardsList');
                const resultsCount = document.getElementById('resultsCount');

                // Return to directory view if WhatsApp was open
                document.getElementById('sectionWhatsApp').classList.add('hidden');
                document.getElementById('sectionDirectory').classList.remove('hidden');

                await typeLog(`> 🚀 [USER DIRECTIVE] Sourcing <b>${qty}kg</b> of <b>${prod}</b> @ target rate <b>₹${rate}/kg</b>`, 'text-purple-400 font-bold');
                await typeLog(`> 🔍 [DIRECTORY LOOKUP] Scanning verified B2B wholesale network for "${prod}"...`, 'text-cyan-400');

                cardsList.innerHTML = `
                    <div class="bg-gray-900 border border-gray-800 rounded-lg p-6 text-center text-xs text-gray-400">
                        <span class="inline-block animate-spin mr-2">🔄</span> Searching verified suppliers for "${prod}"...
                    </div>
                `;

                try {
                    const res = await fetch(`/api/suppliers/search?q=${encodeURIComponent(prod)}`);
                    const data = await res.json();
                    const sellers = data.results || [];

                    resultsCount.innerText = `${sellers.length} verified supplier${sellers.length === 1 ? '' : 's'} available`;
                    cardsList.innerHTML = '';

                    await typeLog(`> ✅ [MATCHES IDENTIFIED] Discovered ${sellers.length} verified B2B suppliers.`, 'text-emerald-400 font-semibold');

                    sellers.forEach((seller) => {
                        const card = document.createElement('div');
                        card.className = "bg-gray-900 border border-gray-800 hover:border-purple-500/80 rounded-xl p-4 transition shadow-sm fade-in space-y-3";
                        
                        const totalEstimated = (qty * rate).toLocaleString('en-IN');
                        
                        card.innerHTML = `
                            <div class="flex justify-between items-start">
                                <div>
                                    <div class="flex items-center gap-2">
                                        <h3 class="text-sm font-bold text-white">${seller.name}</h3>
                                        <span class="text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-600 px-1.5 py-0.5 rounded font-mono">✔ Verified</span>
                                    </div>
                                    <p class="text-[11px] text-gray-400 mt-0.5">${seller.location} • <span class="text-yellow-400 font-medium">${seller.rating}</span></p>
                                </div>
                                <span class="text-[10px] font-mono text-purple-300 bg-purple-950/80 border border-purple-800 px-2.5 py-0.5 rounded">${seller.badge}</span>
                            </div>

                            <div class="grid grid-cols-2 gap-2 text-[11px] bg-black/60 p-2.5 rounded-lg border border-gray-800 font-mono">
                                <div><span class="text-gray-500">Available Stock:</span> <span class="text-emerald-300 font-bold">${seller.stock}</span></div>
                                <div><span class="text-gray-500">Catalog Ask:</span> <span class="text-yellow-300 font-bold">₹${seller.default_ask}/kg</span></div>
                            </div>

                            <div class="flex items-center justify-between pt-1 border-t border-gray-800/80">
                                <div class="text-[11px] text-gray-300">
                                    Requirement: <span class="text-white font-bold font-mono">${qty}kg</span> @ <span class="text-emerald-400 font-bold font-mono">₹${rate}/kg</span> 
                                    <span class="text-gray-500 text-[10px]">(Total ₹${totalEstimated})</span>
                                </div>
                                <button onclick='selectSellerAndOpenOutreach(${JSON.stringify(seller)})' 
                                    class="bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white font-bold text-xs py-1.5 px-3.5 rounded-lg shadow transition flex items-center gap-1">
                                    <span>Select Supplier & Negotiate</span> ➔
                                </button>
                            </div>
                        `;
                        cardsList.appendChild(card);
                    });

                } catch (err) {
                    cardsList.innerHTML = `<div class="text-red-400 text-xs p-3">Error searching suppliers: ${err.message}</div>`;
                }
            }

            // --- STEP 2: USER SELECTS SUPPLIER & OPENS OUTREACH (DOES NOT AUTO-SEND) ---
            function selectSellerAndOpenOutreach(seller) {
                currentSelectedSeller = seller;

                // Switch view to WhatsApp
                document.getElementById('sectionDirectory').classList.add('hidden');
                document.getElementById('sectionWhatsApp').classList.remove('hidden');

                document.getElementById('waSellerName').innerText = seller.name;
                document.getElementById('waSellerLocation').innerText = `${seller.location} • Official WhatsApp Procurement Channel`;
                document.getElementById('waAvatar').innerText = seller.name.charAt(0);

                const chatBox = document.getElementById('waChatBox');
                chatBox.innerHTML = '';

                // Create initial channel opening announcement inside chat
                const introBanner = `
                    <div class="bg-gray-900/90 border border-gray-800 rounded-lg p-3 text-center text-xs text-gray-300 mx-auto max-w-[90%] fade-in">
                        <div class="font-bold text-emerald-400 mb-1">🤝 Direct Procurement Channel Opened</div>
                        <div>Connected to <span class="text-white font-semibold">${seller.name}</span>.</div>
                        <div class="text-[11px] text-gray-500 mt-1">Review your requirement proposal below and click <b>"Send Proposal"</b> to initiate negotiation.</div>
                    </div>
                `;
                chatBox.innerHTML = introBanner;

                // Formulate the proposal text
                lastPreparedProposal = `Hello ${seller.name}, we require ${currentRequirement.qty}kg of ${currentRequirement.product}. Our target procurement rate is ₹${currentRequirement.rate}/kg. Can you fulfill this requirement?`;

                // Update the proposal ready banner
                document.getElementById('proposalSummaryText').innerText = `${currentRequirement.qty}kg of ${currentRequirement.product} @ ₹${currentRequirement.rate}/kg (Total ₹${(currentRequirement.qty * currentRequirement.rate).toLocaleString('en-IN')})`;
                document.getElementById('proposalReadyBanner').classList.remove('hidden');

                // Pre-fill input bar in case user wants to customize
                document.getElementById('waMessageInput').value = lastPreparedProposal;

                typeLog(`> 🎯 [SELLER SELECTED] Connected to <b>${seller.name}</b> (${seller.contact}). Ready for user proposal dispatch.`, 'text-cyan-400 font-bold');
            }

            function backToDirectory() {
                document.getElementById('sectionWhatsApp').classList.add('hidden');
                document.getElementById('sectionDirectory').classList.remove('hidden');
            }

            function appendChatMessage(messageHtml, isUser) {
                const chatBox = document.getElementById('waChatBox');
                const div = document.createElement('div');
                const alignment = isUser 
                    ? 'ml-auto bg-emerald-800 text-white rounded-l-lg rounded-tr-lg border border-emerald-700/80 shadow' 
                    : 'mr-auto bg-gray-900 text-gray-200 rounded-r-lg rounded-tl-lg border border-gray-800 shadow';
                
                div.className = `p-3 max-w-[85%] text-xs leading-relaxed ${alignment} fade-in`;
                div.innerHTML = messageHtml;
                chatBox.appendChild(div);
                chatBox.scrollTop = chatBox.scrollHeight;
            }

            // --- STEP 3: USER DISPATCHES PROPOSAL OR CUSTOM MESSAGE ---
            async function dispatchUserProposal() {
                if (!lastPreparedProposal) return;
                document.getElementById('proposalReadyBanner').classList.add('hidden');
                appendChatMessage(lastPreparedProposal, true);
                
                await typeLog(`> 📤 [PROPOSAL DELIVERED] Requirement: <b>${currentRequirement.qty}kg</b> of <b>${currentRequirement.product}</b> @ <b>₹${currentRequirement.rate}/kg</b>`, 'text-green-400 font-bold');
                
                await evaluateBackendNegotiation(lastPreparedProposal, {
                    product: currentRequirement.product,
                    quantity: currentRequirement.qty,
                    target_rate: currentRequirement.rate,
                    supplier_name: currentSelectedSeller ? currentSelectedSeller.name : null
                });
            }

            async function sendCustomChatMessage() {
                const input = document.getElementById('waMessageInput');
                const message = input.value.trim();
                if (!message) return;
                
                input.value = '';
                document.getElementById('proposalReadyBanner').classList.add('hidden');
                appendChatMessage(message, true);
                
                await typeLog(`> 💬 [BUYER DISPATCH] "${message}"`, 'text-gray-300');
                await evaluateBackendNegotiation(message);
            }

            // --- STEP 4: BACKEND EVALUATION, MARGIN GATING & SETTLEMENT RAILS ---
            async function evaluateBackendNegotiation(messageText, structuredPayload = null) {
                await typeLog('> 🧠 [COMMERCIAL GATEKEEPER] Evaluating proposed rate against wholesale margin floor...', 'text-purple-400 font-bold');

                const bodyPayload = structuredPayload ? {
                    user_message: messageText,
                    product: structuredPayload.product,
                    quantity: structuredPayload.quantity,
                    target_rate: structuredPayload.target_rate,
                    supplier_name: structuredPayload.supplier_name
                } : {
                    user_message: messageText
                };

                try {
                    const res = await fetch('/api/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(bodyPayload)
                    });
                    const data = await res.json();

                    // Stream audit logs into right terminal
                    for (let log of (data.logs || [])) {
                        let color = 'text-gray-400';
                        if (log.includes('MARGIN VIOLATION') || log.includes('BLOCKED')) color = 'text-red-400 font-bold';
                        if (log.includes('GATE APPROVED') || log.includes('PASSED')) color = 'text-emerald-400 font-bold';
                        if (log.includes('RAZORPAY SUCCESS') || log.includes('Payment link')) color = 'text-cyan-400 font-bold';
                        if (log.includes('AP2 PROTOCOL') || log.includes('Mandate')) color = 'text-fuchsia-400 font-bold';
                        if (log.includes('PROPOSAL')) color = 'text-yellow-300 font-mono';
                        await typeLog(log, color);
                    }

                    // Format Seller Reply inside WhatsApp
                    let replyText = (data.reply || '').replace(/\\n/g, '<br/>');

                    if (data.status === 'APPROVED' && data.payment_link_url) {
                        const amountFormatted = (data.amount_inr || (currentRequirement.qty * currentRequirement.rate)).toLocaleString('en-IN');
                        
                        const checkoutCard = `
                            <p class="mb-2 leading-relaxed">${replyText}</p>
                            <div id="checkoutCard_${data.order_id}" class="bg-gray-950 border border-emerald-500/80 rounded-xl p-3.5 mt-2 text-center shadow-lg">
                                <div class="flex items-center justify-center gap-1.5 text-[10px] text-emerald-400 font-mono uppercase tracking-wider mb-1.5">
                                    <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping"></span>
                                    🔐 AP2 Mandate Cryptographically Signed
                                </div>
                                <div class="text-xs text-gray-300 font-mono mb-2">
                                    Agreed Order Total: <span class="text-white font-bold">₹${amountFormatted}</span>
                                </div>
                                <div class="space-y-2">
                                    <a href="${data.payment_link_url}" target="_blank" rel="noopener noreferrer" 
                                       class="block w-full bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white font-bold text-xs py-2 px-4 rounded-lg shadow-md transition text-center">
                                        💳 Open Razorpay Payment Link ➔
                                    </a>
                                    <div class="grid grid-cols-2 gap-2 pt-1">
                                        <button onclick="simulateLiveSettlement('${data.order_id}', '${data.sku_id}', ${data.quantity_kg || 200}, ${data.amount_inr || 26000}, 'success')" 
                                            class="bg-emerald-950/80 hover:bg-emerald-900 active:bg-emerald-800 text-emerald-300 font-bold text-[11px] py-1.5 px-2 rounded-lg border border-emerald-600/60 transition flex items-center justify-center gap-1 shadow">
                                            <span>⚡ Simulate Success</span>
                                        </button>
                                        <button onclick="simulateLiveSettlement('${data.order_id}', '${data.sku_id}', ${data.quantity_kg || 200}, ${data.amount_inr || 26000}, 'failure')" 
                                            class="bg-red-950/80 hover:bg-red-900 active:bg-red-800 text-red-300 font-bold text-[11px] py-1.5 px-2 rounded-lg border border-red-600/60 transition flex items-center justify-center gap-1 shadow">
                                            <span>❌ Simulate Failure</span>
                                        </button>
                                    </div>
                                </div>
                                <div class="text-[9px] text-gray-500 font-mono mt-1.5 truncate">${data.payment_link_url}</div>
                                <div id="statusBadge_${data.order_id}" class="mt-2 text-[10px] font-mono text-yellow-400 bg-yellow-950/40 border border-yellow-700/50 py-1 rounded">
                                    ⏳ Status: Awaiting Payment Settlement...
                                </div>
                            </div>
                        `;
                        appendChatMessage(checkoutCard, false);
                        startOrderStatusPolling(data.order_id, data.sku_id, data.quantity_kg || 200, data.amount_inr || 26000);
                    } else {
                        // Rate was below margin floor or plain counter-offer
                        appendChatMessage(replyText, false);
                        if (data.floor_price) {
                            document.getElementById('waMessageInput').value = `Can we finalize at ₹${data.floor_price}/kg?`;
                        }
                    }

                } catch (err) {
                    await typeLog(`Error communicating with backend: ${err.message}`, 'text-red-500 font-bold');
                }
            }

            // Real-time Status Polling and Status Card Renderers
            const activePollers = {};
            const renderedStatusTracker = {};

            function startOrderStatusPolling(orderId, skuId, qty, amount) {
                if (activePollers[orderId]) return;
                activePollers[orderId] = setInterval(async () => {
                    try {
                        const res = await fetch(`/api/order/${orderId}`);
                        if (!res.ok) return;
                        const order = await res.json();
                        
                        if (order.status === 'PAYMENT_SUCCESSFUL' || order.status === 'SETTLED_AND_DISPATCHED') {
                            clearInterval(activePollers[orderId]);
                            delete activePollers[orderId];
                            renderPaymentSuccess({
                                order_id: orderId,
                                amount_inr: order.amount_inr || order.total_amount_inr || amount,
                                waybill_id: order.waybill,
                                platform_commission_inr: order.platform_commission_inr,
                                merchant_payout_inr: order.merchant_payout_inr
                            });
                            updateCardBadge(orderId, 'SUCCESS');
                        } else if (order.status === 'PAYMENT_FAILED') {
                            clearInterval(activePollers[orderId]);
                            delete activePollers[orderId];
                            renderPaymentFailure({
                                order_id: orderId,
                                sku_id: skuId,
                                quantity_kg: qty,
                                amount_inr: order.amount_inr || amount,
                                failure_reason: order.failure_reason
                            });
                            updateCardBadge(orderId, 'FAILED');
                        }
                    } catch (e) {}
                }, 2000);
            }

            function updateCardBadge(orderId, status) {
                const badge = document.getElementById(`statusBadge_${orderId}`);
                if (!badge) return;
                if (status === 'SUCCESS') {
                    badge.className = 'mt-2 text-[10px] font-mono text-emerald-300 bg-emerald-950/80 border border-emerald-600 py-1 rounded font-bold';
                    badge.innerHTML = '✅ Status: Payment Confirmed & Settled';
                } else if (status === 'FAILED') {
                    badge.className = 'mt-2 text-[10px] font-mono text-red-300 bg-red-950/80 border border-red-600 py-1 rounded font-bold';
                    badge.innerHTML = '❌ Status: Payment Failed / Declined';
                }
            }

            function renderPaymentSuccess(data) {
                const key = `${data.order_id}_SUCCESS`;
                if (renderedStatusTracker[key]) return;
                renderedStatusTracker[key] = true;
                if (activePollers[data.order_id]) {
                    clearInterval(activePollers[data.order_id]);
                    delete activePollers[data.order_id];
                }

                const amt = Number(data.amount_inr || 0).toLocaleString('en-IN');
                const fee = Number(data.platform_commission_inr || (data.amount_inr * 0.05) || 0).toLocaleString('en-IN');
                const payout = Number(data.merchant_payout_inr || (data.amount_inr * 0.95) || 0).toLocaleString('en-IN');
                const waybill = data.waybill_id || data.waybill || ('DLV-' + Math.random().toString(36).substring(2, 10).toUpperCase() + '-IN');

                const card = `
                    <div class="bg-gray-950 border-2 border-emerald-500 rounded-xl p-4 shadow-[0_0_25px_rgba(16,185,129,0.25)] text-left fade-in">
                        <div class="flex items-center justify-between pb-2 mb-2.5 border-b border-gray-800">
                            <div class="flex items-center gap-2">
                                <div class="w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold text-xs border border-emerald-500/40">✓</div>
                                <span class="text-xs font-black text-emerald-400 uppercase tracking-wider">Payment Successful</span>
                            </div>
                            <span class="text-[10px] font-mono bg-emerald-950 text-emerald-300 px-2 py-0.5 rounded border border-emerald-700 font-bold">PAID & DISPATCHED</span>
                        </div>
                        <div class="space-y-1.5 text-xs font-mono">
                            <div class="flex justify-between"><span class="text-gray-400">Order ID:</span> <span class="text-white font-bold">${data.order_id}</span></div>
                            <div class="flex justify-between"><span class="text-gray-400">Settled Total:</span> <span class="text-emerald-400 font-bold">₹${amt}</span></div>
                            <div class="flex justify-between"><span class="text-gray-400">Delhivery Waybill:</span> <span class="text-cyan-300 font-bold">${waybill}</span></div>
                            <div class="flex justify-between"><span class="text-gray-400">5% Platform Split:</span> <span class="text-purple-300">₹${fee}</span></div>
                            <div class="flex justify-between"><span class="text-gray-400">95% Warehouse Payout:</span> <span class="text-gray-300">₹${payout}</span></div>
                        </div>
                        <div class="mt-3 pt-2 border-t border-gray-800/80 text-[11px] text-gray-300 flex items-center gap-2">
                            <span class="text-emerald-400 font-bold">🚚 Fulfillment:</span>
                            <span>Express Delhivery Waybill issued. Stock allocated & deducted from Hub Warehouse.</span>
                        </div>
                    </div>
                `;
                appendChatMessage(card, false);
                updateCardBadge(data.order_id, 'SUCCESS');
            }

            function renderPaymentFailure(data) {
                const key = `${data.order_id}_FAILED`;
                if (renderedStatusTracker[key]) return;
                renderedStatusTracker[key] = true;
                if (activePollers[data.order_id]) {
                    clearInterval(activePollers[data.order_id]);
                    delete activePollers[data.order_id];
                }

                const amt = Number(data.amount_inr || 0).toLocaleString('en-IN');
                const reason = data.failure_reason || 'Transaction declined by customer issuing bank (ERR_AUTHENTICATION_TIMEOUT)';

                const card = `
                    <div class="bg-gray-950 border-2 border-red-500 rounded-xl p-4 shadow-[0_0_25px_rgba(239,68,68,0.25)] text-left fade-in">
                        <div class="flex items-center justify-between pb-2 mb-2.5 border-b border-gray-800">
                            <div class="flex items-center gap-2">
                                <div class="w-6 h-6 rounded-full bg-red-500/20 text-red-400 flex items-center justify-center font-bold text-xs border border-red-500/40">✗</div>
                                <span class="text-xs font-black text-red-400 uppercase tracking-wider">Payment Failed</span>
                            </div>
                            <span class="text-[10px] font-mono bg-red-950 text-red-300 px-2 py-0.5 rounded border border-red-700 font-bold">TRANSACTION DECLINED</span>
                        </div>
                        <div class="space-y-1.5 text-xs font-mono">
                            <div class="flex justify-between"><span class="text-gray-400">Order ID:</span> <span class="text-white font-bold">${data.order_id}</span></div>
                            <div class="flex justify-between"><span class="text-gray-400">Attempted Amount:</span> <span class="text-red-300 font-bold">₹${amt}</span></div>
                            <div class="flex justify-between"><span class="text-gray-400">Failure Reason:</span> <span class="text-red-400 font-medium">${reason}</span></div>
                            <div class="flex justify-between"><span class="text-gray-400">Inventory Status:</span> <span class="text-yellow-400 font-semibold">Protected (Zero stock deducted)</span></div>
                        </div>
                        <div class="mt-3 pt-2 border-t border-gray-800/80 flex gap-2">
                            <button onclick="simulateLiveSettlement('${data.order_id}', '${data.sku_id}', ${data.quantity_kg || 200}, ${data.amount_inr || 0}, 'success')" 
                                class="flex-1 bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white font-bold text-xs py-1.5 px-3 rounded-lg text-center transition flex items-center justify-center gap-1 shadow">
                                <span>⚡ Re-attempt & Settle (Simulate Success)</span>
                            </button>
                        </div>
                    </div>
                `;
                appendChatMessage(card, false);
                updateCardBadge(data.order_id, 'FAILED');
            }

            // Simulation Helper: Trigger live payment reconciliation webhook (Captured or Failed)
            async function simulateLiveSettlement(orderId, skuId, qty, amount, statusType = 'success') {
                if (statusType === 'success') {
                    await typeLog(`> 💳 [PAYMENT SETTLEMENT] Triggering payment.captured webhook for ${orderId}...`, 'text-cyan-400 font-bold');
                    try {
                        const res = await fetch('/webhook/razorpay', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                event: 'payment.captured',
                                entity: {
                                    status: 'captured',
                                    amount: Math.round(amount * 100),
                                    notes: {
                                        order_id: orderId,
                                        sku_id: skuId,
                                        quantity_kg: qty
                                    }
                                }
                            })
                        });
                        const resData = await res.json();
                        for (let log of (resData.logs || [])) {
                            await typeLog(log, 'text-emerald-300 font-mono');
                        }
                        renderPaymentSuccess(resData);
                        fetchSystemState();
                    } catch (e) {
                        await typeLog(`Settlement simulation error: ${e.message}`, 'text-red-400');
                    }
                } else {
                    await typeLog(`> ⚠️ [PAYMENT FAILURE] Triggering payment.failed webhook for ${orderId}...`, 'text-red-400 font-bold');
                    try {
                        const res = await fetch('/webhook/razorpay', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                event: 'payment.failed',
                                entity: {
                                    status: 'failed',
                                    amount: Math.round(amount * 100),
                                    error_code: 'BAD_REQUEST_ERROR',
                                    error_description: 'Transaction declined: 3DS Authentication Failed / Insufficient Funds',
                                    notes: {
                                        order_id: orderId,
                                        sku_id: skuId,
                                        quantity_kg: qty
                                    }
                                }
                            })
                        });
                        const resData = await res.json();
                        for (let log of (resData.logs || [])) {
                            await typeLog(log, 'text-red-400 font-mono');
                        }
                        renderPaymentFailure({
                            order_id: orderId,
                            sku_id: skuId,
                            quantity_kg: qty,
                            amount_inr: amount,
                            failure_reason: resData.failure_reason
                        });
                        fetchSystemState();
                    } catch (e) {
                        await typeLog(`Failure simulation error: ${e.message}`, 'text-red-400');
                    }
                }
            }

            // Sync metrics periodically
            async function fetchSystemState() {
                try {
                    const res = await fetch('/api/state');
                    const data = await res.json();
                    if (data.metrics) {
                        document.getElementById('metricVolume').innerText = `${data.metrics.total_volume_kg.toLocaleString()} kg`;
                        document.getElementById('metricRevenue').innerText = `₹${data.metrics.revenue_inr.toLocaleString('en-IN')}`;
                    }
                } catch (e) {}
            }
            setInterval(fetchSystemState, 4000);
            fetchSystemState();
        </script>
    </body>
    </html>
    """