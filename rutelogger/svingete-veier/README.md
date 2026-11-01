# Svingete veier i Norden – datasett fra RuteLogger

Dette er datasettet bak kartlaget «Svingete veier» i appen RuteLogger, med metoden som lager det.

© OpenStreetMap-bidragsytere. Datasettet er avledet fra OpenStreetMap og gjøres tilgjengelig under
**Open Database License (ODbL) 1.0**: https://opendatacommons.org/licenses/odbl/1-0/
(full tekst i `LICENSE.txt`). Opphavsrett og lisens for OpenStreetMap: https://www.openstreetmap.org/copyright

## Innhold

| Fil | Hva |
|---|---|
| `svingete_veier.json` | Hele datasettet, 6061 svingete veistrekninger (ca. 26 690 km) i Norge, Sverige, Finland, Danmark og Island. |
| `LICENSE.txt` | Lisensteksten (ODbL 1.0). |
| `metode/svingkart_land.py` | Finner de svingete strekningene i OpenStreetMap-filer (`.osm.pbf`). |
| `metode/svingkart_til_app.py` | Gjør resultatet om til det kompakte formatet appen bruker. |

## Kilde og versjon

| Land | Strekninger | km | Kildedata (OpenStreetMap fra Geofabrik) |
|---|---|---|---|
| Norge | 2891 | 13 640 | `norway-latest.osm.pbf`, beregnet 15. oktober 2026 |
| Sverige | 2116 | 9 210 | `sweden-latest.osm.pbf`, beregnet 15. oktober 2026 |
| Finland | 888 | 3 364 | `finland-latest.osm.pbf`, beregnet 1. november 2026 |
| Danmark | 143 | 392 | `denmark-latest.osm.pbf`, beregnet 1. november 2026 |
| Island | 23 | 81 | `iceland-latest.osm.pbf`, beregnet 1. november 2026 |

- Beregnet: 1. november 2026 (feltet `laget` i fila), med samme metode som før. Norge og Sverige er ikke lest på nytt
  fra nyere OpenStreetMap-data, så de strekningene er de samme som i utgaven fra 15. oktober.
- Island har få strekninger fordi nesten halvparten av landevegene der er grus, og grus tas ikke med.
- Færøyene og Grønland er ikke med.
- Rangene (`r`) er nummerert på nytt for hele Norden.
- Bortsett fra feltene `kilde`, `lisens` og `info` er innholdet det samme som fila appen bruker
  (`RuteKjerne/Resources/svingete_veier.json`, kodeversjon `cf81eb7`).
  SHA-256 for fila her: `43723d495e6f1b0780961bc8028527df081722a102362704cfc903801e3aa29e`.
- Forrige utgave (15. oktober 2026, 5007 strekninger i Norge og Sverige) ligger i historikken til lageret
  https://github.com/mikaelroijen/roijenapp.

## Format

```json
{"kilde": "…", "lisens": "…", "info": "…", "v": 1, "laget": "2026-11-01",
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
python3 metode/svingkart_land.py norway-latest.osm.pbf sweden-latest.osm.pbf finland-latest.osm.pbf \
    denmark-latest.osm.pbf iceland-latest.osm.pbf
python3 metode/svingkart_til_app.py svingkart_land.json
```

`svingkart_til_app.py` skriver til mappestrukturen i RuteLogger-prosjektet. Endre `dst` i skriptet hvis du kjører det et annet sted.

## Ansvar

Datasettet er beregnet automatisk og kan inneholde feil. Det sier ingenting om vegens tilstand eller om det er trygt
å kjøre der. Kjør alltid etter skilt og forholdene på vegen.

Kontakt: support@roijenapp.no
