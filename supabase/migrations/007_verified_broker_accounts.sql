-- ApnaGhar: admin-reviewed broker accounts. Properties publish immediately.
-- Run once after migrations 001-006. No broker password is stored in public tables.
begin;
alter table public.brokers add column if not exists auth_user_id uuid references auth.users(id) on delete set null;
alter table public.brokers add column if not exists approval_status text not null default 'pending';
alter table public.brokers add column if not exists agency text;
alter table public.brokers add column if not exists verification_reference text;
alter table public.brokers add column if not exists reviewed_at timestamptz;
alter table public.brokers add column if not exists reviewed_by text;
alter table public.brokers alter column is_active set default false;
do $$ begin
  if not exists (select 1 from pg_constraint where conname = 'brokers_approval_status_check' and conrelid = 'public.brokers'::regclass) then
    alter table public.brokers add constraint brokers_approval_status_check
      check (approval_status in ('pending', 'approved', 'rejected', 'suspended'));
  end if;
end $$;
-- Existing shared-login profiles do not automatically become verified accounts.
update public.brokers set is_active = false where approval_status <> 'approved';
create unique index if not exists brokers_auth_user_idx on public.brokers(auth_user_id) where auth_user_id is not null;
create unique index if not exists brokers_account_email_idx on public.brokers(lower(email)) where auth_user_id is not null;
create unique index if not exists brokers_account_phone_idx on public.brokers(phone) where auth_user_id is not null;
alter table public.properties add column if not exists broker_id text references public.brokers(id);
update public.properties p set broker_id = b.id from public.brokers b
  where p.broker_id is null and p.data #>> '{source_ids,broker_id}' = b.id;
create index if not exists properties_broker_idx on public.properties(broker_id);
create table if not exists public.broker_reviews (
  id uuid primary key default gen_random_uuid(),
  broker_id text not null references public.brokers(id),
  action text not null check (action in ('approved', 'rejected', 'suspended')),
  reviewer text not null,
  note text not null default '',
  created_at timestamptz not null default now()
);
alter table public.broker_reviews enable row level security;
alter table public.brokers enable row level security;
revoke all on public.broker_reviews from anon, authenticated;
grant all on public.broker_reviews to service_role;
create or replace function public.review_broker_application(
  target_broker_id text, next_status text, reviewer_name text, review_note text default ''
) returns jsonb language plpgsql security definer set search_path = public as $$
declare result public.brokers;
begin
  if next_status not in ('approved', 'rejected', 'suspended') then
    raise exception 'Invalid review status';
  end if;
  update public.brokers set approval_status = next_status,
      is_active = (next_status = 'approved'), reviewed_at = now(), reviewed_by = reviewer_name
    where id = target_broker_id and auth_user_id is not null returning * into result;
  if not found then raise exception 'Broker account not found'; end if;
  insert into public.broker_reviews(broker_id, action, reviewer, note)
    values(target_broker_id, next_status, reviewer_name, coalesce(review_note, ''));
  return to_jsonb(result);
end $$;
revoke all on function public.review_broker_application(text, text, text, text) from public, anon, authenticated;
grant execute on function public.review_broker_application(text, text, text, text) to service_role;
commit;
