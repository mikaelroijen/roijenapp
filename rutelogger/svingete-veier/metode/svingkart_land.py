#!/usr/bin/env python3
"""
RuteLogger – svingkart for hele land (Norge, Sverige …) fra Geofabrik .osm.pbf

Samme metode som svingkart_pilot_v5.py (godkjent av Tellef 15. okt 2026),
men leser landsfiler direkte i stedet for Overpass.

Kjøres i din egen Terminal, f.eks.:
    cd ~/Downloads
    python3 svingkart_land.py norway-latest.osm.pbf sweden-latest.osm.pbf

Hver .pbf-fil leses i to omganger (1: landeveiene, 2: koordinatene til nodene
deres), så bare det vi trenger holdes i minnet. Resultatet lagres i en
mellomfil (svingdata_<navn>.pkl) ved siden av skriptet, så en ny kjøring med
andre terskler slipper å lese .pbf på nytt. Slett .pkl-fila hvis du laster ned
en nyere .pbf.

Utdata (i mappen du står i):
    svingkart_land.csv   alle svingete partier, svingeteste først
    svingkart_land.json  kompakt fil for appen (partier med punkt hver ~100 m)
    svingkart_land.html  kart over alle partiene (åpnes i nettleser)

Krever pyosmium (pip3 install osmium), som du installerte 4. okt.

Metode (som v5):
  - Veityper trunk, primary, secondary, tertiary.
  - Biter med fartsgrense <= 40 km/t tas ut (--maks-tettsted).
  - Grusbiter (surface=gravel/unpaved/…) tas ut (--tillat-grus for å beholde).
  - Biter med samme ref/navn settes sammen gjennom kryss (maks 60° knekk).
  - Svingete parti: sentrert 1 km-vindu >= 150 °/km, hull <= 1500 m slås
    sammen, minst 2 km. Rangert etter totale svingegrader.
"""
import argparse, csv, json, math, os, pickle, sys, time, webbrowser
from array import array
from collections import defaultdict

try:
    import osmium
except ImportError:
    sys.exit("Finner ikke pyosmium. Installer med:  pip3 install osmium")

RESAMPLE_M = 20.0
MIN_DREIING_GRADER = 2.0
MAKS_KNEKK_GRADER = 60.0
STANDARD_VEITYPER = "trunk,primary,secondary,tertiary"
ASFALT = {"asphalt", "paved", "concrete", "chipseal", "paving_stones", "sett",
          "concrete:plates", "concrete:lanes"}
GRUS = {"gravel", "unpaved", "compacted", "fine_gravel", "dirt", "ground",
        "earth", "sand", "grass", "mud", "pebblestone", "rock"}
CACHE_VERSJON = 1

KLASSER = [  # (nedre grense grader/km, navn, farge)
    (0,   "rett",           "#9aa5b1"),
    (60,  "litt svingete",  "#f2c94c"),
    (150, "svingete",       "#f2994a"),
    (300, "veldig svingete","#eb5757"),
    (500, "kronglete",      "#9b51e0"),
]

# ---------------------------------------------------------------- geometri

def klasse(gpk):
    valgt = KLASSER[0]
    for k in KLASSER:
        if gpk >= k[0]:
            valgt = k
    return valgt

def hav(a, b):
    R = 6371000.0
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    d = math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 2*R*math.asin(math.sqrt(d))

def peiling(a, b):
    la1, la2 = math.radians(a[0]), math.radians(b[0])
    dlo = math.radians(b[1]-a[1])
    y = math.sin(dlo)*math.cos(la2)
    x = math.cos(la1)*math.sin(la2) - math.sin(la1)*math.cos(la2)*math.cos(dlo)
    return (math.degrees(math.atan2(y, x)) + 360) % 360

def vinkelforskjell(a, b):
    return abs((a - b + 180) % 360 - 180)

def resample(pts, steg=RESAMPLE_M):
    if len(pts) < 2:
        return pts
    ut = [pts[0]]
    neste = steg
    akk = 0.0
    for i in range(len(pts)-1):
        a, b = pts[i], pts[i+1]
        d = hav(a, b)
        while d > 0 and neste <= akk + d:
            t = (neste - akk) / d
            ut.append((a[0] + (b[0]-a[0])*t, a[1] + (b[1]-a[1])*t))
            neste += steg
        akk += d
    return ut

