#!/usr/bin/env python3
# Lager turistveger fra en rute-relasjon i OpenStreetMap (ODbL) i appens turistvegformat
# (RuteKjerne/Resources/TuristvegerData). 7. nov 2026, «Kartlag og steder». Regler: claude/protokoll-kartlag.md.
# Først brukt for Margueritruten i Danmark (superrelasjon 4441962, 82 kommunebiter, ca. 4 450 km).
#
# Fremgangsmåte (nettet er ikke én linje, men et nett med avstikkere, dobbeltspor og hull):
#  1. Vegbitene i alle underrelasjonene (rolle «backward» utelates – den andre kjøreretningen).
#  2. Hull under 150 m mellom bitene kobles.
#  3. Korte blindgreiner (< 3 km), små sløyfer (< 5 km) og parallelle spor ryddes bort.
#  4. Nettet deles i kryss (3+ greiner) og ved ferjer. Hver kjede er én sammenhengende tur.
#  5. Kjeder under 20 km tas ikke med. Kjeder over 250 km deles i like lange biter (høyst 200 km).
#  6. Navn i hver ende: nærmeste by/tettsted (place=city/town, ellers village) innen 15 km.
#
# Krever pyosmium. Bruk:
#   python3 Tools/turistveg_osm.py <landsfil.osm.pbf> <superrelasjon-id> <land> <id-prefiks> <navn> <ut-mappe> <første sortOrder>
#   f.eks. python3 Tools/turistveg_osm.py denmark.osm.pbf 4441962 DK dk-marguerit Margueritruten ut 101
# Skriver <ut-mappe>/turistveger/<id>.json og <ut-mappe>/index-<land>.json (flettes inn i turistveger_index.json).
import sys, os, json, math, collections, osmium, osmium.filter as F

HULL_M, BLINDGREIN_M, SLOYFE_M = 150, 3000, 5000
MIN_KM, DEL_OVER_KM, MAKS_KM = 20, 250, 200
VIA_HVER_M = 15000          # via-punkt ca. hver 15. km (som gpx_to_turistveg.py)
SPOR_MIN_M = 30             # punktene i sporet tynnes til minst 30 m mellom
KILDE = "© OpenStreetMap-bidragsytere (ODbL)"

def mellomlager_mappe():
    """Mappe for store midlertidige filer (nodeindekser): USB-disken RuteData hvis den er koblet til
    (Mac: /Volumes/RuteData, Claude-økt: ~/mnt/RuteData), ellers systemets tempmappe. 7. nov 2026."""
    import os, tempfile
    for d in (os.environ.get("RUTELOGGER_MELLOMLAGER"), "/Volumes/RuteData/mellomlager/nodeindeks",
              os.path.expanduser("~/mnt/RuteData/mellomlager/nodeindeks")):
        if d and os.path.isdir(d): return d
    return tempfile.gettempdir()

def m(p, q):
    k = math.cos(math.radians((p[0] + q[0]) / 2))
    return math.hypot((q[0] - p[0]) * 111195, (q[1] - p[1]) * 111195 * k)

def key(p): return (round(p[0], 5), round(p[1], 5))

def les(fil, superid, skip_navn=("Skiltning udenfor",)):
    rels = {}
    for r in osmium.FileProcessor(fil, osmium.osm.RELATION):
        rels[r.id] = (dict(r.tags), [(x.type, x.ref, x.role) for x in r.members])
    sup = rels[superid]
    under = [ref for t, ref, _ in sup[1] if t == "r" and ref in rels]
    # Ferjer og broer mellom landsdeler er bindeledd, ikke turer («Færger og broer mellem landsdele»).
    ferje_rel = {rid for rid in under if any(o in (rels[rid][0].get("name") or "").lower() for o in ("færge", "ferge", "ferry", "broer"))}
    ways = {}
    for rid in under:
        navn = rels[rid][0].get("name") or ""
        if any(s in navn for s in skip_navn): continue
        for t, ref, role in rels[rid][1]:
            if t == "w" and role != "backward": ways.setdefault(ref, rid in ferje_rel)
    pts = {}
    fp = (osmium.FileProcessor(fil, osmium.osm.NODE | osmium.osm.WAY).with_locations()
          .with_filter(F.EntityFilter(osmium.osm.WAY)).with_filter(F.IdFilter(set(ways))))
    for w in fp:
        p = [(n.location.lat, n.location.lon) for n in w.nodes if n.location.valid()]
        if len(p) >= 2: pts[w.id] = (p, ways[w.id] or w.tags.get("route") == "ferry")
    steder = []
    for n in osmium.FileProcessor(fil, osmium.osm.NODE).with_filter(F.TagFilter(("place", "city"), ("place", "town"), ("place", "village"))):
        if n.tags.get("name"): steder.append((n.location.lat, n.location.lon, n.tags["name"], n.tags["place"]))
    return list(pts.values()), steder

