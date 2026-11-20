-- ApnaGhar: include customer login and CRM offer fields in normal migrations.
create table if not exists public.customers (
  id uuid primary key default gen_random_uuid(),
  email text unique not null,
  name text,
  phone text,
  google_sub text,
  favourites jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists customers_email_idx on public.customers (email);
alter table public.leads add column if not exists broker_offer text;
alter table public.leads add column if not exists customer_offer text;
