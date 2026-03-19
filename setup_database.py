import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

print("Setting up Sabaro database...")

# We'll run this SQL directly in Supabase
# Go to Supabase → SQL Editor → paste and run this:

sql = """
-- Enable vector extension for AI search
create extension if not exists vector;

-- Sellers table
create table if not exists sellers (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  category text,
  city text,
  area text,
  since int,
  trust_score int default 50,
  shipments int default 0,
  buyer_recommendations int default 0,
  last_shipment text,
  decay_warning boolean default false,
  shop_proof boolean default false,
  shop_detail text,
  business_verified boolean default false,
  business_detail text,
  sample_available boolean default false,
  sample_detail text,
  inspection_available boolean default false,
  inspection_detail text,
  transport_available boolean default false,
  transport_detail text,
  inspection_videos int default 0,
  price_range text,
  moq text,
  whatsapp text,
  created_at timestamp default now()
);

-- Products table (with AI embedding)
create table if not exists products (
  id uuid primary key default gen_random_uuid(),
  seller_id uuid references sellers(id) on delete cascade,
  name text not null,
  description text,
  material text,
  use_cases text,
  min_order int,
  price_per_unit numeric,
  embedding vector(384),
  created_at timestamp default now()
);

-- Buyers table
create table if not exists buyers (
  id uuid primary key default gen_random_uuid(),
  name text,
  email text unique,
  phone text,
  city text,
  company text,
  created_at timestamp default now()
);

-- Bookings table
create table if not exists bookings (
  id uuid primary key default gen_random_uuid(),
  buyer_id uuid references buyers(id),
  seller_id uuid references sellers(id),
  type text check (type in ('sample', 'inspection', 'transport')),
  status text default 'pending' check (status in ('pending', 'confirmed', 'completed', 'cancelled', 'refunded')),
  amount int,
  details jsonb,
  created_at timestamp default now()
);

-- AI search function
create or replace function search_products(
  query_embedding vector(384),
  match_threshold float default 0.3,
  match_count int default 20
)
returns table (
  id uuid,
  seller_id uuid,
  name text,
  description text,
  similarity float
)
language sql stable
as $$
  select
    products.id,
    products.seller_id,
    products.name,
    products.description,
    1 - (products.embedding <=> query_embedding) as similarity
  from products
  where 1 - (products.embedding <=> query_embedding) > match_threshold
  order by products.embedding <=> query_embedding
  limit match_count;
$$;
"""

print(sql)
print("\n✅ Copy the SQL above and run it in:")
print("supabase.com → your project → SQL Editor → New query → paste → Run")