class Nett:
    def __init__(self, biter):
        self.E = {}; self.nid = 0
        for p, ferje in biter: self.ny(key(p[0]), key(p[-1]), [list(x) for x in p], ferje)
    def ny(self, a, b, p, f):
        l = sum(m(x, y) for x, y in zip(p, p[1:])); self.E[self.nid] = [a, b, p, l, f]; self.nid += 1
    def adj(self):
        A = collections.defaultdict(list)
        for i, (a, b, *_) in self.E.items(): A[a].append(i); A[b].append(i)
        return A
    def sl_sammen(self):
        A = self.adj(); kø = [n for n, l in A.items() if len(l) == 2]
        for n in kø:
            l = A.get(n)
            if not l or len(l) != 2 or l[0] == l[1] or l[0] not in self.E or l[1] not in self.E: continue
            i, j = l; ei, ej = self.E[i], self.E[j]
            if ei[4] != ej[4]: continue
            pi, ai = (ei[2], ei[0]) if ei[1] == n else (ei[2][::-1], ei[1])
            pj, bj = (ej[2], ej[1]) if ej[0] == n else (ej[2][::-1], ej[0])
            del self.E[i], self.E[j]
            self.E[self.nid] = [ai, bj, pi + pj[1:], ei[3] + ej[3], ei[4]]; k = self.nid; self.nid += 1
            for x in (ai, bj):
                A[x] = [k if y in (i, j) else y for y in A[x]]
            del A[n]
    def koble_hull(self, maks_m=None):
        maks_m = maks_m or HULL_M
        A = self.adj(); G = collections.defaultdict(list)
        for i, e in self.E.items():
            for j, p in enumerate(e[2]): G[(int(p[0] * 200), int(p[1] * 100))].append((i, j))
        n_koblet = 0
        for n in [n for n, l in A.items() if len(l) == 1]:
            own = A[n][0] if A.get(n) else None
            if own is None or own not in self.E: continue
            best = None; c = (int(n[0] * 200), int(n[1] * 100))
            for da in (-1, 0, 1):
                for db in (-1, 0, 1):
                    for i, j in G.get((c[0] + da, c[1] + db), ()):
                        if i == own or i not in self.E or j >= len(self.E[i][2]): continue
                        d = m(n, self.E[i][2][j])
                        if d <= maks_m and (best is None or d < best[0]): best = (d, i, j)
            if not best: continue
            d, i, j = best; a, b, p, l, f = self.E[i]; pk = key(p[j])
            if 0 < j < len(p) - 1:
                del self.E[i]
                for part, (x, y) in ((p[:j + 1], (a, pk)), (p[j:], (pk, b))):
                    self.ny(x, y, part, f)
                    for jj, pp in enumerate(part): G[(int(pp[0] * 200), int(pp[1] * 100))].append((self.nid - 1, jj))
            self.ny(n, pk, [list(n), p[j]], False); n_koblet += 1
        return n_koblet
    def rydd(self):
        fjernet = 0; A = self.adj()
        for i, (a, b, p, l, f) in list(self.E.items()):
            if a == b and l < SLOYFE_M: del self.E[i]; fjernet += 1; continue
            ende_a, ende_b = len(A[a]) == 1, len(A[b]) == 1
            if l < BLINDGREIN_M and (ende_a != ende_b): del self.E[i]; fjernet += 1
        sett = {}
        for i, (a, b, p, l, f) in list(self.E.items()):
            k = tuple(sorted([a, b]))
            if k in sett and sett[k] in self.E and a != b:
                j = sett[k]; drop = i if l > self.E[j][3] else j
                del self.E[drop]; fjernet += 1; sett[k] = j if drop == i else i
            else: sett[k] = i
        return fjernet

def tynn(p):
    ut = [p[0]]
    for q in p[1:-1]:
        if m(ut[-1], q) >= SPOR_MIN_M: ut.append(q)
    ut.append(p[-1]); return ut

