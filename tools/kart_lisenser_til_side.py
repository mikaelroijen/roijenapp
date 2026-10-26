#!/usr/bin/env python3
"""
Lager /rutelogger/kreditering/kart-uten-nett/ (fullstendige lisenstekster for nødkartet på iPhone)
og delen «Kart uten nett (iPhone)» på /rutelogger/kreditering/.

Lisensfilene ligger i rutelogger/kreditering/kart-uten-nett/ og er uendrede kopier fra:
  maplibre-LICENSE.md, maplibre-LICENSES.core.md  – maplibre/maplibre-native, tag ios-v6.31.0 (01791ad)
  protomaps-basemaps-LICENSE.md                    – protomaps/basemaps (LICENSE.md)
  tangrams-icons-LICENSE.md                        – tangrams/icons (LICENSE.md)
  noto-sans-OFL.txt                                – RuteKart/…/KartRessurser/fonts/OFL.txt i appen

    python3 tools/kart_lisenser_til_side.py
"""
import html, os, re

ROT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
MAPPE = os.path.join(ROT, "rutelogger", "kreditering", "kart-uten-nett")
SIDE = os.path.join(ROT, "rutelogger", "kreditering", "index.html")
START, SLUTT = "<!-- KART START -->", "<!-- KART SLUTT -->"
e = html.escape

FREETYPE = ("Portions of this software are copyright © 2024 The FreeType Project "
            "(www.freetype.org). All rights reserved.")

TEKSTER = [
    ("maplibre-LICENSE.md", "MapLibre Native iOS 6.31.0 – BSD-2-Clause",
     "https://github.com/maplibre/maplibre-native/blob/ios-v6.31.0/LICENSE.md"),
    ("maplibre-LICENSES.core.md", "Komponenter i MapLibre Native (LICENSES.core.md): Boost, HarfBuzz, FreeType, RapidJSON, earcut, kdbush, supercluster, protozero, nlohmann/json, metal-cpp m.fl.",
     "https://github.com/maplibre/maplibre-native/blob/ios-v6.31.0/LICENSES.core.md"),
    ("protomaps-basemaps-LICENSE.md", "Protomaps basemaps – kartstil (kode BSD-3-Clause, utseende CC0)",
     "https://github.com/protomaps/basemaps/blob/main/LICENSE.md"),
    ("tangrams-icons-LICENSE.md", "tangrams/icons – kartsymboler (MIT)",
     "https://github.com/tangrams/icons/blob/master/LICENSE.md"),
    ("noto-sans-OFL.txt", "Noto Sans – skrift (SIL Open Font License 1.1)",
     "https://github.com/notofonts/latin-greek-cyrillic"),
]


def side_med_tekster():
    deler = []
    for fil, tittel, adresse in TEKSTER:
        tekst = open(os.path.join(MAPPE, fil), encoding="utf-8").read().strip()
        deler.append(f"""    <section class="del" id="{e(fil.rsplit('.', 1)[0])}">
      <h2>{e(tittel)}</h2>
      <p><a href="{e(adresse)}">{e(adresse)}</a> · <a href="{e(fil)}">{e(fil)}</a></p>
      <pre class="lisens lang">{e(tekst)}</pre>
    </section>""")
    return f"""<!doctype html>
<html lang="nb">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Kart uten nett – lisenser</title>
  <meta name="description" content="Fullstendige lisenstekster for kartet uten nett i RuteLogger for iPhone (MapLibre, Protomaps, tangrams, Noto Sans).">
  <link rel="stylesheet" href="/style.css">
</head>
<body>
  <div class="kart" aria-hidden="true"></div>

  <main class="bred">
    <p class="sti"><a href="/">Røijen Applikasjoner</a> › <a href="/rutelogger/">RuteLogger</a> › <a href="/rutelogger/kreditering/#kart-uten-nett">Datakilder</a> › Kart uten nett – lisenser</p>

    <header>
      <h1>Kart uten nett – lisenser</h1>
      <p class="ingress">Fullstendige lisenstekster for programvaren, kartstilen, symbolene og skriften i kartet uten nett i RuteLogger for iPhone. Oversikten står på <a href="/rutelogger/kreditering/#kart-uten-nett">datakildesiden</a>.</p>
    </header>

    <section class="del">
      <h2>FreeType</h2>
      <p>{e(FREETYPE)}</p>
      <p class="liten">FreeType 2.13.3 (2024) er med i MapLibre Native iOS 6.31.0. Setningen kreves av FreeType-lisensen (FTL).</p>
    </section>

{chr(10).join(deler)}

    <footer>
      <p class="liten">© 2026 Mikael Røijen · <a href="mailto:support@roijenapp.no">support@roijenapp.no</a></p>
    </footer>
  </main>
</body>
</html>
"""


