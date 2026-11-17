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
    p = {"action": "query", "format": "json", "generator": "search", "gsrsearch": f"{q} {y} film".replace("  ", " "), "gsrlimit": "5",
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
    j = get("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({"action": "wbgetentities", "format": "json", "ids": qid, "props": "claims|sitelinks"}))
    E = (j.get("entities") or {}).get(qid) or {}
    C = E.get("claims") or {}
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
    # eleştirmen/izleyici puanları (Wikidata P444, kaynak P447)
    KAYNAK = {"Q37312": "IMDb", "Q105584": "Rotten Tomatoes", "Q150248": "Metacritic"}
    puan = {}
    for c in C.get("P444", []):
        v = ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value")
        q = ((c.get("qualifiers") or {}).get("P447") or [{}])[0]
        src = (((q.get("datavalue") or {}).get("value")) or {}).get("id", "")
        if not (isinstance(v, str) and src in KAYNAK): continue
        k, v = KAYNAK[src], v.strip()
        if k == "Rotten Tomatoes":
            if not v.endswith("%"): continue
            v = "%" + v[:-1].strip()
        puan[k] = v
    # Oscar ödülleri (P166 = kazandığı ödüller)
    aw = [v.get("id") for v in vals("P166", 40) if isinstance(v, dict)]
    oscar = 0
    if aw:
        try:
            jj = get("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({"action": "wbgetentities", "format": "json", "ids": "|".join(aw[:50]), "props": "labels", "languages": "en"}))
            oscar = sum(1 for e in (jj.get("entities") or {}).values() if ((e.get("labels") or {}).get("en") or {}).get("value", "").startswith("Academy Award for"))
        except Exception: pass
    yon = [v.get("id") for v in vals("P57", 2) if isinstance(v, dict)]
    LY = labels(yon) if yon else {}
    # konusu: Türkçe Vikipedi'nin giriş paragrafı
    konu = ""
    tt = ((E.get("sitelinks") or {}).get("trwiki") or {}).get("title", "")
    if tt:
        try:
            jj = get("https://tr.wikipedia.org/w/api.php?" + urllib.parse.urlencode({"action": "query", "format": "json", "prop": "extracts", "exintro": "1", "explaintext": "1", "exsentences": "4", "titles": tt}))
            pg = next(iter((jj.get("query") or {}).get("pages", {}).values()), {})
            konu = re.sub(r"\s*\([^()]*\)", "", pg.get("extract", "")).strip()[:600]
        except Exception: pass
    o = {"imdb": imdb, "sure": sure, "puan": puan, "oscar": oscar, "yonetmen": [LY[x] for x in yon if LY.get(x)], "konu": konu, "tur": tur[:3], "ulke": [ULKE.get(L.get(c, ""), L.get(c, "")) for c in cty if L.get(c)],
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

# ---- Arama ile büyüyen film kataloğu: wants.json (kind=film "wd:Q.. Ad", kind=sahne serbest arama) -> app/afis/katalog.json ----
def wd_entity(qid):
    j = get("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({"action": "wbgetentities", "format": "json", "ids": qid, "props": "labels|descriptions|claims|sitelinks", "languages": "tr|en"}))
    return (j.get("entities") or {}).get(qid) or {}
def wd_film(qid):
    E = wd_entity(qid)
    C = E.get("claims") or {}
    inst = [((c.get("mainsnak") or {}).get("datavalue") or {}).get("value", {}).get("id") for c in C.get("P31", [])]
    FILM = {"Q11424", "Q24862", "Q506240", "Q202866", "Q93204", "Q24869", "Q229390", "Q130232", "Q157394", "Q188473", "Q1054574", "Q1257444"}
    if not any(i in FILM for i in inst): return None
    L = E.get("labels") or {}
    tr = (L.get("tr") or L.get("en") or {}).get("value", "")
    en = (L.get("en") or L.get("tr") or {}).get("value", "")
    y = 0
    for c in C.get("P577", [])[:3]:
        t = str((((c.get("mainsnak") or {}).get("datavalue") or {}).get("value") or {}).get("time", ""))
        if t[1:5].isdigit(): y = int(t[1:5]); break
    yon = [((c.get("mainsnak") or {}).get("datavalue") or {}).get("value", {}).get("id") for c in C.get("P57", [])[:2]]
    LY = labels([x for x in yon if x]) if any(yon) else {}
    D = E.get("descriptions") or {}
    line = (D.get("tr") or D.get("en") or {}).get("value", "")
    if not tr or not y: return None
    return {"id": "wd-" + qid, "q": qid, "t": tr, "o": en, "y": y, "d": ", ".join(LY[x] for x in yon if LY.get(x)), "line": line[:1].upper() + line[1:]}
katp = "app/afis/katalog.json"
try: kat = json.load(open(katp, encoding="utf-8"))
except Exception: kat = {"films": []}
have = {f["id"] for f in kat.get("films", [])} | set(films.keys())
have_names = {fold(v[1]) for v in films.values()} | {fold(f["o"]) for f in kat.get("films", [])}
try: W = json.load(open("app/wants.json", encoding="utf-8")).get("wants", [])
except Exception: W = []
for w in W[:80]:
    q, kind = str(w.get("q", "")), w.get("kind", "")
    try:
        qid = ""
        m = re.match(r"wd:(q\d+)", q, re.I)
        if kind == "film" and m: qid = m.group(1).upper()
        elif kind == "sahne" and len(q) >= 3:
            for lang in ("tr", "en"):
                for src, qd in wiki(lang, q, ""):
                    if qd: qid = qd; break
                if qid: break
        if not qid or "wd-" + qid in have: continue
        f = wd_film(qid)
        if not f or fold(f["o"]) in have_names: continue
        kat["films"].append(f); have.add(f["id"]); have_names.add(fold(f["o"]))
        films[f["id"]] = (f["t"], f["o"], f["y"])
        print("KATALOG +", f["id"], f["t"], f["y"])
    except Exception as x:
        print("katalog hata", q, x)
    time.sleep(0.3)
# ---- Me First Sineması: Wikidata'dan sevilen filmlerle kataloğu büyüt (her turda en çok TOHUM_N yeni film) ----
TOHUM_N = int(os.environ.get("TOHUM_N", "170")); YERLI_N = 70
GMAP = {"Q1054574": "ask", "Q860626": "ask", "Q157443": "gul", "Q859369": "gul", "Q130232": "agla", "Q842256": "iyi", "Q1361932": "iyi", "Q2973181": "iyi"}
SICAK = {"Q1054574", "Q860626", "Q157443", "Q859369", "Q842256", "Q1361932", "Q2973181"}
BAD = {"Q188473", "Q959790", "Q2484376", "Q200092", "Q369747", "Q471839", "Q1535153", "Q7444356", "Q496523", "Q1200678", "Q172980", "Q1341051", "Q846544",
       "Q853630", "Q1342372", "Q185529", "Q20442589", "Q1270142", "Q2421031", "Q7174604", "Q645928", "Q3072049", "Q19367312", "Q2297927", "Q1146335", "Q192881"}
def sparql(q):
    req = urllib.request.Request("https://query.wikidata.org/sparql?" + urllib.parse.urlencode({"query": q, "format": "json"}), headers={**UA, "Accept": "application/sparql-results+json"})
    with urllib.request.urlopen(req, timeout=120) as r: return json.loads(r.read().decode("utf-8"))["results"]["bindings"]
def tohum():
    G = " ".join("wd:" + g for g in GMAP)
    qs = [f"""SELECT ?f (SAMPLE(?sl) AS ?s) (GROUP_CONCAT(DISTINCT STRAFTER(STR(?ag),"entity/");separator=",") AS ?gs) WHERE {{
      {{ SELECT DISTINCT ?f ?sl WHERE {{ ?f wdt:P31 wd:Q11424; wikibase:sitelinks ?sl; wdt:P136 ?g. VALUES ?g {{ {G} }} FILTER(?sl > 40)
        ?a schema:about ?f; schema:isPartOf <https://tr.wikipedia.org/>. }} }}
      ?f wdt:P577 ?d. FILTER(YEAR(?d) >= 1950) OPTIONAL {{ ?f wdt:P136 ?ag. }}
    }} GROUP BY ?f ORDER BY DESC(?s) LIMIT 900""",
          """SELECT ?f (SAMPLE(?sl) AS ?s) (GROUP_CONCAT(DISTINCT STRAFTER(STR(?ag),"entity/");separator=",") AS ?gs) WHERE {
      { SELECT DISTINCT ?f ?sl WHERE { ?f wdt:P31 wd:Q11424; wdt:P495 wd:Q43; wikibase:sitelinks ?sl. FILTER(?sl > 5)
        ?a schema:about ?f; schema:isPartOf <https://tr.wikipedia.org/>. } }
      OPTIONAL { ?f wdt:P136 ?ag. }
    } GROUP BY ?f ORDER BY DESC(?s) LIMIT 300"""]
    out = [[], []]
    for i, q in enumerate(qs):
        for deneme in range(3):
            try:
                for b in sparql(q):
                    qid = b["f"]["value"].rsplit("/", 1)[-1]
                    gs = set((b.get("gs") or {}).get("value", "").split(",")) - {""}
                    if gs & BAD: continue
                    if i == 0 and not (gs & SICAK) and "Q130232" not in gs: continue
                    out[i].append((int(b["s"]["value"]), qid, gs, i == 1))
                print("SPARQL", i, len(out[i])); break
            except Exception as e: print("SPARQL hata", i, deneme, e); time.sleep(10)
        time.sleep(2)
    # önce sıcak türler (aşk/komedi/müzikal), sonra dramlar; yerliler ayrı kotayla
    out[0].sort(key=lambda x: (not (x[2] & SICAK), -x[0]))
    return out
# önceki turda tür süzgeci olmadan eklenenleri temizle
if not kat.get("v2"):
    eski = [f for f in kat.get("films", []) if "p" in f]
    kat["films"] = [f for f in kat.get("films", []) if "p" not in f]
    for f in eski:
        have.discard(f["id"]); have_names.discard(fold(f["o"])); films.pop(f["id"], None)
    kat["v2"] = 1; print("eski tohum temizlendi:", len(eski))
eklenen = 0
T = tohum() if TOHUM_N > 0 else [[], []]
for liste, kota in ((T[0], TOHUM_N - YERLI_N), (T[1], YERLI_N)):
    n = 0
    for sl, qid, gs, yerli in liste:
        if n >= kota: break
        if "wd-" + qid in have: continue
        try:
            f = wd_film(qid)
            if not f or fold(f["o"]) in have_names: continue
            g = {GMAP[x] for x in gs if x in GMAP} | ({"gul"} if "Q860626" in gs else set())
            if f["y"] < 1985 or (yerli and f["y"] < 1995): g.add("nost")
            if yerli: f["tr"] = 1
            f["g"] = sorted(g); f["p"] = sl
            kat["films"].append(f); have.add(f["id"]); have_names.add(fold(f["o"])); n += 1; eklenen += 1
            print("SİNEMA +", f["id"], f["t"], f["y"], f["g"])
        except Exception as x: print("tohum hata", qid, x)
        time.sleep(0.25)
print("Sinemaya eklenen:", eklenen, "toplam katalog:", len(kat.get("films", [])))
for f in kat.get("films", []): films.setdefault(f["id"], (f["t"], f["o"], f["y"]))
kat["updated"] = time.strftime("%Y-%m-%d")
json.dump(kat, open(katp, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
os.makedirs("app/afis", exist_ok=True)
outp = "app/afis/afis.json"
try: out = json.load(open(outp, encoding="utf-8"))
except Exception: out = {}
infop = "app/afis/bilgi.json"
try: info = json.load(open(infop, encoding="utf-8"))
except Exception: info = {}
if info.get("_v") != 6: info = {"_v": 6}
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

# ---- Sahne etkinlikleri: mekân fotoğrafı, oyun afişi (og:image), sanatçı/mekân tek satır bilgi ----
def wsum(lang, q, strict=True):
    p = {"action": "query", "format": "json", "generator": "search", "gsrsearch": q, "gsrlimit": "4", "prop": "pageimages|extracts",
         "exintro": "1", "explaintext": "1", "exsentences": "1", "exlimit": "4", "piprop": "thumbnail", "pithumbsize": "640", "pilicense": "any"}
    j = get(f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(p))
    want = fold(q)
    for pg in sorted((j.get("query") or {}).get("pages", {}).values(), key=lambda x: x.get("index", 0)):
        t = fold(re.sub(r"\(.*?\)", "", pg.get("title", "")))
        if t == want or (not strict and match(pg.get("title", ""), want)):
            src = (pg.get("thumbnail") or {}).get("source", "")
            if ".svg" in src.lower() or re.search(r"logo|emblem|amblem", src, re.I): src = ""
            ex = re.sub(r"\s*\(.*?\)", "", pg.get("extract", "")).strip()
            return {"src": src, "ex": ex[:220], "wp": f"{lang}:{pg.get('title','')}"}
    return None
def og(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        h = r.read(300000).decode("utf-8", "ignore")
    m = re.search(r'<meta[^>]+(?:property|name)=["\'](?:og:image(?::secure_url)?|twitter:image)["\'][^>]*content=["\']([^"\']+)', h, re.I) or \
        re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\'](?:og:image|twitter:image)["\']', h, re.I)
    if not m: return ""
    u = urllib.parse.urljoin(url, m.group(1).replace("&amp;", "&").strip())
    return "" if re.search(r"logo|favicon|default|placeholder|no-?image|share-?image|site-?image|apple-touch", u, re.I) else u
def artist(t):
    t = re.sub(r"\(.*?\)", "", t)
    t = re.split(r"\s+[-–—:|·]\s+|\s+ile\s+|\s+&\s+|,", t)[0]
    t = re.sub(r"\s*(konseri|konser|stand-?up|gösterisi|show|tour|turnesi|world tour).*$", "", t, flags=re.I).strip()
    return t if 3 <= len(t) <= 40 else ""
def venue(v):
    return re.split(r",|\(", v)[0].strip()
def save_img(key, url):
    b = get(url, raw=True)
    if len(b) < 3000: raise ValueError("çok küçük")
    ext = "png" if b[:4] == b"\x89PNG" else "jpg"
    name = f"afis/{key}.{ext}"
    open("app/" + name, "wb").write(b)
    return name
try: events = json.load(open("app/sahne.json", encoding="utf-8")).get("sahne", [])
except Exception: events = []
links = {}
for e in events:
    if len(e) > 8 and e[8]: links[e[8]] = links.get(e[8], 0) + 1
VCACHE = {}
SKIP_OG = {"t20261210-kaspar-bursa"}  # logo/boş görsel dönenler
SANAT = re.compile(r"şarkıcı|müzisyen|sanatçı|besteci|komedyen|oyuncu|piyanist|grup|orkestra|keman|kanun|gitarist|rapçi|söz yazarı|singer|musician|band|comedian|composer", re.I)
for e in events:
    eid = e[0]
    if out.get(eid, "").startswith("afis/m-"): out.pop(eid)
    if eid in out and eid in info: continue
    kind, title, ven, link = e[2], e[1], venue(e[6] or ""), (e[8] if len(e) > 8 else "")
    B = info.get(eid) or {}
    try:
        if kind in ("konser", "standup") and "sanatci" not in B:
            a = artist(title)
            r = wsum("tr", a) if a else None
            if r and r["ex"] and SANAT.search(r["ex"]): B["sanatci"] = r["ex"]; B["wp"] = r["wp"]
        if ven and "mekan" not in B:
            if ven not in VCACHE:
                try: VCACHE[ven] = wsum("tr", ven)
                except Exception as x: print("mekan hata", ven, x); VCACHE[ven] = None
            r = VCACHE[ven]
            if r and r["ex"]: B["mekan"] = r["ex"]
        if eid not in out:
            u = ""
            if kind not in ("konser", "standup") and link.startswith("https://") and links.get(link, 0) == 1 and eid not in SKIP_OG:
                try: u = og(link)
                except Exception as x: print("og hata", eid, x)
            if False and not u and VCACHE.get(ven) and VCACHE[ven]["src"]:
                vk = "m-" + re.sub(r"[^a-z0-9]+", "-", fold(ven)).strip("-")[:40]
                if vk not in out:
                    try: out[vk] = save_img(vk, VCACHE[ven]["src"])
                    except Exception as x: print("mekan foto hata", ven, x)
                if vk in out: out[eid] = out[vk]
            elif u:
                try: out[eid] = save_img("e-" + eid[:60], u)
                except Exception as x: print("afiş hata", eid, x)
        info[eid] = B
        if B or eid in out: print("SAHNE", eid, out.get(eid, "-"), list(B))
    except Exception as x:
        print("sahne hata", eid, x)
    time.sleep(0.2)
json.dump(info, open(infop, "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)
json.dump(out, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)
print(len(out), "/", len(films), "afiş hazır")
