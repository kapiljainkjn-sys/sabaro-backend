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
  App.jsx              - Buyer marketplace (~1800 lines)
  Seller.jsx           - Seller registration (4-step)
  SellerDashboard.jsx  - Seller dashboard
  TeamPortal.jsx       - Team review tool (split screen spreadsheet)
  Chat.jsx             - Messaging (buyer identity gate + WhatsApp-style UI)
  ProductPage.jsx      - SEO product page (/p/{id}) — LIVE, wired in main.jsx
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
/p/{product_id}      → ProductPage.jsx (LIVE)

## App.jsx Key Patterns
- S = {HOME, LISTING, PROFILE, SAMPLE, INSPECTION, TRANSPORT, CHAT, HISTORY, ACCOUNT}
- C = colour tokens object
- API = "https://sabaro-api.onrender.com"
- normalizeSeller() maps API fields to component fields
  IMPORTANT: must include topProducts: s.top_products ?? [] and matchedProduct: s.matched_product ?? null
- useIsMobile() hook, breakpoint 768px
- useSpeechRecognition() hook — Web Speech API, lang en-IN
- saveHistory(query) — saves to localStorage sabaro_history (max 30)
- NAV_ICONS — Feather-style SVG icons for bottom nav (Home/History/Quote/Chat/Account)
- allSellers = hardcoded mock sellers (fallback)

## Screens in App.jsx
- HomeScreen — search, industry browse, photo search, custom requirement, mic search
- ListingScreen — search results, filter panel, mic + photo in search bar
- HistoryScreen — localStorage search history, clickable to re-search
- AccountScreen — buyer profile (name + WhatsApp), callbacks, requirements, searches
- SellerProfileScreen — tabs: Trust, Products, Reviews, Book, Contact
- SampleFlow / InspectionFlow / TransportFlow — booking flows

## SupplierCard Key Patterns (App.jsx)
- 80% image strip: horizontal scroll of product tiles (174px mobile, 190px desktop)
  - Trust badge overlaid top-left (dark glass pill with SVG ring + name)
  - Verif dots overlaid top-right (dark glass pill, 5 dots + count)
- 20% info strip: recommendations/shipments + service pills + action buttons
- Action buttons: View Profile | 💬 Message | 📞 (callback icon)
- 📞 saves to localStorage sabaro_callbacks, visible in AccountScreen
- Verification expand: 🛡️ chip → 5-row dropdown with CTAs
- Shows "👍 X recommended" instead of shipments when recommendations > 0

## SellerDashboard.jsx Key Patterns
- Login: WhatsApp + password, stored in localStorage as sabaro_seller
- Tabs: Home, Bookings, Products, Catalogue, Leads 🔥, Verification, Profile
- LeadsTab: product view metrics, callback queue, tier system (Starter/Verified/Premium), locked analytics
- VerificationTab: trust score ring, 5-step checklist with actionable CTAs
- EditProfile (enhanced): completion bar, 10+ fields incl. description, GST, certifications, machinery, capacity, export countries, Instagram, website
- ProductsTab: spreadsheet table view with image, all columns, View/Del actions
- CatalogueUpload: saves record ONLY (no AI extraction) — two separate FormData calls

## TeamPortal.jsx Key Patterns
- Login: WhatsApp → team_members table, stored as sabaro_team in localStorage
- Kapil's number: 9800000000 (admin)
- Views: TeamLogin → CatalogueList → SplitScreenTool
- SplitScreenTool:
  - LEFT: PDF rendered via PDF.js canvas (fetch → arrayBuffer approach)
    - High-res rendering: scale = 2.0 × devicePixelRatio (eliminates blurry crops)
    - CSS size set separately from canvas internal size
    - Read Text toggle: extracts page text via getTextContent(), Copy all button
  - RIGHT: Spreadsheet table — one row per product variant
  - On open: loads existing products via GET /team/catalogues/{id}/products
  - saveRow: PATCH /products/{id} if _product_id exists, else POST /team/products
  - AI summary: calls POST /team/ai-summary (backend proxy)
  - markDone: PATCH /sellers/{seller_id}/catalogues/{catalogue_id}/status → "done"

## Chat.jsx
- BuyerIdentityGate: WhatsApp + name gate, persists to localStorage
  sabaro_buyer_name, sabaro_buyer_phone
- ConversationList: polls /conversations/buyer/{phone} every 10s
- ChatWindow: WhatsApp-style bubbles, quick replies, file/image preview, read receipts
- Synced with AccountScreen — same localStorage keys

## LocalStorage Keys (buyer-side)
- sabaro_buyer_name, sabaro_buyer_phone — identity (shared across chat + account)
- sabaro_history — search history [{query, timestamp}] max 30
- sabaro_requirements — custom requirements [{category, desc, qty, city, phone, timestamp}]
- sabaro_callbacks — callback requests [{sellerId, sellerName, city, timestamp, status}]
- sabaro_reviews_{sellerId} — reviews per seller [{id, name, rating, comment, date}]