def del_paa_kreditering():
    return f"""{START}
    <section class="del" id="kart-uten-nett">
      <h2>Kart uten nett (iPhone)</h2>
      <p>Når nettet er borte, kan iPhone-appen vise et kart fra en fil på telefonen. Kartet tegnes av MapLibre og bygger på OpenStreetMap-data fra Protomaps. På kartet står «Kart: Protomaps · © OpenStreetMap», og «· ESA WorldCover» når laget «Terreng» er på.</p>
      <div class="tabell">
      <table>
        <thead><tr><th>Del</th><th>Lisens</th><th>Opphav</th></tr></thead>
        <tbody>
          <tr><td>Kartdata</td><td><a href="https://opendatacommons.org/licenses/odbl/1-0/">ODbL 1.0</a></td><td>© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap-bidragsytere</a>. Vann og kyst fra osmdata.openstreetmap.de (ODbL), lave zoomnivåer fra Natural Earth (offentlig eiendom).</td></tr>
          <tr><td>Kartfliser</td><td>–</td><td><a href="https://build.protomaps.com">Protomaps basemap</a>, daglig bygg 26. oktober 2026, utsnitt for Norden.</td></tr>
          <tr><td>Landdekke (laget «Terreng»)</td><td><a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a></td><td>© ESA WorldCover project / Contains modified Copernicus Sentinel data processed by ESA WorldCover consortium (via Daylight Landcover).</td></tr>
          <tr><td>Kartstil</td><td>Utseende <a href="https://creativecommons.org/publicdomain/zero/1.0/">CC0</a>, kode BSD-3-Clause</td><td><a href="https://github.com/protomaps/basemaps">protomaps/basemaps</a> 5.7.2 (© Protomaps LLC, Kelso Cartography), endret av RuteLogger.</td></tr>
          <tr><td>Skrift</td><td>SIL Open Font License 1.1</td><td>Noto Sans (© The Noto Project Authors), glyfer fra protomaps/basemaps-assets.</td></tr>
          <tr><td>Kartsymboler</td><td>MIT</td><td><a href="https://github.com/tangrams/icons">tangrams/icons</a> (© Mapzen, Linux Foundation).</td></tr>
          <tr><td>Kartmotor</td><td>BSD-2-Clause</td><td><a href="https://github.com/maplibre/maplibre-native">MapLibre Native iOS</a> 6.31.0 (© MapLibre contributors, MapTiler.com, Mapbox), med om lag 30 komponenter under egne lisenser.</td></tr>
          <tr><td>Filformat</td><td>Offentlig eiendom</td><td>PMTiles-spesifikasjonen.</td></tr>
        </tbody>
      </table>
      </div>
      <p>{e(FREETYPE)}</p>
      <p><a href="kart-uten-nett/">Fullstendige lisenstekster for kart uten nett</a> (MapLibre med alle komponenter, Protomaps-stilen, tangrams-symbolene og Noto Sans).</p>
    </section>
    {SLUTT}"""


def main():
    with open(os.path.join(MAPPE, "index.html"), "w", encoding="utf-8") as f:
        f.write(side_med_tekster())
    s = open(SIDE, encoding="utf-8").read()
    ny = del_paa_kreditering()
    if START in s:
        s = re.sub(re.escape(START) + r".*?" + re.escape(SLUTT), lambda m: ny, s, flags=re.S)
    else:
        anker = '    <section class="del" id="steder">'
        assert anker in s, "fant ikke stedet å sette inn"
        s = s.replace(anker, "    " + ny + "\n\n" + anker, 1)
    open(SIDE, "w", encoding="utf-8").write(s)
    print("Kart uten nett: side og del oppdatert")


if __name__ == "__main__":
    main()
