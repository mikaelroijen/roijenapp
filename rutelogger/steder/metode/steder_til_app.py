#!/usr/bin/env python3
# Lager RuteKjerne/Sources/RuteKjerne/Resources/steder.json – bensin, lading, mat, overnatting og
# rasteplasser i Norden fra OpenStreetMap (ODbL). 25. okt 2026, «Egen ruting og offline».
# Grunnlag: claude/steder-fra-osm-2026-10-25.md. Brukes av RuteKjerne/Steder.swift (søk langs ruten
# og «nærmeste» på iPhone og Mac, uavhengig av rutemotor). Erstatter Apples MKLocalSearch for disse kategoriene.
#
# Krever pyosmium (pip3 install osmium). Bruk:
#   python3 -I Tools/steder_til_app.py <utfil> NO=norway.osm.pbf SE=sweden.osm.pbf FI=... DK=... IS=...
# Rekkefølgen avgjør landet når et sted ligger i to landsfiler (overlapp ved grensene).
import sys, json, time, datetime, osmium, osmium.filter as F

TYPER = ["fuel", "charging", "food", "lodging", "restArea"]
KIND = {("amenity", "fuel"): 0, ("amenity", "charging_station"): 1,
        ("amenity", "restaurant"): 2, ("amenity", "cafe"): 2, ("amenity", "fast_food"): 2,
        ("tourism", "hotel"): 3, ("tourism", "motel"): 3, ("tourism", "guest_house"): 3,
        ("tourism", "hostel"): 3, ("tourism", "camp_site"): 3,
        ("highway", "rest_area"): 4, ("highway", "services"): 4}

def kind(tags):
    if tags.get("access") in ("private", "no"):
        return None
    for (k, v), t in KIND.items():
        if tags.get(k) == v:
            if t == 0 and (tags.get("waterway") == "fuel" or tags.get("motorcar") == "no"):
                return None          # båtanlegg / ikke for kjøretøy
            return t
    return None

def main():
    ut, filer = sys.argv[1], sys.argv[2:]
    land_liste, steder, sett = [], [], set()
    for arg in filer:
        land, fil = arg.split("=", 1)
        li = len(land_liste); land_liste.append(land)
        t0 = time.time(); ways = {}
        for o in osmium.FileProcessor(fil, osmium.osm.NODE | osmium.osm.WAY).with_filter(F.TagFilter(*KIND.keys())):
            t = kind(o.tags)
            if t is None: continue
            key = (o.type_str(), o.id)
            if key in sett: continue
            navn = o.tags.get("name") or o.tags.get("brand") or ""
            if o.is_node():
                sett.add(key); steder.append([t, navn, round(o.location.lat, 5), round(o.location.lon, 5), li])
            else:
                ways[o.id] = ([t, navn, 0, 0, li], [n.ref for n in o.nodes])
        if ways:
            trenger = {r for _, refs in ways.values() for r in refs}
            pos = {n.id: (n.location.lat, n.location.lon)
                   for n in osmium.FileProcessor(fil, osmium.osm.NODE).with_filter(F.IdFilter(trenger))}
            for wid, (rec, refs) in ways.items():
                pts = [pos[r] for r in refs if r in pos]
                if not pts or ("w", wid) in sett: continue
                rec[2] = round(sum(p[0] for p in pts) / len(pts), 5)
                rec[3] = round(sum(p[1] for p in pts) / len(pts), 5)
                sett.add(("w", wid)); steder.append(rec)
        print(f"{land}: {time.time() - t0:.0f} s", flush=True)
    steder.sort(key=lambda s: (s[2], s[3]))
    data = {"v": 1, "laget": datetime.date.today().isoformat(),
            "kilde": "© OpenStreetMap-bidragsytere",
            "lisens": "ODbL 1.0 – https://opendatacommons.org/licenses/odbl/1-0/",
            "info": "Utdrag av OpenStreetMap (Geofabrik) laget med Tools/steder_til_app.py",
            "typer": TYPER, "land": land_liste,
            "felt": ["type", "navn", "lat", "lon", "land"], "s": steder}
    with open(ut, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    tell = {}
    for s in steder: tell[(land_liste[s[4]], TYPER[s[0]])] = tell.get((land_liste[s[4]], TYPER[s[0]]), 0) + 1
    for l in land_liste: print(l, {t: tell.get((l, t), 0) for t in TYPER})
    print(f"{len(steder)} steder → {ut}")

if __name__ == "__main__":
    main()
