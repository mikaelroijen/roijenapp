"""
Kø-fila data/trafikkflyt.json (oppdrag-nettside-trafikkflyt-fil-2026-11-05): strekninger og
målepunkter der trafikken nå går tregere enn 70 % av normalt, fra

  NO  Statens vegvesen, DATEX 3.1 TravelTimeData + PredefinedTravelTimeLocations (NLOD 2.0)
  SE  Trafikverket, TravelTimeRoute 1.5 (CC0 1.0)
  FI  Fintraffic / Digitraffic, TMS (LAM) stations/data + sensor-constants (CC BY 4.0)

Feiler ett land, er de andre likevel med (status «feil» i kilder[]). Hemmeligheter leses fra
miljøet (DATEX_USER, DATEX_PASSWORD, TRAFIKVERKET_NOKKEL) og skrives aldri ut.

Utvalg og målefeil (skrives også i loggen):
- med: forhold < 0,7 («alvorlig» når < 0,5); forhold = fart nå / normal fart (strekninger:
  normal tid / tid nå);
- ikke med: uten måling (NO/SE «unknown»), måling eldre enn 15 min, FI-stasjoner som ikke
  samler data;
- målefeil: forhold < 0,05 tas bort; NO-strekninger med forsinkelse over 1 time tas bort
  hvis ingen trafikkmelding (stengt, vegarbeid, ulykke) ligger innenfor 1 km av strekningen.
"""
import gzip, json, math, os, urllib.error, urllib.request, xml.etree.ElementTree as ET
from base64 import b64encode
from collections import Counter
from datetime import datetime, timedelta, timezone

from geo_felles import DESIMALER, iso_lokal, linje_latlon, uten_tomme, wkt

GRENSE, ALVORLIG, MIN_FORHOLD = 0.7, 0.5, 0.05
MAKS_ALDER = timedelta(minutes=15)
NO_MAKS_FORSINKELSE_S = 3600
NO_SJEKK_AVSTAND_M = 1000

KILDER = {
    "NO": ("Statens vegvesen – reisetider (DATEX II)", "NLOD 2.0 – https://data.norge.no/nlod/no/2.0"),
    "SE": ("Trafikverket – öppna API för trafikinformation (TravelTimeRoute)",
           "CC0 1.0 – https://creativecommons.org/publicdomain/zero/1.0/"),
    "FI": ("Source: Fintraffic / digitraffic.fi, license CC 4.0 BY",
           "CC BY 4.0 – https://creativecommons.org/licenses/by/4.0/"),
}
DATEX = "https://datex-server-get-v3-1.atlas.vegvesen.no/datexapi/"
TRV = "https://api.trafikinfo.trafikverket.se/v2/data.json"
TMS = "https://tie.digitraffic.fi/api/tms/v1/"


class Feil(Exception):
    pass


