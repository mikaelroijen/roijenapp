"""
Engangs-kartlegging (5. nov 2026): finnes åpne fartsdata/reisetider til å oppdage kø i NO, SE og FI?
Skriver bare en oppsummering i loggen (antall, størrelse, felt, eksempler). Publiserer ingenting.
Hemmeligheter leses fra miljøet og skrives aldri ut.
"""
import gzip, json, os, re, sys, time, urllib.error, urllib.request, xml.etree.ElementTree as ET
from base64 import b64encode
from collections import Counter


def hent(url, data=None, headers=None, auth=None):
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    req.add_header("Accept-Encoding", "gzip")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    if auth:
        req.add_header("Authorization", "Basic " + b64encode(f"{auth[0]}:{auth[1]}".encode()).decode())
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=180) as svar:
        rå = svar.read()
        komprimert = len(rå)
        if svar.headers.get("Content-Encoding") == "gzip":
            rå = gzip.decompress(rå)
        hode = {k: svar.headers.get(k) for k in ("Content-Type", "Last-Modified", "Cache-Control", "ETag")}
    print(f"  {url.split('?')[0]}: {len(rå)/1024:.0f} kB ({komprimert/1024:.0f} kB overført), "
          f"{time.time()-t0:.1f} s, {hode}")
    return rå


def lokal(tag):
    return tag.rsplit("}", 1)[-1]


def xml_oversikt(rå, navn, eksempel_tagg=None, maks_eksempel=2500):
    rot = ET.fromstring(rå)
    tagger = Counter(lokal(e.tag) for e in rot.iter())
    typer = Counter(v for e in rot.iter() for k, v in e.attrib.items() if lokal(k) == "type")
    print(f"  {navn}: {sum(tagger.values())} elementer. Vanligste tagger: {tagger.most_common(45)}")
    print(f"  {navn}: xsi:type: {typer.most_common(20)}")
    if eksempel_tagg:
        for e in rot.iter():
            if lokal(e.tag) == eksempel_tagg:
                s = ET.tostring(e, encoding="unicode")
                s = re.sub(r"\s+", " ", re.sub(r'xmlns(:\w+)?="[^"]*"', "", s))
                print(f"  {navn}: eksempel <{eksempel_tagg}>: {s[:maks_eksempel]}")
                break
    return rot


