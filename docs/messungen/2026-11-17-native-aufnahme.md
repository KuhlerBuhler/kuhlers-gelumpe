# Natives Aufnehmen und Abspielen: Master-Abgriff, Kartenrate, RAM

Stand 18. November 2026, Erststand vom 17. November. Grundlage für das Hauptfeature von 1.6: den laufenden Mix ohne PC und Interface auf die Karte
aufnehmen und eine WAV von der Karte abspielen. Gelesen im DSP-Programm (Hacktribe 2.02, rot und blau 2.02, ausgepackt mit
[`dsp_extract.py`](../../tools/dsp/dsp_extract.py), Blackfin-binutils 2.42) und im ARM-Code (capstone). Ergänzt um Simulatorprüfungen und die späteren READ-Messungen aus Abschnitt 10. Marker: **gelesen** (Code gelesen),
**gemessen** (am Gerät oder aus einer verlinkten Messung),
**hergeleitet**, **offen**.

Rot und Hacktribe haben dasselbe DSP-Programm ([DSP-Modell](2026-11-12-dsp-modell.md)), alles zu Hacktribe gilt dort.

## Kurz

| Frage | Antwort | Marker |
|---|---|---|
| Wo liegt der Mix vor THRU und Metronom? | DSP-Wort `0xFF802888`: links (obere 16 Bit) und rechts (untere 16 Bit), nach dem Master-Effekt und einem Soft-Clipper, jedes Sample neu. Daneben `0xFF80288C`, die Mono-Summe | gelesen |
| Wie nimmt Korg ihn auf? | RESAMPLING ist Postfach-Kommando `0x3B` mit Quelle 1: der DSP kopiert dieses Wort jedes Sample per DMA linear in den Sample-Speicher | gelesen |
| Geht es mit `korg.audio.capture`? | Ja, mit einem Wort: die Erfassung (`0x37`) liest ihre Quelle über einen Zeiger in `0xFF9031DC`. Zeigt er auf `0xFF802888`, läuft der Master in den Ring. Der Ring fasst aber nur 4800 Frames, 100 ms | gelesen, hergeleitet |
| Reicht die Karte? | Lesen 3,1 MiB/s (12,5 MHz) und 5,1 MiB/s (25 MHz) am Gerät. Aufnahme braucht 0,19 MB/s. Schreiben ist auf rund 3 MB/s geschätzt (Erfahrungswert des Besitzers); Schreibrate und Schreibpausen am Gerät sind nicht gemessen | gemessen (lesen), geschätzt (schreiben) |
| WAV ohne `f_truncate`? | Ja: nur anhängen, am Ende mit `f_lseek` auf den Kopf und die zwei Längen überschreiben | hergeleitet |
| RAM | Ring auf dem ARM 2 MiB (rund 10 s), Sample Swap belegt `0xC274F000..0xC4000000` | hergeleitet |
| Abspielen | Ohne DSP-Patch nur über einen Sample-Platz und eine Stimme; sauber über einen kleinen DSP-Patch, der einen Ring in den Mix liest | hergeleitet |
| Blau | Erfassung `0x37` da, aber kein gepacktes Stereo-Wort und kein `0x3B`: ohne DSP-Patch nur mono | gelesen |

## 1. Master-Abgriff

### Die Ausgangsstufe

**Gelesen** (Hacktribe): die Audioschleife arbeitet mit `P5 = 0xFF9030A4` und `P4 = [0xFF9030B0]`. Die Initialisierung
schreibt dort `0xFF802870` hinein (`0x01F0C626`, `[P0 + 0xC] = R2` mit `P0 = 0xFF9030A4`). Die Master-Stufe ab `0xFFA0162C`:

| Stelle | Was |
|---|---|
| `0xFFA016AC` | Aufruf des Master-Effekts, vorher wartet sie auf MDMA (`0xFFC00F28` Bit 3) |
| `0xFFA016B6..0xFFA0171C` | Effektausgang mal Pegel plus trockener Anteil |
| `0xFFA01720..0xFFA01734` | dazu `[P4 + 0x6C]`, `[P4 + 0x70]` (Sammelbus, der MFX umgeht, hergeleitet), mal 2 mit Sättigung |
| `0xFFA0174A` | `0xFFA0135C`, ein Soft-Clipper (kubisch über einer Schwelle `0x361962E9`), in place auf `[P4 + 0x10]`, `[P4 + 0x14]` |
| `0xFFA01750..0xFFA01784` | ein Verstärkungsfaktor aus `[P5 + 0x144..0x150]`, einpolig geglättet (hergeleitet: Pegelrampe) |
| `0xFFA0179A` | **`[P4 + 0x18]` = L obere 16 Bit, R untere 16 Bit**, also `0xFF802888` |
| `0xFFA017A8` | **`[P4 + 0x1C]` = L/2 + R/2**, also `0xFF80288C` |
| `0xFFA017AA..0xFFA017EC` | Erfassung (`0x37`, siehe unten) |
| `0xFFA017EE..0xFFA0183C` | Aufnahme (`0x3B`, siehe unten) |
| `0xFFA0189A..0xFFA0193A` | AUDIO IN THRU, danach Metronom mit eigener Hüllkurve und Ausgangsverstärkung (siehe Simulatorprüfung) |
| `0xFFA01946..0xFFA01966` | Spitzenpegel `[P5 + 0x50]`, `[P5 + 0x54]` = `0xFF9030F4` ([Pegel-LEDs](2026-11-12-pegel-leds.md)) |
| `0xFFA019C6` | Ausgang nach `[P4 + 0x10]`, `[P4 + 0x14]` |

