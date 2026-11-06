# tools/ – trafikkmeldinger fra Norge, Sverige og Finland

`datex_uttrekk.py` henter trafikkmeldinger (DATEX II v3.1, `GetSituation/pullsnapshotdata`), plukker ut
stengte veger og vegarbeid med ventetid, og skriver `data/trafikkmeldinger.json`. Jobben
`.github/workflows/nettside.yml` kjører det hvert 10. minutt og publiserer fila på
https://roijenapp.no/data/trafikkmeldinger.json. Mappen `tools/` publiseres ikke.

Brukernavn og passord ligger **bare** som GitHub-hemmelighetene `DATEX_USER` og `DATEX_PASSWORD`,
og Trafikverkets nøkkel bare som `TRAFIKVERKET_NOKKEL`. De skal aldri stå i kode, i en commit eller i en logg.

| Land | Kilde | Modul | Lisens |
|---|---|---|---|
| NO | Statens vegvesen, DATEX II 3.1 `GetSituation` | `datex_uttrekk.py` | NLOD 2.0 |
| SE | Trafikverket, öppna API, objekttypen `Situation` 1.6 (`road.trafficinfo`) | `trafikverket_uttrekk.py` | CC0 1.0 |
| FI | Fintraffic / Digitraffic, `traffic-message/v2/roadworks` og `…/traffic-announcements` | `digitraffic_uttrekk.py` | CC BY 4.0 («Source: Fintraffic / digitraffic.fi, license CC 4.0 BY») |

Feiler ett land, brukes forrige meldinger fra det landet, og de andre landene publiseres som vanlig.
Jobben skriver antall meldinger per land og en oversikt over Trafikverkets og Digitraffics
meldingstyper og koder i loggen (aldri nøkkelen).

**Hovedfila** `data/trafikkmeldinger.json` har Norge, Sverige og Finland (`--land NO,SE,FI`, fra 4. nov 2026).
**Ulykker** (kategori `ulykke`) er med i hovedfila fra 6. nov 2026 (`--ulykker-i-hovedfil`).
Prøvefila https://roijenapp.no/data/trafikkmeldinger-norden-test.json lages fortsatt en stund.

Utvalg (Chat A 4. nov 2026: det som stopper eller forsinker deg, pluss ulykker):
- **NO:** `roadClosed`, `intermittentShortTermClosures`, `closedPermanentlyForTheWinter` → `stengt`;
  `temporaryTrafficLights`, `trafficBeingManuallyDirected`, `blastingWork` → `vegarbeid`; `Accident` (`accidentType`) → `ulykke`.
- **SE:** `roadClosed` → `stengt`; `blastingWork` → `vegarbeid`; `roadworks`/`resurfacingWork` → `vegarbeid` når `Message`/`Header`
  nevner trafikljus, signal, lots, flaggvakt, växelvis eller väntetid (`undertype` = første ord som traff); MessageType `Olycka` → `ulykke`.
- **FI:** vegarbeidsfaser med `road closed`/`intermittent short term closure` → `stengt`; `traffic lights`, `single alternate line traffic`,
  `intermittent short term stops`, `intermittent stops and closure effective`, `estimated delay`, `estimated delay during rush hour` → `vegarbeid`;
  trafikkmeldinger (`general`) med «Tie on suljettu liikenteeltä» → `stengt`; `accident report`/`preliminary accident report` → `ulykke`.
- Ikke med: motorstopp, dyr i vegen, felt stengt, fartsgrenser, vekt, tele, ferjer.

## Kjøre lokalt (test)

```sh
read -s DATEX_PASSWORD; export DATEX_PASSWORD; export DATEX_USER=<brukernavn>
python3 tools/datex_uttrekk.py --ut /tmp/trafikkmeldinger.json
# eller fra en lagret XML:
python3 tools/datex_uttrekk.py --fra-fil datex.xml --ut /tmp/trafikkmeldinger.json
```

## Format (versjon 1)

Toppnivå: `versjon`, `hentet` (UTC), `publisert` (Vegvesenets tidspunkt), `datex_sist_endret`
(Last-Modified, brukes til If-Modified-Since), `kilde`, `lisens` (Norge, som før), `kilder`
(per land: `land`, `kilde`, `lisens`, `antall`, `status`), `antall`, `meldinger`.

Per melding (felt uten verdi er utelatt):

