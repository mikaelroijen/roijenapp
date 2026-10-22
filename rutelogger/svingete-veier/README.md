# Svingete veier i Norge og Sverige – datasett fra RuteLogger

Dette er datasettet bak kartlaget «Svingete veier» i appen RuteLogger, med metoden som lager det.

© OpenStreetMap-bidragsytere. Datasettet er avledet fra OpenStreetMap og gjøres tilgjengelig under
**Open Database License (ODbL) 1.0**: https://opendatacommons.org/licenses/odbl/1-0/
(full tekst i `LICENSE.txt`). Opphavsrett og lisens for OpenStreetMap: https://www.openstreetmap.org/copyright

## Innhold

| Fil | Hva |
|---|---|
| `svingete_veier.json` | Hele datasettet, 5007 svingete veistrekninger (ca. 22 850 km). |
| `LICENSE.txt` | Lisensteksten (ODbL 1.0). |
| `metode/svingkart_land.py` | Finner de svingete strekningene i OpenStreetMap-filer (`.osm.pbf`). |
| `metode/svingkart_til_app.py` | Gjør resultatet om til det kompakte formatet appen bruker. |

## Kilde og versjon

- Kildedata: OpenStreetMap, landsfilene `norway-latest.osm.pbf` og `sweden-latest.osm.pbf` fra Geofabrik.
- Beregnet: 15. oktober 2026 (feltet `laget` i fila).
- Hører til RuteLogger 1.0. Bortsett fra feltene `kilde`, `lisens` og `info` er innholdet det samme som
  fila appen bruker (`RuteKjerne/Resources/svingete_veier.json`, kodeversjon `4227821`).

## Format

```json
{"kilde": "…", "lisens": "…", "info": "…", "v": 1, "laget": "2026-10-15",
 "s": [{"r": 1, "v": "4224", "n": "Lyseveien", "l": 31.12, "g": 15311, "k": 1, "p": [5905674, 666748, -48, 109, …]}]}
```

| Felt | Betydning |
|---|---|
| `r` | Rang, etter totale svingegrader (1 = flest). |
| `v` | Vegnummer (`ref`) eller navn fra OpenStreetMap. |
| `n` | Navn på vegen (kan være tomt). |
| `l` | Lengde i km. |
| `g` | Sum av retningsendringer i grader. |
| `k` | Klasse: 0 = svingete (under 300 °/km), 1 = veldig svingete (300–500), 2 = kronglete (500 eller mer). |
| `p` | Koordinater × 100 000 som heltall. Første par er bredde, lengde. Resten er differanser til forrige punkt. |

## Metode

1. Veityper `trunk`, `primary`, `secondary` og `tertiary` fra OpenStreetMap.
2. Biter med fartsgrense 40 km/t eller lavere tas ut, og det samme gjør grusbiter (`surface` = gravel, unpaved m.fl.).
3. Biter med samme `ref` eller navn settes sammen gjennom kryss, med høyst 60° knekk.
4. Geometrien legges om til et punkt hver 20. meter. Retningsendringer under 2° telles ikke.
5. Et svingete parti er der et sentrert vindu på 1 km har minst 150° per km. Hull på opptil 1500 m slås sammen,
   og partiet må være minst 2 km langt.
6. Partiene rangeres etter totale svingegrader. Til appen beholdes hvert femte punkt (om lag hver 100. meter).

Slik lages fila:

```sh
pip3 install osmium
python3 metode/svingkart_land.py norway-latest.osm.pbf sweden-latest.osm.pbf
python3 metode/svingkart_til_app.py svingkart_land.json
```

`svingkart_til_app.py` skriver til mappestrukturen i RuteLogger-prosjektet. Endre `dst` i skriptet hvis du kjører det et annet sted.

## Ansvar

Datasettet er beregnet automatisk og kan inneholde feil. Det sier ingenting om vegens tilstand eller om det er trygt
å kjøre der. Kjør alltid etter skilt og forholdene på vegen.

Kontakt: support@roijenapp.no
