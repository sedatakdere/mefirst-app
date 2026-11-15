# Perde afişlerini indirir: app/afis/<id>.jpg + app/afis/afis.json
import json, os, re, time, unicodedata, urllib.parse, urllib.request
UA = {"User-Agent": "MeFirstPosterBot/1.0 (https://mefirst.app)"}
def get(url, raw=False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        b = r.read()
    return b if raw else json.loads(b.decode("utf-8"))
def fold(s):
    s = str(s or "").replace("ı", "i").replace("İ", "i").lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s)).strip()
def match(t, want):
    t = fold(re.sub(r"\(.*?\)", "", t))
    return t and (t == want or t.startswith(want) or (want.startswith(t) and len(t) >= 4))
def wiki(lang, q, y):
    p = {"action": "query", "format": "json", "generator": "search", "gsrsearch": f"{q} {y} film", "gsrlimit": "5",
         "prop": "pageimages|pageprops", "ppprop": "wikibase_item", "piprop": "thumbnail", "pithumbsize": "500", "pilicense": "any"}
    j = get(f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(p))
    pages = sorted((j.get("query") or {}).get("pages", {}).values(), key=lambda x: x.get("index", 0))
    want = fold(q)
    exact, loose = [], []
    for pg in pages:
        src = (pg.get("thumbnail") or {}).get("source", "")
        if ".svg" in src.lower(): src = ""
        qid = (pg.get("pageprops") or {}).get("wikibase_item", "")
        t = fold(re.sub(r"\(.*?\)", "", pg.get("title", "")))
        if not (src or qid) or not match(pg.get("title", ""), want): continue
        (exact if t == want else loose).append((src, qid))
    return exact + loose
def itunes(q, y):
    for c in ("tr", "us"):
        j = get("https://itunes.apple.com/search?" + urllib.parse.urlencode({"term": q, "media": "movie", "entity": "movie", "limit": 8, "country": c}))
        want = fold(q)
        for x in j.get("results", []):
            yr = int(str(x.get("releaseDate", "0"))[:4] or 0)
            if x.get("artworkUrl100") and (not y or abs(yr - y) <= 1) and match(x.get("trackName", ""), want):
                return re.sub(r"/\d+x\d+bb\.(jpg|png|webp)$", "/600x900bb.jpg", x["artworkUrl100"])
    return ""