**Hergeleitet:** das aufgenommene Wort enthält den Mix nach dem Master-Effekt und dem Soft-Clipper, aber nicht die Stufe ab
`0xFFA0189A`. Dort kommen AUDIO IN THRU und danach das Metronom dazu (gelesen und im Simulator geprüft, siehe Abschnitt 6).

### Korgs RESAMPLING: Kommando `0x3B`

**Gelesen** (Handler `0xFFA056F0`, Sprungtabelle `0x01F02B84`, Eintrag `0x3B`; `P0 = 0xFF9031D8`, `P5 = 0xFF802878` beim
Eintritt, `0xFFA04F3C`):

| Wort | Bedeutung |
|---|---|
| +4 | 0 = Aufnahme beenden, sonst starten |
| +6 | 0 = mono (Schritt 2 Byte), sonst stereo (Schritt 4 Byte) |
| +8 | Quelle: 0 = `0xFF80287C`/`0xFF802878` (Eingang, hergeleitet AUDIO IN), sonst `0xFF80288C`/`0xFF802888` (Master) |
| +10, +12 | Startadresse im DSP-Speicher (hoch, tief) |

Beim Start setzt er `[0xFF9031F8] = 1` (aktiv), `[0xFF9031FC]` = Schritt, `[0xFF903200]` = Quelle, `[0xFF903204]` = Ziel,
`[0xFF90320C] = 1`. Die Audioschleife (`0xFFA017EE`) schreibt jedes Sample das Quellwort (Hälften getauscht) nach
`0xFF80004C`, trägt Quelle und Ziel in einen DMA-Auftrag ein und rückt das Ziel um den Schritt vor. Erreicht es
`[0xFF903208]` (Ende), setzt sie `[0xFF90320C] = 2` und hört auf. Das Ende schreibt die CPU direkt (hergeleitet: der
Handler setzt es nicht). Das passt zur Gerätemessung `docs/messungen/2026-11-06-sample-ram-aufnahme.md` im Zweig `feature/sample-swap-native-dsp`:
dort wächst der DSP-Frei-Zeiger bei Resampling, Quelle 1, stereo, um 479 984 Byte (**gemessen** dort).

Für eine lange Aufnahme taugt `0x3B` so nicht: der Weg schreibt linear bis zu einem Ende im Sample-Speicher.

### Die Erfassung: Kommando `0x37`

**Gelesen** (Handler `0xFFA05620`): Wort +4 ungleich 0 startet, setzt `[0xFF9031D8]` auf den Ring `0x01C722A0` und
`[0xFF9031D0] = 1`. Wort +6 wählt die Quelle über die Tabelle `0x01F02C74` (Prüfung `< 0x19`):

| Art | Quelle `[0xFF9031DC]` |
|---|---|
| 0 | `0xFF802878`, also `P4 + 8` (hergeleitet: Eingang) |
| 1 bis 16 | Ausgang eines Parts, `0xFF90186C + ((Art - 1) * 0x46 + 0x44) * 4` |
| 17 bis 24 | Ausgang eines Part-Paars |

Einen Eintrag für den Master gibt es nicht. Die Audioschleife (`0xFFA017AA`) liest aber nur den Zeiger:
`R7 = [[0xFF9031DC]]`, Ziel `[0xFF9031D8]` im Kreis mit `B0 = 0x01C722A0` und `L0 = [0xFF9031D4]`, dann derselbe
DMA-Auftrag über `0xFF80004C`. Die Ringgröße steht beim Start auf `0x4B00` (19 200 Byte, 4800 Frames). Der ARM startet die
Erfassung über `0xC0014368` (Postfach `0x37`, `(1, Art)`) und beendet sie über `0xC00143E4` (`(0, 0)`), beides gelesen.

