-- Me First · Arama istekleri: Sahne & Perde aramaları da kaydedilsin (film, sahne)
-- Supabase > SQL Editor'e yapıştırıp bir kez "Run" de.

-- tabloda tür kısıtı varsa genişlet
do $$ declare c text;
begin
  for c in select conname from pg_constraint
           where conrelid = 'public.catalog_wants'::regclass and contype = 'c' and pg_get_constraintdef(oid) ilike '%kind%'
  loop execute format('alter table public.catalog_wants drop constraint %I', c); end loop;
end $$;
alter table public.catalog_wants add constraint catalog_wants_kind_chk check (kind in ('ara','yazar','kitap','film','sahne'));

create or replace function public.want_touch(q text, kind text, dev text)
 returns void
 language plpgsql
 security definer
 set search_path to 'public'
as $function$
declare t text := lower(btrim(regexp_replace(coalesce(q,''), '\s+', ' ', 'g')));
begin
  if char_length(t) not between 3 and 80 or kind not in ('ara','yazar','kitap','film','sahne')
     or dev is null or char_length(dev) not between 8 and 64
     or t ~ '@|https?:'
     or (t ~ '[0-9]{5,}' and t !~ '^wd:q[0-9]+ ') then return; end if;
  insert into catalog_wants(q, kind, dev) values (t, kind, dev)
    on conflict on constraint catalog_wants_pkey do update set at = now();
end $function$;
