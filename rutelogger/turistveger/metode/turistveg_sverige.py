#!/usr/bin/env python3
# Lager svenske turistveger i appens turistvegformat fra OpenStreetMap (ODbL). 7. nov 2026, «Kartlag og steder».
# Kandidatliste og vedtak: claude/turistveger-sverige-kandidater-2026-11-07.md (Mikael: A og B, grusveger merkes).
# Tre måter å finne sporet på (se STREKNINGER):
#   osm  – rute-relasjon i OSM (samme metode som Margueritruten, Tools/turistveg_osm.py)
#   ref  – vegbiter med gitte vegnummer innenfor et område; korteste veg mellom endepunktene
#   navn – vegbiter med gitt vegnavn innenfor et område; korteste veg mellom endepunktene
# Grusandel: andel av sporet på veg med surface=gravel/unpaved/… i OSM. «Grusveg» merkes i appen.
#
# Bruk: python3 Tools/turistveg_sverige.py sweden.osm.pbf <ut-mappe> 301
import sys, os, json, math, heapq, collections, unicodedata, re, tempfile, osmium, osmium.filter as F
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import turistveg_osm as T

OSM_KILDE = "© OpenStreetMap-bidragsytere (ODbL)"
GRUS = {"gravel", "unpaved", "compacted", "fine_gravel", "dirt", "ground", "earth", "pebblestone", "grass", "sand"}
SKILTET, NAVNGITT = "Skiltet turistväg", "Navngitt vegstrekning"

# (navn, status, metode, parametre). A/B-nummer fra kandidatlista.
STREKNINGER = [
    ("Turistväg Riksettan", SKILTET, "osm", (2307312, "Örkelljunga", "Vaggeryd")),  # A1
    ("Tre sjöars väg", SKILTET, "osmring", 6440072),                  # A6 (rundtur ved Nora, Örebro län)
    # A3 Tidövägen: «Tidövägen» i OSM er bare en gate i Västerås – strekningen må finnes (kommer).
    ("Vildmarksvägen", NAVNGITT, "via", ["Strömsund", "Gäddede", "Klimpfjäll", "Vilhelmina"]),  # B8 (OSM-relasjonen henger ikke sammen)
    ("Inlandsvägen", NAVNGITT, "ref", (["E 45"], "Göteborg", "Karesuando")),  # B9 (OSM-relasjonen er ufullstendig)
    ("Blå vägen", NAVNGITT, "osm", 3631515),                          # B10
    ("Sagavägen", NAVNGITT, "osm", 2401267),                          # B11
    ("Kopparleden", NAVNGITT, "osm", 3412790),                        # B12
    ("Jungfrukustvägen", NAVNGITT, "osm", 169822),                    # B13
    ("Kustvägen Bohuslän", NAVNGITT, "via", ["Tanumshede", "Grebbestad", "Fjällbacka", "Hamburgsund", "Bovallstrand", "Hunnebostrand", "Kungshamn"]),  # B14
    ("Fiskevägen", NAVNGITT, "via", ["Krokom", "Lillholmsjö", "Valsjöbyn"]),  # B15
    ("Husbyringen", NAVNGITT, "osmring", 557946),                     # B16 (rundtur, Hedemora)
    ("Grönsöö turistväg", SKILTET, "via", ["Enköping", "Boglösa", (59.522, 17.213), "Grillby"]),                       # A2
    ("Tidövägen", SKILTET, "via", ["Västerås", (59.505, 16.490), "Kolbäck"]),                                             # A3
    ("Kulturväg Skaraborg", SKILTET, "via", [(58.172, 13.610), "Broddetorp", "Varnhem", "Tidan"]),                       # A4
    ("Utflyktsvägen", SKILTET, "via", ["Södertälje", "Trosa", "Nyköping", "Oxelösund", "Norrköping"]),          # A7
    ("Kulturvägen Västergötland", NAVNGITT, "via", ["Falköping", "Ulricehamn", "Tranemo"]),                     # B35
    ("Ljungandalsvägen", NAVNGITT, "via", ["Stöde", "Torpshammar", "Ljungaverk", "Borgsjöbyn"]),                # B27
    ("Guldvägen", NAVNGITT, "via", ["Skelleftehamn", "Boliden", "Kristineberg"]),                               # B18
    ("Silvervägen", NAVNGITT, "ref", (["95"], "Skellefteå", None)),    # B17
    ("Barents väg", NAVNGITT, "viahoved", ["Arvidsjaur", "Älvsbyn", "Luleå", "Kalix", "Haparanda"]),  # B19 (rv 94 og E4)
    ("Midnattssolvägen", NAVNGITT, "ref", (["374", "E 45"], "Piteå", "Jokkmokk")),  # B20
    ("Konstvägen sju älvar", NAVNGITT, "ref", (["E 12", "92", "AC 1052"], "Holmsund", "Borgafjäll")),  # B21
    # B24 Ammeråstigen: lv 344 ga feil strekning (Föllinge) – må finnes (kommer).
    ("Flatruetvägen", NAVNGITT, "ref", (["Z 531"], "Funäsdalen", "Ljungdalen")),   # B25
    ("Fäbodvägen", NAVNGITT, "navn", ("Fäbodvägen", "Börtnan", "Persåsen")),      # B26
    ("Tidernas väg", NAVNGITT, "ref", (["272", "83"], "Uppsala", "Ånge")),          # B28
    ("Italienska vägen", NAVNGITT, "navn", ("Italienska vägen", "Mölle", None)),   # B30
    ("Länsväg Y 906", NAVNGITT, "ref", (["Y 906"], None, None)),                    # B32
    ("Nordkalottvägen", NAVNGITT, "ref", (["E 10"], "Kiruna", (68.4250, 18.1300))),  # Riksgränsen      # B33
    ("Norrskensvägen", NAVNGITT, "ref", (["99"], "Haparanda", "Karesuando")),       # B34
]
MARGIN = 0.35   # grader rundt endepunktene for ref/navn
BEREGNET = "beregnet mellom stedene – kan avvike fra skiltingen"
# Kostnad per meter i «via»: hovedveger telles lengre, så turistvegen (oftest den mindre vegen) velges.
VEKT = {"motorway": 4.0, "motorway_link": 4.0, "trunk": 1.6, "trunk_link": 1.6, "primary": 1.25, "primary_link": 1.25}

