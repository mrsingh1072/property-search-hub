-- Completed purchases/rentals recorded by an approved listing broker.
-- Run after migrations 001-007. No existing leads or favourites become purchases.
begin;
create table if not exists public.property_transactions (
  id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references public.customers(id) on delete cascade,
  property_id text references public.properties(id) on delete set null,
  broker_id text references public.brokers(id) on delete set null,
  transaction_type text not null check (transaction_type in ('purchase','rent')),
  completed_on date not null,
  property_snapshot jsonb not null,
  recorded_by text not null,
  created_at timestamptz not null default now(),
  unique(property_id, customer_id, transaction_type, completed_on)
);
create index if not exists property_transactions_customer_idx on public.property_transactions(customer_id,completed_on desc);
alter table public.property_transactions enable row level security;
revoke all on public.property_transactions from anon, authenticated;
grant all on public.property_transactions to service_role;

create or replace function public.record_property_transaction(
  p_property_id text, p_customer_id uuid, p_broker_id text,
  p_transaction_type text, p_completed_on date, p_recorded_by text
) returns uuid language plpgsql security definer set search_path = public as $$
declare prop public.properties; existing_id uuid; result_id uuid;
begin
  if p_transaction_type is null or p_transaction_type not in ('purchase','rent') or p_completed_on is null
    or p_completed_on > (now() at time zone 'Asia/Kolkata')::date then
    raise exception 'Invalid completion details';
  end if;
  if not exists(select 1 from public.brokers where id=p_broker_id and approval_status='approved' and is_active=true) then
    raise exception 'Approved listing broker required';
  end if;
  select * into prop from public.properties where id=p_property_id and broker_id=p_broker_id for update;
  if not found then raise exception 'Listing not found'; end if;
  if prop.city is distinct from 'Patna' then raise exception 'Only Patna listings are supported'; end if;
  select id into existing_id from public.property_transactions where property_id=p_property_id
    and customer_id=p_customer_id and transaction_type=p_transaction_type and completed_on=p_completed_on;
  if found then return existing_id; end if;
  if coalesce(prop.status,'') not in ('available','booked','sold','rented') or
    (prop.status in ('sold','rented') and exists(select 1 from public.property_transactions where property_id=p_property_id)) then
    raise exception 'Listing already completed or unavailable';
  end if;
  insert into public.property_transactions(customer_id,property_id,broker_id,transaction_type,completed_on,recorded_by,property_snapshot)
  values(p_customer_id,p_property_id,p_broker_id,p_transaction_type,p_completed_on,p_recorded_by,
    jsonb_build_object('property_id',prop.id,'property_type',prop.property_type,'bhk',prop.bhk,
      'area_name',prop.area_name,'city',prop.city,'address',prop.data #>> '{metadata,raw_full_address}',
      'images',coalesce(prop.data->'images','[]'::jsonb))) returning id into result_id;
  update public.properties set status=case when p_transaction_type='purchase' then 'sold' else 'rented' end,
    updated_at=now() where id=p_property_id;
  return result_id;
end $$;
revoke all on function public.record_property_transaction(text,uuid,text,text,date,text) from public,anon,authenticated;
grant execute on function public.record_property_transaction(text,uuid,text,text,date,text) to service_role;
commit;
