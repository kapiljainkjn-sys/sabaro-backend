import os
from dotenv import load_dotenv
from supabase import create_client
from openai import OpenAI


load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def embed(text):
    """Convert text to vector using OpenAI — one time per product"""
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding


def add_seller(seller_data):
    """Add a seller to the database"""
    result = supabase.table("sellers").insert({
        "name": seller_data["name"],
        "category": seller_data["category"],
        "city": seller_data["city"],
        "area": seller_data["area"],
        "since": seller_data["since"],
        "trust_score": seller_data["trust_score"],
        "shipments": seller_data["shipments"],
        "recommendations": seller_data["recommendations"],
        "sample_available": seller_data["sample_available"],
        "inspection_available": seller_data["inspection_available"],
        "transport_available": seller_data["transport_available"],
        "price_range": seller_data["price_range"],
        "moq": seller_data["moq"],
        "whatsapp": seller_data.get("whatsapp", ""),
    }).execute()

    seller_id = result.data[0]["id"]
    print(f"✅ Seller added: {seller_data['name']} → {seller_id}")
    return seller_id


def add_product(seller_id, product):
    """Embed a product and store in database"""

    # Create rich text for embedding
    text = f"""
    Product: {product['name']}
    Description: {product.get('description', '')}
    Material: {product.get('material', '')}
    Use cases: {product.get('use_cases', '')}
    Minimum order: {product.get('min_order', '')}
    Price per unit: {product.get('price_per_unit', '')}
    """

    # Convert to vector locally — no API call, free
    vector = embed(text)

    # Store in Supabase
    supabase.table("products").insert({
        "seller_id": seller_id,
        "product_name": product["name"],
        "description": product.get("description", ""),
        "material": product.get("material", ""),
        "use_cases": product.get("use_cases", ""),
        "min_order": product.get("min_order", 0),
        "price_per_unit": product.get("price_per_unit", 0),
        "embedding": vector,
    }).execute()

    print(f"   ✅ Product embedded: {product['name']}")


def ingest_seller(seller_data, products):
    """Full pipeline — add seller + all their products"""
    print(f"\nIngesting: {seller_data['name']}...")
    seller_id = add_seller(seller_data)
    for product in products:
        add_product(seller_id, product)
    print(f"✅ Done: {seller_data['name']} — {len(products)} products")
    return seller_id


# ── SELLER DATA ────────────────────────────────────────────────────────────────
if __name__ == "__main__":

    sellers = [
        {
            "data": {
                "name": "Sharma Packaging",
                "category": "Food & Retail Packaging",
                "city": "Ahmedabad",
                "area": "Odhav GIDC",
                "since": 2015,
                "trust_score": 94,
                "shipments": 847,
                "recommendations": 312,
                "sample_available": True,
                "inspection_available": True,
                "transport_available": True,
                "price_range": "₹8–₹14 per unit",
                "moq": "500 units",
                "whatsapp": "919800000001",
            },
            "products": [
                {
                    "name": "5-ply Corrugated Box",
                    "description": "Heavy duty 5-ply corrugated box for industrial and food packaging",
                    "material": "Corrugated cardboard, kraft paper",
                    "use_cases": "Food packaging, e-commerce shipping, industrial goods",
                    "min_order": 500,
                    "price_per_unit": 12,
                },
                {
                    "name": "3-ply Corrugated Box",
                    "description": "Standard 3-ply corrugated box for retail packaging",
                    "material": "Corrugated cardboard",
                    "use_cases": "Retail packaging, light goods, gifting",
                    "min_order": 500,
                    "price_per_unit": 8,
                },
                {
                    "name": "Mono Carton",
                    "description": "Single layer carton for pharmaceutical and FMCG packaging",
                    "material": "Duplex board, SBS board",
                    "use_cases": "Pharma packaging, FMCG, cosmetics",
                    "min_order": 1000,
                    "price_per_unit": 5,
                },
            ]
        },
        {
            "data": {
                "name": "Rajat Polymers",
                "category": "Flexible Packaging",
                "city": "Ahmedabad",
                "area": "Naroda Industrial",
                "since": 2019,
                "trust_score": 71,
                "shipments": 234,
                "recommendations": 89,
                "sample_available": True,
                "inspection_available": False,
                "transport_available": True,
                "price_range": "₹4–₹9 per unit",
                "moq": "1000 units",
                "whatsapp": "919800000002",
            },
            "products": [
                {
                    "name": "BOPP Bags",
                    "description": "Biaxially oriented polypropylene bags for food and retail",
                    "material": "BOPP film",
                    "use_cases": "Food packaging, snacks, dry fruits, retail",
                    "min_order": 1000,
                    "price_per_unit": 6,
                },
                {
                    "name": "PP Woven Bags",
                    "description": "Polypropylene woven bags for bulk material storage",
                    "material": "PP woven fabric",
                    "use_cases": "Agriculture, chemicals, construction, bulk storage",
                    "min_order": 500,
                    "price_per_unit": 9,
                },
                {
                    "name": "Laminated Pouches",
                    "description": "Multi-layer laminated pouches for food and pharma",
                    "material": "PET/PE laminate",
                    "use_cases": "Food packaging, pharma, moisture barrier packaging",
                    "min_order": 2000,
                    "price_per_unit": 4,
                },
            ]
        },
        {
            "data": {
                "name": "Patel Print & Pack",
                "category": "Custom Printed Packaging",
                "city": "Ahmedabad",
                "area": "Kathwada GIDC",
                "since": 2017,
                "trust_score": 83,
                "shipments": 521,
                "recommendations": 198,
                "sample_available": True,
                "inspection_available": True,
                "transport_available": True,
                "price_range": "₹10–₹22 per unit",
                "moq": "300 units",
                "whatsapp": "919800000003",
            },
            "products": [
                {
                    "name": "Custom Printed Box",
                    "description": "Full colour custom printed corrugated box for branding",
                    "material": "Corrugated with offset print",
                    "use_cases": "Brand packaging, gifting, e-commerce, retail",
                    "min_order": 300,
                    "price_per_unit": 18,
                },
                {
                    "name": "Offset Printed Carton",
                    "description": "High quality offset printed mono carton",
                    "material": "Duplex board with offset print",
                    "use_cases": "FMCG, pharma, retail product packaging",
                    "min_order": 500,
                    "price_per_unit": 14,
                },
            ]
        },
    ]

    print("\n🚀 Starting ingestion...\n")
    for seller in sellers:
        ingest_seller(seller["data"], seller["products"])

    print("\n🎉 All sellers loaded into Supabase!")
    print("Run search.py next to test AI search.")
