-- Me First · Perde: film yorumları ve beğenileri
-- Supabase > SQL Editor'e yapıştırıp bir kez "Run" de.

create table if not exists public.film_reviews (
  id uuid primary key default gen_random_uuid(),
  film_id text not null check (char_length(film_id) between 1 and 80),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  rating smallint check (rating between 1 and 5),
  body text not null default '' check (char_length(body) <= 600),
  spoiler boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (film_id, user_id)
);
create index if not exists film_reviews_film_idx on public.film_reviews (film_id, created_at desc);

create table if not exists public.film_review_likes (
  review_id uuid not null references public.film_reviews(id) on delete cascade,
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (review_id, user_id)
);

create table if not exists public.film_review_reports (
  id uuid primary key default gen_random_uuid(),
  review_id uuid not null references public.film_reviews(id) on delete cascade,
  user_id uuid not null default auth.uid(),
  created_at timestamptz not null default now(),
  unique (review_id, user_id)
);

alter table public.film_reviews enable row level security;
alter table public.film_review_likes enable row level security;
alter table public.film_review_reports enable row level security;

drop policy if exists "fr okuma" on public.film_reviews;
drop policy if exists "fr ekleme" on public.film_reviews;
drop policy if exists "fr guncelleme" on public.film_reviews;
drop policy if exists "fr silme" on public.film_reviews;
create policy "fr okuma" on public.film_reviews for select using (true);
create policy "fr ekleme" on public.film_reviews for insert to authenticated with check (auth.uid() = user_id);
create policy "fr guncelleme" on public.film_reviews for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "fr silme" on public.film_reviews for delete to authenticated using (auth.uid() = user_id);

drop policy if exists "frl okuma" on public.film_review_likes;
drop policy if exists "frl ekleme" on public.film_review_likes;
drop policy if exists "frl silme" on public.film_review_likes;
create policy "frl okuma" on public.film_review_likes for select using (true);
create policy "frl ekleme" on public.film_review_likes for insert to authenticated with check (auth.uid() = user_id);
create policy "frl silme" on public.film_review_likes for delete to authenticated using (auth.uid() = user_id);

drop policy if exists "frr ekleme" on public.film_review_reports;
create policy "frr ekleme" on public.film_review_reports for insert to authenticated with check (auth.uid() = user_id);

-- 3 şikâyet alan yorum otomatik gizlenir
create or replace view public.film_review_feed as
select r.id, r.film_id, r.user_id, r.rating, r.body, r.spoiler, r.created_at, r.updated_at,
       p.name, p.avatar,
       (select count(*) from public.film_review_likes l where l.review_id = r.id)::int as like_count
from public.film_reviews r
left join public.profiles p on p.id = r.user_id
where (select count(*) from public.film_review_reports x where x.review_id = r.id) < 3;

-- film başına ortalama puan
create or replace view public.film_review_stats as
select film_id, round(avg(rating)::numeric, 1) as avg_rating, count(rating)::int as n_rating, count(*)::int as n
from public.film_reviews group by film_id;

grant select on public.film_review_feed, public.film_review_stats to anon, authenticated;
