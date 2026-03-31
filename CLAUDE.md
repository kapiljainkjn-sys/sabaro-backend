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
- Storage: Supabase Storage (chat-files bucket)
- Payments: Razorpay (mock UI only)
- Dev: Windows, Python 3.11, Node.js v24, VS Code

## Repository Structure
Desktop\sabaro-app\src\
  App.jsx              - Buyer marketplace (~1500 lines)
  Seller.jsx           - Seller registration (4-step)
  SellerDashboard.jsx  - Seller dashboard
  TeamPortal.jsx       - Team review tool (split screen)
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

## SellerDashboard.jsx Key Patterns
- Login: WhatsApp lookup only, stored in localStorage as sabaro_seller
- Tabs: Home, Bookings, Products, Catalogue, Profile
- CatalogueUpload: two API calls (save record + AI extract)
- sellerIndustry = seller.category passed to CatalogueUpload

## TeamPortal.jsx Key Patterns
- Login: WhatsApp → team_members table, stored as sabaro_team
- PDF.js renders pages as canvas, click+drag to crop image
- POST /team/products → product goes live immediately

## Chat.jsx
- Imported in App.jsx: import ChatScreen from "./Chat.jsx"
- State in App: showChat, chatSeller, buyerName, buyerPhone

## API Endpoints (api.py)
GET  /sellers
POST /search
POST /sellers/register
POST /sellers/login
GET  /sellers/{id}/dashboard      ← explicit columns only, NO search_text or embedding
PATCH /sellers/{id}
POST /sellers/{id}/products
PATCH /products/{id}
DELETE /products/{id}
GET  /products/{id}
POST /sellers/{id}/catalogue      ← AI extraction
POST /sellers/{id}/catalogues     ← save record
GET  /sellers/{id}/catalogues
GET  /team/login/{whatsapp}
GET  /team/catalogues
POST /team/products
POST /team/products/temp/image
POST /conversations/start
GET  /conversations/buyer/{phone}
GET  /conversations/{id}/messages
POST /messages/send
POST /chat/upload
POST /bookings
POST /bookings/{id}/confirm

CRITICAL: Never SELECT search_text or embedding — causes JSON serialization error.

## Database Tables
sellers, products, bookings, conversations, messages, catalogues, team_members

products columns:
  Basic (shown on card): product_name, product_code, brand, series_name,
    category, industry, description, material, color, dimensions, finish_grade,
    use_cases, suitable_for, certifications, country_of_origin, unit_of_measure,
    min_order, price_per_unit, image_url
  Search: tags(jsonb [{key,value}]), embedding(vector 1536), search_text(tsvector generated)
  Meta: status, added_by, catalogue_id, created_at

Search indexes: products_fts_idx (gin/search_text), products_tags_idx (gin/tags), pgvector

## Search
Current: embed query → search_products() RPC → rank by (similarity×0.5 + trust×0.5)
TODO: 3-layer search (keyword FTS + tags filter + semantic vector)

## Trust Score
HIGH TRUST 80+, MEDIUM TRUST 60-79, BUILDING TRUST <60
final_score = (similarity × 0.5) + (trust_score/100 × 0.5)

## Deployment
Frontend: cd Desktop\sabaro-app → git add -A → git commit → git push --force
Backend:  cd Desktop\sabaro-search → git add . → git commit → git push

## Known Issues
1. Render sleeps after 15 min — wake at https://sabaro-api.onrender.com/
2. Frontend needs git push --force (history rewrite)
3. Never use SELECT * on products — search_text/embedding break JSON
4. Catalogue extracts only 7-15 of 200+ products (chunking not implemented)
5. No real auth — WhatsApp lookup only
6. Open CORS — needs locking before production

## Build Status
DONE: Buyer app, AI search, bookings (mock), seller registration,
      seller dashboard, catalogue upload+AI, product edit modal,
      team portal + split screen, chat, product schema

IN PROGRESS: Product SEO page, 3-layer search

PENDING: WhatsApp (Twilio), buyer login, real Razorpay,
         search history, quotes, API security

## Session Protocol
- "start session" → Claude recaps where we left off
- "end session" → Claude generates daily log