def norm(r): return r.replace(" ", "").upper()
def pos(x, sted_pos):
    if x is None: return None
    if isinstance(x, tuple): return x
    return sted_pos[x][:2] if x in sted_pos else None
def slug(s):
    s = unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:24]

def main():
    pbf, ut, sort0 = sys.argv[1], sys.argv[2], int(sys.argv[3])
    # 1) steder (endepunkter og navn)
    steder, sted_pos, alle_steder = [], {}, {}
    for n in osmium.FileProcessor(pbf, osmium.osm.NODE).with_filter(F.KeyFilter("place")):
        navn = n.tags.get("name"); typ = n.tags.get("place")
        if not navn: continue
        if typ in ("city", "town", "village"): steder.append((n.location.lat, n.location.lon, navn, typ))
        rang = {"city": 0, "town": 1, "village": 2, "hamlet": 3, "locality": 4, "isolated_dwelling": 5}.get(typ, 9)
        if navn not in sted_pos or rang < sted_pos[navn][2]: sted_pos[navn] = (n.location.lat, n.location.lon, rang)
        alle_steder.setdefault(navn, []).append((n.location.lat, n.location.lon, rang))
    # 2) relasjoner
    def relid(p): return p[0] if isinstance(p, tuple) else p
    rel_ids = {relid(p) for _, _, m, p in STREKNINGER if m in ("osm", "osmring")}
    rels = {}; ref_rel = collections.defaultdict(set)
    for r in osmium.FileProcessor(pbf, osmium.osm.RELATION):
        rels[r.id] = [(x.type, x.ref, x.role) for x in r.members]
        if r.tags.get("route") == "road" and r.tags.get("ref"):
            for x in r.tags["ref"].split(";"): ref_rel[norm(x)].add(r.id)
    def rel_ways(rid, seen=None):
        seen = seen or set(); ut_ = []
        if rid in seen or rid not in rels: return ut_
        seen.add(rid)
        for t, ref, role in rels[rid]:
            if t == "w" and role != "backward": ut_.append(ref)
            elif t == "r": ut_ += rel_ways(ref, seen)
        return ut_
    osm_ways = {rid: set(rel_ways(rid)) for rid in rel_ids}
    # vegbiter som hører til en rute-relasjon med et av vegnumrene (tetter hull der ref mangler på vegen)
    way_ref = collections.defaultdict(set)
    for _, _, metode, p in STREKNINGER:
        if metode == "ref":
            for k in p[0]:
                for rid in ref_rel.get(norm(k), ()):
                    for w in rel_ways(rid): way_ref[w].add(norm(k))
    alle_rel_ways = set().union(*osm_ways.values())
    # områder for ref/navn
    oppgaver = []
    via_bokser = []
    def velg(liste):
        """Stedsnavn → koordinat. Finnes navnet flere steder, velges det som ligger nærmest de andre stedene i lista."""
        entydige = [x if isinstance(x, tuple) else alle_steder[x][0][:2] for x in liste
                    if isinstance(x, tuple) or len(alle_steder.get(x, [])) == 1]
        ut_ = []
        for x in liste:
            if isinstance(x, tuple): ut_.append(x); continue
            kand = alle_steder.get(x)
            if not kand: print(f"!! fant ikke stedet {x}"); continue
            ref_ = entydige or [k[:2] for y in liste if not isinstance(y, tuple) for k in alle_steder.get(y, [])[:1]]
            beste = min(kand, key=lambda k: (sum(T.m(k[:2], r) for r in ref_), k[2]))
            ut_.append(beste[:2])
        return ut_
    via_punkter = {}
    for i, (navn, status, metode, p) in enumerate(STREKNINGER):
        if metode in ("via", "viahoved"):
            q = velg(p); via_punkter[i] = q
            via_bokser.append((i, metode, (min(a[0] for a in q) - 0.12, max(a[0] for a in q) + 0.12, min(a[1] for a in q) - 0.25, max(a[1] for a in q) + 0.25)))
            continue
        if metode in ("osm", "osmring"): continue
        nøkler, a, b = p
        punkter = [q for q in (pos(a, sted_pos), pos(b, sted_pos)) if q]
        for x in (a, b):
            if x and pos(x, sted_pos) is None: print(f"!! {navn}: fant ikke stedet {x}")
        if punkter:
            boks = (min(q[0] for q in punkter) - MARGIN, max(q[0] for q in punkter) + MARGIN,
                    min(q[1] for q in punkter) - MARGIN * 2, max(q[1] for q in punkter) + MARGIN * 2)
            if len(punkter) == 1:   # bare start: større område
                boks = (boks[0] - 1, boks[1] + 1, boks[2] - 2, boks[3] + 2)
        else:
            boks = (55, 69.1, 10, 24.2)
        oppgaver.append((i, metode, {norm(k) for k in nøkler} if metode == "ref" else nøkler, boks))
    # 3) vegbiter med posisjoner (indeks på disk)
    idx = os.path.join(T.mellomlager_mappe(), "turistveg_se_nodeindeks.bin")
    biter = collections.defaultdict(list)   # strekningsindeks -> [(punkter, grus)]
    grus_ways = {}
    fp = (osmium.FileProcessor(pbf, osmium.osm.NODE | osmium.osm.WAY).with_locations(f"sparse_file_array,{idx}")
          .with_filter(F.EntityFilter(osmium.osm.WAY)).with_filter(F.KeyFilter("highway")))
    try:
        for w in fp:
            tags = w.tags
            i_rel = w.id in alle_rel_ways
            refs = {norm(x) for x in (tags.get("ref") or "").split(";") if x.strip()} | way_ref.get(w.id, set())
            mc = via_bokser and T_mc(tags)
            navn = tags.get("name") or ""
            treff = []
            for i, metode, nøkler, boks in oppgaver:
                if (metode == "ref" and refs & nøkler) or (metode == "navn" and navn == nøkler): treff.append((i, boks))
            if not i_rel and not treff and not mc: continue
            p = [(n.location.lat, n.location.lon) for n in w.nodes if n.location.valid()]
            if len(p) < 2: continue
            if mc:
                vekt = VEKT.get(tags.get("highway"), 1.0)
                for i, vm, boks in via_bokser:
                    if any(boks[0] <= q[0] <= boks[1] and boks[2] <= q[1] <= boks[3] for q in (p[0], p[-1])):
                        biter[i].append((p, tags.get("surface") in GRUS or tags.get("highway") == "track", vekt if vm == "via" else 1.0))
            grus = tags.get("surface") in GRUS or (tags.get("highway") == "track")
            if not i_rel and not treff: continue
            for rid, ws in osm_ways.items():
                if w.id in ws:
                    i = next(k for k, s in enumerate(STREKNINGER) if s[2] in ("osm", "osmring") and relid(s[3]) == rid)
                    biter[i].append((p, grus))
            for i, boks in treff:
                if any(boks[0] <= q[0] <= boks[1] and boks[2] <= q[1] <= boks[3] for q in (p[0], p[-1])):
                    biter[i].append((p, grus))
    finally:
        if os.path.exists(idx): os.remove(idx)
    # 4) spor per strekning
    os.makedirs(os.path.join(ut, "turistveger"), exist_ok=True)
    index = []; nr_ref = [0]
    for i, (navn, status, metode, p) in enumerate(STREKNINGER):
        bb = biter.get(i, [])
        if not bb: print(f"!! {navn}: ingen vegbiter"); continue
        grus_pkt = {T.key(q) for b_ in bb if b_[1] for q in b_[0]}
        if metode == "osmring":
            alle = [q for b_ in bb for q in b_[0]]
            sl = sum(q[0] for q in alle) / len(alle); so = sum(q[1] for q in alle) / len(alle)
            # ytterpunktene i fire retninger, i rekkefølge rundt midten, og tilbake til start
            ytter = [max(alle, key=f) for f in (lambda q: q[0], lambda q: q[1], lambda q: -q[0], lambda q: -q[1])]
            ytter.sort(key=lambda q: math.atan2(q[0] - sl, (q[1] - so) * math.cos(math.radians(sl))))
            sti = via_sti([(b_[0], b_[1], 1.0) for b_ in bb], ytter + ytter[:1])
            spor = [sti] if sti else []
            lag_filer(navn, status, metode, spor, grus_pkt, steder, ut, index, sort0, nr_ref)
            continue
        if metode in ("via", "viahoved"):
            sti = via_sti(bb, via_punkter[i])
            spor = T.del_opp(sti, sum(T.m(x, y) for x, y in zip(sti, sti[1:]))) if sti else []
            lag_filer(navn, status, metode, spor, grus_pkt, steder, ut, index, sort0, nr_ref)
            continue
        nett = T.Nett([(b_[0], False) for b_ in bb]); nett.sl_sammen(); nett.koble_hull(300 if metode == "osm" else 1500)
        spor = []
        ende = (p[1], p[2]) if isinstance(p, tuple) else (None, None)
        if ende == (None, None):
            for _ in range(30):
                nett.sl_sammen()
                if nett.rydd() == 0: break
            nett.sl_sammen()
            for e in sorted(nett.E.values(), key=lambda e: -e[3]):
                if e[3] / 1000 >= (T.MIN_KM if metode == "osm" else 1): spor += T.del_opp(e[2], e[3])
            if metode != "osm": spor = spor[:1] if spor else []
        else:
            a = pos(ende[0], sted_pos); b = pos(ende[1], sted_pos)
            sti = korteste(nett, a, b)
            if sti: spor = T.del_opp(sti, sum(T.m(x, y) for x, y in zip(sti, sti[1:])))
        lag_filer(navn, status, metode, spor, grus_pkt, steder, ut, index, sort0, nr_ref)
    json.dump(index, open(os.path.join(ut, "index-SE.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for x in index: print(f"  {x['id']:30s} {x['name']:24s} {x['fromTo']:34s} {x['lengthKm']:6.1f} km  grus {x['gravelShare']:.0%}")
    print(f"{len(index)} strekninger, {sum(x['lengthKm'] for x in index):.0f} km")

def lag_filer(navn, status, metode, spor, grus_pkt, steder, ut, index, sort0, nr_ref):
        if not spor: print(f"!! {navn}: fant ikke sammenhengende spor"); return
        for del_spor in spor:
            del_spor = T.tynn(del_spor); l = sum(T.m(x, y) for x, y in zip(del_spor, del_spor[1:]))
            if l < 2000: continue
            g = sum(T.m(x, y) for x, y in zip(del_spor, del_spor[1:]) if T.key(x) in grus_pkt and T.key(y) in grus_pkt) / l
            a_n, b_n = T.stedsnavn(del_spor[0], steder), T.stedsnavn(del_spor[-1], steder)
            fra_til = f"{a_n} – {b_n}" if a_n != b_n else f"rundt {a_n}"
            nr_ref[0] += 1; nr = nr_ref[0]; rid = f"se-{slug(navn)}-{nr:02d}"
            rute = {"id": rid, "name": navn, "fromTo": fra_til, "lengthKm": round(l / 1000, 1),
                    "trackPoints": [[round(x[0], 5), round(x[1], 5)] for x in del_spor],
                    "viaPoints": [[round(x[0], 5), round(x[1], 5)] for x in T.via(del_spor)],
                    "country": "SE", "source": OSM_KILDE, "official": status == SKILTET,
                    "note": status + (f" ({BEREGNET})" if metode in ("via", "viahoved") else ""), "gravelShare": round(g, 2)}
            json.dump(rute, open(os.path.join(ut, "turistveger", rid + ".json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
            index.append({k: rute[k] for k in ("id", "name", "fromTo", "lengthKm", "country", "source", "official", "note", "gravelShare")}
                         | {"sortOrder": sort0 + nr - 1, "pointCount": len(del_spor)})

def T_mc(tags):
    import steder_til_app as S   # samme definisjon av «veg en MC kan kjøre på»
    return S.mc_veg(tags)

def via_sti(bb, punkter):
    """Korteste vektede veg gjennom punktene i rekkefølge, på alle MC-veger i området."""
    # Hvert punkt er en node (vegene møtes ofte midt på en vegbit, ikke bare i endene).
    G = collections.defaultdict(list)
    for pts, g, vekt in bb:
        for x, y in zip(pts, pts[1:]):
            a, b = T.key(x), T.key(y); l = T.m(x, y) * vekt
            G[a].append((b, l, [x, y])); G[b].append((a, l, [y, x]))
    noder = list(G)
    if not noder or len(punkter) < 2: return None
    # nærmeste node med minst 2 naboer (en veg, ikke en blindvei-ende)
    def nærmest(q): return min((n for n in noder if len(G[n]) >= 2), key=lambda n: T.m(n, q))
    sti = []
    for q0, q1 in zip(punkter, punkter[1:]):
        s0, s1 = nærmest(q0), nærmest(q1)
        dist = {s0: 0}; forrige = {}; kø = [(0, s0)]
        while kø:
            d, n = heapq.heappop(kø)
            if n == s1: break
            if d > dist[n]: continue
            for m_, w, pts in G[n]:
                if d + w < dist.get(m_, 1e18): dist[m_] = d + w; forrige[m_] = (n, pts); heapq.heappush(kø, (d + w, m_))
        if s1 not in forrige and s1 != s0: print("   (ingen veg mellom to steder)"); return None
        del_ = []; n = s1
        while n != s0:
            p, pts = forrige[n]; del_ = pts[:-1] + del_ if del_ else pts; n = p
        sti = sti + del_[1:] if sti else del_
    return sti

def korteste(nett, a, b):
    """Korteste veg i nettet fra nærmeste node ved a til nærmeste node ved b (b=None: lengst unna a)."""
    A = nett.adj(); noder = list(A)
    if not noder: return None
    na = min(noder, key=lambda n: T.m(n, a))
    dist = {na: 0}; forrige = {}; kø = [(0, na)]
    while kø:
        d, n = heapq.heappop(kø)
        if d > dist.get(n, 1e18): continue
        for i in A[n]:
            e = nett.E[i]; m_ = e[1] if e[0] == n else e[0]
            nd = d + e[3]
            if nd < dist.get(m_, 1e18): dist[m_] = nd; forrige[m_] = (n, i); heapq.heappush(kø, (nd, m_))
    nb = min(dist, key=lambda n: T.m(n, b)) if b else max(dist, key=lambda n: dist[n])
    if b and T.m(nb, b) > 25000: print(f"   (endepunkt {T.m(nb, b) / 1000:.0f} km fra målet)")
    sti = []; n = nb
    while n != na:
        p, i = forrige[n]; e = nett.E[i]
        pts = e[2] if e[1] == n else e[2][::-1]
        sti = pts[:-1] + sti if sti else pts
        n = p
    return sti if len(sti) >= 2 else None

if __name__ == "__main__":
    main()
