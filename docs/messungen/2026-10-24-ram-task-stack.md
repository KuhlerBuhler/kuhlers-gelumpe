# Der Stack bei 0xC274E000 und wer den RAM darüber nutzt (24.10.)

Frage: Am Gerät änderte sich beim normalen Spielen oberhalb von `0xC1010000` nur der Block `0xC274E000`
([Freier RAM](2026-10-22-ram-frei.md)). Wem gehört dieser Stack, liegt ein Heap daneben, und welcher Code schreibt
in den Arbeitspuffer `[0xC0D3A940, 0xC273AA40)` und in alles darüber, bei Start, Spielen, Pattern-Wechsel,
Import/Export und Ausschalten? Ist der Arbeitspuffer nach Import/Export wieder frei?

Gemessen im Emulator und am Abbild, nicht am Gerät. Firmware 2.02 mit Hacktribe (`hacktribe-original.VSB`,
unverändert), eigener Flash-Dump vom 9.10., virtuelle Karte mit eigener `e2sSample.all` (40 Samples à 40.000 Byte
aus `sampleset.py`) und einer eigenen WAV. Start, Spielen, Pattern-Wechsel und Ausschalten auch mit dem BLECH-Satz
(`SYSTEM-hacktribe.VSB`).

## Aufbau

`tools/emu/highram_watch.py` startet die Firmware und hakt sich auf jeden Schreib- und Lesezugriff in den
Arbeitspuffer und in `[0xC274EA3C, 0xC8000000)` (der Emulator mappt 128 MiB, darüber liegt am Gerät der
64-MiB-Spiegel). Jeder Zugriff wird mit PC, LR, CPU-Modus, SP und Phase gezählt. Die beiden Stacks darunter
werden nur in zwei Fenstern von je rund 2 s gehakt (jeder Interrupt schreibt dort, ein Dauerhaken macht den Lauf
etwa zehnmal langsamer) und sonst an jedem Phasenwechsel blockweise verglichen. In den Startstack schreibt das
Skript vor dem ersten Befehl dasselbe Kanarienmuster wie am Gerät (`Adresse ^ 0x5A5AA5A5`), den Interrupt-Stack
füllt die Firmware selbst mit `0xEEEEEEEE`. Zusätzlich zählt ein Haken die Aufrufe des Puffergebers `0xC00369F0`
mit ihrer Rücksprungadresse.

```bash
tools/emu/.venv/bin/python tools/emu/highram_watch.py --vsb hacktribe-original.VSB \
    --flash flash_full_2026-10-09.bin --report run.json            # Wache
tools/emu/.venv/bin/python tools/emu/highram_watch.py --vsb hacktribe-original.VSB \
    --flash flash_full_2026-10-09.bin --report run-poison.json --poison   # Gegenprobe
```

Ablauf: Start mit Laden der Samples, 4 s Hauptbildschirm, Muster spielen mit 16 Pads, sechs Menüseiten,
Pattern-Wechsel beim Spielen und im Stand, dann DATA UTILITY: IMPORT SAMPLE (WAV von der Karte, Platz wie
angeboten: 501, ersetzt das Sample dort), EXPORT ALL SAMPLE, EXPORT ALL PATTERN, IMPORT ALL PATTERN (die eben exportierte Datei), danach noch
einmal Spielen und Pattern-Wechsel, zuletzt die Einschalttaste. Alle vier DATA-UTILITY-Wege liefen durch: die exportierte
`e2sSample.all` ist um 60.000 Byte größer als die eingelesene (das ersetzte Sample), die `.e2sallpat` hat 4.161.792
Byte, kein Assert, das Gerät ging aus.

`--poison` füllt nach dem Start den ganzen Arbeitspuffer und alles ab `0xC274EA3C` mit einem fremden Wort. Der
Lauf mit `--poison` hatte IMPORT SAMPLE noch hinter den Pattern-Wegen; dort fand das Skript die WAV nicht (der
Dateibrowser merkt sich den Ordner), IMPORT SAMPLE fehlt in der Gegenprobe also.

