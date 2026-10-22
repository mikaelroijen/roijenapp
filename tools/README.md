# tools/ – trafikkmeldinger fra Statens vegvesen

`datex_uttrekk.py` henter trafikkmeldinger (DATEX II v3.1, `GetSituation/pullsnapshotdata`), plukker ut
stengte veger og vegarbeid med ventetid, og skriver `data/trafikkmeldinger.json`. Jobben
`.github/workflows/nettside.yml` kjører det hvert 10. minutt og publiserer fila på
https://roijenapp.no/data/trafikkmeldinger.json. Mappen `tools/` publiseres ikke.

Brukernavn og passord ligger **bare** som GitHub-hemmelighetene `DATEX_USER` og `DATEX_PASSWORD`.
De skal aldri stå i kode, i en commit eller i en logg.

## Kjøre lokalt (test)

```sh
read -s DATEX_PASSWORD; export DATEX_PASSWORD; export DATEX_USER=<brukernavn>
python3 tools/datex_uttrekk.py --ut /tmp/trafikkmeldinger.json
# eller fra en lagret XML:
python3 tools/datex_uttrekk.py --fra-fil datex.xml --ut /tmp/trafikkmeldinger.json
```

## Format (versjon 1)

Toppnivå: `versjon`, `hentet` (UTC), `publisert` (Vegvesenets tidspunkt), `datex_sist_endret`
(Last-Modified, brukes til If-Modified-Since), `kilde`, `lisens`, `antall`, `meldinger`.

Per melding (felt uten verdi er utelatt):

| Felt | Innhold |
|---|---|
| `id`, `versjon` | situationRecord-id og versjon |
| `situasjon` | id for situasjonen meldingen hører til |
| `kategori` | `stengt` eller `vegarbeid` |
| `type` | DATEX-verdien: `roadClosed`, `intermittentShortTermClosures`, `closedPermanentlyForTheWinter`, `temporaryTrafficLights`, `trafficBeingManuallyDirected`, `blastingWork` |
| `tekst` | `generalPublicComment`, ferdig tekst til brukeren |
| `sted`, `veg`, `vegnavn` | stedstekst, vegnummer (f.eks. `F862`, `E10`), vegnavn |
| `start`, `slutt` | ISO-tid; mangler `slutt` = til videre |
| `gjentatt` | liste over gyldighetsperioder: `fra`, `til` (ISO), `tider` (`[{"fra":"07:00","til":"15:00"}]`, norsk lokaltid), `dager` (`monday` … `sunday`) |
| `retning` | `both`, `positive`, `negative` (alertCAffectedDirection) |
| `lengde_m` | berørt lengde |
| `punkt` | `[bredde, lengde]` |
| `linjer` | liste av linjer, hver `[[bredde, lengde], …]`, omregnet fra EPSG:25833 og forenklet (største avvik 10 m) |
| `nvdb` | `"veglenkesekvens;fra;til;retning"` (NVDB;LINE;ROADWAY), sammenhengende biter slått sammen, 6 desimaler |

Meldinger med `slutt` i fortiden tas ikke med.