def dreininger(r):
    pb = [peiling(r[i], r[i+1]) for i in range(len(r)-1)]
    d = []
    for i in range(len(pb)-1):
        x = vinkelforskjell(pb[i+1], pb[i])
        d.append(x if x >= MIN_DREIING_GRADER else 0.0)
    return d

def tell_krappe(d):
    krappe, vindu, i_sving = 0, [], False
    for x in d:
        vindu.append(x)
        if len(vindu) > 3:
            vindu.pop(0)
        if not i_sving and sum(vindu) >= 60:
            krappe += 1
            i_sving = True
        elif i_sving and x < MIN_DREIING_GRADER * 2:
            i_sving = False
            vindu = []
    return krappe

def finn_partier(r, d, vindu_m, min_gpk, min_parti_m, maks_gap_m):
    n = len(d)
    w = max(3, int(round(vindu_m / RESAMPLE_M)))
    if n < w:
        return []
    h = w // 2
    pre = [0.0]
    for x in d:
        pre.append(pre[-1] + x)
    merket = [False] * n
    for j in range(n):
        lo, hi = max(0, j - h), min(n, j + h + 1)
        km = (hi - lo) * RESAMPLE_M / 1000.0
        merket[j] = (pre[hi] - pre[lo]) / km >= min_gpk
    partier, i = [], 0
    while i < n:
        if merket[i]:
            slutt = i
            while slutt + 1 < n and merket[slutt + 1]:
                slutt += 1
            a, z = i, slutt
            b = max(1, int(round(200 / RESAMPLE_M)))
            bit_terskel = 0.5 * min_gpk * b * RESAMPLE_M / 1000.0
            while z - a + 1 > b and sum(d[a:a + b]) < bit_terskel:
                a += b
            while z - a + 1 > b and sum(d[z - b + 1:z + 1]) < bit_terskel:
                z -= b
            if (z + 2 - a) * RESAMPLE_M >= 200:
                partier.append((a, z + 2))
            i = slutt + 1
        else:
            i += 1
    sammen = []
    for fra, til in partier:
        if sammen and (fra - sammen[-1][1]) * RESAMPLE_M <= maks_gap_m:
            sammen[-1] = (sammen[-1][0], til)
        else:
            sammen.append((fra, til))
    return [(f, t) for f, t in sammen if (t - f) * RESAMPLE_M >= min_parti_m]

def fartsgrense(v):
    tall = "".join(ch for ch in (v or "").split(";")[0] if ch.isdigit())
    return int(tall) if tall else None

def dekkegruppe(s):
    s = (s or "").split(";")[0].strip()
    if not s:
        return "mangler"
    if s in ASFALT:
        return "asfalt"
    if s in GRUS:
        return "grus"
    return "annet"

# ---------------------------------------------------------------- lesing av .pbf

class VeiLeser(osmium.SimpleHandler):
    """Omgang 1: landeveier med tagger og node-id-er."""
    def __init__(self, veityper):
        super().__init__()
        self.veityper = veityper
        self.veier = []
        self.noder = set()
        self.antall = 0

    def way(self, w):
        self.antall += 1
        if self.antall % 2_000_000 == 0:
            print(f"    … {self.antall/1e6:.0f} mill. veier lest, {len(self.veier)} landeveibiter", flush=True)
        t = w.tags
        hw = t.get("highway")
        if hw not in self.veityper:
            return
        refs = array("q", (n.ref for n in w.nodes))
        if len(refs) < 2:
            return
        ref, navn = t.get("ref", ""), t.get("name", "")
        self.veier.append({"id": w.id, "nokkel": ref or navn or f"uten navn #{w.id}",
                           "navn": navn, "ref": ref, "type": hw,
                           "dekke": dekkegruppe(t.get("surface")),
                           "fart": fartsgrense(t.get("maxspeed")), "refs": refs})
        self.noder.update(refs)