## Ergebnis

### 1. Der Stack bei 0xC274E000

| Befund | Status | Beleg |
|---|---|---|
| `0xC274E000` ist der oberste Block des Interrupt- und Leerlaufstacks `[0xC274AA40, 0xC274EA3C)`, kein Task-Stack | gemessen am Abbild | Literal `0xC274EA3C` nur bei `0xC00015A8`, `0xC00017F4`, `0xC00296D0` |
| Er entsteht nicht über das Anlegen eines Tasks: der Interrupt-Einstieg `0xC0001560` schaltet in den SVC-Modus, zählt die Tiefe bei `[0xC000172C]` hoch und setzt nur auf der äußersten Ebene SP fest auf `0xC274EA3C` (`0xC00015A8`). Der Scheduler setzt denselben SP im Leerlauf (`0xC00017F4`) und wartet dort per `mcr p15, c7, c0, 4` auf den nächsten Interrupt | gemessen am Abbild | Disassemblierung `0xC0001560` bis `0xC00015D0`, `0xC00017CC` bis `0xC000181C` |
| Der Start (`0xC00296B0`, aufgerufen vom Reset bei `0xC0000078`) füllt `[0xC274AA40, 0xC274EA3C)` mit `0xEEEEEEEE`, 16.380 Byte | gemessen am Abbild und im Emulator | Literale `0xC0029880`/`0xC0029884`/`0xC0029888`; Füllwort aus dem Lauf |
| Alle Schreiber dort laufen im SVC-Modus, 95 PCs im Leerlauf, 131 beim Spielen, häufigste `0xC009AEA8`, `0xC009AF24`, `0xC002BB10`, `0xC0001568` | gemessen im Emulator | `stack_marks`, Phasen "... (stack writes hooked)" |
| Tiefste Stelle: `0xC274E918`, also 292 Byte genutzt; in allen Phasen ändert sich nur der Block `0xC274E000`, die Blöcke darunter nur beim Füllen im Start | gemessen im Emulator | `stack_marks`, `stack_blocks_changed` |
| Passt zum Gerät: dort 82 bis 84 veränderte Wörter in genau diesem Block | gemessen am Gerät (22.10.) | [Freier RAM](2026-10-22-ram-frei.md) |

Die zehn Task-Stacks liegen alle weit unten, `[0xC0200000, 0xC03167A8)`, Größe und Basis aus der
Deskriptortabelle ab `0xC00A37A8` ([Systemspeicher](2026-10-08-systemspeicher-offline.md)), Namen und
Hochwasser in [Plugin-Laufzeit 3.1](../hintergrund/skript-laufzeit.md).

**Startstack:** Vom Reset-SP `0xC274AA40` an braucht der Start 144 Byte (tiefstes geändertes Kanarienwort
`0xC274A9B0`); danach schreibt nichts mehr hinein, auch nicht bei Import/Export (gemessen im Emulator). Die
reservierten 64 KiB `[0xC273AA40, 0xC274AA40)` sind also großzügig, bleiben aber gesperrt.

### 2. Heap oder anderer Allokator daneben

Nein. Der Heap ist `[0xC06A2940, 0xC08A2940)` ([Systemspeicher](2026-10-08-systemspeicher-offline.md)).
Oberhalb von `0xC274EA3C` lädt kein Code der Firmware einen Zeiger: die einzigen PC-relativen Literale oberhalb
von `0xC274EA3C` bis `0xC8000000` sind `0xC28F5C29`, `0xC2FE0000`, `0xC3500000`, `0xC7EFFFFF`, und die werden
gerechnet oder als Wert übergeben (hergeleitet aus der Disassemblierung bei `0xC00946DC`, `0xC00422E4`,
`0xC0005310`, `0xC0004330`; sie sehen nach Gleitkomma-Konstanten aus). Gleich bei Korg-Original und Hacktribe.
Im BLECH-Satz kommen dazu: der Doom-Lader (`0xC1000000` bis `0xC1800000`, nur im Doom-Start, `tools/doom/runtime.ld`)
und ein Vergleich mit `0xC4000000` bei `0xC0172CFC`.

