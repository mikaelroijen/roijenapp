"""
Trafikmeldinger fra Trafikverket (Sverige), objekttypen Situation (namespace road.trafficinfo,
schemaversion 1.6) fra Trafikverkets öppna API. Lisens CC0 1.0.

Nøkkelen ligger bare i miljøvariabelen TRAFIKVERKET_NOKKEL (GitHub-hemmelighet). Den skrives
aldri ut, og feilmeldinger tar ikke med svaret fra serveren ordrett.

Tider uten UTC-forskyvning er svensk lokaltid (Trafikverkets dokumentasjon, «The Response»,
gjengitt i OpenConditions' testdata); de skrives med forskyvning i fila.
"""
import gzip, json, os, urllib.error, urllib.request
from collections import Counter

from geo_felles import DESIMALER, iso_lokal, linje_latlon, utløpt, uten_tomme, wkt

URL = "https://api.trafikinfo.trafikverket.se/v2/data.json"
SONE = "Europe/Stockholm"
KILDE = "Trafikverket – öppna API för trafikinformation (Situation)"
LISENS = "CC0 1.0 – https://creativecommons.org/publicdomain/zero/1.0/"

# Utvalg (Chat A, beskjed-nettside-trafikkmeldinger-utvalg-2026-11-04). Nøkkel: MessageCodeValue.
STENGT = {"roadClosed"}
VEGARBEID = {"blastingWork"}


# Vegarbeid som stopper eller forsinker (Chat A 4. nov): roadworks/resurfacingWork når Message
# eller Header nevner et av ordene. «lots» dekker også «lotsbil».
VEGARBEID_TEKST_KODER = {"roadworks", "resurfacingWork"}
VEGARBEID_ORD = ("trafikljus", "signal", "lots", "flaggvakt", "växelvis", "väntetid")
# Ulykker (Mikael 4. nov): MessageType «Olycka», type = MessageCodeValue.
ULYKKE_TYPE = "Olycka"


def _kategori(d):
    """(kategori, undertype) eller (None, None)."""
    kode = d.get("MessageCodeValue")
    if kode in STENGT:
        return "stengt", None
    if kode in VEGARBEID:
        return "vegarbeid", None
    if d.get("MessageType") == ULYKKE_TYPE:
        return "ulykke", None
    if kode in VEGARBEID_TEKST_KODER:
        tekst_ = f"{d.get('Message') or ''} {d.get('Header') or ''}".lower()
        ord_ = min(((tekst_.find(o), o) for o in VEGARBEID_ORD if o in tekst_), default=None)
        if ord_:
            return "vegarbeid", ord_[1]
    return None, None


class Feil(Exception):
    pass


class ManglerNokkel(Exception):
    pass