## API Endpoints (api.py)
GET  /sellers
GET  /sellers/{id}
GET  /sellers/{id}/dashboard
POST /sellers/register
POST /sellers/login
PATCH /sellers/{id}
POST /sellers/{id}/products
PATCH /products/{id}
DELETE /products/{id}
GET  /products/{id}
POST /sellers/{id}/catalogue          ← AI extraction (legacy)
POST /sellers/{id}/catalogues         ← save catalogue record
GET  /sellers/{id}/catalogues
PATCH /sellers/{id}/catalogues/{id}/status
POST /search                          ← 3-tier search (fulltext + attribute + vector)
GET  /team/login/{whatsapp}
GET  /team/catalogues
GET  /team/catalogues/{id}/products
POST /team/products
POST /team/products/temp/image
POST /team/ai-summary
POST /conversations/start
GET  /conversations/buyer/{phone}
GET  /conversations/{id}/messages
POST /messages/send
POST /chat/upload
POST /bookings
POST /bookings/{id}/confirm

CRITICAL: Never SELECT search_text or embedding — causes JSON serialization error.

## Route Order in api.py (IMPORTANT)
FastAPI matches routes in order. These must appear BEFORE @app.get("/sellers/{seller_id}"):
- POST /sellers/register
- POST /sellers/login
- GET  /sellers/{id}/dashboard
- POST /sellers/{id}/catalogue
- POST /sellers/{id}/catalogues
- GET  /sellers/{id}/catalogues
- PATCH /sellers/{id}/catalogues/{id}/status

## Database Tables
sellers, products, bookings, conversations, messages, catalogues, team_members

products columns:
  Basic: product_name, product_code, brand, series_name, category, industry,
    description, material, color, dimensions, finish_grade, use_cases,
    suitable_for, certifications, country_of_origin, unit_of_measure,
    min_order, price_per_unit, image_url
  Search: tags(jsonb [{key,value}]), embedding(vector 1536), search_text(tsvector generated)
  Meta: id, seller_id, catalogue_id, status(live/pending_review), added_by, created_at

catalogues: id, seller_id, file_name, file_url, status(uploaded/done), products_extracted, created_at
team_members: id, name, whatsapp, role — Kapil: 9800000000, admin

## Search (3-tier — deployed)
Tier 1: Full-text tsvector search on products
Tier 2: Attribute/category ilike match + product name ilike
Tier 3: Semantic vector cosine similarity via match_products() RPC
Results merged, deduped, ranked by relevance + trust score
TODO: Run match_products() SQL function in Supabase SQL editor (in TeamAndSearchFixes.jsx)

## Trust Score
HIGH TRUST 80+, MEDIUM TRUST 60-79, BUILDING TRUST <60

## Seller Tiers
- Starter (0-59): basic listing, 3 products, search visibility
- Verified (60-79): 20 products, badge, basic analytics, email leads
- Premium (80+): unlimited products, featured placement, WhatsApp leads, priority search

## Deployment
Frontend: cd Desktop\sabaro-app → git add -A → git commit -m "msg" → git push --force
Backend:  cd Desktop\sabaro-search → git add . → git commit -m "msg" → git push
IMPORTANT: git mv required for case-sensitive renames on Windows (not regular rename)
IMPORTANT: Never paste terminal commands into source files

## Known Issues
1. Render sleeps after 15 min — wake at https://sabaro-api.onrender.com/
2. Frontend needs git push --force (history rewrite)
3. NEVER use SELECT * on products — search_text/embedding break JSON
4. Catalogue AI extracts only 7-15 of 200+ products (chunking not built)
5. No real auth — WhatsApp lookup only, no password verification
6. Open CORS — needs locking before production
7. PDF.js needs fetch → arrayBuffer approach (QUIC protocol error otherwise)
8. match_products() SQL function not yet created in Supabase (needed for vector search tier)
9. Message button on SupplierCard not wired to open chat
10. Desktop nav Account/History icons not wired to screens

## Build Status
DONE:
- Buyer marketplace with AI semantic search (3-tier)
- Booking flows: Sample, Inspection, Transport (mock Razorpay)
- Seller registration (4-step)
- Seller dashboard: Home, Bookings, Products (spreadsheet), Catalogue, Leads, Verification, Profile
- Team portal: full split-screen spreadsheet, HD PDF crops, text extraction
- Chat: buyer identity gate, WhatsApp-style UI, file upload, quick replies
- AccountScreen: buyer profile synced with chat, callbacks, requirements, search history
- HistoryScreen: search history with re-search
- SupplierCard: 80-20 image/info split, trust overlay, recommendations, 📞 callback
- SVG nav icons (Feather-style) across all bottom navs
- Photo search + mic search in HomeScreen and ListingScreen
- Custom requirement modal (localStorage)
- Reviews tab in seller profile
- FilterPanel (sort by trust/shipments/recommendations)
- ProductPage.jsx live at /p/{id}
- Seller tiers: Starter/Verified/Premium with locked analytics

PENDING:
- Run match_products() SQL in Supabase (unblocks vector search)
- Wire Message button on SupplierCard to open chat
- Fix catalogue save to DB on seller dashboard upload (unblocks team portal queue)
- Wire desktop nav Account/History icons
- WhatsApp notifications (Twilio)
- Real Razorpay
- API security (CORS, auth tokens)
- Render paid upgrade
- Catalogue AI chunking for 200+ products

## Session Protocol
- "start session" → upload CLAUDE.md, Claude recaps where we left off
- "end session" → Claude generates daily progress log
- "update CLAUDE.md" → Claude updates this file with latest progress
- Full docs: Sabaro-Documentation.docx