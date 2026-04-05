# Sabaro Project — Claude Context File

## Stack
- Frontend: React + Vite → Vercel (https://sabaro-app.vercel.app)
- Backend: FastAPI → Render (https://sabaro-api.onrender.com)
- DB: Supabase (postgres + realtime + storage)
- AI: OpenAI (embeddings + extraction)
- GitHub: kapiljainkjn-sys/sabaro-app

## Deployment Commands
```bash
# Frontend
cd Desktop\sabaro-app
git add -A && git commit -m "msg" && git push --force

# Backend
cd Desktop\sabaro-search
git add . && git commit -m "msg" && git push
```

## File Architecture
```
src/
├── main.jsx
├── App.jsx                    ← slim router, openChat, bookService, viewSeller
├── constants.js               ← S, C, API, normalizeSeller (20+ fields)
├── hooks.js                   ← useIsMobile, useSpeechRecognition, saveHistory, saveProductVisit
├── components/
│   ├── BottomNav.jsx
│   └── GlobalStyles.jsx
├── screens/
│   ├── HomeScreen.jsx         ← REBUILT: new layout, timeline how-it-works, modern icons
│   ├── HistoryScreen.jsx      ← REBUILT: product visit history (not keywords)
│   ├── ListingScreen.jsx      ← FilterPanel + SupplierCard
│   ├── AccountScreen.jsx      ← bookmarks, bookings, requirements, callbacks
│   ├── BookingScreen.jsx
│   ├── ChatScreen.jsx         ← identity gate as overlay bottom sheet
│   └── SellerProfileScreen.jsx ← mobile 5-tab + desktop 2-col + bookmark button
├── SellerDashboard/
│   ├── index.jsx
│   ├── SellerLogin.jsx
│   ├── SellerShell.jsx
│   ├── SellerHelpers.jsx
│   ├── HomeTab.jsx
│   ├── BookingsTab.jsx
│   ├── ProductsTab.jsx        ← CatalogueUploadSection lives here
│   ├── LeadsTab.jsx
│   ├── VerificationTab.jsx
│   └── ProfileTab.jsx
└── ProductPage.jsx            ← /p/{id}, calls saveProductVisit on load
```

## Screen Constants (S)
```js
S = { HOME, LISTING, PROFILE, BOOKING, CHAT, HISTORY, ACCOUNT }
```

## Colour Tokens (C)
```js
C = {
  bg, card, navBg, navMid,
  primary, bright, sky, electric,
  tint, tintMid, tintDark,
  border, borderMid,
  gold, goldBg, goldBorder,
  green, greenBg, greenBorder,
  purple, purpleBg, purpleBorder,
  text, textMid, textLight,
}
```

## Key Hooks / Helpers
- `useIsMobile()` — breakpoint 768px
- `useSpeechRecognition()` — Web Speech API, lang en-IN
- `saveHistory(query)` — localStorage sabaro_history (max 30)
- `saveProductVisit({product_id, product_name, seller_name, city, price, unit, image_url, category})` — localStorage sabaro_product_visits (max 100)

## HomeScreen.jsx (REBUILT this session)
Layout (mobile):
1. Nav — logo + Sell on Sabaro dropdown
2. Hero (dark navy) — headline + search bar (Enter to search, mic icon only) + photo search + custom requirement cards (same blue tint style) + stats
3. White section:
   - All Sellers (C.primary blue) + Near me side by side
   - Browse by industry — 3-col grid, modern SVG icons (Packaging/Raw Materials/Fabrication/Chemicals/Hotel & Kitchen/Auto Parts)
   - How it works — 6-step vertical timeline with coloured step icons + connecting lines (Search → Trust → Sample → Inspect → Transport → Pay safe)
4. BottomNav

Key decisions:
- No Search button — Enter key only
- Mic = icon only, no text label
- All Sellers = C.primary (not dark navy)
- Photo search + Custom requirement = same rgba(96,165,250,0.13) style on dark hero
- "Why Sabaro is different" section removed — merged into How It Works timeline
- "VERIFIED BY PROOF" pill removed from hero

## HistoryScreen.jsx (REBUILT this session)
- Reads `sabaro_product_visits` from localStorage
- Shows product cards grouped by date with image, seller, price, category, time ago
- Filter: Today / This week / All
- Empty state with "Browse suppliers →" CTA
- Links to `/p/{product_id}` on click

## AccountScreen.jsx — Bookmarks feature added
- `bookmarks` state reads from `sabaro_bookmarks` localStorage
- "Saved Sellers" AccRow in Quick Access section
- Bookmarks view: list of saved sellers with avatar, trust pill, View → and Remove
- `getBookmarks()` / `toggleBookmark()` helpers defined at top of SellerProfileScreen.jsx

## SellerProfileScreen.jsx — Bookmarks added
- `getBookmarks()` / `toggleBookmark()` at file top
- `bookmarked` state + `handleBookmark` inside component
- Mobile: bookmark icon in header top row + "Save/Saved" button in CTA bar
- Desktop: "Save seller" button in Sidebar after Call button
- localStorage key: `sabaro_bookmarks` [{type, id, name, sub, city, trust, timestamp}]

## ChatScreen.jsx — Fixes applied
- `showIdentityGate` + `pendingConvo` states inside component (not module level)
- Identity gate shows as bottom sheet overlay when tapping a conversation (not full screen block)
- BottomNav always visible on mobile (both list and window views)
- `needsIdentity` early return removed

## AccountScreen.jsx — Hook fixes
- All useState calls at top of component (none inside if blocks)
- `eName` initialized from localStorage directly: `useState(() => localStorage.getItem("sabaro_buyer_name") || "Buyer")`

## BookingScreen.jsx — Copy improvements
- "Select seller above" → "Pick a supplier to check what services are available"
- "Sample" → "Get a sample before ordering"
- "Inspection" → "Send an inspector before it ships"
- "Transport" → "Arrange delivery of your order"
- Discovery stage: "What would you like to do with {seller}?"

## ProductPage.jsx — saveProductVisit wired
```js
// Inside useEffect after product loads:
saveProductVisit({
  product_id:   d.product.id,
  product_name: d.product.product_name,
  seller_name:  d.seller?.name,
  city:         d.seller?.city,
  price:        d.product.price_per_unit,
  unit:         d.product.unit_of_measure,
  image_url:    d.product.image_url,
  category:     d.product.category,
});
```

## localStorage Keys (buyer-side)
- `sabaro_buyer_name`, `sabaro_buyer_phone` — identity
- `sabaro_history` — search history [{query, timestamp}] max 30
- `sabaro_product_visits` — product views [{product_id, product_name, seller_name, city, price, unit, image_url, category, timestamp}] max 100
- `sabaro_bookmarks` — saved sellers [{type, id, name, sub, city, trust, timestamp}]
- `sabaro_requirements` — custom requirements
- `sabaro_callbacks` — callback requests
- `sabaro_seller` — seller session
- `sabaro_team` — team portal session

## Critical Rules (Never Break)
- NEVER `SELECT *` on products — `search_text` / `embedding` break JSON serialization
- React import must be first in every file
- All `useState` calls must be at top of component body — never inside `if` blocks
- Vite oxc parser rejects IIFEs inside JSX — extract logic into variables before return
- Windows case-insensitivity: use `git mv` for file renames, never regular rename
- SellerDashboard: all tab files flat in one folder, no subfolders
- `normalizeSeller` must include all 20+ fields incl. topProducts, matchedProduct

## SupplierCard Patterns
- 80% image strip: horizontal scroll of product tiles
- Trust badge overlaid top-left, verif dots top-right
- Action buttons: View Profile | Message | 📞 callback
- 📞 saves to `sabaro_callbacks`

## SellerDashboard Patterns
- Login: WhatsApp + password → `sabaro_seller` localStorage
- 5 tabs mobile: Home | Products | Bookings | Leads | Verify
- Profile avatar in topbar → navigates to ProfileTab
- Logout in ProfileTab
- CatalogueTab deleted — catalogue upload in ProductsTab as CatalogueUploadSection
- Public seller profile: `/?seller=id` URL param, App.jsx useEffect handles it

## TeamPortal Patterns
- Login: WhatsApp → `team_members` table → `sabaro_team` localStorage
- Kapil admin number: 9800000000
- Views: TeamLogin → CatalogueList → SplitScreenTool
- PDF.js: fetch → arrayBuffer approach (not direct URL — QUIC error otherwise)
- High-res crop: scale = 2.0 × devicePixelRatio

## API Endpoints
```
GET  /sellers
GET  /sellers/{id}
POST /sellers/register
POST /sellers/login
PATCH /sellers/{id}
POST /sellers/{id}/products
PATCH /products/{id}
DELETE /products/{id}
GET  /products/{id}
POST /sellers/{id}/catalogues
GET  /sellers/{id}/catalogues
PATCH /sellers/{id}/catalogues/{id}/status
POST /search
GET  /team/login/{whatsapp}
GET  /team/catalogues
GET  /team/catalogues/{id}/products
POST /team/products
POST /team/ai-summary
POST /conversations/start
GET  /conversations/buyer/{phone}
GET  /conversations/{id}/messages
POST /messages/send
POST /chat/upload
POST /bookings
POST /bookings/{id}/confirm
```

## Database Tables
sellers, products, bookings, conversations, messages, catalogues, team_members

## Trust Score Tiers
- Starter: 0–59
- Verified: 60–79
- Premium: 80+

## Build Status

### DONE
- Buyer marketplace with AI semantic search (3-tier)
- Booking flows: Sample, Inspection, Transport
- Seller registration (4-step)
- Seller dashboard: Home, Bookings, Products, Leads, Verification, Profile
- Team portal: split-screen PDF review, spreadsheet, AI summary
- Chat: overlay identity gate, WhatsApp UI, file upload, BottomNav always visible
- ChatScreen: identity gate as bottom sheet (not full screen block)
- AccountScreen: buyer profile, callbacks, requirements, bookmarks, search history
- HistoryScreen: product visit history grouped by date (not keywords)
- SellerProfileScreen: bookmark save/unsave on mobile + desktop
- HomeScreen: full redesign — timeline how-it-works, modern SVG industry icons, photo+custom req cards, all sellers+near me banner
- ProductPage: saveProductVisit wired on load
- SVG nav icons across all bottom navs
- Seller tiers: Starter/Verified/Premium

### PENDING
- Run `match_products()` SQL in Supabase (unblocks vector search tier 3)
- Wire Message button on SupplierCard to open ChatScreen
- Fix catalogue save to DB on seller dashboard upload (unblocks team portal queue)
- Wire desktop nav Account/History icons in ListingScreen/HomeScreen
- WhatsApp notifications (Twilio)
- Real Razorpay integration
- API security (CORS lock, auth tokens)
- Render paid upgrade (stops sleeping)
- Catalogue AI chunking for 200+ products

## Known Issues
1. Render sleeps after 15 min — wake at https://sabaro-api.onrender.com/
2. Frontend: always use `git push --force`
3. NEVER `SELECT *` on products
4. No real auth — WhatsApp lookup only
5. Open CORS — lock before production
6. match_products() SQL not yet created in Supabase
7. Catalogue save to DB on upload not verified working

## Session Protocol
- "start session" → upload CLAUDE.md, Claude recaps where we left off
- "end session" → Claude generates daily progress log
- "update CLAUDE.md" → Claude updates this file
- Full docs: Sabaro-Documentation.docx