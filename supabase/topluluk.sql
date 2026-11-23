-- Me First · Topluluk: "Ben de gidiyorum" sayaçları, Ayın kitabı kulübü, Haftanın sorusu duvarı
-- Supabase > SQL Editor'e yapıştırıp bir kez "Run" de. Tekrar çalıştırmak zararsızdır.

-- 1) Gidiyorum / kulübe katıldım (etkinlik, imza günü, macera, ayın kitabı)
create table if not exists public.going (
  item text not null check (char_length(item) between 3 and 90),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (item, user_id)
);
create index if not exists going_item_idx on public.going (item);
alter table public.going enable row level security;
drop policy if exists "go okuma" on public.going;
drop policy if exists "go ekleme" on public.going;
drop policy if exists "go silme" on public.going;
-- kimse başkasının kaydını göremez; sadece sayılar fonksiyonla açılır
create policy "go okuma" on public.going for select to authenticated using (auth.uid() = user_id);
create policy "go ekleme" on public.going for insert to authenticated with check (auth.uid() = user_id);
create policy "go silme" on public.going for delete to authenticated using (auth.uid() = user_id);

create or replace function public.going_counts(p_items text[])
returns table(item text, n int)
language sql security definer set search_path to 'public' stable as $$
  select g.item, count(*)::int from going g
  where g.item = any(p_items[1:120]) group by g.item $$;
grant execute on function public.going_counts(text[]) to anon, authenticated;

-- 2) Haftanın sorusu: cevaplar, beğeniler, şikâyetler
create table if not exists public.week_answers (
  id uuid primary key default gen_random_uuid(),
  week text not null check (char_length(week) between 4 and 16),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  body text not null check (char_length(body) between 2 and 160),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (week, user_id)
);
create index if not exists week_answers_week_idx on public.week_answers (week, created_at desc);

create table if not exists public.week_answer_likes (
  answer_id uuid not null references public.week_answers(id) on delete cascade,
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (answer_id, user_id)
);

create table if not exists public.week_answer_reports (
  id uuid primary key default gen_random_uuid(),
  answer_id uuid not null references public.week_answers(id) on delete cascade,
  user_id uuid not null default auth.uid(),
  created_at timestamptz not null default now(),
  unique (answer_id, user_id)
);

alter table public.week_answers enable row level security;
alter table public.week_answer_likes enable row level security;
alter table public.week_answer_reports enable row level security;

drop policy if exists "wa okuma" on public.week_answers;
drop policy if exists "wa ekleme" on public.week_answers;
drop policy if exists "wa guncelleme" on public.week_answers;
drop policy if exists "wa silme" on public.week_answers;
create policy "wa okuma" on public.week_answers for select using (true);
create policy "wa ekleme" on public.week_answers for insert to authenticated with check (auth.uid() = user_id);
create policy "wa guncelleme" on public.week_answers for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "wa silme" on public.week_answers for delete to authenticated using (auth.uid() = user_id);

drop policy if exists "wal okuma" on public.week_answer_likes;
drop policy if exists "wal ekleme" on public.week_answer_likes;
drop policy if exists "wal silme" on public.week_answer_likes;
create policy "wal okuma" on public.week_answer_likes for select using (true);
create policy "wal ekleme" on public.week_answer_likes for insert to authenticated with check (auth.uid() = user_id);
create policy "wal silme" on public.week_answer_likes for delete to authenticated using (auth.uid() = user_id);

drop policy if exists "war ekleme" on public.week_answer_reports;
create policy "war ekleme" on public.week_answer_reports for insert to authenticated with check (auth.uid() = user_id);

-- 3 şikâyet alan cevap otomatik gizlenir
create or replace view public.week_answer_feed as
select a.id, a.week, a.user_id, a.body, a.created_at, a.updated_at, p.name, p.avatar,
       (select count(*) from public.week_answer_likes l where l.answer_id = a.id)::int as like_count
from public.week_answers a
left join public.profiles p on p.id = a.user_id
where (select count(*) from public.week_answer_reports x where x.answer_id = a.id) < 3;
grant select on public.week_answer_feed to anon, authenticated;

-- cevabın beğenilince sahibine bildirim ('qlike')
create or replace function public.notify_week_like() returns trigger
language plpgsql security definer set search_path to 'public' as $$
declare o uuid; w text; n text; begin
  select user_id, week into o, w from week_answers where id = new.answer_id;
  select name into n from profiles where id = new.user_id;
  if o is not null and o <> new.user_id then
    insert into notifications(user_id, kind, book_key, book_title, actor)
    values (o, 'qlike', 'soru:' || w, 'Haftanın sorusu', coalesce(n, 'Bir Me First''lü'));
  end if;
  return new; end $$;
drop trigger if exists t_week_like on public.week_answer_likes;
create trigger t_week_like after insert on public.week_answer_likes for each row execute function public.notify_week_like();
