# SABARO — Project Context for Claude

## What is Sabaro?
B2B marketplace platform for India. Connects buyers with verified suppliers.
Core value: Trust scores built from real shipments, inspections, and shop visits.
Tagline: Verified by Proof, Not by Promise.

## Live URLs
- Buyer app: https://sabaro-app.vercel.app
- Seller dashboard: https://sabaro-app.vercel.app/seller/dashboard
- Seller register: https://sabaro-app.vercel.app/seller
- Team portal: https://sabaro-app.vercel.app/team
- Python API: https://sabaro-api.onrender.com
- GitHub frontend: https://github.com/kapiljainkjn-sys/sabaro-app
- GitHub backend: https://github.com/kapiljainkjn-sys/sabaro-backend

## Tech Stack
- Frontend: React + Vite → Vercel
- Backend: Python FastAPI → Render.com (free tier, sleeps after 15 min)
- Database: Supabase (PostgreSQL + pgvector)
- AI embeddings: OpenAI text-embedding-3-small (1536 dimensions)
- AI extraction: OpenAI GPT-4o-mini
- PDF reading: pypdf
- Storage: Supabase Storage (chat-files bucket) — RLS policy: allow all on chat-files
- Payments: Razorpay (mock UI only)
- Dev: Windows, Python 3.11, Node.js v24, VS Code

## Repository Structure
Desktop\sabaro-app\src\
  App.jsx              - Buyer marketplace (~1500 lines)
  Seller.jsx           - Seller registration (4-step)
  SellerDashboard.jsx  - Seller dashboard
  TeamPortal.jsx       - Team review tool (split screen spreadsheet)
  Chat.jsx             - Messaging
  ProductPage.jsx      - SEO product page (/p/{id})
  main.jsx             - Path-based router
  vercel.json          - SPA routing

Desktop\sabaro-search\
  api.py               - All API endpoints
  requirements.txt     - fastapi uvicorn supabase openai pypdf python-multipart pydantic python-dotenv
  .env                 - SUPABASE_URL, SUPABASE_KEY, OPENAI_API_KEY

## Routing
/                    → App.jsx
/seller              → Seller.jsx
/seller/dashboard    → SellerDashboard.jsx
/team                → TeamPortal.jsx
/p/{product_id}      → ProductPage.jsx

## App.jsx Key Patterns
- S = {HOME, LISTING, PROFILE, SAMPLE, INSPECTION, TRANSPORT, CHAT}
- C = colour tokens object
- API = "https://sabaro-api.onrender.com"
- normalizeSeller() maps API fields to component fields
- useIsMobile() hook, breakpoint 768px
- allSellers = hardcoded mock sellers (fallback)
- SellerProfileScreen fetches real products via GET /sellers/{id} on mount
- Products tab shows real products from API with image, description, price, MOQ

## SellerDashboard.jsx Key Patterns
- Login: WhatsApp + password (no real verification), stored in localStorage as sabaro_seller
- Tabs: Home, Bookings, Products, Catalogue, Profile
- CatalogueUpload: saves record ONLY (no AI extraction) — two separate FormData calls
- CatalogueTab: shows upload form + list of uploaded catalogues with status
- Products show with View → link to /p/{id}
- sellerIndustry = seller.category passed as prop

## TeamPortal.jsx Key Patterns
- Login: WhatsApp → team_members table, stored as sabaro_team in localStorage
- Kapil's number: 9800000000 (admin)
- Views: TeamLogin → CatalogueList → SplitScreenTool
- SplitScreenTool is a SPREADSHEET with:
  - LEFT: PDF rendered via PDF.js canvas
    IMPORTANT: Must fetch(url) → arrayBuffer → pdfjsLib.getDocument({data:arrayBuffer}) to avoid QUIC error
  - RIGHT: Spreadsheet table — one row per product variant
  - Catalogue defaults bar at top: industry, brand, category, certifications, country, unit
  - INDUSTRY_COLUMNS map — columns change based on industry selected
  - Active row (◉): click to set, cropped image goes to active row
  - ⊕ button: duplicate row (resets _saved, _saving, _generating, _product_id)
  - Save button per row → POST /team/products → live immediately
  - Save All button → saves all unsaved rows with product_name
  - After save: URL → and ✨ AI buttons appear
  - AI summary: calls Anthropic API (claude-sonnet-4-20250514), updates description field
  - emptyRow(defaults) function creates new row with shared defaults

## Chat.jsx
- Imported in App.jsx: import ChatScreen from "./Chat.jsx"
- State in App: showChat, chatSeller, buyerName, buyerPhone