### 3. Wer in den Arbeitspuffer und darüber schreibt

| Phase | Bereich | Schreiber (PC, LR) | Leser (PC) | Puffergeber gerufen von |
|---|---|---|---|---|
| Start mit 40 Samples | `[0xC0D3A940, 0xC0D44580)`, 40 KB = ein Sample | `0xC0018178` (LR `0xC001810C`, SP im Stack von Task 8), `0xC009BB2C` (LR `0xC009DF84`, SP im Stack von Task 5) | `0xC0014840` (DSP-Schreibweg, LR `0xC001461C`) | `0xC00362B8`, 40-mal |
| Leerlauf, Spielen, Pads, Menüs, Pattern-Wechsel (spielend und im Stand) | nichts | | | |
| IMPORT SAMPLE, WAV mit 100 KB | `[0xC0D3A940, 0xC0D4A940)`, genau 64 KiB | `0xC0018178`, `0xC009BB2C` | `0xC0014840` | `0xC00362B8`, einmal |
| EXPORT ALL SAMPLE | `[0xC0D3A940, 0xC0D4A940)`, 64 KiB | `0xC0014A70` (DSP-Leseweg) | `0xC0017F98`, `0xC009BB28` | `0xC0039BFC`, 40-mal |
| EXPORT ALL PATTERN | nichts, die Datei entsteht ohne den Puffer | | | |
| IMPORT ALL PATTERN | `[0xC0D3A940, 0xC1122940)`, 4.096.000 Byte = 250 × `0x4000` | `0xC0018178`, `0xC009BB2C` | `0xC0009880` bis `0xC000989C` (Kopie in die Patternslots, LR `0xC00476E0`) | `0xC002E488`, einmal |
| nach DATA UTILITY: Spielen, Pattern-Wechsel | nichts, auch kein Lesen | | | |
| Ausschalten über die Taste | nichts | | | |
| `[0xC274EA3C, 0xC8000000)` in allen Phasen | kein einziger Zugriff | | | |

Alle Zeilen gemessen im Emulator mit `hacktribe-original.VSB` (`run.json`, Abschnitt `watch`). Der BLECH-Satz zeigt
beim Start, Spielen, Pattern-Wechsel und Ausschalten dieselben Schreiber und Bereiche. Die DATA UTILITY lief mit
BLECH nicht: seine Seiten sehen anders aus, die Titelkennungen im Skript gelten nur für Hacktribe.

Die Samples gehen in 64-KiB-Stücken durch den Puffer: der Import einer 100-KB-WAV und der Export mit ihr berühren
nur die ersten 64 KiB (gemessen). Dass das für jede Samplegröße gilt, ist hergeleitet; der Puffergeber meldet
trotzdem die vollen `0x01A00100` Byte.

**Hacktribe selbst** nutzt den Puffer über SysEx: der Schreibbefehl `0x54` legt Daten ab `0xC1000000` ab, das
Flash-Lesen `0x55` schreibt ab `0xC2000000` (`0xC0170700`: Ziel fest, Offset und Länge aus der Anfrage, eine
Obergrenze ist im Code nicht zu sehen, hergeleitet). `tools/device/flash_dump.py` fragt in Blöcken von `0x4000`,
bleibt also in `[0xC2000000, 0xC2004000)`. Eine Anfrage über `0x73AA40` Byte würde in den freien Bereich
oberhalb `0xC273AA40` schreiben.

### 4. Ist der Arbeitspuffer nach Import/Export frei?

Ja, im Emulator: Er wird nur während der Vorgänge oben beschrieben und danach nicht mehr gelesen. Gegenprobe
`--poison` gegen denselben Ablauf ohne Gift: gleiche Exportdateien (`e2sSample.all` und `.e2sallpat`, gleiche
sha256), gleiche 250 Patternslots nach IMPORT ALL PATTERN, kein Assert (gemessen; ohne IMPORT SAMPLE, siehe Aufbau). Die Firmware erwartet dort also keinen Inhalt von früher.

