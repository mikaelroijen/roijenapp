#!/usr/bin/env python3
# Lager RuteKjerne/Sources/RuteKjerne/Resources/steder.json – steder i Norden fra OpenStreetMap (ODbL):
# bensin, lading, mat, overnatting, rasteplasser, campingplasser, bobilplasser og utsiktspunkter.
# 25. okt 2026 «Egen ruting og offline» (v1). 7. nov 2026 «Kartlag og steder» (v2): camping og bobil
# skilt ut fra overnatting, utsiktspunkter lagt til, og avstand til nærmeste veg en MC kan kjøre på.
# Regler: claude/protokoll-kartlag.md. Plan: claude/plan-norden-svingete-turistveger-camping-utsikt-2026-11-07.md.
#
# Krever pyosmium. Bruk:
#   python3 -I Tools/steder_til_app.py <utfil> NO=norway.osm.pbf SE=sweden.osm.pbf FI=... DK=... IS=...
# Valg: --mellomlager <mappe> lagrer hvert land for seg (gjenbrukes); --bare NO,SE lager bare
# mellomlageret for de landene (for maskiner som må kjøre landene i hver sin omgang).
# Tid på 4 kjerner: Norge ca. 65 s. Nodeindeksen legges på disk (Norge ca. 3 GB ledig plass).
# Rekkefølgen avgjør landet når et sted ligger i to landsfiler (overlapp ved grensene).
#
# Format: «s» er rader [type, navn, lat, lon, land] – camping, bobil og utsikt har i tillegg
# [veg_m, ekstra]: meter til nærmeste MC-veg og biter for camping (1 hytter, 2 telt, 4 bobil/campingvogn).
# Nye typer legges bare til bakerst i TYPER (eldre appversjoner hopper over typer de ikke kjenner).
import sys, json, time, datetime, math, osmium, osmium.filter as F

TYPER = ["fuel", "charging", "food", "lodging", "restArea", "camping", "caravan", "viewpoint"]
CAMPING, CARAVAN, VIEWPOINT = 5, 6, 7
KIND = {("amenity", "fuel"): 0, ("amenity", "charging_station"): 1,
        ("amenity", "restaurant"): 2, ("amenity", "cafe"): 2, ("amenity", "fast_food"): 2,
        ("tourism", "hotel"): 3, ("tourism", "motel"): 3, ("tourism", "guest_house"): 3,
        ("tourism", "hostel"): 3, ("tourism", "camp_site"): CAMPING, ("tourism", "caravan_site"): CARAVAN,
        ("tourism", "viewpoint"): VIEWPOINT,
        ("highway", "rest_area"): 4, ("highway", "services"): 4}
VEGMAAL = {CAMPING, CARAVAN, VIEWPOINT}
# Største avstand (m) til MC-veg for å komme med. Camping/bobil måles fra midten av området.
MAKS_M = {CAMPING: 500, CARAVAN: 500, VIEWPOINT: 200}
MAALT_M = 1000          # avstander over dette regnes som «over 1000 m»
FORMAT = 2
# Midlertidig nodeindeks på disk (16 byte per node; Norge ca. 3 GB). Slettes etter hvert land.
import os, tempfile
INDEKS = os.path.join(tempfile.gettempdir(), "steder_nodeindeks.bin")

# Veger en MC kan kjøre på (Mikael 7. nov: også små og stille veger).
MC_VEG = {"motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link",
          "secondary", "secondary_link", "tertiary", "tertiary_link", "unclassified",
          "residential", "living_street", "service", "road"}
JA = {"yes", "permissive", "destination", "designated", "customers"}

def mc_veg(tags):
    hw = tags.get("highway")
    mc = tags.get("motorcycle") or tags.get("motor_vehicle") or tags.get("vehicle")
    if hw == "track":                      # skogsbilveg o.l.: bare når motorkjøretøy er tillatt
        return mc in JA
    if hw not in MC_VEG:
        return False
    if mc in ("no", "private", "agricultural", "forestry", "delivery"):
        return False
    if tags.get("access") in ("no", "private") and mc not in JA:
        return False
    return True

def kind(tags):
    if tags.get("access") in ("private", "no"):
        return None
    for (k, v), t in KIND.items():
        if tags.get(k) == v:
            if t == 0 and (tags.get("waterway") == "fuel" or tags.get("motorcar") == "no"):
                return None          # båtanlegg / ikke for kjøretøy
            return t
    return None

