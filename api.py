import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client
from openai import OpenAI
import pypdf
import io
import json

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
    from collections import defaultdict
    sellers = supabase.table("sellers").select("*").execute()
    if not sellers.data:
        return {"sellers": []}

    seller_ids = [s["id"] for s in sellers.data]

    products_result = supabase.table("products").select(
        "id, seller_id, product_name, image_url, price_per_unit, min_order, unit_of_measure, category"
    ).in_("seller_id", seller_ids).execute()

    products_by_seller = defaultdict(list)
    for p in (products_result.data or []):
        if len(products_by_seller[p["seller_id"]]) < 6:
            products_by_seller[p["seller_id"]].append(p)

    for s in sellers.data:
        s["top_products"] = products_by_seller.get(s["id"], [])

    return {"sellers": sellers.data}


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

    # Attach top products, matched product first
    if ranked:
        from collections import defaultdict
        ranked_ids = [r["id"] for r in ranked]
        prod_res = supabase.table("products").select(
            "id, seller_id, product_name, image_url, price_per_unit, min_order, unit_of_measure, category"
        ).in_("seller_id", ranked_ids).eq("status", "live").execute()

        prods_by_seller = defaultdict(list)
        for p in (prod_res.data or []):
            if len(prods_by_seller[p["seller_id"]]) < 6:
                prods_by_seller[p["seller_id"]].append(p)

        for r in ranked:
            seller_prods = list(prods_by_seller.get(r["id"], []))
            matched = r.get("matched_product", "")
            if matched:
                seller_prods.sort(key=lambda p: 0 if p["product_name"] == matched else 1)
            r["top_products"] = seller_prods

    return {
        "query": req.query,
        "count": len(ranked),
        "sellers": ranked[:req.limit]
    }



