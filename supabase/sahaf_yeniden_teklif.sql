-- Me First · Sahaf: reddedilen TAKAS teklifinin yerine başka bir kitap önerilebilsin
-- Supabase > SQL Editor'e yapıştırıp bir kez "Run" de. Tekrar çalıştırmak zarar vermez.
-- Değişen tek yer: takas ilanında, reddedilen talep farklı bir kitapla yeniden "bekliyor" olur.
-- Hediye ve ödünç ilanlarında ret kesindir; aynı kitabı yeniden önermek de engellenir.

create or replace function public.sahaf_request(p_ad uuid, p_msg text, p_offer text default ''::text)
 returns uuid
 language plpgsql
 security definer
 set search_path to 'public'
as $function$
declare u uuid := sahaf_me(); a sahaf_ads; r sahaf_reqs; i uuid; m text := btrim(coalesce(p_msg, '')); o text := coalesce(btrim(p_offer), '');
begin
  select * into a from sahaf_ads where id = p_ad;
  if a.id is null or a.hidden or a.status not in ('open','reserved') then raise exception 'ilan yok'; end if;
  if a.user_id = u then raise exception 'kendi ilanin'; end if;
  if sahaf_blocked(u, a.user_id) then raise exception 'ulasilamiyor'; end if;
  if char_length(m) < 1 then raise exception 'mesaj bos'; end if;
  if (select count(*) from sahaf_reqs where user_id = u and created_at > now() - interval '1 day') >= 20 then raise exception 'yavas'; end if;
  select * into r from sahaf_reqs where ad_id = p_ad and user_id = u;
  if r.id is not null then
    if r.status = 'declined' then
      -- yalnızca takasta ve farklı bir kitapla yeniden teklif
      if a.kind <> 'takas' or o = '' or lower(o) = lower(coalesce(r.offer, '')) then raise exception 'reddedildi'; end if;
    elsif r.status in ('pending','accepted','done') then return r.id;
    end if;
    update sahaf_reqs set status = 'pending', offer = o, last_at = now(), owner_seen = 'epoch' where id = r.id;
    i := r.id;
  else
    insert into sahaf_reqs(ad_id, user_id, owner_id, offer) values (p_ad, u, a.user_id, o) returning id into i;
  end if;
  insert into sahaf_msgs(req_id, user_id, body) values (i, u, left(m, 600));
  update sahaf_reqs set last_at = now(), user_seen = now() where id = i;
  return i;
end $function$;