def norge():
    print("== NORGE (Statens vegvesen, DATEX 3.1 reisetider)")
    bruker, passord = os.environ.get("DATEX_USER"), os.environ.get("DATEX_PASSWORD")
    if not bruker or not passord:
        print("  mangler DATEX_USER/DATEX_PASSWORD")
        return
    base = "https://datex-server-get-v3-1.atlas.vegvesen.no/datexapi/"
    for tjeneste, tagg in (("GetPredefinedTravelTimeLocations", "predefinedLocation"),
                           ("GetTravelTimeData", "physicalQuantity")):
        try:
            rå = hent(base + tjeneste + "/pullsnapshotdata", auth=(bruker, passord))
        except urllib.error.HTTPError as f:
            print(f"  {tjeneste}: HTTP {f.code}")
            continue
        except Exception as f:
            print(f"  {tjeneste}: {type(f).__name__}")
            continue
        rot = xml_oversikt(rå, tjeneste, tagg)
        if tjeneste == "GetTravelTimeData":
            # Forsinkelse: se etter felt med «delay» / «normally» / «freeFlow»
            felt = Counter(lokal(e.tag) for e in rot.iter()
                           if re.search(r"delay|normal|freeFlow|travelTime|trend|type", lokal(e.tag), re.I))
            print(f"  GetTravelTimeData: felt om tid/forsinkelse: {felt.most_common(30)}")
            tider = Counter((e.text or "")[:16] for e in rot.iter() if lokal(e.tag) in ("measurementOrCalculationTime", "publicationTime"))
            print(f"  GetTravelTimeData: målt/publisert (til minutt): {tider.most_common(8)}")
            status = Counter((e.text or "") for e in rot.iter() if lokal(e.tag) == "trafficStatusValue")
            print(f"  GetTravelTimeData: trafficStatusValue: {status.most_common()}")
            print(f"  GetTravelTimeData: travelTimeType: {Counter(e.text for e in rot.iter() if lokal(e.tag) == 'travelTimeType').most_common()}")
            print(f"  GetTravelTimeData: travelTimeTrendType: {Counter(e.text for e in rot.iter() if lokal(e.tag) == 'travelTimeTrendType').most_common()}")
            # Forhold reisetid / fri flyt per strekning
            per = {}
            for pq in rot.iter():
                if lokal(pq.tag) != "physicalQuantity":
                    continue
                ref = next((e.attrib.get("id") for e in pq.iter() if lokal(e.tag) == "predefinedLocationReference"), None)
                for e in pq.iter():
                    if lokal(e.tag) in ("travelTime", "freeFlowTravelTime"):
                        d = next((x.text for x in e.iter() if lokal(x.tag) == "duration"), None)
                        if d:
                            per.setdefault(ref, {})[lokal(e.tag)] = float(d)
                    if lokal(e.tag) == "measurementOrCalculationTime" or lokal(e.tag) == "startOfPeriod":
                        per.setdefault(ref, {}).setdefault("tid", e.text)
            kø = sorted(((round(v["travelTime"] / v["freeFlowTravelTime"], 1), round(v["travelTime"] - v["freeFlowTravelTime"]), r)
                         for r, v in per.items() if v.get("travelTime") and v.get("freeFlowTravelTime")), reverse=True)
            print(f"  GetTravelTimeData: {len(per)} strekninger, {len(kø)} med reisetid nå; ≥ 1,5 × fri flyt: "
                  f"{sum(k[0] >= 1.5 for k in kø)}; de verste: {kø[:10]}")
            print(f"  GetTravelTimeData: tider: {Counter((v.get('tid') or '')[:16] for v in per.values()).most_common(6)}")
            forsinkelser = []
            for e in rot.iter():
                if re.search(r"delay", lokal(e.tag), re.I):
                    try:
                        forsinkelser.append(float(e.text))
                    except (TypeError, ValueError):
                        pass
            if forsinkelser:
                forsinkelser.sort()
                n = len(forsinkelser)
                print(f"  GetTravelTimeData: {n} forsinkelsesverdier; median {forsinkelser[n//2]}, "
                      f"90 % {forsinkelser[int(n*0.9)]}, maks {forsinkelser[-1]}, > 300: {sum(x > 300 for x in forsinkelser)}")


