-- Me First · Anonim kullanım sayacı (hangi bölüm kaç farklı telefonda açıldı)
-- Supabase > SQL Editor'e yapıştırıp bir kez "Run" de. Tekrar çalıştırmak zarar vermez.
-- Kişisel bilgi yok: sadece gün, bölüm adı ve telefonda rastgele üretilen bir kodun özeti tutulur.

create table if not exists public.usage_hits (
  day date not null default current_date,
  sect text not null check (char_length(sect) <= 24),
  dev text not null check (char_length(dev) <= 64),
  primary key (day, sect, dev)
);
alter table public.usage_hits enable row level security;
-- Uygulama tabloya doğrudan yazamaz ve okuyamaz; sadece aşağıdaki fonksiyonla sayaç artırır.

create or replace function public.usage_hit(p_sect text, p_dev text)
returns void
language sql
security definer
set search_path = public
as $$
  insert into public.usage_hits(day, sect, dev)
  values (current_date, left(p_sect, 24), left(md5(p_dev), 32))
  on conflict do nothing;
$$;
revoke all on function public.usage_hit(text, text) from public;
grant execute on function public.usage_hit(text, text) to anon, authenticated;

-- Raporlar (SQL Editor'de çalıştır):
-- Son 14 gün, bölüm başına farklı telefon:
--   select sect, count(distinct dev) telefon, count(*) gun_telefon from usage_hits where day > current_date - 14 group by sect order by telefon desc;
-- Günlük aktif telefon:
--   select day, count(distinct dev) from usage_hits where sect = 'acilis' group by day order by day desc;
