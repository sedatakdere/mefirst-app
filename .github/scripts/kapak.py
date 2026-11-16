# Öneri kitaplarının kapaklarını bulur ve kendi sunucumuza koyar: app/kapak/<id>.jpg + app/kapak/kapak.json
import hashlib, html, io, json, os, re, time, unicodedata, urllib.parse, urllib.request
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36 MeFirstCoverBot/1.0",
      "Accept-Language": "tr-TR,tr;q=0.9"}
DBG = {}
ALIAS = {"Ove Adında Bir Adam": "Hayata Röveşata Çeken Adam"}
ROOT = "app/kapak"; MAP = ROOT + "/kapak.json"; REP = ROOT + "/rapor.json"
def fetch(url, raw=False, t=15):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=t) as r:
        b = r.read()
    return b if raw else b.decode("utf-8", "replace")
def fold(s):
    s = str(s or "").replace("ı", "i").replace("İ", "i").lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s)).strip()
def tkey(t): return fold(re.split(r"\s*[:(]\s*", str(t))[0])
def same(cand, t, loose=False):
    raw = html.unescape(cand)
    if re.search(r"\bset(i)?\b|\bkutu\b|\+|\bciltlik\b", fold(raw)): return False
    c, w = tkey(re.split(r"\s+[-–]\s+", raw)[0]), tkey(t)
    if not (c and w): return False
    if c == w: return True
    return loose and ((c.startswith(w) and len(w) >= 5) or (w.startswith(c) and len(c) >= 6))
def imgs(page, host):
    out = []
    for m in re.finditer(r"<img\b[^>]*>", page, re.I):
        tag = m.group(0)
        src = re.search(r'(?:data-src|data-original|src)="([^"]+)"', tag)
        alt = re.search(r'(?:alt|title)="([^"]*)"', tag)
        if src and host in src.group(1): out.append((alt.group(1) if alt else "", html.unescape(src.group(1))))
    return out
def kitapyurdu(t, a):
    q = urllib.parse.quote_plus(f"{t} {a}".strip())
    p = fetch(f"https://www.kitapyurdu.com/index.php?route=product/search&filter_name={q}")
    for alt, src in imgs(p, "img.kitapyurdu.com"):
        if same(alt, t): return re.sub(r"/wi:\d+", "/wi:500", src)
    return ""
def dr(t, a):
    for qq in (f"{t} {a}".strip(), t):
        p = fetch("https://www.dr.com.tr/search?q=" + urllib.parse.quote_plus(qq))
        L = imgs(p, "dr.com.tr")
        for alt, src in L:
            fa = fold(html.unescape(alt)); sur = fold(a).split()[-1] if fold(a) else ""
            ok = same(alt, t) or (sur and sur in fa and fa.endswith(" " + tkey(t)))
            if ok and re.search(r"\.(jpe?g|png|webp)", src, re.I): return re.sub(r"/cache/\d+x\d+-\d+/", "/cache/500x400-0/", src)
        DBG.setdefault(t, []).append({"q": qq, "n": len(p), "alts": [a for a, _ in L if fold(t).split()[0] in fold(html.unescape(a))][:6], "imgs": len(L), "raw": [m.group(0)[:300] for m in re.finditer(r"<img\b[^>]*>", p) if fold(t).split()[-1] in fold(html.unescape(m.group(0)))][:3]})
        time.sleep(0.6)
    return ""
def idefix(t, a):
    q = urllib.parse.quote_plus(f"{t} {a}".strip())
    p = fetch(f"https://www.idefix.com/search?q={q}")
    for alt, src in imgs(p, "idefix.com"):
        if same(alt, t): return re.sub(r"/resize/\d+/\d+/", "/resize/400/0/", src)
    for m in re.finditer(r'"(?:name|productName|title)"\s*:\s*"([^"]{2,160})"[^{}]{0,600}?"(https?:[^"]+idefix\.com[^"]+\.(?:jpg|jpeg|png|webp))"', p):
        if same(m.group(1), t): return m.group(2)
    return ""
def gbooks(t, a):
    sur = (a or "").split()[-1] if a else ""
    j = json.loads(fetch("https://www.googleapis.com/books/v1/volumes?" + urllib.parse.urlencode({"q": f'intitle:"{t}"' + (f" inauthor:{sur}" if sur else ""), "maxResults": 10, "printType": "books"})))
    for it in j.get("items", []) or []:
        v = it.get("volumeInfo") or {}; il = v.get("imageLinks") or {}
        u = il.get("thumbnail") or il.get("smallThumbnail")
        if u and same(v.get("title", ""), t, True):
            return u.replace("http://", "https://").replace("&edge=curl", "").replace("zoom=1", "zoom=2")
    return ""