class NodeLeser(osmium.SimpleHandler):
    """Omgang 2 (reserve): koordinater for nodene vi trenger."""
    def __init__(self, trengs):
        super().__init__()
        self.trengs = trengs
        self.pos = {}

    def node(self, n):
        if n.id in self.trengs:
            self.pos[n.id] = (n.location.lat, n.location.lon)

def hent_nodeposisjoner(sti, trengs):
    # Raskest: la libosmium filtrere på id i C++ (pyosmium 4.x).
    try:
        ids = sorted(trengs)
        fp = osmium.FileProcessor(sti, osmium.osm.NODE).with_filter(osmium.filter.IdFilter(ids))
        pos = {}
        for n in fp:
            pos[n.id] = (n.location.lat, n.location.lon)
        return pos
    except (AttributeError, TypeError):
        pass
    leser = NodeLeser(trengs)
    leser.apply_file(sti)
    return leser.pos

def les_pbf(sti, veityper):
    navn = os.path.basename(sti).replace(".osm.pbf", "").replace(".pbf", "").replace("-latest", "")
    mappe = os.path.dirname(os.path.abspath(__file__))
    cache = os.path.join(mappe, f"svingdata_{navn}.pkl")
    if os.path.exists(cache) and os.path.getmtime(cache) > os.path.getmtime(sti):
        with open(cache, "rb") as f:
            data = pickle.load(f)
        if data.get("versjon") == CACHE_VERSJON and data.get("veityper") == sorted(veityper):
            print(f"  {navn}: bruker mellomfila {os.path.basename(cache)} ({len(data['veier'])} veibiter)")
            return navn, data["veier"]
    t0 = time.time()
    print(f"  {navn}: omgang 1 av 2 – finner landeveiene …", flush=True)
    vl = VeiLeser(veityper)
    vl.apply_file(sti)
    print(f"    {len(vl.veier)} landeveibiter, {len(vl.noder)/1e6:.1f} mill. noder "
          f"({(time.time()-t0)/60:.1f} min)", flush=True)
    t1 = time.time()
    print(f"  {navn}: omgang 2 av 2 – henter koordinater …", flush=True)
    pos = hent_nodeposisjoner(sti, vl.noder)
    print(f"    {len(pos)/1e6:.1f} mill. koordinater ({(time.time()-t1)/60:.1f} min)", flush=True)
    del vl.noder
    veier = []
    for v in vl.veier:
        pts = array("d")
        refs = [r for r in v["refs"] if r in pos]
        if len(refs) < 2:
            continue
        for r in refs:
            pts.extend(pos[r])
        v["start"], v["slutt"] = refs[0], refs[-1]
        v["pts"] = pts
        del v["refs"]
        veier.append(v)
    del pos
    with open(cache, "wb") as f:
        pickle.dump({"versjon": CACHE_VERSJON, "veityper": sorted(veityper), "veier": veier}, f,
                    protocol=pickle.HIGHEST_PROTOCOL)
    print(f"  {navn}: ferdig lest på {(time.time()-t0)/60:.1f} min, mellomfil lagret", flush=True)
    return navn, veier

# ---------------------------------------------------------------- beregning

def punkter(v):
    p = v["pts"]
    return [(p[i], p[i+1]) for i in range(0, len(p), 2)]

def lengde_km(pts):
    return sum(hav(pts[i], pts[i+1]) for i in range(len(pts)-1)) / 1000