def del_opp(p, l):
    if l / 1000 <= DEL_OVER_KM: return [p]
    n = math.ceil(l / 1000 / MAKS_KM); mål = l / n; deler = []; cur = [p[0]]; acc = 0
    for x, y in zip(p, p[1:]):
        acc += m(x, y); cur.append(y)
        if acc >= mål and len(deler) < n - 1: deler.append(cur); cur = [y]; acc = 0
    deler.append(cur); return deler

def via(p):
    ut = [p[0]]; acc = 0
    for x, y in zip(p, p[1:]):
        acc += m(x, y)
        if acc >= VIA_HVER_M: ut.append(y); acc = 0
    if ut[-1] != p[-1]: ut.append(p[-1])
    return ut

def stedsnavn(p, steder):
    best = None
    for lat, lon, navn, typ in steder:
        if abs(lat - p[0]) > 0.15 or abs(lon - p[1]) > 0.3: continue
        d = m(p, (lat, lon)) * (1 if typ in ("city", "town") else 2.5)   # by/tettsted foretrekkes
        if d <= 15000 * (1 if typ in ("city", "town") else 2.5) and (best is None or d < best[0]): best = (d, navn)
    if best: return best[1]
    # Glissent befolket (f.eks. Kainuu): nærmeste sted innen 60 km, uansett type.
    for lat, lon, navn, typ in steder:
        if abs(lat - p[0]) > 0.6 or abs(lon - p[1]) > 1.2: continue
        d = m(p, (lat, lon))
        if d <= 60000 and (best is None or d < best[0]): best = (d, navn)
    return best[1] if best else "?"

def main():
    fil, superid, land, prefiks, navn, ut, sort0 = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6], int(sys.argv[7])
    biter, steder = les(fil, superid)
    nett = Nett(biter); print("vegbiter", len(nett.E))
    nett.sl_sammen(); print("hull koblet", nett.koble_hull())
    for _ in range(30):
        nett.sl_sammen()
        if nett.rydd() == 0: break
    nett.sl_sammen()
    kjeder = sorted((e for e in nett.E.values() if not e[4] and e[3] / 1000 >= MIN_KM), key=lambda e: (-e[2][0][0], e[2][0][1]))
    os.makedirs(os.path.join(ut, "turistveger"), exist_ok=True)
    index = []; nr = 0
    for e in kjeder:
        for p in del_opp(e[2], e[3]):
            p = tynn(p); l = sum(m(x, y) for x, y in zip(p, p[1:]))
            if l / 1000 < MIN_KM: continue
            a, b = stedsnavn(p[0], steder), stedsnavn(p[-1], steder)
            fra_til = f"{a} – {b}" if a != b else f"rundt {a}"
            if any(x["fromTo"] == fra_til for x in index) or any(x["fromTo"].startswith(fra_til + " via") for x in index):
                kandidater = [stedsnavn(p[int(len(p) * t)], steder) for t in (0.5, 0.35, 0.65, 0.2, 0.8)]
                via_navn = next((v for v in kandidater if v not in (a, b, "?")), None)
                fra_til += f" via {via_navn}" if via_navn else " (2)"
            nr += 1; rid = f"{prefiks}-{nr:02d}"
            rute = {"id": rid, "name": navn, "fromTo": fra_til, "lengthKm": round(l / 1000, 1),
                    "trackPoints": [[round(x[0], 5), round(x[1], 5)] for x in p],
                    "viaPoints": [[round(x[0], 5), round(x[1], 5)] for x in via(p)],
                    "country": land, "source": KILDE, "official": True}
            json.dump(rute, open(os.path.join(ut, "turistveger", rid + ".json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
            index.append({"id": rid, "sortOrder": sort0 + nr - 1, "name": navn, "fromTo": rute["fromTo"], "lengthKm": rute["lengthKm"],
                          "pointCount": len(p), "country": land, "source": KILDE, "official": True})
    json.dump(index, open(os.path.join(ut, f"index-{land}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    tot = sum(x["lengthKm"] for x in index)
    for x in index: print(f"  {x['id']}  {x['fromTo']:45s} {x['lengthKm']:6.1f} km  {x['pointCount']} pkt")
    print(f"{len(index)} strekninger, {tot:.0f} km → {ut}")

if __name__ == "__main__":
    main()