@app.post("/sellers/{seller_id}/catalogue")
async def upload_catalogue(
    seller_id: str,
    file: UploadFile = File(...),
    industry: str = Form("")
):
    content = await file.read()
    try:
        pdf_reader = pypdf.PdfReader(io.BytesIO(content))
        full_text = ""
        for i, page in enumerate(pdf_reader.pages):
            if i > 60:
                break
            text = page.extract_text()
            if text:
                full_text += text + "\n"
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read PDF: {str(e)}")

    if not full_text.strip():
        raise HTTPException(status_code=400, detail="No text found in PDF.")

    industry_context = f"This is a {industry} catalogue." if industry else ""

    extraction = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content":"You are a B2B product data extractor for Indian suppliers. Extract structured product data accurately."},
            {"role":"user","content":f"""{industry_context}

STEP 1 — Identify the industry from: Chemicals/Dyes/Solvents, Pharmaceuticals/Medical, Metals/Engineering/Auto Parts, Electronics/Electrical, Construction/Building Materials, Textiles/Apparel/Leather, Food/Beverage/Agriculture, Packaging/Paper/Printing, Plastics/Rubber, Furniture/Hotel Supplies, Industrial Machinery, Gems/Jewellery, Other.

STEP 2 — Extract ALL products. Never skip any product.

BASIC FIELDS (extract for every product):
- product_name: full product name
- product_code: SKU, model number, catalogue code, item code
- brand: brand or manufacturer name
- series_name: product series or range name
- category: specific category (e.g. Corrugated Box, Vitrified Tile, Cotton Fabric)
- industry: from STEP 1
- description: 2-3 sentences — what it is and key benefit
- material: primary material or composition
- color: color or shade
- dimensions: size, dimensions, capacity
- finish_grade: finish, grade, purity (e.g. Glossy, Grade A, 99.9% pure, 350 GSM)
- use_cases: comma separated applications
- suitable_for: who uses it (e.g. restaurants, factories, hospitals)
- certifications: ISO/BIS/FSSAI/CE/RoHS/REACH/FDA/Agmark etc
- country_of_origin: country of manufacture
- unit_of_measure: piece/kg/litre/metre/sq ft/box/roll/set/ton/dozen
- min_order: number (0 if unknown)
- price_per_unit: number (0 if unknown)

EXTENDED FIELDS — put into tags array as [{{"key":"...","value":"..."}}]:

IF Chemicals/Dyes/Solvents:
  chemical_formula, cas_number, concentration, ph_level, flash_point, boiling_point, specific_gravity, hazard_class, purity_percentage, shelf_life, storage_conditions

IF Pharmaceuticals/Medical:
  active_ingredient, dosage_form, strength, storage_temp, shelf_life, schedule_class, packaging_type, sterile

IF Metals/Engineering/Auto Parts:
  alloy_grade, hardness_hrc, tensile_strength, yield_strength, tolerance, surface_finish, heat_treatment, weight_per_unit, operating_pressure, thread_type, vehicle_make, vehicle_model

IF Electronics/Electrical:
  voltage, wattage, current_rating, frequency, ip_rating, operating_temp, connector_type, efficiency_rating, warranty_years, power_factor, phase

IF Construction/Building Materials:
  thickness, water_absorption, slip_resistance, load_capacity, compressive_strength, fire_rating, thermal_insulation, installation_method, coverage_per_unit

IF Textiles/Apparel/Leather:
  fabric_type, gsm, weave_type, thread_count, width_cm, shrinkage_percent, color_fastness, care_instructions, pattern_type, blend_ratio

IF Food/Beverage/Agriculture:
  ingredients, shelf_life, storage_conditions, fssai_number, organic_certified, food_grade, allergens, moisture_content, net_weight, variety_strain

IF Packaging/Paper/Printing:
  gsm_paper, layers_ply, burst_strength, print_type, recyclable, food_grade_packaging, barrier_properties, moisture_resistance, lamination_type

IF Plastics/Rubber:
  polymer_type, hardness_shore, elongation_percent, temperature_range, chemical_resistance, uv_stabilized, food_grade_plastic, wall_thickness, pressure_rating

IF Furniture/Hotel Supplies:
  weight_capacity_kg, assembly_required, room_type, wood_type, upholstery_material, water_resistant, scratch_resistant, stackable, foldable

IF Industrial Machinery:
  power_kw, capacity_per_hour, working_pressure, noise_level_db, power_supply, cycle_time, accuracy, warranty_machine

IF Gems/Jewellery:
  metal_purity, carat, stone_type, stone_weight_ct, clarity, cut_grade, hallmark_certified, setting_type

Use empty string for basic fields not found. Only add tags actually mentioned in catalogue. Never invent values.

Catalogue text:
{full_text[:10000]}

Return only JSON: {{"industry_detected": "...", "products": [...]}}
Tags format: [{{"key": "gsm", "value": "350"}}, {{"key": "color", "value": "white"}}]"""}
        ],
        response_format={"type":"json_object"}
    )

    parsed = json.loads(extraction.choices[0].message.content)
    products = parsed.get("products", [])
    industry_detected = parsed.get("industry_detected", "")
    print(f"Industry: {industry_detected}, Products found: {len(products)}")

    # Extract images from PDF
    extracted_images = []
    try:
        pdf_reader2 = pypdf.PdfReader(io.BytesIO(content))
        for page_num, page in enumerate(pdf_reader2.pages):
            if len(extracted_images) >= 50:
                break
            if "/Resources" in page and "/XObject" in page["/Resources"]:
                xobjects = page["/Resources"]["/XObject"].get_object()
                for obj_name, obj in xobjects.items():
                    obj = obj.get_object()
                    if obj.get("/Subtype") == "/Image":
                        try:
                            data = obj.get_data()
                            ext = "png" if obj.get("/Filter") == "/FlateDecode" else "jpg"
                            img_path = f"catalogues/{seller_id}/p{page_num}_{obj_name}.{ext}"
                            supabase.storage.from_("chat-files").upload(
                                img_path, data,
                                {"content-type": f"image/{ext}", "upsert": "true"}
                            )
                            url = supabase.storage.from_("chat-files").get_public_url(img_path)
                            extracted_images.append(url)
                        except:
                            continue
    except Exception as e:
        print(f"Image extraction failed: {e}")

    added = []
    for i, product in enumerate(products[:50]):
        try:
            tags = product.get("tags", [])
            tags_text = " ".join([f"{t.get('key','')} {t.get('value','')}" for t in tags])

            embed_text = f"""
Product: {product.get('product_name','')}
Code: {product.get('product_code','')}
Brand: {product.get('brand','')}
Series: {product.get('series_name','')}
Category: {product.get('category','')}
Industry: {product.get('industry', industry_detected)}
Description: {product.get('description','')}
Material: {product.get('material','')}
Color: {product.get('color','')}
Dimensions: {product.get('dimensions','')}
Finish/Grade: {product.get('finish_grade','')}
Use cases: {product.get('use_cases','')}
Suitable for: {product.get('suitable_for','')}
Certifications: {product.get('certifications','')}
{tags_text}
"""
            vector = embed(embed_text)

            # Use extracted image or fallback to Unsplash
            if i < len(extracted_images):
                image_url = extracted_images[i]
            else:
                name = product.get('product_name','').replace(' ','+')
                cat = product.get('category','').replace(' ','+')
                image_url = f"https://source.unsplash.com/400x300/?{name},{cat}"

            result = supabase.table("products").insert({
                "seller_id": seller_id,
                "product_name": product.get("product_name",""),
                "product_code": product.get("product_code",""),
                "brand": product.get("brand",""),
                "series_name": product.get("series_name",""),
                "category": product.get("category",""),
                "industry": product.get("industry", industry_detected),
                "description": product.get("description",""),
                "material": product.get("material",""),
                "color": product.get("color",""),
                "dimensions": product.get("dimensions",""),
                "finish_grade": product.get("finish_grade",""),
                "use_cases": product.get("use_cases",""),
                "suitable_for": product.get("suitable_for",""),
                "certifications": product.get("certifications",""),
                "country_of_origin": product.get("country_of_origin",""),
                "unit_of_measure": product.get("unit_of_measure",""),
                "min_order": int(product.get("min_order") or 0),
                "price_per_unit": float(product.get("price_per_unit") or 0),
                "tags": tags,
                "image_url": image_url,
                "embedding": vector,
            }).execute()
            added.append(result.data[0])
        except Exception as e:
            print(f"Product error: {e}")
            continue

    return {"products": added, "products_added": len(added)}



