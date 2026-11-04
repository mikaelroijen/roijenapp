"""Felles hjelpere for trafikkmeldinger fra flere land (bare standardbiblioteket)."""
import math
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

DESIMALER = 5              # ca. 1 m
LINJE_TOLERANSE_M = 10.0   # Douglas–Peucker: største avvik fra opprinnelig linje


def forenkle_xy(pts, tol=LINJE_TOLERANSE_M):
    """Douglas–Peucker på (x, y) i meter. Returnerer indeksene som beholdes."""
    if len(pts) <= 2:
        return list(range(len(pts)))
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
            d = math.hypot(x - x1, y - y1) if lengde == 0 else abs(dy * x - dx * y + x2 * y1 - y2 * x1) / lengde
            if d > maks:
                maks, k = d, m
        if maks > tol:
            behold[k] = True
            stakk += [(i, k), (k, j)]
    return [i for i, b in enumerate(behold) if b]


def linje_latlon(lonlat):
    """[(lengde, bredde), …] → forenklet [[bredde, lengde], …] (største avvik 10 m)."""
    if len(lonlat) < 2:
        return None
    lat0 = math.radians(sum(p[1] for p in lonlat) / len(lonlat))
    xy = [(lo * math.cos(lat0) * 111320.0, la * 110540.0) for lo, la in lonlat]
    linje = [[round(lonlat[i][1], DESIMALER), round(lonlat[i][0], DESIMALER)] for i in forenkle_xy(xy)]
    return linje if len(linje) >= 2 else None


_WKT = re.compile(r"^\s*(POINT|LINESTRING|MULTILINESTRING)\s*(?:ZM|Z|M)?\s*\((.*)\)\s*$", re.S | re.I)


def wkt(tekst_):
    """WKT i WGS84 (lengde bredde [z]) → ("punkt", (lo, la)) eller ("linjer", [[(lo, la), …], …])."""
    if not tekst_:
        return None
    m = _WKT.match(tekst_)
    if not m:
        return None
    art, kropp = m.group(1).upper(), m.group(2)

    def par(s):
        ut = []
        for p in s.split(","):
            tall = p.strip().split()
            if len(tall) >= 2:
                try:
                    ut.append((float(tall[0]), float(tall[1])))
                except ValueError:
                    return None
        return ut

    if art == "POINT":
        p = par(kropp)
        return ("punkt", p[0]) if p else None
    if art == "LINESTRING":
        p = par(kropp)
        return ("linjer", [p]) if p and len(p) >= 2 else None
    deler = [par(d) for d in re.findall(r"\(([^()]*)\)", kropp)]
    deler = [d for d in deler if d and len(d) >= 2]
    return ("linjer", deler) if deler else None


def iso_lokal(t, sone):
    """ISO-tid → ISO med UTC-forskyvning i landets tid. Tid uten forskyvning regnes som
    lokal tid i `sone`. Returnerer None hvis tiden ikke kan leses."""
    if not t:
        return None
    try:
        d = datetime.fromisoformat(t.replace("Z", "+00:00"))
    except ValueError:
        return None
    z = ZoneInfo(sone)
    d = d.replace(tzinfo=z) if d.tzinfo is None else d.astimezone(z)
    return d.replace(microsecond=0).isoformat()


def utløpt(slutt, naa=None):
    if not slutt:
        return False
    try:
        d = datetime.fromisoformat(slutt.replace("Z", "+00:00"))
    except ValueError:
        return False
    return d < (naa or datetime.now(timezone.utc))


def uten_tomme(m):
    return {k: v for k, v in m.items() if v not in (None, "", [], {})}
