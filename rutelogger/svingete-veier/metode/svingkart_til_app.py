#!/usr/bin/env python3
"""
Lager appens kompakte svingkart (RuteKjerne/Sources/RuteKjerne/Resources/svingete_veier.json;
før 18. okt 2026: RuteLogger/SvingeteVeierData/)
fra svingkart_land.json, som svingkart_land.py lager fra Geofabrik-filene.

    python3 Tools/svingkart_til_app.py ~/Downloads/svingkart_land.json

Format (lest av SvingeteVeier.swift):
  {"v":1, "laget":"…", "s":[{"r":rang, "v":vei, "n":navn, "l":km, "g":grader,
                             "k":klasse 0/1/2, "p":[lat0, lon0, dlat, dlon, …]}]}
  - klasse: 0 = svingete (< 300 °/km, også «litt svingete» som har fått
    lavere snitt etter sammenslåing), 1 = veldig svingete (300–500),
    2 = kronglete (≥ 500)
  - p: koordinater × 100 000 som heltall; første punkt absolutt, resten som
    differanse til forrige punkt (gjør fila omtrent halvparten så stor).
"""
import json, os, sys

src = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/Downloads/svingkart_land.json")
here = os.path.dirname(os.path.abspath(__file__))
dst = os.path.join(here, "..", "RuteKjerne", "Sources", "RuteKjerne", "Resources", "svingete_veier.json")

d = json.load(open(src, encoding="utf-8"))
ut = []
for p in d["partier"]:
    gpk = p["grader_per_km"]
    k = 2 if gpk >= 500 else (1 if gpk >= 300 else 0)
    flat, plat, plon = [], None, None
    for lat, lon in p["punkter"]:
        a, b = round(lat * 1e5), round(lon * 1e5)
        if plat is None:
            flat += [a, b]
        else:
            flat += [a - plat, b - plon]
        plat, plon = a, b
    ut.append({"r": p["rang"], "v": p["vei"], "n": p["navn"], "l": p["lengde_km"],
               "g": p["grader"], "k": k, "p": flat})
os.makedirs(os.path.dirname(dst), exist_ok=True)
with open(dst, "w", encoding="utf-8") as f:
    json.dump({"v": 1, "laget": d.get("laget", ""), "s": ut}, f, ensure_ascii=False, separators=(",", ":"))
print(f"{len(ut)} strekninger -> {os.path.normpath(dst)} ({os.path.getsize(dst)/1e6:.1f} MB)")