**Hergeleitet:** startet die CPU die Erfassung mit einer gültigen Art und schreibt danach `0xFF802888` nach `0xFF9031DC`
(Host-Port-Schreiben `0xAB`, wie beim Postfach), dann landet der Master im Ring. Pro Frame ein 32-Bit-Wort, im Speicher
erst R, dann L (die Hälften werden in diesem Weg nicht getauscht). Das ist ein Wort Schreiben, kein DSP-Patch. Quellzugriff und Deskriptoren im
Simulator geprüft (Abschnitt 6), nicht am Gerät.

**Gelesen:** Erfassung und Aufnahme teilen sich das Zwischenwort `0xFF80004C` und den DMA-Auftrag. Beide gleichzeitig
gehen nicht; der Spettro-Dienst prüft das schon ([API 31](2026-11-12-plugin-api31-spektrum.md), Status 2). Aufnahme,
Spettro-Plugins und Korgs SAMPLING schließen sich also gegenseitig aus.

### Die Grenze: 100 ms Ring im DSP

**Gelesen:** der Ring ist fest: `0x01C722A0` steht als Konstante in `0xFFA017BA` und im Handler `0xFFA05634`, direkt hinter
`0x01C76DA0` liegen Daten des DSP-Programms (eigener Ladebereich im Bootstrom). Bei 48 kHz sind 4800 Frames 100 ms.
Der ARM muss also spätestens alle rund 90 ms lesen (Spettro hält 256 Frames Abstand zum Schreiber).

**Hergeleitet:** das ist knapp. Die CommandTask, in der der Spettro-Dienst läuft, lädt auch Patterns und schreibt den
Flash beim WRITE unter der Sperre `0xC0000D80(2)`; die Löschzeit eines Sektors am Gerät ist **offen**
([Einstellungen im Flash](2026-11-13-einstellungen-flash.md)). Für eine Aufnahme ohne Lücke braucht es entweder einen
Leser in einer eigenen, höher priorisierten Task, deren Laufabstand am Gerät gemessen ist, oder einen größeren Ring im DSP:

| Weg | Was | Kosten |
|---|---|---|
| A | `0x37` plus Quellzeiger auf `0xFF802888`, Ring 100 ms | kein DSP-Patch; Leser muss alle 90 ms laufen |
| B | `0x3B` mit Quelle 1 in einen reservierten Bereich des Sample-Speichers (zum Beispiel 768 KiB, 4 s), der ARM setzt das Ziel `[0xFF903204]` vor dem Ende zurück | kein DSP-Patch; das Zurücksetzen kann mit dem Vorrücken des DSP kollidieren (lesen, schreiben, nachlesen), Platz geht den User-Samples ab |
| C | DSP-Patch: Ringbasis und Größe der Erfassung auf einen reservierten Bereich im Sample-Speicher legen (zwei Konstanten, ein Startwert) | Patch am DSP-Programm wie `stage2-memory` (#550); im QEMU-DSP-Kern prüfbar; Platz geht den User-Samples ab |

### Durchsatz am Host-Port

**Gemessen** ([SD-Takt](2026-10-25-sd-takt.md), Gerät): der Sample-Lader schreibt 21 240 170 Byte PCM in 1797 ms in den
DSP, rund 11 MiB/s. **Hergeleitet:** Lesen (`0xA9`) läuft über denselben Port mit demselben Kopf; 0,19 MB/s belegen ihn
dann unter 2 % der Zeit. Die Leserate selbst ist **offen**.

## 2. Datenrate und Karte

48 kHz, stereo, 16 Bit: 192 000 Byte je Sekunde, 11,5 MB je Minute, 691 MB je Stunde.

**Gemessen** ([SD-Takt](2026-10-25-sd-takt.md), Gerät, Lesen in 32-KiB-Blöcken über die FatFs der Firmware):
3156 KiB/s bei 12,5 MHz, 5172 KiB/s bei 25 MHz. Die Firmware läuft heute mit 25 MHz beim Laden.

**Geschätzt:** der Besitzer schätzt die Schreibrate der Karte am Gerät auf rund 3 MB/s (Erfahrungswert, keine Messung).

**Offen:** Schreiben am Gerät ist nicht gemessen, weder Rate noch die längste Pause eines einzelnen `f_write`. Die
640 KB/s im Emulator ([Virtuelle SD](../hintergrund/virtuelle-sd.md)) sind kein Gerätewert. Der SD-Standard erlaubt einer
Karte bis 250 ms (SDHC) und 500 ms (SDXC) Belegtzeit je Schreibblock (Spezifikation, nicht gemessen). Dazu kommen die
FAT-Einträge, wenn die Datei einen neuen Cluster braucht.

**Hergeleitet:** bei einer Leserate von über 3 MiB/s ist eine Schreibrate unter 0,2 MB/s selbst für langsame Karten
wahrscheinlich; das Risiko sind die Pausen, nicht die Rate. Der Treiber holt laut Emulator 64 Byte je Interrupt
([Emulator](../emulator.md)); das kostet CPU je Sektor, die LOAD METER am Gerät zeigen kann.

### WAV ohne `f_truncate`

**Gelesen** (Disassembly, Hacktribe): die FatFs der Firmware hat `f_open` `0xC009DB60`, `f_write`
`0xC009DFB8`, `f_lseek` `0xC009E404`, `f_close` `0xC009E3DC`, aber kein `f_truncate` und kein `f_rename`.

**Hergeleitet:** eine wachsende WAV braucht beides nicht:

1. Datei neu anlegen, Kopf mit Platzhalterlängen schreiben. Den Kopf auf 512 Byte auffüllen (ein `JUNK`-Chunk vor
   `fmt `), dann beginnen die Daten auf einer Sektorgrenze und volle Blöcke gehen ohne Umweg über den Fensterpuffer.
2. Daten in Blöcken zu 64 KiB anhängen (Korgs eigener WAV-Export schreibt auch 65 536 Byte am Stück,
   [DSP-Audiopfade](2026-10-08-dsp-audiopfade.md)).
3. Beim Zwischenstand zuerst `f_sync`: PCM und Verzeichnisgröße müssen stehen, bevor der Kopf mehr Daten verspricht.
   Danach `f_lseek` auf 0, den 512-Byte-Kopf mit RIFF-Länge bei Byte 4 und data-Länge bei Byte 508 schreiben,
   auf das PCM-Ende zurückspringen und erneut `f_sync`. Der Abschluss verwendet dieselbe Reihenfolge.

**Am 18.11. im ARM-Emulator geprüft:** `f_sync` liegt bei `0xC009E2C8`; der native `f_close` ruft sie zuerst auf.
Eine noch offene Datei hält nach dem Aufruf Verzeichnisgröße und 32 KiB exakte PCM-Daten auf der virtuellen SD.
Auf blau liegt dieselbe Routine bei `0xC008AE20`: alle 69 Befehle bis zum folgenden `f_close` stimmen nach Maskieren
von Sprungabständen überein. Ein isolierter Lauf im ursprünglichen blauen ARM-Emulator sichert ebenfalls 32 KiB
exakte PCM-Daten. Er läuft an der zugeordneten UI-Rahmengrenze; der Sampler-CommandTask-Haken ist auf blau nicht
zugeordnet. Das prüft den Dateischreiber, keinen blauen Aufnahmeweg und kein Gerät.

Eine Datei schrumpft dabei nie. Die Aufnahme sichert nach ungefähr einer Sekunde neu geschriebener PCM-Daten einen
Zwischenstand. Nach Wegfall von CPU- und FatFs-Zustand zeigen die geprüften SD-Abbilder vor und nach den einzelnen
Sicherungsschritten jeweils einen gültigen PCM-Anfang. Auch nach einem fehlgeschlagenen Sync wird der Kopf erst
vergrößert, wenn PCM und Verzeichnis erfolgreich gesichert sind. Die Fälle prüfen Aufrufgrenzen im Emulator,
keinen Stromausfall mitten in einem physischen SD-Sektorschreibvorgang ([Virtuelle SD](../hintergrund/virtuelle-sd.md)).
Grenze: FAT32 und RIFF erlauben 4 GiB, das sind 6,2 Stunden je Datei.

**Offen:** ob andere Kartenzugriffe der Firmware während einer Aufnahme (Einstellungen, Patterns-Ordner, Sample Swap,
Plugins) sauber warten oder die FatFs gleichzeitig betreten.

## 3. RAM

**Gemessen** ([Freier RAM](2026-10-22-ram-frei.md), Gerät): `0xC1010000..0xC4000000` fasst die Firmware im normalen
Spielen nicht an, bis auf einen Task-Stack bei `0xC274E000`. Der Sample-Swap-Zweig belegt davon `0xC274F000..0xC4000000`
als Sample-Cache (24,7 MiB, `HIGH` in `tools/patch/sample_swap.py` auf `feature/sample-swap-native-dsp`, gelesen) und kennt
das Verleihen von Teilen davon an andere Bereiche (`cache_lenders` in `tools/patch/test_projects.py`, gelesen).
Korgs Arbeitspuffer `0xC0D3A940..0xC273AA40` benutzen IMPORT und EXPORT ([Speicherbereiche](../speicherbereiche.md)).
Der Spettro-Kontext braucht 103 424 Byte vom Heap ([API 31](2026-11-12-plugin-api31-spektrum.md)).

**Hergeleitet:** die Ringgröße auf dem ARM richtet sich nach der längsten Zeit, in der der Schreiber nicht auf die Karte
kommt. Kandidaten: Belegtzeit der Karte (bis 0,5 s laut Standard), ein Sample-Swap-Ladevorgang (1 MiB Sample bei
3 MiB/s rund 0,33 s, große Samples länger), ein WRITE mit Flash-Löschen (offen). 2 MiB Ring sind 10,9 s Audio und decken
das mit Abstand; 1 MiB (5,5 s) reichen vermutlich auch. Der DSP-Ring (100 ms) gehört nicht dazu, er muss vom Leser
geleert werden, egal was die Karte tut.

| Teil | Größe | Wo |
|---|---|---|
| DSP-Ring (Weg A) | 19 200 Byte | DSP-Speicher, fest |
| ARM-Ring | 1 bis 2 MiB | eigener `ram`-Bereich oder geliehen vom Sample-Swap-Cache |
| Lesepuffer | 4 bis 16 KiB | im Ring selbst |
| Kopf, Zustand | unter 1 KiB | Laufzeit-RAM |

## 4. Abspielen

Reihenfolge (Entscheidung 17.11.): erst die Aufnahme. Der Player ist ein späterer Schritt und baut auf Sample Swap
(#166, Zweig `feature/sample-swap-native-dsp`) auf.

**Gelesen:** die CPU schickt heute kein Audio in den DSP; Samples liegen im DSP-Speicher und werden von Stimmen gespielt
([DSP im Simulator](2026-11-12-dsp-im-simulator.md), [DSP-Modell](2026-11-12-dsp-modell.md)). Eine Stimme bekommt ihre
Startadresse als Wort 10 ihres Blocks, Stimmen werden reihum vergeben (24 Blöcke, hergeleitet).

| Weg | Wie | Kosten |
|---|---|---|
| P1: Sample-Platz als Ring | Ein reservierter Bereich im Sample-Speicher (zum Beispiel 2 × 1 s stereo, 384 KB) wird als langes Loop-Sample auf einem Part gespielt; der ARM füllt die Hälfte nach, die gerade nicht läuft (Host-Port-Schreiben, gemessen rund 11 MiB/s) | kein DSP-Patch, aber ein ganzer Part samt Filter, IFX, Level und MFX-Send; die Stimme kann durch die reihum Vergabe gestohlen werden; die Abspielposition muss aus dem Stimmenblock gelesen werden (welches Wort, offen); Stereo braucht STEREO 1 PAD oder zwei Parts; Platz geht den User-Samples ab; baut auf Sample Swap (#166) |
| P2: DSP-Patch, Ring in den Mix | Spiegel der Erfassung: die Audioschleife holt je Sample ein 32-Bit-Wort aus einem Ring im DSP-Speicher und addiert es vor oder nach dem Master-Effekt; der ARM füllt den Ring wie bei P1 | Patch am DSP-Programm (eigener Code, eigenes Zwischenwort statt `0xFF80004C`, damit Aufnahme und Wiedergabe gleichzeitig gehen); im QEMU-DSP-Kern bit-genau prüfbar; belegt keinen Part und keine Stimme |
| P3: AUDIO IN ersetzen | Statt des Eingangs (`P4 + 0..0xC`) Ringdaten einspeisen | ist P2 an einer anderen Stelle; folgt dann AUDIO IN THRU und dessen Pegel |

**Hergeleitet:** P2 ist der saubere Weg. P1 geht ohne DSP-Patch, ist aber kein Player, sondern ein Part, der so tut.

## 5. Blaue Electribe

**Gelesen** (blaues DSP-Programm, `0xC00DFB80`):

- Die Erfassung `0x37` gibt es (Handler `0xFFA05508`), mit 17 Arten, Ring `0x01371EC0`, Größe `0x4B00` (19 200 Byte, wie rot),
  Zustand ab `0xFF9031C8`. Art 0 ist `0xFF802810`, das ist dort `P4 + 8`, denn `P4 = 0xFF802808` (`0x01F0C51C`).
- Die Master-Stufe gleicht der roten (Master-Effekt, Soft-Clipper `0xFFA01348`, Verstärkung `[P5 + 0x13C]`), schreibt aber
  **kein gepacktes Stereo-Wort und keine Mono-Summe**. Links und rechts stehen nur als 32-Bit-Werte in `0xFF802818` und
  `0xFF80281C` (`P4 + 0x10`, `+0x14`), vor der Verstärkung.
- Blau kennt `0x3A` und `0x3B` nicht ([DSP-Modell](2026-11-12-dsp-modell.md)): kein SAMPLING, kein RESAMPLING.
- Auf dem ARM fehlt der native Erfassungsstart; `korg.audio.*` gibt dort 6 zurück ([API 31](2026-11-12-plugin-api31-spektrum.md)).

**Hergeleitet:** ohne DSP-Patch geht auf blau nur mono (ein Kanal, Quellzeiger auf `0xFF802818`), und der Start braucht
eigenen ARM-Code, der `0x37` ans Postfach schickt. Stereo braucht auf blau einen eigenen DSP-Patch (das Packen nachrüsten);
die Wiedergabe geht auf blau nur über P2, weil es dort keine User-Samples im Sample-Speicher gibt. Der Besitzer hat nur
eine rote; blau braucht einen Tester.

## 6. Simulatorprüfung am 17. November 2026

**Im Simulator geprüft:** [`native_recording_probe.py`](../../tools/dsp/native_recording_probe.py) führt Abschnitte des
originalen roten Blackfin-Programms mit synthetischen Signalen im GNU-Simulator aus. Die Firmwarebereiche werden aus einem
externen Verzeichnis gelesen; ELF und Binärdateien entstehen nur im temporären Verzeichnis. Rücksprünge an den Grenzen
isolieren die Abschnitte. Das ist kein vollständiger DSP-Boot und keine Messung am Gerät.

Die Werkzeuge und das ausgepackte rote DSP-Programm werden beim Aufruf ausdrücklich übergeben:

```sh
node tools/load-gate.mjs python3 tools/dsp/native_recording_probe.py REGIONS \
  --as BFIN_AS --objcopy BFIN_OBJCOPY --run BFIN_RUN
```

`REGIONS` kommt aus `tools/dsp/dsp_extract.py` und bleibt außerhalb des Repos. Die Adressen dieses Prüfers gelten für
rot und Hacktribe, nicht für blau. Das DSP-Programm beider Sampler ist gleich (siehe DSP-Modell).

### Erfassung und Ring

Der Handler `0xFFA05620` startet die Erfassung. Danach wird der Quellzeiger vor jedem Frame zwischen dem Master-Wort und
einem synthetischen zweiten Wort umgestellt. Für 4803 Frames werden Zwischenwort, DMA-Quelladresse, DMA-Zieladresse und
nächster Ringzeiger geprüft. Die ersten 4800 Frames füllen einen Ring, die nächsten drei laufen wieder vom Anfang.
Die Wörter bleiben bitgleich. Die Bytefolge ist R vor L; für eine Stereo-WAV muss der ARM die beiden 16-Bit-Hälften tauschen.

**Grenze:** Die DMA-Register sind in diesem Lauf RAM. Der Prüfer bildet die Ringdaten aus den geprüften Deskriptoren nach.
Das belegt den Quellzugriff, die Wortfolge und den Ringumlauf, keine echte MDMA-Übertragung oder deren Dauer. Schreibpausen
und Leserabstände am Gerät bleiben offen. Gleichzeitiges Ändern des Zeigers durch einen Host-Port-Transfer ist nicht getestet.

### AUDIO IN THRU und Metronom

**Gelesen und im Simulator geprüft:** `0xFFA0189A..0xFFA018DC` glättet den THRU-Pegel und addiert die vorherigen linken und
rechten Eingangswerte. Die aktuellen Werte aus `[P4]` und `[P4+4]` werden für den nächsten Frame gespeichert. Dieser Anteil
steht noch nicht in `0xFF802888`.

**Gelesen:** Der Sequencer liest über `0xC0046B8C` die Metronomeinstellung. Der Auslöser `0xC005EA3C` führt über
`0xC003FC60` nach `0xC0014198`. Dort werden DSP-Parameter `0x4C55` und `0x4C56` beschrieben. Sie entsprechen den Wörtern
`0xFF903154` und `0xFF903158`, also `[P5+0xB0]` und `[P5+0xB4]`. Der DSP verarbeitet sie bei
`0xFFA018E0..0xFFA01906`: Mono-Klick links und rechts, Hüllkurve und Abklingen. Die Initialisierung setzt Abklingen 34 und
Pegel `0x2000` über `0xC003FC48`.

**Im Simulator geprüft:** Getrennte linke und rechte Eingangssignale erscheinen nur auf ihrem Kanal. Der isolierte Klick
erscheint gleich auf beiden Kanälen; sein Pegel null entfernt ihn. Vor `0xFFA018E0` bleibt AUDIO IN erhalten und der Klick
fehlt. Die Ausgangsverstärkung folgt bei `0xFFA0190A..0xFFA0193A`.

**Hergeleitet:** Das eigene Aufnahme-Wort muss nach dem THRU-Anteil und der Player-Summe entstehen. Der Klick muss getrennt
bleiben; die nachfolgende Ausgangsverstärkung ist auch auf den Aufnahmezweig anzuwenden. Der vorhandene Capture-Abschnitt
läuft davor, daher muss auch die Reihenfolge oder der definierte Abstand von einem Frame berücksichtigt werden. Der Klick
bleibt für den Ausgang eingeschaltet. Ein einfacher Wechsel des Quellzeigers auf `0xFF802888` erfüllt das Aufnahmeziel nicht.

**Gelesen, hergeleitet:** `[P4+0x6C]` und `[P4+0x70]` sind die linken und rechten Sammelwerte, die MFX umgehen, aber vor dem
Clipper zugemischt werden. Die Audioschleife sammelt Werte ab `[P4+0x20+2*Route]`, skaliert die vier Buswörter ab `+0x6C`
bei `0xFFA0157C` und leert sie bei `0xFFA019CA`. `+0x74` und `+0x78` gehen durch den MFX-Zweig; `+0x6C` und `+0x70` kommen
bei `0xFFA01720` dazu. Sie sind nicht der nachgelagerte THRU- oder Klickweg.

### Ausstehende Gerätemessungen

| Aufgabe | Messwerte | Stand |
|---|---|---|
| 0.1 | Quelle und Zustand während RESAMPLING; Ringzeiger bei Spettro | offen, Besitzer misst |
| 0.3 | Schreibrate, längste Pause und Clusterwechsel bei 64-KiB-Blöcken, je 60 s mit 12,5 und 25 MHz | offen, Besitzer misst |
| 0.4 | längste Leserlücke bei Pattern-Wechsel, WRITE und Sample Swap, CommandTask und eigener Task | offen, Besitzer misst |
| 0.5 | A bei gemessener Leserlücke unter 80 ms, sonst C oder B | noch nicht entschieden |

Simulatorgeschwindigkeit ersetzt keine dieser Zeitmessungen. Die Freigabe für lückenlose Aufnahmen wartet auf die Ringentscheidung.

## 7. Eigener Aufnahmezweig und nativer Schreiber

**Im Simulator geprüft:** Der eigene DSP-Code liegt ab `0x01F12000`, sein Zustand ab `0x01F12100`. Das gepackte
Aufnahme-Wort steht bei `0x01F12108`, die Freigabe bei `0x01F1210C`, ein Kennwort bei `0x01F12110`. Die beiden
Umleitungen nach THRU und nach der Ausgangsverstärkung erhalten den hörbaren Ausgang in acht Vergleichsfällen bitgleich.
Der Abgriff entspricht demselben Originallauf ohne Klick, auch mit Eingangssignal und Sättigung. Die Erfassung davor
liest das Wort des vorigen Frames; beim Start wird der bisherige Ringinhalt verworfen.

**Gelesen und geprüft:** Der Bootstrom erhält einen eigenen Block vor seinem abschließenden Start-Header. Seine Länge
wird mit angepasst. Der Builder prüft freien Platz vor `0xC013C200`, die originalen Umleitungsstellen, vorhandene
Ladeblöcke und die vier Heap-Einträge ab `0x01F02438`. Jeder Eintrag enthält Basis, gespeicherte Länge und ID. Der neue
DSP-Bereich liegt außerhalb aller vier Heaps. Die Patch-Datei enthält eigenen Code und Prüfsummen, keine Originalbytes.

**Im ARM-Emulator geprüft:** Der private WAV-Schreiber nutzt einen eigenen `0x240`-Byte-FIL-Kontext. Er legt
`SD:Recordings/REC0001.WAV` mit FA_CREATE_NEW an und überspringt vorhandene Namen. Der Kopf umfasst 512 Byte: JUNK,
PCM-Format und data-Header, danach ganze 64-KiB-Blöcke und beim Stop der Rest. Längen werden beim Abschluss gesetzt.
Ein Teilwrite meldet einen Fehler; nur vollständige Frames stehen im data-Chunk. Ein fehlgeschlagenes Schließen behält
seinen Dateikontext bis zum nächsten Abschlussversuch.

**Gelesen und im ARM-Emulator geprüft:** `0xC0014284` schreibt keine Transfers unter 16 Wörtern. Kurze Host-Port-Writes
laufen über `0xC00146B4` mit exakter Länge und Schritt 2. Der Port kommt aus `0xC0015C98`, davor und danach steht die
native DSP-Sperre 1 (`0xC0000D80`/`0xC0000CA8`). Das verhindert das Überschreiben benachbarter Zustandswörter.

**Im ARM-Emulator geprüft:** Auf rot und Hacktribe schreibt der Worker aus CommandTask mit den originalen FatFs- und
SD-Routinen eine lesbare Stereo-WAV auf die virtuelle Karte. Ihre PCM-Daten stimmen mit dem synthetischen DSP-Signal
überein. Benutzer-Flash bleibt unverändert; keine Assertions. Die Fälle nutzen Emulator-Arbeitsraum und beweisen noch
keine Menüanbindung, keine Gerätezeiten und kein störungsfreies langes Set.

## Offen

- Gerät, nur lesend: Quellzeiger und Ring während RESAMPLING und mit laufendem Spettro lesen, Bestätigung des im
  Simulator geprüften Abgriffs mit AUDIO IN THRU und Metronom.
- Gerät, schreibend (nur mit Zustimmung): Schreibrate und längste Pause von `f_write` mit 64-KiB-Blöcken, mit 12,5 und 25 MHz.
- Gerät: Laufabstand eines Lesers, wenn die CommandTask ein Pattern lädt oder WRITE den Flash löscht.
- Ob Weg A ohne Lücke hält; sonst Weg B oder C.
- Polarität: die Ausgangsstufe dreht beide Kanäle nach dem Abgriff um (`0xFFA0197E`); ob die Aufnahme gegen den Ausgang
  am Gerät invertiert ist, ist offen und für eine WAV egal.

## 8. Native Bedienung und vorläufiger Dienst

**Im ARM-Emulator geprüft:** SHIFT+REC öffnet die Sampling-Ansicht. RECORD ist eine eigene dritte Quellwahl; der native
Quellwert bleibt 0 oder 1. Die Lebensdauer der Ansicht wird an Konstruktor und Destruktor erkannt, kein Ansichtszeiger
bleibt im Aufnahmedienst. PLAY schließt die native Ansicht und startet keine Aufnahme. REC startet und stoppt in RECORD.
Während des Starts und Abschlusses bleibt die Quelle gesperrt. Die Anzeige nennt Datei, Dauer aus PCM-Bytes und Fehler.

**Im ARM-Emulator geprüft:** CommandTask besitzt den Aufnahmekontext und einen dynamischen Ring, nur solange Ressourcen
belegt sind. Es wird der größte verfügbare Zweierpotenz-Block von 128 KiB bis 2 MiB versucht. Im vollständigen Startlauf
waren 1 MiB möglich; das ist keine Zusage für das Gerät. Der Bereich liegt im allgemeinen Heap, nicht im reservierten
Sample-Swap-Bereich. Spettro und andere Apps mit Erfassung sind während der Aufnahme nicht wählbar.

**Im ARM-Emulator geprüft:** Mit dem ganzen Patch-Set bestehen je 15 Aufnahmeprüfungen auf rot und Hacktribe. Kurze Takes
enthalten exakt das künstliche Signal. Ein voller 64-KiB-Write im aktuellen Karten-/CPU-Modell überschreitet die vorläufige
80-ms-Frist: sichtbarer Lückenstatus, gültiger WAV-Kopf und zusammenhängender PCM-Anfang. Dieser Fall belegt den Abbruch,
nicht lückenlose lange Aufnahmen, keine SD-Schreibrate und keine längste Pause am Gerät. 0.3 und 0.4 bleiben offen.

## 9. Dauerhafter Beleg eines Erfassungsfehlers

**Im ARM-Emulator geprüft:** Ein terminaler Lückenfehler, verlorener Erfassungsbesitz oder ARM-Ring-Überlauf erhält einen
cue-Marker am Ende des gültigen PCM-Anfangs. Die zugehörige LIST/adtl/labl-Beschriftung nennt den Grund. Ein Teil des
JUNK-Bereichs im 512-Byte-Kopf wird dafür verwendet; PCM-Position, RIFF-Länge und Schreibanzahl bleiben gleich. Die Anzeige
zeigt den Lückenzähler bis zum nächsten Start. Die unbekannte Zahl verlorener Frames wird nicht als Messwert ausgegeben.
Beide vollständigen Sampler-Patchsets bestehen je 17 Aufnahmeprüfungen mit Dateimarker und sichtbarem Zähler.

**Hergeleitet:** cue darf an beliebiger Stelle der WAV stehen; die Beschriftung verweist über ihre ID auf den cue-Punkt.
Grundlage: [FADGI, Teil III, Seiten 22 und 23](https://www.digitizationguidelines.gov/audio-visual/documents/BWF_Embed_Guideline_v3_2021.pdf).

## 10. Geräteprüfung am 18.11.2026, nur READ

**Gemessen:** Verbindung über den Linux-Rechner und den USB-SOUND-Port, BLECH READ `0x61`, MIDI-Kanal 10.
Es wurde kein WRITE, EXEC oder fernbedienter Tastendruck gesendet. Der bestehende DSP-Leser wäre EXEC-basiert und
wird hier nicht verwendet. Stattdessen werden vorhandene ARM-Metadaten gelesen.

**Gemessen, Ausgangszustand:** `0xC018D000..0xC018D00F` ist vollständig `0xFFFFFFFF`, also noch kein Kontext des
Spektrumdienstes. Der native Samplerzeiger aus `0xC0345A08` zeigt auf `0xC06C42B8`. Stereo- und Quellwahl dort bei
`+0x704` und `+0x708` sind beide 0, also mono und AUDIO IN. Das bestätigt noch keinen DSP-Abgriff und keine Ringbewegung.
