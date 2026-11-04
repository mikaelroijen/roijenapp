"""
Trafikkmeldinger fra Fintraffic / Digitraffic (Finland), traffic-message API v2 (GeoJSON).
Lisens CC BY 4.0: «Source: Fintraffic / digitraffic.fi, license CC 4.0 BY».

Digitraffic krever gzip (svarer 406 uten) og ber om en Digitraffic-User-header som sier hvilken
app som spør, uten personopplysninger (tmfg/digitraffic, pages/ohjeita.md).
"""
import gzip, json, urllib.error, urllib.request
from collections import Counter

from geo_felles import DESIMALER, iso_lokal, linje_latlon, utløpt, uten_tomme

URLER = {
    "roadworks": "https://tie.digitraffic.fi/api/traffic-message/v2/roadworks",
    "traffic-announcements": "https://tie.digitraffic.fi/api/traffic-message/v2/traffic-announcements",
}
SONE = "Europe/Helsinki"
KILDE = "Source: Fintraffic / digitraffic.fi, license CC 4.0 BY"
LISENS = "CC BY 4.0 – https://creativecommons.org/licenses/by/4.0/"

# Utvalg (Chat A, beskjed-nettside-trafikkmeldinger-utvalg-2026-11-04).
# Begrensningstyper i vegarbeidsfaser (v2 skriver dem med små bokstaver og mellomrom).
STENGT = {"road closed", "intermittent short term closure", "intermittent short term closures"}
VEGARBEID = {"traffic lights", "single alternate line traffic", "intermittent short term stops",
             "intermittent stops and closure effective", "estimated delay", "estimated delay during rush hour"}
# Ulykker (Mikael 4. nov): trafikkmeldinger av disse typene → kategori «ulykke».
ULYKKE = {"accident report", "preliminary accident report"}
# Trafikkmeldinger (ikke vegarbeid): «Tie on suljettu liikenteeltä» = vegen er stengt for trafikk.
STENGT_TEKST = ("suljettu liikenteeltä",)


class Feil(Exception):
    pass