def hent():
    nokkel = os.environ.get("TRAFIKVERKET_NOKKEL", "").strip()
    if not nokkel:
        raise ManglerNokkel()
    if any(c in nokkel for c in '<>"&\'') or len(nokkel) > 200:
        raise Feil("nøkkelen har et uventet format")
    sporring = (
        f'<REQUEST><LOGIN authenticationkey="{nokkel}"/>'
        '<QUERY objecttype="Situation" namespace="road.trafficinfo" schemaversion="1.6">'
        '<FILTER><NE name="Deviation.MessageType" value="Färjor"/></FILTER>'
        '</QUERY></REQUEST>'
    ).encode("utf-8")
    req = urllib.request.Request(URL, data=sporring, method="POST")
    req.add_header("Content-Type", "text/xml; charset=utf-8")
    req.add_header("Accept-Encoding", "gzip")
    req.add_header("User-Agent", "roijenapp-trafikkmeldinger/1")
    try:
        with urllib.request.urlopen(req, timeout=120) as svar:
            data = svar.read()
            if svar.headers.get("Content-Encoding") == "gzip":
                data = gzip.decompress(data)
    except urllib.error.HTTPError as feil:
        raise Feil(f"HTTP {feil.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as feil:
        raise Feil(type(feil).__name__) from None
    try:
        d = json.loads(data)
        res = d["RESPONSE"]["RESULT"][0]
    except (ValueError, KeyError, IndexError, TypeError):
        raise Feil("uventet svar") from None
    if "ERROR" in res:
        raise Feil("feil fra API-et: " + str((res.get("ERROR") or {}).get("MESSAGE", "ukjent"))[:120])
    return res.get("Situation") or []


def _avvik(situasjoner):
    for s in situasjoner:
        if s.get("Deleted"):
            continue
        for d in s.get("Deviation") or []:
            yield s, d


def oversikt(situasjoner):
    """Linjer til jobbens logg: hvilke meldingstyper og koder Trafikverket faktisk bruker."""
    koder, restr = Counter(), Counter()
    for _, d in _avvik(situasjoner):
        koder[(d.get("MessageType"), d.get("MessageTypeValue"), d.get("MessageCode"),
               d.get("MessageCodeValue"))] += 1
        if d.get("TrafficRestrictionType"):
            restr[d["TrafficRestrictionType"]] += 1
    ut = ["Sverige – MessageType / MessageTypeValue / MessageCode / MessageCodeValue: antall"]
    ut += [f"  {a} / {b} / {c} / {e}: {n}" for (a, b, c, e), n in sorted(koder.items(), key=lambda x: -x[1])]
    # Vegarbeid sier ikke i kodene om det er lysregulering eller ventetid; tell ord i teksten.
    ord_ = {"signal": 0, "trafikljus": 0, "omväxlande": 0, "växelvis": 0, "väntetid": 0, "lots": 0,
            "flaggvakt": 0, "stopp": 0, "avstängd": 0, "enkelriktad": 0, "körfält": 0}
    for _, d in _avvik(situasjoner):
        if d.get("MessageType") == "Vägarbete":
            tekst_ = f"{d.get('Message') or ''} {d.get('TemporaryLimit') or ''}".lower()
            for o in ord_:
                ord_[o] += o in tekst_
    ut.append("Sverige – vegarbeid (MessageType Vägarbete) der teksten inneholder ordet: antall")
    ut += [f"  {o}: {n}" for o, n in ord_.items()]
    utvalgt = Counter()
    for _, d in _avvik(situasjoner):
        k = d.get("MessageCodeValue")
        if _kategori(d)[0]:
            utvalgt[(k, "pause" if d.get("Suspended") else "aktiv",
                     "utløpt" if utløpt(iso_lokal(d.get("EndTime"), SONE)) and not d.get("ValidUntilFurtherNotice") else "")] += 1
    ut.append("Sverige – utvalgte koder etter Suspended/utløpt: antall")
    ut += [f"  {a} {b} {c}: {n}" for (a, b, c), n in sorted(utvalgt.items())]
    ut.append("Sverige – TrafficRestrictionType: antall")
    ut += [f"  {k}: {n}" for k, n in restr.most_common(40)]
    return ut


def plukk_ut(situasjoner, naa=None):
    meldinger = []
    for s, d in _avvik(situasjoner):
        kode = d.get("MessageCodeValue")
        kategori, undertype = _kategori(d)
        if not kategori or d.get("Suspended"):
            continue
        start = iso_lokal(d.get("StartTime") or (d.get("CreationTime") if kategori == "ulykke" else None), SONE)
        slutt = None if d.get("ValidUntilFurtherNotice") else iso_lokal(d.get("EndTime"), SONE)
        if utløpt(slutt, naa):
            continue

        g = d.get("Geometry") or {}
        punkt, linjer = None, []
        for kandidat in ((g.get("Line") or {}).get("WGS84"), g.get("WGS84")):
            r = wkt(kandidat)
            if r and r[0] == "linjer":
                linjer = [l for l in (linje_latlon(x) for x in r[1]) if l]
                break
        r = wkt((g.get("Point") or {}).get("WGS84"))
        if r and r[0] == "punkt":
            punkt = [round(r[1][1], DESIMALER), round(r[1][0], DESIMALER)]
        if punkt is None and linjer:
            punkt = linjer[0][0]

        gjentatt = []
        for p in d.get("Schedule") or []:
            tider = [{"fra": (t.get("Start") or "")[:5], "til": (t.get("End") or "")[:5]}
                     for t in p.get("RecurringTimePeriodOfDay") or [] if t.get("Start") and t.get("End")]
            gjentatt.append(uten_tomme({
                "fra": iso_lokal(p.get("StartOfPeriod"), SONE),
                "til": iso_lokal(p.get("EndOfPeriod"), SONE),
                "tider": tider,
            }))

        meldinger.append(uten_tomme({
            "id": d.get("Id"),
            "situasjon": s.get("Id"),
            "land": "SE",
            "tidssone": SONE,
            "kategori": kategori,
            "type": kode,
            "undertype": undertype,
            "tekst": d.get("Message") or d.get("Header"),
            "overskrift": d.get("Header"),
            "sted": d.get("LocationDescriptor") or d.get("PositionalDescription"),
            "veg": d.get("RoadNumber"),
            "vegnavn": d.get("RoadName"),
            "start": start,
            "slutt": slutt,
            "gjentatt": [x for x in gjentatt if x] or None,
            "retning": d.get("AffectedDirectionValue"),
            "punkt": punkt,
            "linjer": linjer or None,
        }))
    return [m for m in meldinger if m.get("id")]
