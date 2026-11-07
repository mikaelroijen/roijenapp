# Steder langs ruten i Norden – datasett fra RuteLogger

Dette er datasettet bak «Søk langs ruten» og «nærmeste bensinstasjon/ladestasjon/rasteplass» i RuteLogger:
bensin, lading, mat, overnatting, rasteplasser, campingplasser, bobilplasser og utsiktspunkter i Norge,
Sverige, Finland, Danmark og Island.

© OpenStreetMap-bidragsytere. Datasettet er et utdrag av OpenStreetMap og gjøres tilgjengelig under
**Open Database License (ODbL) 1.0**: https://opendatacommons.org/licenses/odbl/1-0/
(full tekst i `LICENSE.txt`). Opphavsrett og lisens for OpenStreetMap: https://www.openstreetmap.org/copyright

## Innhold

| Fil | Hva |
|---|---|
| `steder.json` | Hele datasettet, 99 688 steder (4,0 MB, ca. 1,4 MB komprimert). |
| `LICENSE.txt` | Lisensteksten (ODbL 1.0). |
| `metode/steder_til_app.py` | Lager fila fra OpenStreetMap-filene (`.osm.pbf`) med pyosmium. |

## Kilde og versjon

- Kildedata: OpenStreetMap, landsfilene for Norge, Sverige, Finland, Danmark og Island fra Geofabrik (23. oktober 2026).
- Versjon 2, laget 7. november 2026 (feltet `laget` i fila). Versjon 1 (25. oktober 2026, 93 505 steder) ligger i
  historikken til lageret https://github.com/mikaelroijen/roijenapp.
- Nytt i versjon 2: camping er skilt ut fra overnatting, og bobilplasser og utsiktspunkter er lagt til, med avstand
  til nærmeste veg en motorsykkel kan kjøre på.
- Fila er byte for byte den samme som ligger i appen (`RuteKjerne/Resources/steder.json`, kodeversjon COMMIT_ID,
  SHA-256 `524b161291b937a0019de0b4b211cbd8dc1d374ee3ecf1a7b327e2daa3b5dd9d`).

| Land | Bensin | Lading | Mat | Overnatting | Rasteplass | Camping | Bobil | Utsikt | Sum |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Norge | 2 321 | 2 842 | 7 832 | 1 730 | 1 792 | 1 323 | 373 | 1 684 | 19 897 |
| Sverige | 3 405 | 3 762 | 19 733 | 2 994 | 710 | 1 190 | 625 | 1 450 | 33 869 |
| Finland | 2 229 | 1 338 | 11 198 | 1 442 | 1 182 | 452 | 230 | 895 | 18 966 |
| Danmark | 2 141 | 3 274 | 12 606 | 1 488 | 1 382 | 1 526 | 325 | 840 | 23 582 |
| Island | 264 | 378 | 1 091 | 815 | 135 | 233 | 11 | 447 | 3 374 |
| **Sum** | **10 360** | **11 594** | **52 460** | **8 469** | **5 201** | **4 724** | **1 564** | **5 316** | **99 688** |

## Format

```json
{"v": 2, "laget": "2026-11-07", "kilde": "…", "lisens": "…", "info": "…",
 "typer": ["fuel", "charging", "food", "lodging", "restArea", "camping", "caravan", "viewpoint"],
 "land": ["NO", "SE", "FI", "DK", "IS"],
 "felt": ["type", "navn", "lat", "lon", "land", "veg_m", "ekstra"],
 "maks_veg_m": {"camping": 500, "caravan": 500, "viewpoint": 200},
 "s": [[5, "Gedser Naturskole Primi-Camp", 54.57065, 11.93943, 3, 2, 3], …]}
```

Hvert sted er en liste: `type` (indeks i `typer`), `navn` (`name`, ellers `brand`, kan være tomt),
`lat`, `lon` (5 desimaler; for områder snittet av punktene) og `land` (indeks i `land`). Camping, bobil og utsikt har
i tillegg `veg_m` (meter til nærmeste veg en motorsykkel kan kjøre på) og `ekstra` (biter: 1 hytter, 2 telt,
4 bobil/campingvogn). Sortert etter posisjon. Nye typer legges bare til bakerst i `typer`.

## Metode

| Type | OpenStreetMap-merker |
|---|---|
| Bensin (`fuel`) | `amenity=fuel` – ikke båtanlegg (`waterway=fuel`) eller `motorcar=no` |
| Lading (`charging`) | `amenity=charging_station` |
| Mat (`food`) | `amenity=restaurant`, `cafe`, `fast_food` |
| Overnatting (`lodging`) | `tourism=hotel`, `motel`, `guest_house`, `hostel` |
| Rasteplass (`restArea`) | `highway=rest_area`, `services` |
| Camping (`camping`) | `tourism=camp_site` |
| Bobilplass (`caravan`) | `tourism=caravan_site` |
| Utsiktspunkt (`viewpoint`) | `tourism=viewpoint` |

Steder med `access=private` eller `access=no` tas ikke med.

**Avstand til veg (camping, bobil, utsikt):** som veg en motorsykkel kan kjøre på regnes alle bilveger, også små
grendeveger og serviceveger (`highway=motorway` … `tertiary`, `unclassified`, `residential`, `living_street`,
`service`, `road`), men ikke der motorsykkel eller motorkjøretøy er forbudt eller vegen er privat. Skogsbilveger
(`highway=track`) regnes bare med når motorkjøretøy er tillatt. Camping og bobilplasser må ligge innenfor 500 m fra
midten av plassen, utsiktspunkter innenfor 200 m. Det som faller bort, er særlig teltplasser på øyer, bålplasser og
koier i skogen. Både punkter og områder (ways) tas med. Et sted som ligger i
to landsfiler, telles bare én gang.

```sh
pip3 install osmium
python3 -I metode/steder_til_app.py steder.json NO=norway-latest.osm.pbf SE=sweden-latest.osm.pbf \
    FI=finland-latest.osm.pbf DK=denmark-latest.osm.pbf IS=iceland-latest.osm.pbf
```

## Ansvar

Datasettet er hentet automatisk fra OpenStreetMap og kan være ufullstendig eller utdatert. Særlig ladestasjoner kan mangle.

Kontakt: support@roijenapp.no
