# RuteLogger – landpakker (rutedata og kart uten nett)

Utgave **2026-10-31**. OpenStreetMap-data per 2026-10-30T21:24:51Z.
Filene ligger som GitHub-utgaven `data-2026-10-31`:
https://github.com/mikaelroijen/roijenapp/releases/tag/data-2026-10-31

## Lisens
Inneholder informasjon fra OpenStreetMap (© OpenStreetMap-bidragsytere), som er gjort tilgjengelig
her under Open Database License (ODbL) 1.0: https://opendatacommons.org/licenses/odbl/1-0/
(full tekst i `LICENSE.txt`). Opphavsrett og lisens for OpenStreetMap: https://www.openstreetmap.org/copyright

Kartfilene er utsnitt av Protomaps' kartfliser (OpenStreetMap og Natural Earth).
Øvrige lisenser for kartet uten nett: https://roijenapp.no/rutelogger/kreditering/#kart-uten-nett

## Filer per land
| Land | Rutedata | Bytes | Kart | Bytes |
|---|---|---|---|---|
| NO | rutedata-NO.tar | 515 205 120 | kart-NO.pmtiles | 1 668 844 426 |
| SE | rutedata-SE.tar | 725 739 520 | kart-SE.pmtiles | 1 391 224 770 |
| FI | rutedata-FI.tar | 570 828 800 | kart-FI.pmtiles | 1 012 584 929 |
| DK | rutedata-DK.tar | 391 249 920 | kart-DK.pmtiles | 294 096 568 |
| IS | rutedata-IS.tar | 30 638 080 | kart-IS.pmtiles | 152 395 772 |

SHA-256 for hver fil står i katalogen appen leser (`katalog.json`).

## Metode
- **Rutedata:** Geofabrik-filene `<land>-latest.osm.pbf` for de fem landene → Valhalla 3.9.1
  (motorsykkel) → `rutedata.tar` for Norden. Norge er lagt inn som land i
  Valhallas admin-data (høyrekjøring og avkjøringsnummer). Per land: `valhalla_build_extract` med
  Geofabriks landgrense (GeoJSON).
- **Kart:** `pmtiles extract` fra Protomaps' daglige bygg (build.protomaps.com), maks zoom 14,
  først for Norden og så per land med de samme landgrensene. Flisene er ikke endret.
- Datasettet er laget automatisk og kan være feil eller gamle.
