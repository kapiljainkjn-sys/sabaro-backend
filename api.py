import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client
from openai import OpenAI

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

# Allow React app to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def embed(text):
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding


# ── ROUTES ─────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "Sabaro API running"}


@app.get("/sellers")
def get_sellers():
    """Get all sellers"""
    result = supabase.table("sellers").select("*").execute()
    return {"sellers": result.data}


class SearchRequest(BaseModel):
    query: str
    limit: int = 10


@app.post("/search")
def search(req: SearchRequest):
    """AI search — finds sellers by meaning"""

    # Embed the query
    query_vector = embed(req.query)

    # Vector search in Supabase
    results = supabase.rpc("search_products", {
        "query_embedding": query_vector,
        "match_threshold": 0.3,
        "match_count": 20
    }).execute()

    if not results.data:
        return {"sellers": [], "query": req.query}

    # Get seller details
    seller_ids = list(set([r["seller_id"] for r in results.data]))
    sellers = supabase.table("sellers").select("*").in_("id", seller_ids).execute()
    seller_map = {s["id"]: s for s in sellers.data}

    # Best product match per seller
    product_matches = {}
    for r in results.data:
        sid = r["seller_id"]
        if sid not in product_matches or r["similarity"] > product_matches[sid]["similarity"]:
            product_matches[sid] = r

    # Rank by trust + similarity
    ranked = []
    for sid, match in product_matches.items():
        seller = seller_map.get(sid)
        if not seller:
            continue

        final_score = (match["similarity"] * 0.5) + (seller["trust_score"] / 100 * 0.5)

        ranked.append({
            **seller,
            "matched_product": match["product_name"],
            "similarity": round(match["similarity"], 3),
            "final_score": round(final_score, 3),
        })

    ranked.sort(key=lambda x: x["final_score"], reverse=True)

    return {
        "query": req.query,
        "count": len(ranked),
        "sellers": ranked[:req.limit]
    }


@app.get("/sellers/{seller_id}")
def get_seller(seller_id: str):
    """Get single seller with their products"""
    seller = supabase.table("sellers").select("*").eq("id", seller_id).execute()
    products = supabase.table("products").select("*").eq("seller_id", seller_id).execute()

    if not seller.data:
        return {"error": "Seller not found"}

    return {
        "seller": seller.data[0],
        "products": products.data
    }


class BookingRequest(BaseModel):
    seller_id: str
    buyer_name: str
    buyer_phone: str
    service: str
    amount: int
    details: dict


@app.post("/bookings")
def create_booking(req: BookingRequest):
    """Create a new booking"""
    result = supabase.table("bookings").insert({
        "seller_id": req.seller_id,
        "buyer_name": req.buyer_name,
        "buyer_phone": req.buyer_phone,
        "service": req.service,
        "amount": req.amount,
        "status": "pending",
        "details": req.details,
    }).execute()

    return {
        "booking_id": result.data[0]["id"],
        "status": "pending",
        "message": "Booking created. Seller will confirm within 24 hours."
    }

class SellerRegister(BaseModel):
    name: str
    category: str
    city: str
    area: str
    whatsapp: str
    since: int
    price_range: str
    moq: str
    password: str

@app.post("/sellers/register")
def register_seller(req: SellerRegister):
    """Register a new seller"""

    # Check if seller with same WhatsApp already exists
    existing = supabase.table("sellers").select("id").eq("whatsapp", req.whatsapp).execute()
    if existing.data:
        raise HTTPException(status_code=400, detail="Seller with this WhatsApp already registered.")

    # Add seller
    result = supabase.table("sellers").insert({
        "name": req.name,
        "category": req.category,
        "city": req.city,
        "area": req.area,
        "whatsapp": req.whatsapp,
        "since": req.since,
        "price_range": req.price_range,
        "moq": req.moq,
        "trust_score": 40,
        "shipments": 0,
        "recommendations": 0,
        "sample_available": False,
        "inspection_available": False,
        "transport_available": False,
    }).execute()

    seller_id = result.data[0]["id"]
    return {
        "seller_id": seller_id,
        "message": "Registration successful",
        "name": req.name
    }


@app.get("/sellers/{seller_id}/dashboard")
def seller_dashboard(seller_id: str):
    """Get seller dashboard data"""
    seller = supabase.table("sellers").select("*").eq("id", seller_id).execute()
    bookings = supabase.table("bookings").select("*").eq("seller_id", seller_id).execute()
    products = supabase.table("products").select("*").eq("seller_id", seller_id).execute()

    if not seller.data:
        raise HTTPException(status_code=404, detail="Seller not found")

    return {
        "seller": seller.data[0],
        "bookings": bookings.data,
        "products": products.data,
        "stats": {
            "total_bookings": len(bookings.data),
            "pending_bookings": len([b for b in bookings.data if b["status"] == "pending"]),
            "total_products": len(products.data),
        }
    }


# Seller login
class SellerLogin(BaseModel):
    whatsapp: str
    password: str

@app.post("/sellers/login")
def login_seller(req: SellerLogin):
    result = supabase.table("sellers").select("*").eq("whatsapp", req.whatsapp).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="No seller found with this WhatsApp number.")
    return {"seller": result.data[0]}

# Add product with embedding
class ProductAdd(BaseModel):
    product_name: str = ""
    name: str = ""
    description: str = ""
    material: str = ""
    use_cases: str = ""
    min_order: int = 0
    price_per_unit: float = 0

@app.post("/sellers/{seller_id}/products")
def add_product(seller_id: str, req: ProductAdd):
    name = req.product_name or req.name
    text = f"Product: {name} Description: {req.description} Material: {req.material} Use cases: {req.use_cases}"
    vector = embed(text)
    result = supabase.table("products").insert({
        "seller_id": seller_id,
        "product_name": name,
        "description": req.description,
        "material": req.material,
        "use_cases": req.use_cases,
        "min_order": req.min_order,
        "price_per_unit": req.price_per_unit,
        "embedding": vector,
    }).execute()
    return {"product": result.data[0]}

# Confirm booking
@app.post("/bookings/{booking_id}/confirm")
def confirm_booking(booking_id: str):
    result = supabase.table("bookings").update({"status": "confirmed"}).eq("id", booking_id).execute()
    return {"status": "confirmed"}

# Update seller profile
class SellerUpdate(BaseModel):
    name: str = None
    category: str = None
    city: str = None
    area: str = None
    whatsapp: str = None
    price_range: str = None
    moq: str = None

@app.patch("/sellers/{seller_id}")
def update_seller(seller_id: str, req: SellerUpdate):
    update = {k:v for k,v in req.dict().items() if v is not None}
    result = supabase.table("sellers").update(update).eq("id", seller_id).execute()
    return {"seller": result.data[0]}

    