def _hent(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    req.add_header("Accept-Encoding", "gzip")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=120) as svar:
            rå = svar.read()
            if svar.headers.get("Content-Encoding") == "gzip":
                rå = gzip.decompress(rå)
            return rå
    except urllib.error.HTTPError as f:
        raise Feil(f"HTTP {f.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as f:
        raise Feil(type(f).__name__) from None


def _lokal(tag):
    return tag.rsplit("}", 1)[-1]


def _tid(s):
    try:
        d = datetime.fromisoformat((s or "").replace("Z", "+00:00"))
        return d if d.tzinfo else None
    except ValueError:
        return None


def _avstand(p, q):
    R = 6371000.0
    la1, lo1, la2, lo2 = map(math.radians, (p[0], p[1], q[0], q[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(h)))


def _post(id_, land, navn, malt, status, forhold, **ekstra):
    return uten_tomme({
        "id": id_, "land": land, "navn": navn, "malt": malt, "status": status,
        "forhold": round(forhold, 2), "alvorlig": True if forhold < ALVORLIG else None, **ekstra,
    })


# ------------------------------------------------------------------ Norge

def norge(naa, logg, meldinger_punkter):
    bruker, passord = os.environ.get("DATEX_USER"), os.environ.get("DATEX_PASSWORD")
    if not bruker or not passord:
        raise Feil("mangler DATEX_USER/DATEX_PASSWORD")
    h = {"Authorization": "Basic " + b64encode(f"{bruker}:{passord}".encode()).decode(),
         "User-Agent": "roijenapp-trafikkflyt/1"}
    import datex_uttrekk as du
    steder_rot = ET.fromstring(_hent(DATEX + "GetPredefinedTravelTimeLocations/pullsnapshotdata", headers=h))
    steder, srs = {}, Counter()
    for el in steder_rot.iter():
        if _lokal(el.tag) != "predefinedLocationReference" or "id" not in el.attrib:
            continue
        pos = next((e for e in el.iter() if _lokal(e.tag) == "posList"), None)
        if pos is None or not pos.text:
            continue
        gml = next((e for e in el.iter() if _lokal(e.tag) == "gmlLineString"), None)
        srs[(gml.attrib.get("srsName") if gml is not None else None,
             gml.attrib.get("srsDimension") if gml is not None else None)] += 1
        tall = [float(x) for x in pos.text.split()]
        par = list(zip(tall[0::2], tall[1::2]))
        if par and abs(par[0][0]) > 1000:            # meter → EPSG:25833 (øst, nord)
            lonlat = [tuple(reversed(du.utm33_til_latlon(e, n))) for e, n in par]
        elif par and par[0][0] > 50:                 # (bredde, lengde)
            lonlat = [(b, a) for a, b in par]
        else:                                        # (lengde, bredde)
            lonlat = par
        navn = next((e.text for e in el.iter() if _lokal(e.tag) == "value" and e.text), None)
        steder[el.attrib["id"]] = {"navn": navn, "lonlat": lonlat}
    logg.append(f"NO: {len(steder)} strekninger; srsName/srsDimension i posList: {srs.most_common()}")

    data_rot = ET.fromstring(_hent(DATEX + "GetTravelTimeData/pullsnapshotdata", headers=h))
    per = {}
    for pq in data_rot.iter():
        if _lokal(pq.tag) != "physicalQuantity":
            continue
        ref = next((e.attrib.get("id") for e in pq.iter() if _lokal(e.tag) == "predefinedLocationReference"), None)
        if not ref:
            continue
        d = per.setdefault(ref, {})
        for e in pq.iter():
            t = _lokal(e.tag)
            if t in ("travelTime", "freeFlowTravelTime"):
                v = next((x.text for x in e.iter() if _lokal(x.tag) == "duration"), None)
                if v:
                    d[t] = float(v)
            elif t == "freeFlowSpeed":
                v = next((x.text for x in e.iter() if _lokal(x.tag) == "speed"), None)
                if v:
                    d["ffs"] = float(v)
            elif t == "endOfPeriod" and e.text:
                d["malt"] = e.text
            elif t == "trafficStatusValue" and e.text:
                d["status"] = e.text

    ut, bort = [], Counter()
    eksempel_sjekk = []
    for ref, d in per.items():
        sted = steder.get(ref) or {}
        if d.get("status") in (None, "unknown") or not d.get("travelTime") or not d.get("freeFlowTravelTime"):
            bort["uten måling"] += 1
            continue
        malt = _tid(d.get("malt"))
        if not malt or naa - malt > MAKS_ALDER:
            bort["eldre enn 15 min"] += 1
            continue
        forhold = d["freeFlowTravelTime"] / d["travelTime"]
        if forhold >= GRENSE:
            continue
        if forhold < MIN_FORHOLD:
            bort["målefeil: forhold < 0,05"] += 1
            continue
        forsinkelse = d["travelTime"] - d["freeFlowTravelTime"]
        linje = linje_latlon(sted.get("lonlat") or [])
        if forsinkelse > NO_MAKS_FORSINKELSE_S:
            pkt = [q for q in (linje or [])]
            naer = any(_avstand(m, q) <= NO_SJEKK_AVSTAND_M for m in meldinger_punkter for q in pkt)
            if not naer:
                bort["målefeil: > 1 t uten trafikkmelding"] += 1
                logg.append(f"NO: tatt bort {ref} ({sted.get('navn')}): forsinkelse {forsinkelse:.0f} s, "
                            f"ingen trafikkmelding innen 1 km")
                continue
        lengde = sum(_avstand(a, b) for a, b in zip(linje or [], (linje or [])[1:])) if linje else None
        if len(eksempel_sjekk) < 4 and linje:
            eksempel_sjekk.append(f"{ref} «{sted.get('navn')}»: start {linje[0]}, slutt {linje[-1]}")
        ffs = d.get("ffs")
        ut.append(_post(
            f"NO-{ref}", "NO", sted.get("navn"), iso_lokal(d.get("malt"), "Europe/Oslo"), d.get("status"), forhold,
            fart=round(ffs * forhold, 1) if ffs else None, fart_normal=ffs,
            reisetid_s=round(d["travelTime"]), normal_s=round(d["freeFlowTravelTime"]),
            forsinkelse_s=round(forsinkelse), lengde_m=round(lengde) if lengde else None,
            linjer=[linje] if linje else None,
        ))
    # Kontroll 1: et par strekninger med navn og ende-punkter (navnet sier hvor de skal ligge)
    alle = [f"{r} «{s['navn']}»: {linje_latlon(s['lonlat'])[0] if linje_latlon(s['lonlat']) else None}"
            for r, s in list(steder.items())[:6]]
    logg.append("NO: kontroll av posisjoner (id «navn»: første punkt [bredde, lengde]): " + "; ".join(alle))
    if eksempel_sjekk:
        logg.append("NO: kø-strekninger nå: " + "; ".join(eksempel_sjekk))
    logg.append(f"NO: {len(ut)} med i fila; tatt bort: {dict(bort)}")
    return ut


# ------------------------------------------------------------------ Sverige

def sverige(naa, logg):
    nokkel = os.environ.get("TRAFIKVERKET_NOKKEL", "").strip()
    if not nokkel:
        raise Feil("mangler TRAFIKVERKET_NOKKEL")
    if any(c in nokkel for c in '<>"&\'') or len(nokkel) > 200:
        raise Feil("nøkkelen har et uventet format")
    q = (f'<REQUEST><LOGIN authenticationkey="{nokkel}"/>'
         '<QUERY objecttype="TravelTimeRoute" schemaversion="1.5"/></REQUEST>').encode()
    try:
        res = json.loads(_hent(TRV, data=q, headers={"Content-Type": "text/xml; charset=utf-8"}))["RESPONSE"]["RESULT"][0]
    except (ValueError, KeyError, IndexError, TypeError):
        raise Feil("uventet svar") from None
    if "ERROR" in res:
        raise Feil("feil fra API-et")
    ut, bort, kontroll = [], Counter(), []
    for r in res.get("TravelTimeRoute") or []:
        if r.get("Deleted") or r.get("TrafficStatus") in (None, "unknown"):
            bort["uten måling"] += 1
            continue
        tt, ff, lengde = r.get("TravelTime"), r.get("FreeFlowTravelTime"), r.get("Length")
        if not tt or not ff or tt <= 0:
            bort["uten måling"] += 1
            continue
        malt = _tid(r.get("MeasureTime"))
        if not malt or naa - malt > MAKS_ALDER:
            bort["eldre enn 15 min"] += 1
            continue
        # Kontroll 3: sekunder? Length / TravelTime * 3,6 skal være lik Speed (km/t).
        if lengde and r.get("Speed") and len(kontroll) < 5:
            kontroll.append(f"{r.get('Id')}: Length/TravelTime·3,6 = {lengde / tt * 3.6:.1f} km/t, Speed = {r['Speed']:.1f}; "
                            f"Length/FreeFlow·3,6 = {lengde / ff * 3.6:.1f}; Expected = {r.get('ExpectedFreeFlowTravelTime')}; "
                            f"målt {r.get('MeasureTime')}")
        forhold = ff / tt
        if forhold >= GRENSE:
            continue
        if forhold < MIN_FORHOLD:
            bort["målefeil: forhold < 0,05"] += 1
            continue
        g = wkt((r.get("Geometry") or {}).get("WGS84"))
        linjer = [l for l in (linje_latlon(x) for x in g[1]) if l] if g and g[0] == "linjer" else None
        navn = r.get("Name") or ""
        veg = next((w for w in navn.replace("/", " ").split() if w[:1] == "E" and w[1:].isdigit() or w.isdigit()), None)
        ut.append(_post(
            f"SE-{r.get('Id')}", "SE", navn or None, iso_lokal(r.get("MeasureTime"), "Europe/Stockholm"),
            r.get("TrafficStatus"), forhold,
            veg=veg, fart=round(r["Speed"], 1) if r.get("Speed") else None,
            fart_normal=round(lengde / ff * 3.6, 1) if lengde else None,
            reisetid_s=round(tt), normal_s=round(ff), forsinkelse_s=round(tt - ff),
            lengde_m=round(lengde) if lengde else None, linjer=linjer,
        ))
    logg.append("SE: kontroll av enheter: " + " | ".join(kontroll))
    logg.append(f"SE: {len(ut)} med i fila; tatt bort: {dict(bort)}")
    return ut


# ------------------------------------------------------------------ Finland

def _vvapaas(konstanter, retning, dag):
    """Fri-flyt-fart (km/t) for retning 1/2 på datoen (validFrom/validTo er «MM-DD», kan gå over nyttår)."""
    md = dag.strftime("%m-%d")
    for c in konstanter:
        if c.get("name") != f"VVAPAAS{retning}":
            continue
        fra, til = c.get("validFrom", "01-01"), c.get("validTo", "12-31")
        if (fra <= md <= til) if fra <= til else (md >= fra or md <= til):
            return c.get("value")
    return None


def finland(naa, logg):
    h = {"Digitraffic-User": "roijenapp/RuteLogger"}
    try:
        data = json.loads(_hent(TMS + "stations/data", headers=h))
        meta = json.loads(_hent(TMS + "stations", headers=h))
        konst = json.loads(_hent(TMS + "stations/sensor-constants", headers=h))
    except ValueError:
        raise Feil("uventet svar") from None
    stasjoner = {f.get("id"): f for f in meta.get("features") or []}
    konstanter = {s.get("id"): s.get("sensorConstantValues") or [] for s in konst.get("stations") or []}
    helsinki = naa.astimezone(__import__("zoneinfo").ZoneInfo("Europe/Helsinki"))
    ut, bort, kontroll = [], Counter(), []
    for s in data.get("stations") or []:
        sid = s.get("id")
        f = stasjoner.get(sid) or {}
        p = f.get("properties") or {}
        if p.get("collectionStatus") != "GATHERING":
            bort["ikke i drift"] += 1
            continue
        verdier = {v.get("name"): v for v in s.get("sensorValues") or []}
        for r in ("1", "2"):
            pros = verdier.get(f"KESKINOPEUS_5MIN_LIUKUVA_SUUNTA{r}_VVAPAAS{r}")
            kmt = verdier.get(f"KESKINOPEUS_5MIN_LIUKUVA_SUUNTA{r}")
            if not pros or not isinstance(pros.get("value"), (int, float)) or pros["value"] <= 0:
                bort["uten måling"] += 1
                continue
            malt = _tid(pros.get("measuredTime") or pros.get("timeWindowEnd") or s.get("dataUpdatedTime"))
            if not malt or naa - malt > MAKS_ALDER:
                bort["eldre enn 15 min"] += 1
                continue
            ff = _vvapaas(konstanter.get(sid, []), r, helsinki)
            fart = kmt.get("value") if kmt and isinstance(kmt.get("value"), (int, float)) else None
            # Kontroll 2: prosent-sensoren mot km/t delt på VVAPAAS.
            if ff and fart and len(kontroll) < 6:
                kontroll.append(f"{sid}/{r}: sensor {pros['value']} {pros.get('unit')}, km/t {fart} / VVAPAAS {ff} = {100 * fart / ff:.0f} %")
            forhold = pros["value"] / 100.0
            if forhold >= GRENSE:
                continue
            if forhold < MIN_FORHOLD:
                bort["målefeil: forhold < 0,05"] += 1
                continue
            k = (f.get("geometry") or {}).get("coordinates") or []
            peiling = None
            for c in konstanter.get(sid, []):
                if c.get("name") == "Tien_suunta":
                    peiling = c.get("value") if r == "1" else (c.get("value") + 180) % 360 if isinstance(c.get("value"), (int, float)) else None
            ut.append(_post(
                f"FI-{sid}-{r}", "FI", p.get("name"), iso_lokal(pros.get("measuredTime") or pros.get("timeWindowEnd") or s.get("dataUpdatedTime"), "Europe/Helsinki"),
                None, forhold,
                fart=fart, fart_normal=ff,
                punkt=[round(k[1], DESIMALER), round(k[0], DESIMALER)] if len(k) >= 2 else None,
                retning=r, peiling=peiling,
            ))
    eks = next((v for s in data.get("stations") or [] for v in s.get("sensorValues") or []
                if (v.get("name") or "").endswith("VVAPAAS1")), None)
    logg.append(f"FI: eksempel på sensorverdi: {json.dumps(eks, ensure_ascii=False)[:400]}")
    logg.append("FI: kontroll av prosent: " + " | ".join(kontroll))
    logg.append(f"FI: {len(ut)} med i fila; tatt bort: {dict(bort)}")
    return ut


# ------------------------------------------------------------------ samlet

def lag(naa, meldinger):
    """Returnerer (data, logg). `meldinger`: trafikkmeldingene (alle land, også ulykker)."""
    punkter = [m["punkt"] for m in meldinger if m.get("punkt")]
    logg = [f"Trafikkflyt: grense {GRENSE}, alvorlig < {ALVORLIG}; målefeil: forhold < {MIN_FORHOLD} tas bort, "
            f"NO-forsinkelse > {NO_MAKS_FORSINKELSE_S} s tas bort uten trafikkmelding innen {NO_SJEKK_AVSTAND_M} m; "
            f"målinger eldre enn {MAKS_ALDER} tas bort."]
    ko, kilder = [], []
    for land, f in (("NO", lambda: norge(naa, logg, punkter)), ("SE", lambda: sverige(naa, logg)),
                    ("FI", lambda: finland(naa, logg))):
        try:
            poster = f()
            status = "ok"
        except Exception as e:                  # ett land skal ikke stoppe de andre
            poster, status = [], "feil"
            logg.append(f"{land}: feil: {e if isinstance(e, Feil) else type(e).__name__}")
        ko += poster
        kilder.append({"land": land, "kilde": KILDER[land][0], "lisens": KILDER[land][1],
                       "antall": len(poster), "status": status})
    ko.sort(key=lambda p: (p["forhold"], p["id"]))
    return {"versjon": 1, "hentet": naa.replace(microsecond=0).isoformat(), "grense": GRENSE,
            "kilder": kilder, "antall": len(ko), "ko": ko}, logg