@app.post("/sellers/{seller_id}/catalogues")
async def save_catalogue(
    seller_id: str,
    file: UploadFile = File(...),
    industry: str = Form("")
):
    """Save catalogue PDF to storage and create catalogue record"""
    content = await file.read()
    
    # Upload PDF to Supabase storage
    file_path = f"catalogues/{seller_id}/{file.filename}"
    try:
        supabase.storage.from_("chat-files").upload(
            file_path, content,
            {"content-type": "application/pdf", "upsert": "true"}
        )
        file_url = supabase.storage.from_("chat-files").get_public_url(file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage error: {str(e)}")

    # Create catalogue record
    result = supabase.table("catalogues").insert({
        "seller_id": seller_id,
        "file_name": file.filename,
        "file_url": file_url,
        "status": "uploaded",
    }).execute()

    return {"catalogue": result.data[0]}


@app.get("/sellers/{seller_id}")
def get_seller(seller_id: str):
    """Get single seller with their products"""
    seller = supabase.table("sellers").select("*").eq("id", seller_id).execute()
    products = supabase.table("products").select(
    "id, seller_id, catalogue_id, product_name, product_code, brand, series_name, category, industry, description, material, color, dimensions, finish_grade, use_cases, suitable_for, certifications, country_of_origin, unit_of_measure, min_order, price_per_unit, tags, image_url, status, added_by, created_at"
    ).eq("seller_id", seller_id).execute()

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
    products = supabase.table("products").select(
    "id, seller_id, catalogue_id, product_name, product_code, brand, series_name, category, industry, description, material, color, dimensions, finish_grade, use_cases, suitable_for, certifications, country_of_origin, unit_of_measure, min_order, price_per_unit, tags, image_url, status, added_by, created_at"
    ).eq("seller_id", seller_id).execute()

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


# ── CHAT ENDPOINTS ─────────────────────────────────────────────────────────────

class MessageRequest(BaseModel):
    conversation_id: str
    sender: str
    sender_name: str
    content: str
    message_type: str = "text"
    file_url: str = ""
    file_name: str = ""

class ConversationRequest(BaseModel):
    buyer_name: str
    buyer_phone: str
    seller_id: str

@app.post("/conversations/start")
def start_conversation(req: ConversationRequest):
    """Start or get existing conversation between buyer and seller"""
    # Check if conversation already exists
    existing = supabase.table("conversations")\
        .select("*")\
        .eq("buyer_phone", req.buyer_phone)\
        .eq("seller_id", req.seller_id)\
        .execute()

    if existing.data:
        return {"conversation": existing.data[0]}

    # Create new conversation
    result = supabase.table("conversations").insert({
        "buyer_name": req.buyer_name,
        "buyer_phone": req.buyer_phone,
        "seller_id": req.seller_id,
        "last_message": "Conversation started",
        "unread_seller": 1,
    }).execute()

    return {"conversation": result.data[0]}

@app.get("/conversations/buyer/{phone}")
def get_buyer_conversations(phone: str):
    """Get all conversations for a buyer"""
    result = supabase.table("conversations")\
        .select("*, sellers(name, city, category, trust_score)")\
        .eq("buyer_phone", phone)\
        .order("last_message_at", desc=True)\
        .execute()
    return {"conversations": result.data}

@app.get("/conversations/seller/{seller_id}")
def get_seller_conversations(seller_id: str):
    """Get all conversations for a seller"""
    result = supabase.table("conversations")\
        .select("*")\
        .eq("seller_id", seller_id)\
        .order("last_message_at", desc=True)\
        .execute()
    return {"conversations": result.data}

@app.get("/conversations/{conversation_id}/messages")
def get_messages(conversation_id: str):
    """Get all messages in a conversation"""
    result = supabase.table("messages")\
        .select("*")\
        .eq("conversation_id", conversation_id)\
        .order("created_at", asc=True)\
        .execute()
    return {"messages": result.data}

@app.post("/messages/send")
def send_message(req: MessageRequest):
    """Send a message"""
    result = supabase.table("messages").insert({
        "conversation_id": req.conversation_id,
        "sender": req.sender,
        "sender_name": req.sender_name,
        "content": req.content,
        "message_type": req.message_type,
        "file_url": req.file_url,
        "file_name": req.file_name,
    }).execute()

    # Update conversation last message
    supabase.table("conversations").update({
        "last_message": req.content if req.message_type == "text" else f"📎 {req.file_name or 'File'}",
        "last_message_at": "now()",
        "unread_seller": supabase.table("conversations").select("unread_seller").eq("id", req.conversation_id).execute().data[0]["unread_seller"] + (1 if req.sender == "buyer" else 0),
    }).eq("id", req.conversation_id).execute()

    return {"message": result.data[0]}

@app.post("/chat/upload")
async def upload_chat_file(
    file: UploadFile = File(...),
    conversation_id: str = Form(...)
):
    """Upload photo or file to chat"""
    content = await file.read()
    file_path = f"{conversation_id}/{file.filename}"

    result = supabase.storage.from_("chat-files").upload(
        file_path, content,
        {"content-type": file.content_type}
    )

    url = supabase.storage.from_("chat-files").get_public_url(file_path)
    return {"url": url, "file_name": file.filename} 

# ── CATALOGUE MANAGEMENT ───────────────────────────────────────────────────────



@app.get("/sellers/{seller_id}/catalogues")
def get_seller_catalogues(seller_id: str):
    """Get all catalogues for a seller"""
    result = supabase.table("catalogues")\
        .select("*")\
        .eq("seller_id", seller_id)\
        .order("created_at", desc=True)\
        .execute()
    return {"catalogues": result.data}


@app.get("/team/catalogues")
def get_all_catalogues():
    """Get all catalogues across all sellers for team review"""
    result = supabase.table("catalogues")\
        .select("*, sellers(name, city, category)")\
        .order("created_at", desc=True)\
        .execute()
    return {"catalogues": result.data}


@app.get("/team/login/{whatsapp}")
def team_login(whatsapp: str):
    """Team member login by WhatsApp"""
    result = supabase.table("team_members")\
        .select("*")\
        .eq("whatsapp", whatsapp)\
        .execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Not a team member.")
    return {"member": result.data[0]}


@app.post("/team/products")
def team_add_product(product: dict):
    """Team adds a product from catalogue review — goes live immediately"""
    seller_id = product.get("seller_id")
    catalogue_id = product.get("catalogue_id")
    tags = product.get("tags", [])
    tags_text = " ".join([f"{t.get('key','')} {t.get('value','')}" for t in tags])
    embed_text = f"""
Product: {product.get('product_name','')}
Brand: {product.get('brand','')}
Category: {product.get('category','')}
Industry: {product.get('industry','')}
Description: {product.get('description','')}
Material: {product.get('material','')}
Color: {product.get('color','')}
Dimensions: {product.get('dimensions','')}
Use cases: {product.get('use_cases','')}
{tags_text}
"""
    vector = embed(embed_text)
    result = supabase.table("products").insert({
        "seller_id": seller_id,
        "catalogue_id": catalogue_id,
        "product_name": product.get("product_name",""),
        "product_code": product.get("product_code",""),
        "brand": product.get("brand",""),
        "series_name": product.get("series_name",""),
        "category": product.get("category",""),
        "industry": product.get("industry",""),
        "description": product.get("description",""),
        "material": product.get("material",""),
        "color": product.get("color",""),
        "dimensions": product.get("dimensions",""),
        "finish_grade": product.get("finish_grade",""),
        "use_cases": product.get("use_cases",""),
        "suitable_for": product.get("suitable_for",""),
        "certifications": product.get("certifications",""),
        "country_of_origin": product.get("country_of_origin",""),
        "unit_of_measure": product.get("unit_of_measure",""),
        "min_order": int(product.get("min_order") or 0),
        "price_per_unit": float(product.get("price_per_unit") or 0),
        "tags": tags,
        "image_url": product.get("image_url",""),
        "status": "live",
        "added_by": product.get("added_by","team"),
        "embedding": vector,
    }).execute()
    if catalogue_id:
        try:
            cat = supabase.table("catalogues").select("products_extracted").eq("id", catalogue_id).execute()
            if cat.data:
                supabase.table("catalogues").update({
                    "products_extracted": cat.data[0]["products_extracted"] + 1
                }).eq("id", catalogue_id).execute()
        except:
            pass
    return {"product": result.data[0]}


@app.post("/team/products/temp/image")
async def upload_temp_image(file: UploadFile = File(...)):
    """Upload product image from team portal"""
    content = await file.read()
    file_path = f"products/temp/{file.filename}"
    supabase.storage.from_("chat-files").upload(
        file_path, content,
        {"content-type": file.content_type, "upsert": "true"}
    )
    url = supabase.storage.from_("chat-files").get_public_url(file_path)
    return {"image_url": url}


@app.get("/team/catalogues/{catalogue_id}/products")
def get_catalogue_products(catalogue_id: str):
    """Get all products for a catalogue (for team portal pre-fill)"""
    result = supabase.table("products").select(
        "id, seller_id, catalogue_id, product_name, product_code, brand, series_name, "
        "category, industry, description, material, color, dimensions, finish_grade, "
        "use_cases, suitable_for, certifications, country_of_origin, unit_of_measure, "
        "min_order, price_per_unit, image_url, tags, status, added_by"
    ).eq("catalogue_id", catalogue_id).execute()
    return {"products": result.data}


@app.patch("/sellers/{seller_id}/catalogues/{catalogue_id}/status")
def update_catalogue_status(seller_id: str, catalogue_id: str, body: dict):
    """Mark catalogue as done"""
    supabase.table("catalogues").update({"status": body.get("status", "done")}).eq("id", catalogue_id).execute()
    return {"updated": True}



@app.get("/products/{product_id}")
def get_product(product_id: str):
    """Get single product with seller details"""
    result = supabase.table("products").select(
        "id, seller_id, product_name, product_code, brand, series_name, category, industry, description, material, color, dimensions, finish_grade, use_cases, suitable_for, certifications, country_of_origin, unit_of_measure, min_order, price_per_unit, tags, image_url, created_at"
    ).eq("id", product_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Product not found")
    product = result.data[0]
    seller = supabase.table("sellers").select(
        "id, name, category, city, area, trust_score, whatsapp"
    ).eq("id", product["seller_id"]).execute()
    return {"product": product, "seller": seller.data[0] if seller.data else {}}


@app.patch("/products/{product_id}")
def update_product(product_id: str, product: dict):
    """Update product and re-embed"""
    tags = product.get("tags", [])
    tags_text = " ".join([f"{t.get('key','')} {t.get('value','')}" for t in tags])
    text = f"""
Product: {product.get('product_name','')}
Brand: {product.get('brand','')}
Category: {product.get('category','')}
Industry: {product.get('industry','')}
Description: {product.get('description','')}
Material: {product.get('material','')}
Color: {product.get('color','')}
Use cases: {product.get('use_cases','')}
{tags_text}
"""
    product["embedding"] = embed(text)
    result = supabase.table("products").update(product).eq("id", product_id).execute()
    return {"product": result.data[0]}


@app.delete("/products/{product_id}")
def delete_product(product_id: str):
    # Get catalogue_id before deleting
    product = supabase.table("products").select("catalogue_id").eq("id", product_id).execute()
    supabase.table("products").delete().eq("id", product_id).execute()
    # Decrement products_extracted on the catalogue
    if product.data and product.data[0].get("catalogue_id"):
        cat_id = product.data[0]["catalogue_id"]
        try:
            cat = supabase.table("catalogues").select("products_extracted").eq("id", cat_id).execute()
            if cat.data:
                new_count = max(0, cat.data[0]["products_extracted"] - 1)
                supabase.table("catalogues").update({"products_extracted": new_count}).eq("id", cat_id).execute()
        except:
            pass
    return {"deleted": True}

@app.post("/team/ai-summary")
async def ai_summary(body: dict):
    """Proxy for Anthropic AI summary generation"""
    row = body.get("row", {})
    prompt = f"""Write a 2-3 sentence product description for a B2B marketplace listing. Be specific and professional.
Name: {row.get('product_name','')}
Brand: {row.get('brand','')}
Industry: {row.get('industry','')}
Category: {row.get('category','')}
Material: {row.get('material','')}
Color: {row.get('color','')}
Dimensions: {row.get('dimensions','')}
Certifications: {row.get('certifications','')}
Price: {row.get('price_per_unit','')} per {row.get('unit_of_measure','')}
MOQ: {row.get('min_order','')}
Extra: {row.get('finish_grade','')} {row.get('use_cases','')}
Return only the description, no preamble."""

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return {"summary": response.choices[0].message.content.strip()}

