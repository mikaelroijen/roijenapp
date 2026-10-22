#!/usr/bin/env python3
"""
Trafikkmeldinger fra Statens vegvesen (DATEX II v3.1) → liten JSON for RuteLogger.

Henter alle situasjoner (GetSituation/pullsnapshotdata), plukker ut stengte veger og
vegarbeid som gir ventetid, regner om linjene fra EPSG:25833 (UTM 33) til
lengde/bredde, forenkler dem og skriver én JSON-fil som appene kan lese uten passord.

Bare standardbiblioteket i Python 3 brukes.

Bruk:
    # Henting (brukernavn/passord bare i miljøvariabler – aldri i kode eller logg):
    DATEX_USER=… DATEX_PASSWORD=… python3 tools/datex_uttrekk.py --ut data/trafikkmeldinger.json \
        [--forrige forrige.json]

    # Fra en lagret XML-fil (test):
    python3 tools/datex_uttrekk.py --fra-fil datex.xml --ut trafikkmeldinger.json

Utgangskoder: 0 = ny fil skrevet, 3 = ingenting nytt (304 eller samme innhold),
2 = feil (forrige fil beholdes hvis --forrige er gitt), 4 = mangler brukernavn/passord.
Med --github-output skrives «endret=true/false» til $GITHUB_OUTPUT.
"""
import argparse, base64, gzip, json, math, os, shutil, sys, urllib.error, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

URL = "https://datex-server-get-v3-1.atlas.vegvesen.no/datexapi/GetSituation/pullsnapshotdata"
KILDE = "Statens vegvesen – trafikkmeldinger (DATEX II), NLOD"
LISENS = "https://data.norge.no/nlod/no/2.0"
FORMAT_VERSJON = 1

SIT = "{http://datex2.eu/schema/3/situation}"
COM = "{http://datex2.eu/schema/3/common}"
LOC = "{http://datex2.eu/schema/3/locationReferencing}"

# Hvilke meldinger som tas med (oppdrag-nettside-datex-2026-10-22, Mikael: «begge deler»).
UTVALG = {
    "roadOrCarriagewayOrLaneManagementType": {
        "roadClosed": "stengt",
        "intermittentShortTermClosures": "stengt",
        "closedPermanentlyForTheWinter": "stengt",
    },
    "generalNetworkManagementType": {
        "temporaryTrafficLights": "vegarbeid",
        "trafficBeingManuallyDirected": "vegarbeid",
    },
    "constructionWorkType": {
        "blastingWork": "vegarbeid",
    },
}

LINJE_TOLERANSE_M = 10.0   # Douglas–Peucker: største avvik fra opprinnelig linje
DESIMALER = 5              # ca. 1 m


# ------------------------------------------------------------------ koordinater

def utm33_til_latlon(e, n):
    """EPSG:25833 (ETRS89 / UTM 33N) → (bredde, lengde) i grader.
    Krügers rekker (Karney 2011); kontrollert mot PROJ med under 1 mm avvik fra
    Vestlandet til Finnmark. ETRS89 og WGS84 skiller seg med under én meter i Norge,
    uten betydning for kartbruk."""
    a, f = 6378137.0, 1 / 298.257222101           # GRS80
    k0, e0, lon0 = 0.9996, 500000.0, math.radians(15.0)
    nn = f / (2 - f)
    A = a / (1 + nn) * (1 + nn**2 / 4 + nn**4 / 64)
    beta = [nn / 2 - 2 * nn**2 / 3 + 37 * nn**3 / 96,
            nn**2 / 48 + nn**3 / 15,
            17 * nn**3 / 480]
    xi = n / (k0 * A)
    eta = (e - e0) / (k0 * A)
    xi1, eta1 = xi, eta
    for j, b in enumerate(beta, 1):
        xi1 -= b * math.sin(2 * j * xi) * math.cosh(2 * j * eta)
        eta1 -= b * math.cos(2 * j * xi) * math.sinh(2 * j * eta)
    chi = math.asin(math.sin(xi1) / math.cosh(eta1))
    lon = lon0 + math.atan2(math.sinh(eta1), math.cos(xi1))
    # Fra konform bredde (chi) til geodetisk bredde
    delta = [2 * nn - 2 * nn**2 / 3 - 2 * nn**3,
             7 * nn**2 / 3 - 8 * nn**3 / 5,
             56 * nn**3 / 15]
    lat = chi + sum(d * math.sin(2 * j * chi) for j, d in enumerate(delta, 1))
    return math.degrees(lat), math.degrees(lon)