def openlib(t, a):
    j = json.loads(fetch("https://openlibrary.org/search.json?" + urllib.parse.urlencode({"title": t, "author": a or "", "limit": 8, "fields": "title,cover_i"})))
    for d in j.get("docs", []):
        if d.get("cover_i") and same(d.get("title", ""), t, True): return f"https://covers.openlibrary.org/b/id/{d['cover_i']}-L.jpg"
    return ""
SRC = [("dr", dr), ("idefix", idefix), ("kitapyurdu", kitapyurdu), ("google", gbooks)]
def save_img(u, path):
    from PIL import Image
    b = fetch(u, raw=True)
    im = Image.open(io.BytesIO(b)).convert("RGB")
    w, h = im.size
    if w < 80 or h < 110 or h / w < 1.1 or h / w > 2.2: raise ValueError(f"boyut {w}x{h}")
    if w > 400: im = im.resize((400, round(h * 400 / w)), Image.LANCZOS)
    im.save(path, "JPEG", quality=84, optimize=True, progressive=True)
def books():
    s = open("app/index.html", encoding="utf-8").read()
    i = s.find("const KT_BOOKS=[")
    j = s.find("\n];", i)
    rows = re.findall(r'\["((?:[^"\\]|\\.)+)","((?:[^"\\]|\\.)*)",\[', s[i:j])
    have = set()
    try:
        for b in json.load(open("app/books.json", encoding="utf-8")).get("books", []):
            if b.get("c"):
                for n in [b["t"]] + (b.get("al") or []): have.add(tkey(n))
    except Exception: pass
    seen, out = set(), []
    for t, a in rows:
        if a.startswith("#") or "_" in t or not re.search(r"[A-Za-zÇĞİÖŞÜçğıöşü]{2}", t): continue
        k = tkey(t)
        if k in seen or k in have: continue
        seen.add(k); out.append((t, a))
    return out
def main():
    os.makedirs(ROOT, exist_ok=True)
    M = json.load(open(MAP, encoding="utf-8")) if os.path.exists(MAP) else {}
    R = {"tarih": time.strftime("%Y-%m-%d %H:%M"), "bulunan": {}, "bulunamayan": {}, "kaynak": {}}
    L = books(); R["toplam"] = len(L)
    for t, a in L:
        k = tkey(t)
        if k in M and os.path.exists("app/" + M[k]) and os.path.getsize("app/" + M[k]) > 22000: continue
        errs = []
        for name, fn in SRC:
            try:
                u = fn(ALIAS.get(t, t), a)
                if not u: errs.append(name + ":yok"); continue
                fid = hashlib.sha1(k.encode()).hexdigest()[:12]
                if "i.dr.com.tr" in u:
                    base = re.sub(r"/cache/\d+x\d+-\d+/", "/", u)
                    cands = [base, base.replace("/originals/", "/cache/600x600-0/originals/"), base.replace("/originals/", "/cache/354x500-0/originals/"), base.replace("/originals/", "/cache/180x245-0/originals/")]
                else: cands = [u]
                last = None
                for cu in cands:
                    try:
                        save_img(cu, f"{ROOT}/{fid}.jpg"); R.setdefault("boyut", {})[cu.split("/")[3] if "/cache/" in cu else "orijinal"] = R.get("boyut", {}).get(cu.split("/")[3] if "/cache/" in cu else "orijinal", 0) + 1; last = None; break
                    except Exception as e: last = e
                if last: raise last
                M[k] = f"kapak/{fid}.jpg"; R["bulunan"][t] = name; R["kaynak"][name] = R["kaynak"].get(name, 0) + 1
                break
            except Exception as e:
                errs.append(f"{name}:{type(e).__name__}:{str(e)[:60]}")
            finally:
                time.sleep(0.8)
        else:
            R["bulunamayan"][t] = errs
    json.dump(M, open(MAP, "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)
    R["dbg"] = DBG
    json.dump(R, open(REP, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(R["bulunan"]), "bulundu,", len(R["bulunamayan"]), "bulunamadı", R["kaynak"])
main()
# yeniden: küçük kapakları büyüt
