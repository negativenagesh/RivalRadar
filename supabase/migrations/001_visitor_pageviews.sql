-- RivalRadar visitor analytics (run in Supabase SQL editor once).
-- Gateway inserts via service role; no public anon writes needed.

create table if not exists public.visitor_pageviews (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  visitor_id text not null,
  visitor_token text,
  path text not null,
  referrer text,
  title text,
  language text,
  timezone text,
  screen_w int,
  screen_h int,
  viewport_w int,
  viewport_h int,
  platform text,
  user_agent text,
  ip text,
  country text,
  region text,
  city text,
  host text
);

create index if not exists visitor_pageviews_created_at_idx on public.visitor_pageviews (created_at desc);
create index if not exists visitor_pageviews_visitor_id_idx on public.visitor_pageviews (visitor_id);
create index if not exists visitor_pageviews_path_idx on public.visitor_pageviews (path);

alter table public.visitor_pageviews enable row level security;

-- Service role bypasses RLS; block anon/authenticated direct reads/writes by default.
drop policy if exists "no anon access" on public.visitor_pageviews;
create policy "no anon access" on public.visitor_pageviews
  for all
  to anon, authenticated
  using (false)
  with check (false);