ULKE = {"Amerika Birleşik Devletleri": "ABD", "Birleşik Krallık": "İngiltere"}
def labels(ids):
    ids = [i for i in ids if i][:50]
    if not ids: return {}
    j = get("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({"action": "wbgetentities", "format": "json", "ids": "|".join(ids), "props": "labels|sitelinks", "languages": "tr|en"}))
    o = {}
    for k, e in (j.get("entities") or {}).items():
        L = e.get("labels") or {}
        o[k] = (L.get("tr") or L.get("en") or {}).get("value", "")
        FAME[k] = len(e.get("sitelinks") or {}) + (1000 if "tr" in L else 0) * 0
        TRL[k] = "tr" in L
    return o
FAME, TRL = {}, {}
TUR_SIRA = ["romantik komedi", "komedi-drama", "müzikal", "biyografik", "romantik", "acıklı güldürü", "komedi", "drama", "savaş", "macera", "aksiyon", "bilimkurgu", "fantastik"]
def bilgi(qid, y=0):
    j = get("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({"action": "wbgetentities", "format": "json", "ids": qid, "props": "claims"}))
    C = ((j.get("entities") or {}).get(qid) or {}).get("claims") or {}
    def vals(p, n):
        r = []
        for c in C.get(p, [])[:n]:
            v = ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value")
            if v is not None: r.append(v)
        return r
    yy = [int(str(v.get("time", "+0"))[1:5]) for v in vals("P577", 5) if isinstance(v, dict) and str(v.get("time", ""))[1:5].isdigit()]
    if y and yy and min(abs(a - y) for a in yy) > 1: return None
    if y and not yy: return None
    cast = [v.get("id") for v in vals("P161", 15) if isinstance(v, dict)]
    gen = [v.get("id") for v in vals("P136", 6) if isinstance(v, dict)]
    cty = [v.get("id") for v in vals("P495", 2) if isinstance(v, dict)]
    L = labels(cast + gen + cty)
    imdb = next((v for v in vals("P345", 1) if isinstance(v, str) and v.startswith("tt")), "")
    sure = 0
    for v in vals("P2047", 1):
        try: sure = int(round(float(v.get("amount", "0"))))
        except Exception: pass
    cast.sort(key=lambda c: -FAME.get(c, 0))
    gk = lambda g: re.sub(r"\s*(filmi|film)$", "", L.get(g, "")).strip().lower()
    gen.sort(key=lambda g: (not TRL.get(g), TUR_SIRA.index(gk(g)) if gk(g) in TUR_SIRA else 99))
    tur = []
    for g in gen:
        t = re.sub(r"\s*(filmi|film)$", "", L.get(g, "")).strip()
        if t and t not in tur: tur.append(t)
    o = {"imdb": imdb, "sure": sure, "tur": tur[:3], "ulke": [ULKE.get(L.get(c, ""), L.get(c, "")) for c in cty if L.get(c)],
         "oyuncu": [L[c] for c in cast if L.get(c)][:6]}
    return {k: v for k, v in o.items() if v}
html = open("app/index.html", encoding="utf-8").read()
films = {}
for m in re.finditer(r'\["([a-z0-9-]+)","([^"]+)","([^"]+)",(\d{4}),"', html):
    films[m.group(1)] = (m.group(2), m.group(3), int(m.group(4)))
try:
    sj = json.load(open("app/sahne.json", encoding="utf-8"))
    for v in sj.get("vizyon", []):
        films.setdefault(v[0], (v[1], v[2] or v[1], int(str(v[3])[:4] or 0)))
except Exception as e:
    print("sahne.json okunamadı", e)
os.makedirs("app/afis", exist_ok=True)
outp = "app/afis/afis.json"
try: out = json.load(open(outp, encoding="utf-8"))
except Exception: out = {}
infop = "app/afis/bilgi.json"
try: info = json.load(open(infop, encoding="utf-8"))
except Exception: info = {}
if info.get("_v") != 4: info = {"_v": 4}
for fid, (tr, orig, y) in films.items():
    if fid == "_v": continue
    has_img = fid in out and os.path.exists("app/" + out[fid])
    if has_img and fid in info: continue
    yerli = tr == orig
    tries = [("tr", orig), ("en", orig)] if yerli else [("en", orig), ("tr", tr), ("en", tr)]
    url, got = "", fid in info
    for lang, q in tries:
        try: cands = wiki(lang, q, y)
        except Exception as e: print("wiki hata", fid, e); cands = []
        for u, qd in cands:
            if not got and qd:
                try:
                    b = bilgi(qd, y)
                    if b: info[fid] = b; got = True; url = url or u; print("BİLGİ", fid, qd, b)
                except Exception as e: print("bilgi hata", fid, e)
        if not url and cands and cands[0][0] and got: url = cands[0][0]
        if got and (url or has_img): break
        time.sleep(0.3)
    if has_img: continue
    if not url:
        try: url = itunes(orig, y)
        except Exception as e: print("itunes hata", fid, e)
    if not url:
        print("BULUNAMADI", fid, orig); continue
    try:
        b = get(url, raw=True)
        if len(b) < 2000: raise ValueError("çok küçük")
        ext = "png" if b[:4] == b"\x89PNG" else "jpg"
        name = f"afis/{fid}.{ext}"
        open("app/" + name, "wb").write(b)
        out[fid] = name
        print("OK", fid, url)
    except Exception as e:
        print("indirme hata", fid, e)
    time.sleep(0.3)
json.dump(info, open(infop, "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)
json.dump(out, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)
print(len(out), "/", len(films), "afiş hazır")