def ekstra(tags):
    b = 0
    if tags.get("cabins") == "yes": b |= 1
    if tags.get("tents") == "yes": b |= 2
    if tags.get("caravans") == "yes" or tags.get("motorhome") == "yes": b |= 4
    return b

# Rutenett for avstandsmåling: 0,01° breddegrad × 0,02° lengdegrad (ca. 1,1 × 1,1 km ved 60° N).
CLAT, CLON = 0.01, 0.02
def celle(lat, lon): return (int(math.floor(lat / CLAT)), int(math.floor(lon / CLON)))

def meter(lat1, lon1, lat2, lon2):
    k = math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot((lat2 - lat1) * 111_195, (lon2 - lon1) * 111_195 * k)

def til_segment(plat, plon, a, b):
    k = math.cos(math.radians(plat))
    ax, ay = (a[1] - plon) * 111_195 * k, (a[0] - plat) * 111_195
    bx, by = (b[1] - plon) * 111_195 * k, (b[0] - plat) * 111_195
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / l2))
    return math.hypot(ax + t * dx, ay + t * dy)

def maal_avstand(fil, maal):
    """maal: liste av rader (type, navn, lat, lon, ...). Gir avstand i meter til nærmeste MC-veg."""
    grid = {}
    for i, r in enumerate(maal):
        grid.setdefault(celle(r[2], r[3]), []).append(i)
    naer_celler = set()
    for (a, b) in grid:
        for da in (-1, 0, 1):
            for db in (-1, 0, 1):
                naer_celler.add((a + da, b + db))
    best = [float(MAALT_M + 1)] * len(maal)
    def sjekk(p, q):
        c = celle((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
        for da in (-1, 0, 1):
            for db in (-1, 0, 1):
                for i in grid.get((c[0] + da, c[1] + db), ()):
                    r = maal[i]
                    d = til_segment(r[2], r[3], p, q)
                    if d < best[i]: best[i] = d
    # Nodeposisjonene slås opp i C++ (indeks på disk), så Python bare ser vegene.
    t0 = time.time()
    fp = (osmium.FileProcessor(fil, osmium.osm.NODE | osmium.osm.WAY)
          .with_locations(f"sparse_file_array,{INDEKS}")
          .with_filter(F.EntityFilter(osmium.osm.WAY)).with_filter(F.KeyFilter("highway")))
    for w in fp:
        if not mc_veg(w.tags): continue
        forrige = None; forrige_naer = False
        for nd in w.nodes:
            loc = nd.location
            if not loc.valid():
                forrige = None; continue
            p = (loc.lat, loc.lon)
            naer = (int(math.floor(p[0] / CLAT)), int(math.floor(p[1] / CLON))) in naer_celler
            if forrige is not None and (naer or forrige_naer):
                sjekk(forrige, p)
            forrige, forrige_naer = p, naer
    print(f"  veger: {time.time() - t0:.0f} s", flush=True)
    return best

def les_land(land, fil, li, mellom):
    """Kandidater og avstander for én landsfil: liste av ([type_str, id], rad). Lagres i
    `mellom`/<land>.json (gjenbrukes når landsfila ikke er endret), så landene kan kjøres hver for seg."""
    cache = os.path.join(mellom, f"{land}.json") if mellom else None
    stempel = [os.path.basename(fil), os.path.getsize(fil), int(os.path.getmtime(fil))]
    if cache and os.path.exists(cache):
        c = json.load(open(cache, encoding="utf-8"))
        if c.get("fil") == stempel and c.get("v") == FORMAT:
            print(f"{land}: fra mellomlager {cache}", flush=True)
            for _, r in c["rader"]: r[4] = li
            return c["rader"], c["statistikk"]
    t0 = time.time(); ways = {}; nye = []
    for o in osmium.FileProcessor(fil, osmium.osm.NODE | osmium.osm.WAY).with_filter(F.TagFilter(*KIND.keys())):
        t = kind(o.tags)
        if t is None: continue
        navn = o.tags.get("name") or o.tags.get("brand") or ""
        rec = [t, navn, 0, 0, li]
        if t in VEGMAAL: rec += [0, ekstra(o.tags) if t in (CAMPING, CARAVAN) else 0]
        if o.is_node():
            rec[2] = round(o.location.lat, 5); rec[3] = round(o.location.lon, 5); nye.append([["n", o.id], rec])
        else:
            ways[o.id] = (rec, [n.ref for n in o.nodes])
    if ways:
        trenger = {r for _, refs in ways.values() for r in refs}
        pos = {n.id: (n.location.lat, n.location.lon)
               for n in osmium.FileProcessor(fil, osmium.osm.NODE).with_filter(F.IdFilter(trenger))}
        for wid, (rec, refs) in ways.items():
            pts = [pos[r] for r in refs if r in pos]
            if not pts: continue
            rec[2] = round(sum(p[0] for p in pts) / len(pts), 5)
            rec[3] = round(sum(p[1] for p in pts) / len(pts), 5)
            nye.append([["w", wid], rec])
    print(f"{land}: {len(nye)} kandidater ({time.time() - t0:.0f} s)", flush=True)
    statistikk = {}
    maal = [r for _, r in nye if r[0] in VEGMAAL]
    if maal:
        try:
            avst = maal_avstand(fil, maal)
        finally:
            if os.path.exists(INDEKS): os.remove(INDEKS)
        for r, d in zip(maal, avst):
            r[5] = round(min(d, MAALT_M + 1))
            g = "≤100" if d <= 100 else "≤200" if d <= 200 else "≤500" if d <= 500 else "≤1000" if d <= MAALT_M else ">1000"
            statistikk.setdefault(TYPER[r[0]], {}); statistikk[TYPER[r[0]]][g] = statistikk[TYPER[r[0]]].get(g, 0) + 1
    print(f"{land}: ferdig ({time.time() - t0:.0f} s)", flush=True)
    if cache:
        os.makedirs(mellom, exist_ok=True)
        with open(cache, "w", encoding="utf-8") as f:
            json.dump({"v": FORMAT, "fil": stempel, "rader": nye, "statistikk": statistikk}, f, ensure_ascii=False)
    return nye, statistikk

def main():
    args = sys.argv[1:]
    mellom = None
    if "--mellomlager" in args:
        i = args.index("--mellomlager"); mellom = args[i + 1]; del args[i:i + 2]
    bare = None
    if "--bare" in args:                 # lag bare mellomlageret for disse landene, ingen utfil
        i = args.index("--bare"); bare = set(args[i + 1].split(",")); del args[i:i + 2]
    ut, filer = args[0], args[1:]
    land_liste, steder, sett = [], [], set()
    statistikk = {}
    for arg in filer:
        land, fil = arg.split("=", 1)
        li = len(land_liste); land_liste.append(land)
        if bare is not None and land not in bare: continue
        nye, stat = les_land(land, fil, li, mellom)
        for t, g in stat.items(): statistikk[(land, t)] = g
        for key, r in nye:
            key = tuple(key)
            if key in sett: continue
            sett.add(key)
            if r[0] not in VEGMAAL or r[5] <= MAKS_M[r[0]]: steder.append(r)
    if bare is not None:
        print("Mellomlager laget for", ",".join(sorted(bare))); return
    steder.sort(key=lambda s: (s[2], s[3]))
    data = {"v": 2, "laget": datetime.date.today().isoformat(),
            "kilde": "© OpenStreetMap-bidragsytere",
            "lisens": "ODbL 1.0 – https://opendatacommons.org/licenses/odbl/1-0/",
            "info": "Utdrag av OpenStreetMap (Geofabrik) laget med Tools/steder_til_app.py",
            "typer": TYPER, "land": land_liste,
            "felt": ["type", "navn", "lat", "lon", "land", "veg_m", "ekstra"],
            "maks_veg_m": {TYPER[k]: v for k, v in MAKS_M.items()}, "s": steder}
    with open(ut, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print("\nAvstand til nærmeste MC-veg (alle kandidater, før utvalg):")
    for (l, t), g in sorted(statistikk.items()):
        print(f"  {l} {t:10s}", "  ".join(f"{k} {g.get(k, 0)}" for k in ("≤100", "≤200", "≤500", "≤1000", ">1000")))
    tell = {}
    for s in steder: tell[(land_liste[s[4]], TYPER[s[0]])] = tell.get((land_liste[s[4]], TYPER[s[0]]), 0) + 1
    print("\nI fila:")
    for l in land_liste: print(l, {t: tell.get((l, t), 0) for t in TYPER})
    print(f"{len(steder)} steder → {ut}")

if __name__ == "__main__":
    main()
