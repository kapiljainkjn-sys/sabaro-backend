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
    """Convert search query to vector using OpenAI"""
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding


def search(query, limit=10):
    """AI search — finds sellers by meaning, not just keywords"""

    print(f"\n🔍 Searching: '{query}'")

    # Step 1 — convert query to vector
    query_vector = embed(query)

    # Step 2 — find matching products in Supabase
    matches = supabase.rpc("search_products", {
        "query_embedding": query_vector,
        "match_threshold": 0.3,
        "match_count": 20
    }).execute()

    if not matches.data:
        print("No matches found.")
        return []

    # Step 3 — get seller details for each match
    seller_ids = list(set([m["seller_id"] for m in matches.data]))
    sellers = supabase.table("sellers").select("*").in_("id", seller_ids).execute()

    # Step 4 — combine seller + match score + rank by trust
    results = []
    for seller in sellers.data:
        # Find best matching product for this seller
        seller_matches = [m for m in matches.data if m["seller_id"] == seller["id"]]
        best_match = max(seller_matches, key=lambda x: x["similarity"])

        # Trust weighted score
        semantic_score = best_match["similarity"]
        trust_score = seller["trust_score"] / 100
        final_score = (semantic_score * 0.5) + (trust_score * 0.5)

        results.append({
            "name": seller["name"],
            "category": seller["category"],
            "city": seller["city"],
            "trust_score": seller["trust_score"],
            "shipments": seller["shipments"],
            "price_range": seller["price_range"],
            "moq": seller["moq"],
            "matched_product": best_match["product_name"],
            "match_reason": best_match["description"],
            "semantic_score": round(semantic_score, 3),
            "final_score": round(final_score, 3),
        })

    # Sort by final score
    results.sort(key=lambda x: x["final_score"], reverse=True)

    # Print results
    print(f"Found {len(results)} sellers:\n")
    for i, r in enumerate(results):
        print(f"{i+1}. {r['name']} — Trust: {r['trust_score']} — Score: {r['final_score']}")
        print(f"   Matched: {r['matched_product']}")
        print(f"   {r['city']} · {r['price_range']} · MOQ {r['moq']}")
        print()

    return results


# ── TEST SEARCHES ──────────────────────────────────────────────────────────────
if __name__ == "__main__":

    # Test 1 — exact match
    search("corrugated box for food packaging")

    # Test 2 — different wording, should still find correct seller
    search("strong box for shipping products")

    # Test 3 — specific material
    search("moisture proof pouch for snacks")

    # Test 4 — vague query
    search("packaging for pharma")