## API Endpoints (api.py)
GET  /sellers
GET  /sellers/{id}                    ← explicit columns, NO search_text/embedding
GET  /sellers/{id}/dashboard          ← explicit columns, NO search_text/embedding
POST /sellers/register
POST /sellers/login
PATCH /sellers/{id}
POST /sellers/{id}/products           ← manual add with embedding
PATCH /products/{id}                  ← update + re-embed
DELETE /products/{id}
GET  /products/{id}                   ← for SEO product page
POST /sellers/{id}/catalogue          ← AI extraction (kept but not used in seller dashboard)
POST /sellers/{id}/catalogues         ← save catalogue record to DB + Supabase storage
GET  /sellers/{id}/catalogues         ← list catalogues for seller
POST /search                          ← AI semantic search
GET  /team/login/{whatsapp}
GET  /team/catalogues                 ← all catalogues for team queue
POST /team/products                   ← add product, goes live immediately with embedding
POST /team/products/temp/image        ← upload product image
POST /conversations/start
GET  /conversations/buyer/{phone}
GET  /conversations/{id}/messages
POST /messages/send
POST /chat/upload
POST /bookings
POST /bookings/{id}/confirm

CRITICAL: Never SELECT search_text or embedding — causes JSON serialization error.
Always use explicit column list for products queries.

## Route Order in api.py (IMPORTANT)
FastAPI matches routes in order. These must appear BEFORE @app.get("/sellers/{seller_id}"):
- @app.post("/sellers/register")
- @app.post("/sellers/login")
- @app.get("/sellers/{seller_id}/dashboard")
- @app.post("/sellers/{seller_id}/catalogue")
- @app.post("/sellers/{seller_id}/catalogues")
- @app.get("/sellers/{seller_id}/catalogues")

## Database Tables
sellers, products, bookings, conversations, messages, catalogues, team_members

products columns:
  Basic (shown on card): product_name, product_code, brand, series_name,
    category, industry, description, material, color, dimensions, finish_grade,
    use_cases, suitable_for, certifications, country_of_origin, unit_of_measure,
    min_order, price_per_unit, image_url
  Search: tags(jsonb [{key,value}]), embedding(vector 1536), search_text(tsvector generated)
  Meta: id, seller_id, catalogue_id, status(live/pending_review), added_by, created_at

catalogues: id, seller_id, file_name, file_url, status(uploaded/done), products_extracted, created_at
team_members: id, name, whatsapp, role — Kapil: 9800000000, admin

## Search
Current: embed query → search_products() RPC → rank by (similarity×0.5 + trust×0.5)
TODO: 3-layer search (keyword FTS + tags filter + semantic vector)
Indexes: products_fts_idx (gin/search_text), products_tags_idx (gin/tags), pgvector

## Trust Score
HIGH TRUST 80+, MEDIUM TRUST 60-79, BUILDING TRUST <60
final_score = (similarity × 0.5) + (trust_score/100 × 0.5)

## Deployment
Frontend: cd Desktop\sabaro-app → git add -A → git commit -m "msg" → git push --force
Backend:  cd Desktop\sabaro-search → git add . → git commit -m "msg" → git push

## Known Issues
1. Render sleeps after 15 min — wake at https://sabaro-api.onrender.com/
2. Frontend needs git push --force (history rewrite)
3. NEVER use SELECT * on products — search_text/embedding break JSON
4. Catalogue AI extracts only 7-15 of 200+ products (chunking not built)
5. No real auth — WhatsApp lookup only, no password verification
6. Open CORS — needs locking before production
7. PDF.js needs fetch → arrayBuffer approach (QUIC protocol error otherwise)

## Build Status
DONE:
- Buyer marketplace with AI semantic search
- Booking flows: Sample, Inspection, Transport (mock Razorpay)
- Seller registration (4-step)
- Seller dashboard: trust, bookings, products, catalogue list, profile
- Catalogue upload → storage + catalogues table (no AI, team reviews manually)
- Team portal: login, catalogue queue, split-screen spreadsheet tool
  - PDF.js canvas rendering with image crop
  - Industry-specific columns
  - Active row image assignment
  - Duplicate row
  - Save row/Save All → product goes live
  - URL per product after save
  - AI summary generation per product
- Products appear on seller dashboard Products tab
- Products appear on buyer app seller profile Products tab (fetched from API)
- Product SEO page at /p/{id} — built
- Chat/messaging
- Product schema: 18 basic columns + tags jsonb + 3 search indexes in Supabase

IN PROGRESS:
- Product SEO page /p/{id} — needs end-to-end testing
- 3-layer search (indexes ready, endpoint not updated)

PENDING:
- WhatsApp notifications (Twilio)
- Buyer login and account
- Real Razorpay
- Search history, quote requests
- API security (CORS, auth tokens)
- Render paid upgrade
- Catalogue AI chunking for 200+ products

## Session Protocol
- "start session" → upload CLAUDE.md, Claude recaps where we left off
- "end session" → Claude generates daily progress log
- "update CLAUDE.md" → Claude updates this file with latest progress
- Full docs: Sabaro-Documentation.docx