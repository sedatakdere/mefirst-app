-- Me First · Topluluk 2: Kurucu üye numarası, arkadaş davet kodu, rozetler, "Birlikte" sayaçları
-- Supabase > SQL Editor'e yapıştırıp bir kez "Run" de. Tekrar çalıştırmak zararsızdır.

alter table public.profiles add column if not exists founder_no int;
alter table public.profiles add column if not exists ref_code text;
alter table public.profiles add column if not exists ref_by uuid references auth.users(id) on delete set null;
create unique index if not exists profiles_ref_code_idx on public.profiles (ref_code);
create unique index if not exists profiles_founder_idx on public.profiles (founder_no);

-- Kendi kodum + kurucu numaram (ilk 500 kişi kurucu üye olur)
create or replace function public.ref_me() returns json
language plpgsql security definer set search_path to 'public' as $$
declare u uuid := auth.uid(); c text; f int; n int; i int := 0; begin
  if u is null then return null; end if;
  insert into profiles(id, name) values (u, 'Me First''lü') on conflict (id) do nothing;
  select ref_code, founder_no into c, f from profiles where id = u;
  if c is null then
    loop
      c := upper(substr(translate(md5(random()::text || clock_timestamp()::text), '01', 'KM'), 1, 6));
      begin
        update profiles set ref_code = c where id = u; exit;
      exception when unique_violation then i := i + 1; if i > 8 then c := null; exit; end if; end;
    end loop;
  end if;
  if f is null then
    perform pg_advisory_xact_lock(4242);
    select count(*) into n from profiles where founder_no is not null;
    if n < 500 then f := n + 1; update profiles set founder_no = f where id = u; end if;
  end if;
  return json_build_object('code', c, 'founder', f,
    'invites', (select count(*) from profiles where ref_by = u),
    'by', (select p2.name from profiles p1 join profiles p2 on p2.id = p1.ref_by where p1.id = u));
end $$;
grant execute on function public.ref_me() to authenticated;

-- Davet kodunu kullan (bir kez; kendi kodun olmaz)
create or replace function public.ref_redeem(p_code text) returns json
language plpgsql security definer set search_path to 'public' as $$
declare u uuid := auth.uid(); o uuid; nm text; begin
  if u is null then return json_build_object('ok', false, 'err', 'auth'); end if;
  insert into profiles(id, name) values (u, 'Me First''lü') on conflict (id) do nothing;
  select id, name into o, nm from profiles where ref_code = upper(trim(p_code));
  if o is null then return json_build_object('ok', false, 'err', 'yok'); end if;
  if o = u then return json_build_object('ok', false, 'err', 'kendi'); end if;
  if (select ref_by from profiles where id = u) is not null then return json_build_object('ok', false, 'err', 'zaten'); end if;
  update profiles set ref_by = o where id = u;
  insert into notifications(user_id, kind, book_key, book_title, actor)
    values (o, 'ref', 'ref', 'Davet', coalesce((select name from profiles where id = u), 'Bir arkadaşın'));
  return json_build_object('ok', true, 'by', nm);
end $$;
grant execute on function public.ref_redeem(text) to authenticated;

-- Rozet sayıları
create or replace function public.my_badges() returns json
language sql security definer set search_path to 'public' stable as $$
  select json_build_object(
    'founder', (select founder_no from profiles where id = auth.uid()),
    'invites', (select count(*) from profiles where ref_by = auth.uid()),
    'answers', (select count(*) from week_answers where user_id = auth.uid()),
    'likes',   (select count(*) from week_answer_likes l join week_answers a on a.id = l.answer_id where a.user_id = auth.uid()),
    'clubs',   (select count(*) from going where user_id = auth.uid() and item like 'kulup:%'),
    'events',  (select count(*) from going where user_id = auth.uid() and item not like 'kulup:%'),
    'best', (select count(*) from (
        select distinct on (f.week) f.week, f.user_id from week_answer_feed f
        where f.like_count > 0
          and f.week < 'w' || to_char(date_trunc('week', now() at time zone 'Europe/Istanbul'), 'YYYY-MM-DD')
        order by f.week, f.like_count desc, f.created_at) t where t.user_id = auth.uid())
  ) $$;
grant execute on function public.my_badges() to authenticated;

-- isim yanında kurucu işareti için cevap duvarına founder_no eklenir
create or replace view public.week_answer_feed as
select a.id, a.week, a.user_id, a.body, a.created_at, a.updated_at, p.name, p.avatar,
       (select count(*) from public.week_answer_likes l where l.answer_id = a.id)::int as like_count,
       p.founder_no
from public.week_answers a
left join public.profiles p on p.id = a.user_id
where (select count(*) from public.week_answer_reports x where x.answer_id = a.id) < 3;
grant select on public.week_answer_feed to anon, authenticated;

-- "Birlikte" sayaçları: kişi başı günde bir (mum yaktım, kitap bitirdim…)
create table if not exists public.pulse (
  kind text not null check (kind in ('mum','kitap','soru','hareket')),
  day date not null default ((now() at time zone 'Europe/Istanbul')::date),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  primary key (kind, day, user_id)
);
alter table public.pulse enable row level security;

create or replace function public.pulse_add(p_kind text) returns void
language sql security definer set search_path to 'public' as $$
  insert into pulse(kind, user_id) select p_kind, auth.uid()
  where auth.uid() is not null and p_kind in ('mum','kitap','soru','hareket')
  on conflict do nothing $$;
grant execute on function public.pulse_add(text) to authenticated;

create or replace function public.pulse_week(p_kind text) returns json
language sql security definer set search_path to 'public' stable as $$
  with w as (select date_trunc('week', now() at time zone 'Europe/Istanbul')::date as d)
  select json_build_object(
    'now',  (select count(*) from pulse, w where kind = p_kind and day >= w.d),
    'last', (select count(*) from pulse, w where kind = p_kind and day >= w.d - 7 and day < w.d),
    'me',   (select count(*) from pulse, w where kind = p_kind and day >= w.d and user_id = auth.uid())) $$;
grant execute on function public.pulse_week(text) to anon, authenticated;
