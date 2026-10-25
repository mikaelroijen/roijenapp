# Steder langs ruten i Norden – datasett fra RuteLogger

Dette er datasettet bak «Søk langs ruten» og «nærmeste bensinstasjon/ladestasjon/rasteplass» i RuteLogger:
bensin, lading, mat, overnatting og rasteplasser i Norge, Sverige, Finland, Danmark og Island.

© OpenStreetMap-bidragsytere. Datasettet er et utdrag av OpenStreetMap og gjøres tilgjengelig under
**Open Database License (ODbL) 1.0**: https://opendatacommons.org/licenses/odbl/1-0/
(full tekst i `LICENSE.txt`). Opphavsrett og lisens for OpenStreetMap: https://www.openstreetmap.org/copyright

## Innhold

| Fil | Hva |
|---|---|
| `steder.json` | Hele datasettet, 93 505 steder (3,7 MB, ca. 1,3 MB komprimert). |
| `LICENSE.txt` | Lisensteksten (ODbL 1.0). |
| `metode/steder_til_app.py` | Lager fila fra OpenStreetMap-filene (`.osm.pbf`) med pyosmium. |

## Kilde og versjon

- Kildedata: OpenStreetMap, landsfilene for Norge, Sverige, Finland, Danmark og Island fra Geofabrik.
- Laget: 25. oktober 2026 (feltet `laget` i fila).
- Fila er byte for byte den samme som ligger i appen (`RuteKjerne/Resources/steder.json`,
  SHA-256 `0e8d169c3994436a11c22a8cbcd48fc30aaf216751ab85aa147e3a40ae50a938`).

| Land | Bensin | Lading | Mat | Overnatting | Rasteplass | Sum |
|---|---:|---:|---:|---:|---:|---:|
| Norge | 2 321 | 2 842 | 7 832 | 3 161 | 1 794 | 17 950 |
| Sverige | 3 405 | 3 762 | 19 733 | 4 399 | 711 | 32 010 |
| Finland | 2 229 | 1 338 | 11 198 | 2 126 | 1 182 | 18 073 |
| Danmark | 2 141 | 3 274 | 12 606 | 3 113 | 1 382 | 22 516 |
| Island | 264 | 378 | 1 091 | 1 086 | 137 | 2 956 |
| **Sum** | **10 360** | **11 594** | **52 460** | **13 885** | **5 206** | **93 505** |

## Format

```json
{"v": 1, "laget": "2026-10-25", "kilde": "…", "lisens": "…", "info": "…",
 "typer": ["fuel", "charging", "food", "lodging", "restArea"],
 "land": ["NO", "SE", "FI", "DK", "IS"],
 "felt": ["type", "navn", "lat", "lon", "land"],
 "s": [[3, "Gedser Naturskole Primi-Camp", 54.57065, 11.93943, 3], …]}
```

Hvert sted er en liste: `type` (indeks i `typer`), `navn` (`name`, ellers `brand`, kan være tomt),
`lat`, `lon` (5 desimaler; for områder snittet av punktene) og `land` (indeks i `land`). Sortert etter posisjon.

## Metode

| Type | OpenStreetMap-merker |
|---|---|
| Bensin (`fuel`) | `amenity=fuel` – ikke båtanlegg (`waterway=fuel`) eller `motorcar=no` |
| Lading (`charging`) | `amenity=charging_station` |
| Mat (`food`) | `amenity=restaurant`, `cafe`, `fast_food` |
| Overnatting (`lodging`) | `tourism=hotel`, `motel`, `guest_house`, `hostel`, `camp_site` |
| Rasteplass (`restArea`) | `highway=rest_area`, `services` |

Steder med `access=private` eller `access=no` tas ikke med. Både punkter og områder (ways) tas med. Et sted som ligger i
to landsfiler, telles bare én gang.

```sh
pip3 install osmium
python3 -I metode/steder_til_app.py steder.json NO=norway-latest.osm.pbf SE=sweden-latest.osm.pbf \
    FI=finland-latest.osm.pbf DK=denmark-latest.osm.pbf IS=iceland-latest.osm.pbf
```

## Ansvar

Datasettet er hentet automatisk fra OpenStreetMap og kan være ufullstendig eller utdatert. Særlig ladestasjoner kan mangle.

Kontakt: support@roijenapp.no
