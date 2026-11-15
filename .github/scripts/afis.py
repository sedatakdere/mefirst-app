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
         "prop": "pageimages", "piprop": "thumbnail", "pithumbsize": "500", "pilicense": "any"}
    j = get(f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(p))
    pages = sorted((j.get("query") or {}).get("pages", {}).values(), key=lambda x: x.get("index", 0))
    want = fold(q)
    for pg in pages:
        src = (pg.get("thumbnail") or {}).get("source", "")
        if src and ".svg" not in src.lower() and match(pg.get("title", ""), want):
            return src
    return ""
def itunes(q, y):
    for c in ("tr", "us"):
        j = get("https://itunes.apple.com/search?" + urllib.parse.urlencode({"term": q, "media": "movie", "entity": "movie", "limit": 8, "country": c}))
        want = fold(q)
        for x in j.get("results", []):
            yr = int(str(x.get("releaseDate", "0"))[:4] or 0)
            if x.get("artworkUrl100") and (not y or abs(yr - y) <= 1) and match(x.get("trackName", ""), want):
                return re.sub(r"/\d+x\d+bb\.(jpg|png|webp)$", "/600x900bb.jpg", x["artworkUrl100"])
    return ""
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
for fid, (tr, orig, y) in films.items():
    if fid in out and os.path.exists("app/" + out[fid]): continue
    yerli = tr == orig
    tries = [("tr", orig), ("en", orig)] if yerli else [("en", orig), ("tr", tr), ("en", tr)]
    url = ""
    for lang, q in tries:
        try: url = wiki(lang, q, y)
        except Exception as e: print("wiki hata", fid, e)
        if url: break
        time.sleep(0.3)
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
json.dump(out, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)
print(len(out), "/", len(films), "afiş hazır")