def bygg_strekninger(veier):
    """Setter sammen biter med samme nøkkel som deler endepunkt, minst knekk først."""
    grupper = defaultdict(list)
    for v in veier:
        grupper[v["nokkel"]].append(v)
    strekninger = []
    for nokkel, liste in grupper.items():
        ubrukt = {v["id"]: v for v in liste}
        ende = defaultdict(list)
        for v in liste:
            ende[v["start"]].append(v["id"])
            ende[v["slutt"]].append(v["id"])
        rekkefolge = sorted(liste, key=lambda v: -(len(ende[v["start"]]) == 1 or
                                                   len(ende[v["slutt"]]) == 1))
        for start in rekkefolge:
            if start["id"] not in ubrukt:
                continue
            del ubrukt[start["id"]]
            pts = punkter(start)
            fn, ln = start["start"], start["slutt"]
            if len(ende[ln]) == 1 and len(ende[fn]) > 1:
                pts.reverse()
                fn, ln = ln, fn
            for forover in (True, False):
                if not forover:
                    pts.reverse()
                    fn, ln = ln, fn
                while len(pts) >= 2:
                    inn = peiling(pts[-2], pts[-1])
                    beste, beste_knekk = None, MAKS_KNEKK_GRADER
                    for wid in ende[ln]:
                        if wid not in ubrukt:
                            continue
                        w = ubrukt[wid]
                        wp = punkter(w)
                        nyslutt = w["slutt"]
                        if w["start"] != ln:
                            wp.reverse()
                            nyslutt = w["start"]
                        if len(wp) < 2:
                            continue
                        knekk = vinkelforskjell(peiling(wp[0], wp[1]), inn)
                        if knekk <= beste_knekk:
                            beste, beste_knekk = (wid, wp, nyslutt), knekk
                    if not beste:
                        break
                    wid, wp, nyslutt = beste
                    del ubrukt[wid]
                    pts.extend(wp[1:])
                    ln = nyslutt
            strekninger.append({"nokkel": nokkel, "navn": start["navn"],
                                "kilde": start["kilde"], "pts": pts})
    return strekninger

def lag_partier(strekninger, vindu_m, min_gpk, min_parti_m, maks_gap_m):
    partier = []
    t0 = time.time()
    for k, s in enumerate(strekninger, 1):
        if k % 20000 == 0:
            print(f"    … {k} av {len(strekninger)} strekninger ({(time.time()-t0)/60:.1f} min)", flush=True)
        r = resample(s["pts"])
        if len(r) < 3:
            continue
        d = dreininger(r)
        for fra, til in finn_partier(r, d, vindu_m, min_gpk, min_parti_m, maks_gap_m):
            L = (til - fra) * RESAMPLE_M
            dd = d[fra:til - 1]
            sg = sum(dd)
            partier.append({"nokkel": s["nokkel"], "navn": s["navn"], "kilde": s["kilde"],
                            "pts": r[fra:til + 1], "fra_km": fra * RESAMPLE_M / 1000,
                            "til_km": til * RESAMPLE_M / 1000,
                            "vei_km": (len(r) - 1) * RESAMPLE_M / 1000,
                            "lengde_m": L, "sum_grader": sg,
                            "grader_per_km": sg / (L / 1000), "krappe": tell_krappe(dd)})
    partier.sort(key=lambda p: -p["sum_grader"])
    return partier

# ---------------------------------------------------------------- utdata

def skriv_csv(partier, sti):
    with open(sti, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rang", "kilde", "vei", "navn", "fra_km", "til_km", "veiens_lengde_km",
                    "parti_km", "svingegrader_totalt", "grader_per_km", "krappe_svinger",
                    "klasse", "start_lat", "start_lon", "slutt_lat", "slutt_lon"])
        for i, p in enumerate(partier, 1):
            w.writerow([i, p["kilde"], p["nokkel"], p["navn"], f"{p['fra_km']:.1f}",
                        f"{p['til_km']:.1f}", f"{p['vei_km']:.1f}", f"{p['lengde_m']/1000:.1f}",
                        f"{p['sum_grader']:.0f}", f"{p['grader_per_km']:.0f}", p["krappe"],
                        klasse(p["grader_per_km"])[1],
                        f"{p['pts'][0][0]:.5f}", f"{p['pts'][0][1]:.5f}",
                        f"{p['pts'][-1][0]:.5f}", f"{p['pts'][-1][1]:.5f}"])

def forenklet(pts, steg=5):
    ut = pts[::steg]
    if ut[-1] != pts[-1]:
        ut = ut + [pts[-1]]
    return [[round(a, 5), round(b, 5)] for a, b in ut]