def sverige():
    print("== SVERIGE (Trafikverket)")
    nokkel = os.environ.get("TRAFIKVERKET_NOKKEL", "").strip()
    if not nokkel or any(c in nokkel for c in '<>"&\''):
        print("  mangler/ugyldig TRAFIKVERKET_NOKKEL")
        return
    url = "https://api.trafikinfo.trafikverket.se/v2/data.json"
    for objekt, versjon in (("TravelTimeRoute", "1.5"), ("TrafficFlow", "1.4")):
        q = (f'<REQUEST><LOGIN authenticationkey="{nokkel}"/>'
             f'<QUERY objecttype="{objekt}" schemaversion="{versjon}"/></REQUEST>').encode()
        try:
            rå = hent(url, data=q, headers={"Content-Type": "text/xml; charset=utf-8"})
            res = json.loads(rå)["RESPONSE"]["RESULT"][0]
        except urllib.error.HTTPError as f:
            print(f"  {objekt}: HTTP {f.code}")
            continue
        except Exception as f:
            print(f"  {objekt}: {type(f).__name__}")
            continue
        if "ERROR" in res:
            print(f"  {objekt}: feil fra API-et: {str(res['ERROR'].get('MESSAGE'))[:150]}")
            continue
        rader = res.get(objekt) or []
        print(f"  {objekt}: {len(rader)} rader. Felt: {sorted({k for r in rader for k in r})}")
        if rader:
            print(f"  {objekt}: eksempel: {json.dumps(rader[0], ensure_ascii=False)[:1800]}")
        if objekt == "TravelTimeRoute":
            print(f"  status: {Counter(r.get('TrafficStatus') for r in rader).most_common()}")
            print(f"  eier (RouteOwner): {Counter(r.get('RouteOwner') for r in rader).most_common()}")
            print(f"  län: {Counter(c for r in rader for c in (r.get('CountyNo') or [])).most_common()}")
            print(f"  lengde km totalt: {sum(r.get('Length') or 0 for r in rader)/1000:.0f}; navn (utvalg): {[r.get('Name') for r in rader[::20]]}")
            print(f"  målt (til minutt): {Counter((r.get('MeasureTime') or '')[:16] for r in rader).most_common(6)}")
            kø = []
            for r in rader:
                tt, ff = r.get("TravelTime"), r.get("FreeFlowTravelTime")
                if tt and ff and ff > 0 and tt / ff >= 1.5:
                    kø.append((round(tt / ff, 1), round(tt - ff), r.get("Name")))
            kø.sort(reverse=True)
            print(f"  strekninger med restid ≥ 1,5 × fri flyt nå: {len(kø)}; de verste: {kø[:12]}")
        if objekt == "TrafficFlow":
            print(f"  kjøretøytype: {Counter(r.get('VehicleType') for r in rader).most_common(8)}")
            print(f"  målepunkter: {len({r.get('SiteId') for r in rader})}")
            print(f"  målt (til minutt): {Counter((r.get('MeasurementTime') or '')[:16] for r in rader).most_common(6)}")
            print(f"  periode (s): {Counter(r.get('MeasurementOrCalculationPeriod') for r in rader).most_common(5)}")
            print(f"  län: {Counter(r.get('CountyNo') or r.get('County') for r in rader).most_common()}")


def finland():
    print("== FINLAND (Digitraffic TMS/LAM)")
    h = {"Digitraffic-User": "roijenapp/RuteLogger"}
    try:
        rå = hent("https://tie.digitraffic.fi/api/tms/v1/stations/data", headers=h)
        d = json.loads(rå)
        st = d.get("stations") or []
        sensorer = Counter(v.get("name") for s in st for v in s.get("sensorValues") or [])
        print(f"  stations/data: {len(st)} stasjoner; oppdatert {d.get('dataUpdatedTime')}")
        print(f"  sensornavn: {sensorer.most_common(60)}")
        if st:
            print(f"  eksempel: {json.dumps(st[0], ensure_ascii=False)[:2500]}")
        enheter = Counter((v.get("name"), v.get("unit")) for s in st for v in s.get("sensorValues") or [] if "VVAPAAS" in (v.get("name") or ""))
        print(f"  sensorer mot fri flyt (VVAPAAS): {enheter.most_common(10)}")
        lav = []
        for s in st:
            for v in s.get("sensorValues") or []:
                if "VVAPAAS" in (v.get("name") or "") and isinstance(v.get("value"), (int, float)) and 0 < v["value"] < 50:
                    lav.append((v["value"], s.get("id"), v.get("name")))
        print(f"  målinger under 50 % av fri flyt nå: {len(lav)}; eksempler: {sorted(lav)[:10]}")
    except Exception as f:
        print(f"  stations/data: {type(f).__name__}: {str(f)[:120]}")
    try:
        rå = hent("https://tie.digitraffic.fi/api/tms/v1/stations", headers=h)
        d = json.loads(rå)
        print(f"  stations (metadata): {len(d.get('features') or [])} stasjoner; "
              f"eksempel: {json.dumps((d.get('features') or [{}])[0], ensure_ascii=False)[:800]}")
    except Exception as f:
        print(f"  stations: {type(f).__name__}")
    try:
        rå = hent("https://tie.digitraffic.fi/api/tms/v1/stations/23001/sensor-constants", headers=h)
        print(f"  sensor-constants (eksempel 23001): {rå[:1500].decode('utf-8', 'replace')}")
    except Exception as f:
        print(f"  sensor-constants: {type(f).__name__}")


if __name__ == "__main__":
    for f in (norge, sverige, finland):
        try:
            f()
        except Exception as e:
            print(f"{f.__name__}: {type(e).__name__}")
    sys.exit(0)