| Felt | Innhold |
|---|---|
| `land` | `NO`, `SE`, `FI` |
| `tidssone` | IANA-sone for klokkeslettene i `gjentatt`/`arbeidstid`: `Europe/Oslo`, `Europe/Stockholm`, `Europe/Helsinki` |
| `id`, `versjon` | situationRecord-id og versjon (SE: Deviation.Id; FI: id for vegarbeidsfasen eller situationId) |
| `situasjon` | id for situasjonen meldingen hører til |
| `kategori` | `stengt`, `vegarbeid` eller `ulykke` |
| `type` | Kildens egen verdi. SE: `MessageCodeValue`. FI: begrensningstypen (`traffic lights`, `single alternate line traffic` …) eller, for stengte veger i trafikkmeldinger, egenskapen (`Tie on suljettu liikenteeltä`). NO: DATEX-verdien: `roadClosed`, `intermittentShortTermClosures`, `closedPermanentlyForTheWinter`, `temporaryTrafficLights`, `trafficBeingManuallyDirected`, `blastingWork` |
| `tekst` | `generalPublicComment`, ferdig tekst til brukeren |
| `sted`, `veg`, `vegnavn` | stedstekst, vegnummer (f.eks. `F862`, `E10`), vegnavn |
| `start`, `slutt` | ISO-tid; mangler `slutt` = til videre. Ulykke uten starttid: tidspunktet meldingen ble laget (NO `situationRecordCreationTime`, SE `CreationTime`, FI `releaseTime`) |
| `gjentatt` | liste over gyldighetsperioder: `fra`, `til` (ISO), `tider` (`[{"fra":"07:00","til":"15:00"}]`, norsk lokaltid), `dager` (`monday` … `sunday`) |
| `retning` | NO: DATEX (alertCAffectedDirection). SE: `BothDirections`/`OneDirection` (sier ikke hvilken). FI: `BOTH`/`both`/`pos`/`neg` |
| `overskrift` | SE: Trafikverkets `Header` |
| `undertype` | SE: ordet i teksten som gjorde vegarbeidet med (f.eks. `trafikljus`) |
| `arbeidstid` | FI: arbeidstider fra vegarbeidsfasen (`tider`, `dager`), lokal tid. Ikke det samme som når begrensningen gjelder |
| `lengde_m` | berørt lengde |
| `punkt` | `[bredde, lengde]` |
| `linjer` | liste av linjer, hver `[[bredde, lengde], …]`, forenklet (største avvik 10 m). NO: omregnet fra EPSG:25833. SE: WKT i WGS84 (lengde bredde) snudd. FI: GeoJSON (lengde, bredde) snudd |
| `nvdb` | `"veglenkesekvens;fra;til;retning"` (NVDB;LINE;ROADWAY), sammenhengende biter slått sammen, 6 desimaler |

Meldinger med `slutt` i fortiden tas ikke med. SE: `Suspended` (satt på pause) og slettede situasjoner tas ikke med;
`ValidUntilFurtherNotice` gir ingen `slutt`. Alle `start`/`slutt` har UTC-forskyvning; svenske tider uten forskyvning
regnes som svensk lokaltid.

## Kø-fila `data/trafikkflyt.json` (fra 5. nov 2026)

Lages i samme kjøring av `tools/trafikkflyt_uttrekk.py` (kalt fra `datex_uttrekk.py --flyt-ut`). Feiler den,
publiseres trafikkmeldingene likevel.

| Land | Kilde | Lisens |
|---|---|---|
| NO | Statens vegvesen, DATEX 3.1 `GetTravelTimeData` + `GetPredefinedTravelTimeLocations` (linjer i EPSG:32633, UTM 33N/WGS84) | NLOD 2.0 |
| SE | Trafikverket `TravelTimeRoute` 1.5 (sekunder, meter, km/t; nesten bare Stockholm) | CC0 1.0 |
| FI | Digitraffic TMS: `stations/data` (`KESKINOPEUS_5MIN_LIUKUVA_SUUNTA{1,2}_VVAPAAS{1,2}` = prosent av fri flyt), `stations`, `stations/sensor-constants` (`VVAPAAS1/2`, sommer/vinter) | CC BY 4.0 |

Toppnivå: `versjon` (1), `hentet`, `grense` (0,7), `kilder[]` (`land`, `kilde`, `lisens`, `antall`, `status` ok/feil), `antall`, `ko[]`.

Per post: `id` (`NO-<strekning>`, `SE-<Id>`, `FI-<stasjon>-<retning>`), `land`, `navn`, `veg` (SE når navnet har det),
`malt`, `status` (kildens verdi; FI har ingen), `forhold` (fart nå / normal; strekninger: normal tid / tid nå), `alvorlig`
(true når < 0,5), `fart`, `fart_normal` (km/t). NO/SE: `reisetid_s`, `normal_s`, `forsinkelse_s`, `lengde_m`, `linjer`.
FI: `punkt`, `retning` (`1`/`2`), `peiling` (fra `Tien_suunta`; retning 2 = +180°, ikke kontrollert).

Utvalg: `forhold` < 0,7. Ikke med: uten måling (`unknown`), måling eldre enn 15 min, FI-stasjoner som ikke har
`collectionStatus` GATHERING. Målefeil: `forhold` < 0,05 tas bort; NO-strekninger med forsinkelse over 1 time tas bort
hvis ingen trafikkmelding ligger innenfor 1 km. Regelen og det som tas bort, skrives i loggen.
