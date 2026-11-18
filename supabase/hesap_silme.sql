-- Me First · "Verilerimi sil" (Google Play / App Store hesap silme şartı)
-- Supabase > SQL Editor'e yapıştırıp bir kez "Run" de. Tekrar çalıştırmak zarar vermez.
-- Uygulamadaki "Verilerimi sil" düğmesi bu fonksiyonu çağırır: kişinin sunucudaki her izini ve anonim hesabını siler.

create or replace function public.delete_me()
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  u uuid := auth.uid();
  t text;
begin
  if u is null then
    raise exception 'oturum yok';
  end if;

  -- Ruh eşi bağlantısı: kendi açtığı bağlantı tamamen silinir, katıldığı bağlantı "koptu" olur
  begin delete from public.couple_items where author = u; exception when others then null; end;
  begin delete from public.couples where a = u; exception when others then null; end;
  begin update public.couples set b = null, status = 'koptu', ended_at = now() where b = u; exception when others then null; end;

  -- Topluluk ve film içerikleri (user_id sütunu olan tablolar)
  foreach t in array array['likes','polaroid_replies','quotes','reports','polaroids','film_review_likes','film_review_reports','film_reviews','notifications']
  loop
    begin
      execute format('delete from public.%I where user_id = $1', t) using u;
    exception when others then null;
    end;
  end loop;

  begin delete from public.profiles where id = u; exception when others then null; end;

  -- Son olarak anonim hesabın kendisi (bağlı her şey cascade ile gider)
  delete from auth.users where id = u;
end;
$$;

revoke all on function public.delete_me() from public;
grant execute on function public.delete_me() to authenticated;
