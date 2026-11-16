-- Me First · Davet kodunu kimin gönderdiğini göster (kabul ekranı için)
-- Supabase > SQL Editor'e yapıştırıp bir kez "Run" de.
create or replace function public.couple_peek(p_code text)
returns table (inviter_name text, inviter_avatar text)
language sql stable security definer set search_path = public as $$
  select coalesce(p.name, 'Biri'), p.avatar
  from public.couples c left join public.profiles p on p.id = c.a
  where c.code = upper(trim(p_code)) and c.status = 'bekliyor'
  limit 1;
$$;
grant execute on function public.couple_peek(text) to anon, authenticated;
