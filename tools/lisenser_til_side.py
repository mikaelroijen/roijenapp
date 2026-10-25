#!/usr/bin/env python3
"""
Setter inn delen «Rutemotor (Valhalla) og OpenStreetMap» med de fullstendige
lisenstekstene på /rutelogger/kreditering/, laget fra rutelogger/kreditering/lisenser.json.

lisenser.json er en uendret kopi av RuteMotor/Sources/RuteMotor/Resources/lisenser.json
i RuteLogger-lageret, så appen og nettsiden viser de samme tekstene.

    python3 tools/lisenser_til_side.py
"""
import html, json, os, re

ROT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SIDE = os.path.join(ROT, "rutelogger", "kreditering", "index.html")
DATA = os.path.join(ROT, "rutelogger", "kreditering", "lisenser.json")
START, SLUTT = "<!-- RUTEMOTOR START -->", "<!-- RUTEMOTOR SLUTT -->"


def lag(d):
    e = html.escape
    rader = []
    for x in d["lisenser"]:
        rader.append(
            f'        <details>\n'
            f'          <summary><strong>{e(x["navn"])}</strong> {e(x["versjon"])} – {e(x["lisens"])}</summary>\n'
            f'          <p><a href="{e(x["adresse"])}">{e(x["adresse"])}</a></p>\n'
            f'          <pre class="lisens">{e(x["tekst"].strip())}</pre>\n'
            f'        </details>')
    return f"""{START}
    <section class="del" id="rutemotor">
      <h2>Rutemotor (Valhalla) og OpenStreetMap</h2>
      <p>RuteLogger kan regne ut ruter på enheten med Valhalla i stedet for Apple Kart (valg under Innstillinger → Rutemotor). Apple Kart er standard. Valhalla bruker en fil med rutedata som du selv legger inn, og regner uten nett.</p>
      <p>Vegdata © OpenStreetMap-bidragsytere, tilgjengelig under Open Database License (ODbL 1.0). Vegnettet for Norge, Sverige, Finland, Danmark og Island (OpenStreetMap via Geofabrik) er bearbeidet til Valhallas rutefliser av RuteLogger.</p>
      <p><a href="https://www.openstreetmap.org/copyright">OpenStreetMap – opphavsrett og lisens</a> · <a href="https://opendatacommons.org/licenses/odbl/1-0/">Lisens (ODbL 1.0)</a></p>
      <h3>Lisenser for programvaren i rutemotoren</h3>
      <p>Disse komponentene er bygget inn i appen. Trykk på en linje for å se hele lisensteksten. De samme tekstene står i appen under «Om RuteLogger» → «Lisenser for rutemotoren». <a href="lisenser.json">Alle tekstene som JSON</a> (laget {e(d["laget"])}).</p>
      <div class="lisenser">
{chr(10).join(rader)}
      </div>
    </section>
    {SLUTT}"""


def main():
    d = json.load(open(DATA, encoding="utf-8"))
    s = open(SIDE, encoding="utf-8").read()
    ny = lag(d)
    if START in s:
        s = re.sub(re.escape(START) + r".*?" + re.escape(SLUTT), lambda m: ny, s, flags=re.S)
    else:
        anker = '    <section class="del">\n      <h2>Vegdata – Statens vegvesen</h2>'
        assert anker in s, "fant ikke stedet å sette inn"
        s = s.replace(anker, "    " + ny + "\n\n" + anker, 1)
    open(SIDE, "w", encoding="utf-8").write(s)
    print(f"{len(d['lisenser'])} lisenser satt inn i {os.path.relpath(SIDE, ROT)}")


if __name__ == "__main__":
    main()