Er ist aber **kein dauerhafter Speicher**: Beim Laden der Samples im Start, bei IMPORT SAMPLE, EXPORT ALL SAMPLE
und IMPORT ALL PATTERN (die ersten 4.000 KiB) und bei Hacktribes SysEx-Befehlen wird er überschrieben. Ein
Cache für eine zweite Patterndatei darf dort nur liegen, wenn er nach jedem dieser Vorgänge als ungültig gilt und
neu geladen wird. Wer den Puffer ab `0xC1122940` nutzt, kommt IMPORT ALL PATTERN nicht in die Quere, aber SysEx
`0x54` (`0xC1000000`) und `0x55` (`0xC2000000`).

## Freie Bereiche

| Bereich | Größe | Status |
|---|---|---|
| `[0xC274F000, 0xC4000000)` | 25.890.816 Byte (24,7 MiB) | frei: am Gerät beim Spielen unberührt (22.10.), im Emulator in keiner Phase gelesen oder beschrieben, kein Zeiger der Firmware dorthin. Am Gerät nicht geleert (alter RAM-Inhalt), eigener Code muss ihn selbst initialisieren |
| `[0xC0D3A940, 0xC273AA40)` | 27.263.232 Byte | nur zeitweise: frei zwischen den Vorgängen in Abschnitt 4, Inhalt danach ungültig |
| `[0xC273AA40, 0xC274F000)` | | gesperrt: Startstack und Interrupt-/Leerlaufstack. `0xC274EA3C` bis `0xC274F000` beschreibt niemand, liegt aber im Block des Stacks und bleibt als Abstand frei |
| ab `0xC4000000` | | gesperrt: Spiegel von `0xC0000000` am Gerät |

## Was das nicht zeigt

- **Emulator, nicht Gerät.** Der DSP ist eine Attrappe, es gibt kein Audio und keinen DMA. Ob am Gerät ein
  DMA-Weg oder ein Treiber außerhalb der hier gelaufenen Wege den RAM über `0xC274F000` nutzt, zeigt das nicht;
  die Geräteprobe vom 22.10. spricht für das normale Spielen dagegen.
- **Der Spiegel.** Der Emulator mappt 128 MiB, am Gerät ist `0xC4000000` gleich `0xC0000000`. Kein Zugriff ging
  dorthin; ein Schreiben dort würde am Gerät die Firmware treffen.
- **Nicht gelaufen:** RESAMPLING und SAMPLING (die Aufnahme wartet auf Audio vom DSP), Auto Power Off über den
  Zeitgeber (nur das Ausschalten über die Taste; dass der Zeitgeber denselben Weg nimmt, ist nicht geprüft),
  SOFTWARE UPDATE, EXPORT PATTERN einzeln und die übrigen Seiten der DATA UTILITY, USB-Audio und MIDI-Dump,
  Hacktribes SysEx-Befehle, die DATA UTILITY mit BLECH, eine Karte ohne `e2sSample.all`.
- **Größen.** Nur 40 Samples à 40 KB und eine 100-KB-WAV. Ein langes Sample beim Start oder Import ist
  hergeleitet, nicht gemessen.
- Nur Firmware 2.02 mit Hacktribe; eine andere Build verschiebt alle Adressen.

## Offen

- Eine Geräteprobe mit `tools/device/canary.py` über Import, Export und IMPORT ALL PATTERN, um die Tabelle oben am
  Gerät zu bestätigen.
- Die Titelkennungen der DATA UTILITY für den BLECH-Satz, damit derselbe Lauf auch dort durchgeht.
- Auto Power Off über den Zeitgeber und RESAMPLING am Gerät.
- Wem Task 8 gehört (Einstieg `0xC001DA9C`), dessen Stack beim Lesen von der Karte in den Puffer schreibt.
