-- Me First · Perde bildirimleri: film yorumun beğenilince ve yorum yaptığın filme yeni yorum gelince
-- Supabase > SQL Editor'e yapıştırıp bir kez "Run" de.

alter table public.film_reviews add column if not exists film_title text check (char_length(film_title) <= 120);

-- yorumun beğenildi -> yorumun sahibine 'flike'
create or replace function public.notify_film_like() returns trigger
language plpgsql security definer set search_path to 'public' as $$
declare o uuid; fid text; ft text; n text; begin
  select user_id, film_id, film_title into o, fid, ft from film_reviews where id = new.review_id;
  select name into n from profiles where id = new.user_id;
  if o is not null and o <> new.user_id then
    insert into notifications(user_id, kind, book_key, book_title, actor)
    values (o, 'flike', 'film:' || fid, coalesce(ft, fid), coalesce(n, 'Bir izleyici'));
  end if;
  return new; end $$;
drop trigger if exists t_film_like on public.film_review_likes;
create trigger t_film_like after insert on public.film_review_likes for each row execute function public.notify_film_like();

-- yorum yaptığın filme yeni yorum -> o filme yorum yazmış diğerlerine 'fcom'
create or replace function public.notify_film_review() returns trigger
language plpgsql security definer set search_path to 'public' as $$
declare n text; begin
  if char_length(coalesce(new.body, '')) = 0 then return new; end if;
  select name into n from profiles where id = new.user_id;
  insert into notifications(user_id, kind, book_key, book_title, actor)
    select distinct r.user_id, 'fcom', 'film:' || new.film_id, coalesce(new.film_title, new.film_id), coalesce(n, 'Bir izleyici')
    from film_reviews r where r.film_id = new.film_id and r.user_id <> new.user_id;
  return new; end $$;
drop trigger if exists t_film_review on public.film_reviews;
create trigger t_film_review after insert on public.film_reviews for each row execute function public.notify_film_review();
