-- ApnaGhar now serves Patna. Only defaults change; historical rows stay unchanged.
alter table public.properties alter column city set default 'Patna';
alter table public.leads alter column preferred_city set default 'Patna';