def skriv_json(partier, sti, innstillinger):
    data = {"versjon": 1, "laget": time.strftime("%Y-%m-%d"),
            "metode": innstillinger,
            "partier": [{"rang": i, "kilde": p["kilde"], "vei": p["nokkel"], "navn": p["navn"],
                         "lengde_km": round(p["lengde_m"] / 1000, 2),
                         "grader": round(p["sum_grader"]), "grader_per_km": round(p["grader_per_km"]),
                         "krappe": p["krappe"], "klasse": klasse(p["grader_per_km"])[1],
                         "punkter": forenklet(p["pts"])}
                        for i, p in enumerate(partier, 1)]}
    with open(sti, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

def skriv_html(partier, sti, topp_nummer=50):
    feats = []
    for i, p in enumerate(partier, 1):
        k = klasse(p["grader_per_km"])
        feats.append({"c": forenklet(p["pts"]), "f": k[2], "r": i,
                      "t": (f"<b>{i}. {p['nokkel']}</b>" +
                            (f" ({p['navn']})" if p['navn'] and p['navn'] != p['nokkel'] else "") +
                            f"<br>km {p['fra_km']:.1f}–{p['til_km']:.1f} av {p['vei_km']:.1f}"
                            f"<br>{p['lengde_m']/1000:.1f} km · {p['sum_grader']:.0f}° totalt · "
                            f"{p['grader_per_km']:.0f} °/km · {p['krappe']} krappe<br>{k[1]}")})
    forklaring = "".join(f'<div><span style="background:{c}"></span>{n} (≥{g} °/km)</div>'
                         for g, n, c in KLASSER if g >= 150)
    html = f"""<!doctype html><html lang="no"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Svingkart Norge og Sverige</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>html,body,#k{{height:100%;margin:0}}
.lg{{background:#fff;padding:8px 10px;border-radius:6px;font:13px system-ui;box-shadow:0 1px 4px #0004}}
.lg span{{display:inline-block;width:22px;height:5px;margin-right:6px;vertical-align:middle;border-radius:2px}}
.nr{{background:#fff;border:2px solid #333;border-radius:10px;font:bold 11px system-ui;text-align:center;line-height:16px}}</style>
</head><body><div id="k"></div><script>
const D={json.dumps(feats, separators=(',', ':'), ensure_ascii=False)};
const m=L.map('k',{{preferCanvas:true}});
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{maxZoom:19,
 attribution:'© OpenStreetMap-bidragsytere'}}).addTo(m);
const alle=[];
D.slice().reverse().forEach(d=>{{const l=L.polyline(d.c,{{color:d.f,weight:4,opacity:.95}}).bindPopup(d.t).addTo(m);alle.push(l);}});
if(alle.length) m.fitBounds(L.featureGroup(alle).getBounds()); else m.setView([62,12],5);
D.slice(0,{topp_nummer}).forEach(d=>{{const p=d.c[Math.floor(d.c.length/2)];
  L.marker(p,{{icon:L.divIcon({{className:'nr',html:String(d.r),iconSize:[24,18]}})}}).bindPopup(d.t).addTo(m);}});
const lg=L.control({{position:'bottomright'}});
lg.onAdd=()=>{{const e=L.DomUtil.create('div','lg');e.innerHTML='<b>Svingete partier</b>{forklaring}<div style="margin-top:4px;color:#666">Tall = rang (topp {topp_nummer})</div>';return e}};
lg.addTo(m);
</script></body></html>"""
    with open(sti, "w", encoding="utf-8") as f:
        f.write(html)

# ---------------------------------------------------------------- hovedprogram

def main():
    ap = argparse.ArgumentParser(description="Svingkart for hele land fra .osm.pbf")
    ap.add_argument("pbf", nargs="+", help="én eller flere .osm.pbf-filer (Geofabrik)")
    ap.add_argument("--ut", default="svingkart_land")
    ap.add_argument("--min-grader-per-km", type=float, default=150.0)
    ap.add_argument("--min-parti", type=float, default=2000.0)
    ap.add_argument("--vindu", type=float, default=1000.0)
    ap.add_argument("--maks-gap", type=float, default=1500.0)
    ap.add_argument("--maks-tettsted", type=int, default=40)
    ap.add_argument("--tillat-grus", action="store_true")
    ap.add_argument("--veityper", default=STANDARD_VEITYPER)
    ap.add_argument("--bbox", help="begrens til sør,vest,nord,øst (for test eller regionkart)")
    ap.add_argument("--topp", type=int, default=30)
    ap.add_argument("--ikke-apne", action="store_true")
    a = ap.parse_args()
    t_start = time.time()
    veityper = set(x.strip() for x in a.veityper.split(",") if x.strip())
    for sti in a.pbf:
        if not os.path.exists(sti):
            sys.exit(f"Finner ikke {sti}. Står stien i anførselstegn hvis den har mellomrom?")

    print("Leser landsfilene:")
    alle, sett = [], set()
    dekke = defaultdict(lambda: defaultdict(float))
    for sti in a.pbf:
        kilde, veier = les_pbf(sti, veityper)
        for v in veier:
            if v["id"] in sett:          # grenseveier finnes i begge landsfilene
                continue
            sett.add(v["id"])
            v["kilde"] = kilde
            alle.append(v)

    if a.bbox:
        s, w, n, e = (float(x) for x in a.bbox.split(","))
        alle = [v for v in alle if s <= v["pts"][0] <= n and w <= v["pts"][1] <= e]

    # Dekkestatistikk (før filtrering) og filtrering
    beholdt, ut_fart, ut_grus = [], 0, 0
    for v in alle:
        dekke[v["kilde"]][v["dekke"]] += lengde_km(punkter(v))
        if not a.tillat_grus and v["dekke"] == "grus":
            ut_grus += 1
            continue
        if a.maks_tettsted and v["fart"] is not None and v["fart"] <= a.maks_tettsted:
            ut_fart += 1
            continue
        beholdt.append(v)
    print("\nVeidekke på landeveiene (km):")
    for kilde, d in dekke.items():
        tot = sum(d.values()) or 1
        print(f"  {kilde:<22} " + "  ".join(f"{g} {km:,.0f} ({100*km/tot:.0f} %)".replace(",", " ")
                                             for g, km in sorted(d.items(), key=lambda x: -x[1])))
    print(f"\nTatt ut: {ut_fart} biter med fartsgrense <= {a.maks_tettsted} km/t, {ut_grus} grusbiter")

    print("Setter sammen veistrekninger …", flush=True)
    st = bygg_strekninger(beholdt)
    del alle, beholdt
    print(f"  {len(st)} strekninger. Leter etter svingete partier …", flush=True)
    partier = lag_partier(st, a.vindu, a.min_grader_per_km, a.min_parti, a.maks_gap)

    innst = {"min_grader_per_km": a.min_grader_per_km, "vindu_m": a.vindu,
             "min_parti_m": a.min_parti, "maks_gap_m": a.maks_gap,
             "maks_tettsted": a.maks_tettsted, "grus": a.tillat_grus,
             "veityper": sorted(veityper), "kilder": [os.path.basename(p) for p in a.pbf]}
    skriv_csv(partier, a.ut + ".csv")
    skriv_json(partier, a.ut + ".json", innst)
    skriv_html(partier, a.ut + ".html")

    tot_km = f"{sum(p['lengde_m'] for p in partier)/1000:,.0f}".replace(",", " ")
    print(f"\n{len(partier)} svingete partier, til sammen {tot_km} km")
    def tabell(liste, n):
        print(f"{'':>5} {'kilde':<8} {'vei':<28} {'lengde':>6} {'grader':>6} {'°/km':>5} {'krappe':>6}")
        for p in liste[:n]:
            navn = p["nokkel"] + (f" ({p['navn']})" if p["navn"] and p["navn"] != p["nokkel"] else "")
            print(f"{partier.index(p)+1:>4}. {p['kilde'][:8]:<8} {navn[:28]:<28} "
                  f"{p['lengde_m']/1000:6.1f} {p['sum_grader']:6.0f} {p['grader_per_km']:5.0f} {p['krappe']:>6}")
    print(f"\nDe {a.topp} svingeteste totalt:")
    tabell(partier, a.topp)
    for kilde in sorted({p["kilde"] for p in partier}):
        print(f"\nTopp 10 i {kilde}:")
        tabell([p for p in partier if p["kilde"] == kilde], 10)
    print(f"\nFerdig på {(time.time()-t_start)/60:.1f} min.")
    for ext in ("html", "csv", "json"):
        print(f"  {os.path.abspath(a.ut + '.' + ext)}")
    if not a.ikke_apne:
        webbrowser.open("file://" + os.path.abspath(a.ut + ".html"))

if __name__ == "__main__":
    main()
