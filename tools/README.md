# tools/ – trafikkmeldinger fra Norge, Sverige og Finland

`datex_uttrekk.py` henter trafikkmeldinger (DATEX II v3.1, `GetSituation/pullsnapshotdata`), plukker ut
stengte veger og vegarbeid med ventetid, og skriver `data/trafikkmeldinger.json`. Jobben
`.github/workflows/nettside.yml` kjører det hvert 20. minutt og publiserer fila på
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

**Prøveperiode (fra 4. nov 2026):** `data/trafikkmeldinger.json` har bare Norge (`--land NO`). Alle tre land
står i https://roijenapp.no/data/trafikkmeldinger-norden-test.json. Utvalget for Sverige og Finland er
foreløpig og avgjøres av Chat A; deretter settes `--land NO,SE,FI` i jobben.

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
| `kategori` | `stengt` eller `vegarbeid` |
| `type` | Kildens egen verdi. SE: `MessageCodeValue`. FI: begrensningstypen (`traffic lights`, `single alternate line traffic` …) eller, for stengte veger i trafikkmeldinger, egenskapen (`Tie on suljettu liikenteeltä`). NO: DATEX-verdien: `roadClosed`, `intermittentShortTermClosures`, `closedPermanentlyForTheWinter`, `temporaryTrafficLights`, `trafficBeingManuallyDirected`, `blastingWork` |
| `tekst` | `generalPublicComment`, ferdig tekst til brukeren |
| `sted`, `veg`, `vegnavn` | stedstekst, vegnummer (f.eks. `F862`, `E10`), vegnavn |
| `start`, `slutt` | ISO-tid; mangler `slutt` = til videre |
| `gjentatt` | liste over gyldighetsperioder: `fra`, `til` (ISO), `tider` (`[{"fra":"07:00","til":"15:00"}]`, norsk lokaltid), `dager` (`monday` … `sunday`) |
| `retning` | NO: DATEX (alertCAffectedDirection). SE: `BothDirections`/`OneDirection` (sier ikke hvilken). FI: `BOTH`/`both`/`pos`/`neg` |
| `overskrift` | SE: Trafikverkets `Header` |
| `arbeidstid` | FI: arbeidstider fra vegarbeidsfasen (`tider`, `dager`), lokal tid. Ikke det samme som når begrensningen gjelder |
| `lengde_m` | berørt lengde |
| `punkt` | `[bredde, lengde]` |
| `linjer` | liste av linjer, hver `[[bredde, lengde], …]`, forenklet (største avvik 10 m). NO: omregnet fra EPSG:25833. SE: WKT i WGS84 (lengde bredde) snudd. FI: GeoJSON (lengde, bredde) snudd |
| `nvdb` | `"veglenkesekvens;fra;til;retning"` (NVDB;LINE;ROADWAY), sammenhengende biter slått sammen, 6 desimaler |

Meldinger med `slutt` i fortiden tas ikke med. SE: `Suspended` (satt på pause) og slettede situasjoner tas ikke med;
`ValidUntilFurtherNotice` gir ingen `slutt`. Alle `start`/`slutt` har UTC-forskyvning; svenske tider uten forskyvning
regnes som svensk lokaltid.