def avstand_m(p, q):
    R = 6371000.0
    la1, lo1, la2, lo2 = map(math.radians, (p[0], p[1], q[0], q[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(h)))


def forenkle(pts, tol=LINJE_TOLERANSE_M):
    """Douglas–Peucker på (øst, nord) i meter. Beholder endepunktene."""
    if len(pts) <= 2:
        return pts
    behold = [False] * len(pts)
    behold[0] = behold[-1] = True
    stakk = [(0, len(pts) - 1)]
    while stakk:
        i, j = stakk.pop()
        (x1, y1), (x2, y2) = pts[i], pts[j]
        dx, dy = x2 - x1, y2 - y1
        lengde = math.hypot(dx, dy)
        maks, k = -1.0, -1
        for m in range(i + 1, j):
            x, y = pts[m]
            if lengde == 0:
                d = math.hypot(x - x1, y - y1)
            else:
                d = abs(dy * x - dx * y + x2 * y1 - y2 * x1) / lengde
            if d > maks:
                maks, k = d, m
        if maks > tol:
            behold[k] = True
            stakk += [(i, k), (k, j)]
    return [p for p, b in zip(pts, behold) if b]


# ------------------------------------------------------------------ hjelpere

def tekst(el, sti):
    x = el.find(sti)
    return x.text.strip() if x is not None and x.text else None


def verdi(el, sti):
    """Første <value> under en flerspråklig tekst (norsk i praksis)."""
    x = el.find(sti)
    if x is None:
        return None
    v = x.find(f"{COM}values/{COM}value")
    return v.text.strip() if v is not None and v.text else None


def klokkeslett(t):
    """«07:00:00.0000000+02:00» → «07:00». DATEX oppgir +02:00 også for vintertid;
    tekstene viser at det er norsk lokaltid («mellom 07:00 og 15:00»)."""
    return t[:5] if t else None


def tid(t):
    if not t:
        return None
    try:
        return datetime.fromisoformat(t.replace("Z", "+00:00"))
    except ValueError:
        return None


def slå_sammen_nvdb(koder):
    """«veglenkesekvens;fra;til;retning» – avrunder posisjonene til 6 desimaler og slår
    sammen biter som henger sammen på samme veglenkesekvens og retning."""
    biter = []
    for kode in koder:
        deler = kode.split(";")
        if len(deler) != 4:
            continue
        try:
            fra, til = sorted((float(deler[1]), float(deler[2])))
        except ValueError:
            continue
        biter.append((deler[0], deler[3], fra, til))
    biter.sort()
    sammen = []
    for sek, retn, fra, til in biter:
        if sammen and sammen[-1][0] == sek and sammen[-1][1] == retn and fra <= sammen[-1][3] + 1e-9:
            sammen[-1][3] = max(sammen[-1][3], til)
        else:
            sammen.append([sek, retn, fra, til])
    tall = lambda x: f"{x:.6f}".rstrip("0").rstrip(".") or "0"
    return [f"{sek};{tall(fra)};{tall(til)};{retn}" for sek, retn, fra, til in sammen]


# ------------------------------------------------------------------ uttrekk

def plukk_ut(xml_bytes, naa=None):
    naa = naa or datetime.now(timezone.utc)
    meldinger = []
    situasjon_id = None
    publisert = None
    for hendelse, el in ET.iterparse(_bytes_io(xml_bytes), events=("start", "end")):
        if hendelse == "start":
            if el.tag == f"{SIT}situation":
                situasjon_id = el.get("id")
            continue
        if el.tag == f"{COM}publicationTime" and publisert is None:
            publisert = el.text
        if el.tag != f"{SIT}situationRecord":
            continue
        m = _melding(el, situasjon_id, naa)
        if m:
            meldinger.append(m)
        el.clear()
    meldinger.sort(key=lambda m: (m["kategori"], m["veg"] or "", m["id"]))
    return meldinger, publisert


def _bytes_io(b):
    import io
    return io.BytesIO(b)


def _melding(el, situasjon_id, naa):
    kategori = typ = None
    for felt, verdier in UTVALG.items():
        v = tekst(el, f"{SIT}{felt}")
        if v in verdier:
            kategori, typ = verdier[v], v
            break
    if not kategori:
        return None

    gyldig = el.find(f"{SIT}validity/{COM}validityTimeSpecification")
    start = tekst(gyldig, f"{COM}overallStartTime") if gyldig is not None else None
    slutt = tekst(gyldig, f"{COM}overallEndTime") if gyldig is not None else None
    if slutt and tid(slutt) and tid(slutt) < naa:
        return None                                # utløpt

    gjentatt = []
    if gyldig is not None:
        for p in gyldig.findall(f"{COM}validPeriod"):
            tider = [{"fra": klokkeslett(tekst(r, f"{COM}startTimeOfPeriod")),
                      "til": klokkeslett(tekst(r, f"{COM}endTimeOfPeriod"))}
                     for r in p.findall(f"{COM}recurringTimePeriodOfDay")]
            dager = [d.text for r in p.findall(f"{COM}recurringDayWeekMonthPeriod")
                     for d in r.findall(f"{COM}applicableDay") if d.text]
            gjentatt.append({k: v for k, v in {
                "fra": tekst(p, f"{COM}startOfPeriod"),
                "til": tekst(p, f"{COM}endOfPeriod"),
                "tider": tider or None,
                "dager": dager or None,
            }.items() if v})

    sted = veg = vegnavn = retning = lengde = None
    punkt = None
    linjer, nvdb = [], []
    lokasjon = el.find(f"{SIT}locationReference")
    if lokasjon is not None:
        for d in lokasjon.iter(f"{LOC}supplementaryPositionalDescription"):
            sted = sted or verdi(d, f"{LOC}locationDescription")
            veg = veg or tekst(d, f"{LOC}roadInformation/{LOC}roadNumber")
            vegnavn = vegnavn or tekst(d, f"{LOC}roadInformation/{LOC}roadName")
            l = tekst(d, f"{LOC}lengthAffected")
            if l and lengde is None:
                try:
                    lengde = round(float(l))
                except ValueError:
                    pass
        retning = next((x.text for x in lokasjon.iter(f"{LOC}alertCAffectedDirection") if x.text), None)
        for c in list(lokasjon.iter(f"{LOC}coordinatesForDisplay")) + list(lokasjon.iter(f"{LOC}pointCoordinates")):
            la, lo = tekst(c, f"{LOC}latitude"), tekst(c, f"{LOC}longitude")
            if la and lo:
                punkt = [round(float(la), DESIMALER), round(float(lo), DESIMALER)]
                break
        for g in lokasjon.iter(f"{LOC}gmlLineString"):
            if (g.get("srsName") or "25833") not in ("25833", "EPSG:25833"):
                continue
            tall = (tekst(g, f"{LOC}posList") or "").split()
            try:
                utm = [(float(tall[i]), float(tall[i + 1])) for i in range(0, len(tall) - 1, 2)]
            except ValueError:
                continue
            if len(utm) < 2:
                continue
            linje = [[round(v, DESIMALER) for v in utm33_til_latlon(e, n)] for e, n in forenkle(utm)]
            linjer.append(linje)
        for r in lokasjon.iter(f"{LOC}externalReferencing"):
            if tekst(r, f"{LOC}externalReferencingSystem") == "NVDB;LINE;ROADWAY":
                kode = tekst(r, f"{LOC}externalLocationCode")
                if kode:
                    nvdb.append(kode)
        nvdb = slå_sammen_nvdb(nvdb)
    if punkt is None and linjer:
        punkt = linjer[0][0]

    m = {
        "id": el.get("id"),
        "versjon": el.get("version"),
        "situasjon": situasjon_id,
        "kategori": kategori,
        "type": typ,
        "tekst": verdi(el, f"{SIT}generalPublicComment/{SIT}comment"),
        "sted": sted,
        "veg": veg,
        "vegnavn": vegnavn,
        "start": start,
        "slutt": slutt,
        "gjentatt": gjentatt or None,
        "retning": retning,
        "lengde_m": lengde,
        "punkt": punkt,
        "linjer": linjer or None,
        "nvdb": nvdb or None,
    }
    return {k: v for k, v in m.items() if v is not None}


# ------------------------------------------------------------------ henting

def hent(sist_endret=None):
    """Returnerer (xml_bytes, last_modified) eller (None, sist_endret) ved 304."""
    bruker, passord = os.environ.get("DATEX_USER"), os.environ.get("DATEX_PASSWORD")
    if not bruker or not passord:
        raise ManglerInnlogging()
    req = urllib.request.Request(URL)
    nokkel = base64.b64encode(f"{bruker}:{passord}".encode()).decode()
    req.add_header("Authorization", "Basic " + nokkel)
    req.add_header("Accept-Encoding", "gzip")
    req.add_header("User-Agent", "roijenapp-trafikkmeldinger/1 (support@roijenapp.no)")
    if sist_endret:
        req.add_header("If-Modified-Since", sist_endret)
    try:
        with urllib.request.urlopen(req, timeout=120) as svar:
            data = svar.read()
            if svar.headers.get("Content-Encoding") == "gzip":
                data = gzip.decompress(data)
            return data, svar.headers.get("Last-Modified")
    except urllib.error.HTTPError as feil:
        if feil.code == 304:
            return None, sist_endret
        raise HentFeil(f"HTTP {feil.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as feil:
        raise HentFeil(type(feil).__name__) from None


class ManglerInnlogging(Exception):
    pass


class HentFeil(Exception):
    pass


# ------------------------------------------------------------------ hovedprogram

def les_json(sti):
    try:
        with open(sti, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def skriv_ut(sti, data):
    os.makedirs(os.path.dirname(os.path.abspath(sti)), exist_ok=True)
    tekst_ = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    with open(sti, "w", encoding="utf-8") as f:
        f.write(tekst_)
    return len(tekst_.encode()), len(gzip.compress(tekst_.encode(), 6))


def github_output(endret):
    sti = os.environ.get("GITHUB_OUTPUT")
    if sti:
        with open(sti, "a") as f:
            f.write(f"endret={'true' if endret else 'false'}\n")


def behold_forrige(a, grunn):
    print(f"Beholder forrige fil ({grunn}).")
    if a.forrige and os.path.exists(a.forrige) and os.path.abspath(a.forrige) != os.path.abspath(a.ut):
        os.makedirs(os.path.dirname(os.path.abspath(a.ut)), exist_ok=True)
        shutil.copyfile(a.forrige, a.ut)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ut", required=True, help="JSON-fila som skal skrives")
    ap.add_argument("--forrige", help="forrige publiserte JSON (for If-Modified-Since og ved feil)")
    ap.add_argument("--fra-fil", help="les DATEX-XML fra fil i stedet for å hente")
    ap.add_argument("--github-output", action="store_true")
    a = ap.parse_args()

    forrige = les_json(a.forrige) if a.forrige else None
    sist_endret = (forrige or {}).get("datex_sist_endret")

    try:
        if a.fra_fil:
            with open(a.fra_fil, "rb") as f:
                xml_bytes, last_modified = f.read(), None
        else:
            xml_bytes, last_modified = hent(sist_endret)
    except ManglerInnlogging:
        print("DATEX_USER/DATEX_PASSWORD er ikke satt.")
        behold_forrige(a, "mangler innlogging")
        github_output(False)
        return 4
    except HentFeil as feil:
        print(f"Henting feilet: {feil}")
        behold_forrige(a, "hentefeil")
        github_output(False)
        return 2

    if xml_bytes is None:
        print("Ingenting nytt hos Vegvesenet (304).")
        behold_forrige(a, "uendret")
        github_output(False)
        return 3

    try:
        meldinger, publisert = plukk_ut(xml_bytes)
    except ET.ParseError as feil:
        print(f"Ugyldig XML: {feil}")
        behold_forrige(a, "ugyldig XML")
        github_output(False)
        return 2

    data = {
        "versjon": FORMAT_VERSJON,
        "hentet": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "publisert": publisert,
        "datex_sist_endret": last_modified,
        "kilde": KILDE,
        "lisens": LISENS,
        "antall": len(meldinger),
        "meldinger": meldinger,
    }
    if forrige and forrige.get("meldinger") == meldinger:
        print(f"Samme {len(meldinger)} meldinger som før.")
        behold_forrige(a, "samme innhold")
        github_output(False)
        return 3

    rå, komprimert = skriv_ut(a.ut, data)
    typer = {}
    for m in meldinger:
        typer[m["type"]] = typer.get(m["type"], 0) + 1
    print(f"{len(meldinger)} meldinger: " + ", ".join(f"{k} {v}" for k, v in sorted(typer.items())))
    print(f"Fil: {rå/1024:.0f} kB ({komprimert/1024:.0f} kB med gzip)")
    github_output(True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