def hent():
    ut = {}
    for navn, url in URLER.items():
        req = urllib.request.Request(url)
        req.add_header("Accept-Encoding", "gzip")
        req.add_header("Digitraffic-User", "roijenapp/RuteLogger")
        try:
            with urllib.request.urlopen(req, timeout=120) as svar:
                data = svar.read()
                if svar.headers.get("Content-Encoding") == "gzip":
                    data = gzip.decompress(data)
            ut[navn] = json.loads(data).get("features") or []
        except urllib.error.HTTPError as feil:
            raise Feil(f"{navn}: HTTP {feil.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, AttributeError) as feil:
            raise Feil(f"{navn}: {type(feil).__name__}") from None
    return ut


def _norm(s):
    return (s or "").strip().lower().replace("_", " ")


def oversikt(data):
    typer, restr, egenskaper = Counter(), Counter(), Counter()
    for navn, features in data.items():
        for f in features:
            p = f.get("properties") or {}
            typer[(navn, p.get("situationType"), p.get("trafficAnnouncementType"))] += 1
            for a in p.get("announcements") or []:
                for fase in a.get("roadWorkPhases") or []:
                    for r in fase.get("restrictions") or []:
                        restr[_norm(r.get("type"))] += 1
                for e in a.get("features") or []:
                    egenskaper[(navn, e.get("name"))] += 1
    ut = ["Finland – endepunkt / situationType / trafficAnnouncementType: antall"]
    ut += [f"  {a} / {b} / {c}: {n}" for (a, b, c), n in sorted(typer.items(), key=lambda x: -x[1])]
    ut.append("Finland – begrensninger i vegarbeidsfaser (restrictions.type): antall")
    ut += [f"  {k}: {n}" for k, n in restr.most_common(60)]
    ut.append("Finland – features.name i meldingene: antall")
    ut += [f"  {a}: {b}: {n}" for (a, b), n in egenskaper.most_common(60)]
    return ut


def _geometri(f):
    g = f.get("geometry") or {}
    t, k = g.get("type"), g.get("coordinates")
    punkt, linjer = None, []
    try:
        if t == "Point":
            punkt = [round(k[1], DESIMALER), round(k[0], DESIMALER)]
        elif t == "LineString":
            linjer = [linje_latlon([(p[0], p[1]) for p in k])]
        elif t == "MultiLineString":
            linjer = [linje_latlon([(p[0], p[1]) for p in l]) for l in k]
    except (TypeError, IndexError):
        pass
    linjer = [l for l in linjer if l]
    if punkt is None and linjer:
        punkt = linjer[0][0]
    return punkt, linjer or None


def _sted(a):
    ral = ((a.get("locationDetails") or {}).get("roadAddressLocation") or {})
    pp = ral.get("primaryPoint") or {}
    veg = (pp.get("roadAddress") or {}).get("road")
    return {
        "sted": (a.get("location") or {}).get("description"),
        "veg": str(veg) if veg is not None else None,
        "vegnavn": pp.get("roadName"),
        "retning": ral.get("direction"),
    }


def _arbeidstid(fase):
    """workingHours → [{"tider":[{"fra","til"}], "dager":[…]}] gruppert på like klokkeslett."""
    grupper = {}
    for w in fase.get("workingHours") or []:
        if w.get("startTime") and w.get("endTime") and w.get("weekday"):
            grupper.setdefault((w["startTime"][:5], w["endTime"][:5]), []).append(w["weekday"].lower())
    rekke = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    return [{"tider": [{"fra": a, "til": b}], "dager": sorted(d, key=lambda x: rekke.index(x) if x in rekke else 9)}
            for (a, b), d in grupper.items()] or None


def plukk_ut(data, naa=None):
    meldinger = []
    for f in data.get("roadworks", []):
        p = f.get("properties") or {}
        punkt, linjer = _geometri(f)
        for a in (p.get("announcements") or [])[:1]:     # første språkversjon
            for fase in a.get("roadWorkPhases") or []:
                typer = [_norm(r.get("type")) for r in fase.get("restrictions") or []]
                stengt = next((t for t in typer if t in STENGT), None)
                arbeid = next((t for t in typer if t in VEGARBEID), None)
                typ = stengt or arbeid
                if not typ:
                    continue
                td = fase.get("timeAndDuration") or a.get("timeAndDuration") or {}
                slutt = iso_lokal(td.get("endTime"), SONE)
                if utløpt(slutt, naa):
                    continue
                tekst = " ".join(x.strip() for x in (a.get("title"), fase.get("comment")) if x and x.strip())
                meldinger.append(uten_tomme({
                    "id": fase.get("id") or p.get("situationId"),
                    "versjon": str(p["version"]) if p.get("version") is not None else None,
                    "situasjon": p.get("situationId"),
                    "land": "FI",
                    "tidssone": SONE,
                    "kategori": "stengt" if stengt else "vegarbeid",
                    "type": typ,
                    "tekst": tekst,
                    **_sted(a),
                    "start": iso_lokal(td.get("startTime"), SONE),
                    "slutt": slutt,
                    "arbeidstid": _arbeidstid(fase),
                    "punkt": punkt,
                    "linjer": linjer,
                }))
    for f in data.get("traffic-announcements", []):
        p = f.get("properties") or {}
        meldingstype = _norm(p.get("trafficAnnouncementType"))
        if meldingstype not in ULYKKE and meldingstype != "general":
            continue
        punkt, linjer = _geometri(f)
        for a in (p.get("announcements") or [])[:1]:
            navn = [(e.get("name") or "") for e in a.get("features") or []]
            treff = next((n for n in navn if any(s in n.lower() for s in STENGT_TEKST)), None)
            if meldingstype in ULYKKE:
                treff = meldingstype
            if not treff:
                continue
            td = a.get("timeAndDuration") or {}
            slutt = iso_lokal(td.get("endTime"), SONE)
            if utløpt(slutt, naa):
                continue
            tekst = " ".join(x.strip() for x in (a.get("title"), a.get("comment")) if x and x.strip())
            meldinger.append(uten_tomme({
                "id": p.get("situationId"),
                "versjon": str(p["version"]) if p.get("version") is not None else None,
                "situasjon": p.get("situationId"),
                "land": "FI",
                "tidssone": SONE,
                "kategori": "ulykke" if meldingstype in ULYKKE else "stengt",
                "type": treff,
                "tekst": tekst,
                **_sted(a),
                "start": iso_lokal(td.get("startTime") or p.get("releaseTime"), SONE),
                "slutt": slutt,
                "punkt": punkt,
                "linjer": linjer,
            }))
            break
    return [m for m in meldinger if m.get("id")]
