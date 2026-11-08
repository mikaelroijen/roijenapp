# Turistveger i Danmark og Sverige – datasett fra RuteLogger

Dette er sporene for turistvegene i Danmark og Sverige i kartlaget «Turistveger» i RuteLogger.

© OpenStreetMap-bidragsytere. Datasettet er laget av OpenStreetMap og gjøres tilgjengelig under
**Open Database License (ODbL) 1.0**: https://opendatacommons.org/licenses/odbl/1-0/
(full tekst i `LICENSE.txt`). Opphavsrett og lisens for OpenStreetMap: https://www.openstreetmap.org/copyright

De norske turistvegene (Statens vegvesen, NVDB, NLOD 2.0) og de finske (Väylävirasto, CC BY 4.0) er ikke laget av
OpenStreetMap og er ikke med her. Se https://roijenapp.no/rutelogger/kreditering/#turistveger.

## Innhold

| Fil | Hva |
|---|---|
| `turistveger-danmark.geojson` | Margueritruten: 35 strekninger, ca. 4 093 km, som GeoJSON (WGS84). |
| `turistveger-sverige.geojson` | 29 svenske ruter (skiltede turistveger og kjente navngitte vegstrekninger): 47 strekninger, ca. 6 368 km, som GeoJSON (WGS84). |
| `danmark/dk-*.json`, `sverige/se-*.json` | De samme strekningene, nøyaktig som de ligger i appen. |
| `LICENSE.txt` | Lisensteksten (ODbL 1.0). |
| `metode/turistveg_osm.py` | Lager strekninger fra en rute-relasjon i OpenStreetMap (brukt for Danmark og deler av Sverige). |
| `metode/turistveg_sverige.py` | Lager de svenske strekningene (lista `STREKNINGER` sier hvordan hver er funnet). |

## Kilde og versjon

- Kildedata: OpenStreetMap, landsfilene for Danmark og Sverige fra Geofabrik (23. oktober 2026).
- Laget 7. november 2026. Filene i `danmark/` og `sverige/` er byte for byte de samme som i appen
  (`RuteKjerne/Resources/TuristvegerData/turistveger/`, kodeversjon `d3445a4` for Danmark og `ac0e406` for Sverige).
- **Danmark:** Margueritruten, superrelasjon 4441962 i OpenStreetMap. Alle strekningene er skiltet rute.
- **Sverige:** 6 av strekningene er skiltede turistveger («Skiltet turistväg»). De andre er kjente navngitte
  vegstrekninger («Navngitt vegstrekning»). Noen strekninger er regnet ut som korteste veg gjennom oppgitte steder på
  vegnettet i OpenStreetMap, fordi ruten ikke finnes som én linje der. Det er også et utdrag av OpenStreetMap.
- `gravelShare` er andelen av strekningen som går på grusveg ifølge OpenStreetMap (`surface=gravel`, `unpaved` o.l.).

## Format

GeoJSON: én `Feature` per strekning med `LineString` og egenskapene `id`, `name`, `fromTo`, `lengthKm`, `official`,
`note` og `gravelShare` (de to siste bare for Sverige).

Appens format (`dk-*.json`, `se-*.json`): `id`, `name`, `fromTo`, `lengthKm`, `trackPoints` (`[bredde, lengde]`, 5 desimaler,
minst ca. 30 m mellom punktene), `viaPoints` og for Sverige `country`, `source`, `official`, `note`, `gravelShare`.

## Metode

Danmark (`turistveg_osm.py`): vegbitene i alle underrelasjonene samles, hull under 150 m kobles, korte blindgreiner,
små sløyfer og doble spor ryddes bort, og nettet deles i kryss og ved ferjer. Strekninger under 20 km tas ikke med, og
strekninger over 250 km deles. Kommando og detaljer står øverst i skriptet.

Sverige (`turistveg_sverige.py`): rute-relasjon i OpenStreetMap der den finnes og henger sammen, ellers vegnummer,
vegnavn eller korteste veg gjennom oppgitte steder. Begge skriptene krever pyosmium.

## Ansvar

Datasettet er laget automatisk fra OpenStreetMap og kan avvike fra skiltingen på stedet. Sjekk alltid skilt og
vegforhold.

Kontakt: support@roijenapp.no
