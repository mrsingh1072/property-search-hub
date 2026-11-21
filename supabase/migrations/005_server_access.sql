-- ApnaGhar uses FastAPI for access control and a server-only service-role key.
-- These tables must never be readable with the browser's Supabase anon key.
alter table public.properties enable row level security;
alter table public.brokers enable row level security;
alter table public.leads enable row level security;
alter table public.sessions enable row level security;
alter table public.meetings enable row level security;
alter table public.customers enable row level security;
alter table public.broker_confirmations enable row level security;

-- Remove the old unrestricted upload/delete policies from migration 002.
drop policy if exists "Brokers can upload property images" on storage.objects;
drop policy if exists "Brokers can delete property images" on storage.objects;

revoke execute on function public.match_properties(vector, double precision, integer, text, bigint, bigint, integer, text) from public, anon, authenticated;
revoke execute on function public.mark_property_booked(text) from public, anon, authenticated;
grant execute on function public.match_properties(vector, double precision, integer, text, bigint, bigint, integer, text) to service_role;
grant execute on function public.mark_property_booked(text) to service_role;
