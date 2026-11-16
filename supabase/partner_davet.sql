-- Me First · Partner daveti ve ortak "Biz ikimiz"
-- Supabase > SQL Editor'e yapıştırıp bir kez "Run" de. Tekrar çalıştırmak zarar vermez.

-- 1) Profil: hesap türü ve kimin davet ettiği
alter table public.profiles add column if not exists kind text not null default 'uye' check (kind in ('uye','partner'));
alter table public.profiles add column if not exists invited_by uuid references auth.users(id) on delete set null;

-- 2) Çiftler: davet kodu ve bağlantı
create table if not exists public.couples (
  id uuid primary key default gen_random_uuid(),
  a uuid not null references auth.users(id) on delete cascade,          -- daveti açan
  b uuid references auth.users(id) on delete set null,                   -- daveti kabul eden
  code text unique not null,
  status text not null default 'bekliyor' check (status in ('bekliyor','bagli','koptu')),
  share_cycle smallint not null default 0 check (share_cycle in (0,1,2)), -- 0 kapalı · 1 sadece özet · 2 tarihlerle
  cycle_note jsonb,                                                      -- a'nın paylaşmayı seçtiği özet
  created_at timestamptz not null default now(),
  linked_at timestamptz,
  ended_at timestamptz
);
create index if not exists couples_a_idx on public.couples (a, status);
create index if not exists couples_b_idx on public.couples (b, status);

-- 3) Ortak içerik: planlar, mesajlar, özel günler, oyunlar, birlikte izlenecek/okunacaklar
create table if not exists public.couple_items (
  id uuid primary key default gen_random_uuid(),
  couple_id uuid not null references public.couples(id) on delete cascade,
  kind text not null check (char_length(kind) between 2 and 20),
  data jsonb not null default '{}'::jsonb,
  author uuid not null default auth.uid() references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists couple_items_idx on public.couple_items (couple_id, kind, updated_at desc);

-- yardımcı: bu kişi bu çiftin bağlı bir üyesi mi?
create or replace function public.couple_member(cid uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.couples c where c.id = cid and c.status = 'bagli' and auth.uid() in (c.a, c.b));
$$;

alter table public.couples enable row level security;
alter table public.couple_items enable row level security;

drop policy if exists "cp okuma" on public.couples;
create policy "cp okuma" on public.couples for select to authenticated using (auth.uid() in (a, b));
drop policy if exists "cp dongu" on public.couples;
create policy "cp dongu" on public.couples for update to authenticated using (auth.uid() = a) with check (auth.uid() = a);

drop policy if exists "ci okuma" on public.couple_items;
drop policy if exists "ci ekleme" on public.couple_items;
drop policy if exists "ci guncelleme" on public.couple_items;
drop policy if exists "ci silme" on public.couple_items;
create policy "ci okuma" on public.couple_items for select to authenticated using (public.couple_member(couple_id));
create policy "ci ekleme" on public.couple_items for insert to authenticated with check (public.couple_member(couple_id) and author = auth.uid());
create policy "ci guncelleme" on public.couple_items for update to authenticated using (public.couple_member(couple_id)) with check (public.couple_member(couple_id));
create policy "ci silme" on public.couple_items for delete to authenticated using (public.couple_member(couple_id));

-- 4) Davet oluştur: açık bir bağlantı varsa onu, bekleyen davet varsa onun kodunu döndürür
create or replace function public.couple_invite() returns public.couples
language plpgsql security definer set search_path = public as $$
declare r public.couples; k text;
begin
  if auth.uid() is null then raise exception 'giris_gerekli'; end if;
  select * into r from public.couples where (a = auth.uid() or b = auth.uid()) and status = 'bagli' limit 1;
  if found then return r; end if;
  select * into r from public.couples where a = auth.uid() and status = 'bekliyor' limit 1;
  if found then return r; end if;
  loop
    k := upper(substr(translate(md5(random()::text || clock_timestamp()::text), '01', ''), 1, 6));
    exit when char_length(k) = 6 and not exists (select 1 from public.couples where code = k);
  end loop;
  insert into public.couples (a, code) values (auth.uid(), k) returning * into r;
  return r;
end $$;

-- 5) Daveti kabul et
create or replace function public.couple_accept(p_code text) returns public.couples
language plpgsql security definer set search_path = public as $$
declare r public.couples;
begin
  if auth.uid() is null then raise exception 'giris_gerekli'; end if;
  if exists (select 1 from public.couples where (a = auth.uid() or b = auth.uid()) and status = 'bagli') then raise exception 'zaten_bagli'; end if;
  select * into r from public.couples where code = upper(trim(p_code)) and status = 'bekliyor' for update;
  if not found then raise exception 'kod_gecersiz'; end if;
  if r.a = auth.uid() then raise exception 'kendi_kodun'; end if;
  update public.couples set b = auth.uid(), status = 'bagli', linked_at = now() where id = r.id returning * into r;
  update public.profiles set invited_by = coalesce(invited_by, r.a) where id = auth.uid();
  delete from public.couples where a = auth.uid() and status = 'bekliyor';
  return r;
end $$;

-- 6) Bağlantıyı kopar (iki taraf da yapabilir): hesaplar kalır, ortak alan kapanır
create or replace function public.couple_end() returns void
language plpgsql security definer set search_path = public as $$
begin
  update public.couples set status = 'koptu', ended_at = now(), share_cycle = 0, cycle_note = null
  where (a = auth.uid() or b = auth.uid()) and status in ('bagli','bekliyor');
end $$;

-- 7) Partnerin adı ve fotoğrafı (sadece bağlı çiftte)
create or replace view public.couple_view as
select c.id, c.status, c.share_cycle, c.cycle_note, c.linked_at,
       case when c.a = auth.uid() then c.b else c.a end as partner_id,
       p.name as partner_name, p.avatar as partner_avatar,
       (c.a = auth.uid()) as i_invited
from public.couples c
left join public.profiles p on p.id = case when c.a = auth.uid() then c.b else c.a end
where auth.uid() in (c.a, c.b) and c.status = 'bagli';

grant execute on function public.couple_invite(), public.couple_accept(text), public.couple_end(), public.couple_member(uuid) to authenticated;
grant select on public.couple_view to authenticated;
