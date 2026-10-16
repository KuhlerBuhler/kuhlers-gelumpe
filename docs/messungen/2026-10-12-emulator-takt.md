# Emulator-Takt: 1000 Timer-Interrupts je Sekunde

Stand 2026-10-12. Alles im Emulator (`tools/emu/machine.py`, Unicorn 2.1.4), Firmware
`SYSTEM.VSB` und `SYSTEM-ringtest.VSB`, Flash: eigener Dump vom 9.10. Kein Gerätezugriff.
Markierungen: **gemessen**, **hergeleitet**, **offen**.

## Ursache und Behebung

- **Gemessen:** Mit `SLICE = 20000` Befehlen zwischen zwei Interrupt-Prüfungen und 5 ns je Befehl
  (100 µs je Scheibe) kam der 1-kHz-Timer-Interrupt (INT 21) 872-mal je Sekunde Gerätezeit (mit
  dem Flash-Dump; 791-mal ohne, siehe `docs/hintergrund/skript-laufzeit.md`),
  der Bildschirm-Takt (`UiTask`, `0xC006F178`) 21-mal statt 25-mal. Der Zähler vergleicht
  nur am Scheibenende, ob eine Kante verstrichen ist, und meldet höchstens eine je Scheibe.
- **Behoben:** Eine Scheibe endet an der nächsten Timer-Kante oder dem nächsten UART-Byte
  (`slice_length`), im Interrupt-Handler läuft sie nur 256 Befehle, damit der nächste
  anstehende Interrupt gleich danach kommt, und ein Prozessor im Warten-auf-Interrupt
  springt bis zum nächsten Ereignis (`run_slice`). Abfrageschleifen auf den Timer-Registern
  halten die Scheibe an der nächsten Kante an. Die Zustellung ist damit unabhängig von der
  Scheibenlänge; `SLICE = 20000` bleibt die Obergrenze.
- **Gemessen:** Der Boot kostet damit keine Zeit: 5 s Gerätezeit brauchen mit `SLICE = 2000` und
  mit `20000` je 7,0 bis 7,2 s CPU-Zeit. Mit `SLICE = 2000` als Vorgabe bricht dagegen die Tempo-Rate
  in Phasen ein, in denen die Firmware dauernd rechnet (Muster-Sicherung auf eine SD-Karte,
  Flash lesen): `SLICE = 2000` brachte 0,07 der Echtzeit, `20000` bleibt bei 1,0 bis
  zum Flash-Lesen (Dienst, `speed` im Status).

## SD-Karte: der Karten-Interrupt

- **Gemessen:** Mit dem Karten-Interrupt (INT 16) sofort nach dem Ende einer Scheibe bleibt die
  Firmware nach CMD12 (STOP) hängen (kein Panel-Verkehr, dann Assertion in
  `AM180xMMSDCardController.cpp`, Zeile 228 und 413). Der Interrupt-Handler liest ST0 (liest
  löscht) vor der Abfrageschleife des Vordergrunds und nimmt ihr die Antwort weg. Mit den
  Scheiben zu 20000 Befehlen kam der Handler immer eine Scheibe (100 µs) später.
- **Behoben:** `MMC_IRQ_NS`: der Karten-Interrupt wird nur einmal je 100 µs Gerätezeit angesehen
  (`lines`), wie vorher an jedem Scheibenende. Das ist ein Modell, kein Befund vom Gerät:
  **offen**, wie die Firmware am Gerät die Antwort zwischen Handler und Abfrage aufteilt.
- **Gemessen:** Der Ablauf von `test/emulator-card.test.mjs` (IMPORT SAMPLE, EXPORT SAMPLE, EXPORT ALL
  PATTERN) bringt dieselben Sektorzahlen wie vorher (144 gelesen, 8365 geschrieben) und braucht
  120 s statt 283 s Wanduhrzeit (eigener Python-Lauf `flow.py`, nicht im Repo).

## Raten (`tools/emu/test_timer.py`, 1 s Gerätezeit ab 2 s)

| Scheibe | vorher Timer-Interrupts/s | vorher Bildschirm-Takt/s | jetzt Timer | jetzt Bildschirm-Takt |
|---|---|---|---|---|
| 20000 | 872,0 | 21,0 | 1000,0 | 25,0 |
| 2000 | 1000,0 | 25,0 | 1000,0 | 25,0 |
| 500 | 1000,0 | 25,0 | 1000,0 | 25,0 |

Der Test verlangt 1000 plus minus 1 % und 25 plus minus 1 % für 20000 (Vorgabe), 200000 und 500;
ohne `E2_VSB` wird er übersprungen, mit `E2_EMU_REQUIRED=1` ist das ein Fehler.

## Laufzeit von `check.py` und Grenze

CPU-Zeit (`user`) beider Läufe, Startbild-Editor und MFX 2 gegen `SYSTEM-ringtest.VSB`, mit
Flash und den `--allow-code`-Spannen aus `apply.mjs`:

| | Startbild-Editor | MFX 2 | zusammen |
|---|---|---|---|
| alter Takt (vor der Behebung), ohne eigene Parallelläufe | 56,8 s | 60,8 s | 117,6 s |
| richtiger Takt (`SLICE = 2000`), ohne eigene Parallelläufe | 63,0 s | 69,6 s | 132,6 s (+13 %) |
| richtiger Takt (`SLICE = 20000`), Rechner stark belastet | 242,4 s | 276,5 s | 518,9 s |

Die Rechnerlast beim Messen (Lastmittel 5 bis 9 durch andere Läufe) verändert die CPU-Zeit
um den Faktor 2 bis 4: dieselbe Prüfung brauchte am selben Tag 117 s bis 519 s. Zuverlässig
ist nur der Vergleich hintereinander unter gleicher Last: `bootmap.start_phase` (16 Startwege)
braucht mit richtigem Takt 91,6 s gegen 82,5 s im alten Stand (+11 %), ob `SLICE` 2000 oder 20000 ist, ändert
das nicht (88,8 s gegen 91,6 s).

**Grenze:** beide `check.py`-Läufe zusammen höchstens 180 s CPU-Zeit auf einem ruhigen Rechner
(gemessen 133 s; MacBook, Unicorn 2.1.4) und in jedem Fall unter 600 s. Wer `check.py` im
Browser-Ablauf (`POST /check`) aufruft, muss mit rund 2 bis 3 Minuten rechnen. Die Wanduhrzeit
schwankt mit der Last stark.

## Neu geprüft mit richtigem Takt

- **Gemessen:** `splash_cases.py run`: 36 von 36 Schritten bestanden.
- **Gemessen:** `mfx_cases.py run`: 42 von 42 Schritten bestanden (935 s CPU-Zeit unter Last).
- **Gemessen:** `check.py` Startbild-Editor: 30 von 30 Prüfungen, MFX 2: 25 von 25.
- **Zwei Prüfungen waren vom Takt abhängig und sind angepasst** (`mfx_cases.py`), kein Patch
  geändert:
  - Die DSP-Übertragungen zweier getrennt gebooteter Geräte werden verglichen. Die Effekt-Puffer
    wechseln (`0xFF900018` und `0xFF900098`) und ihre Schreibzeiger laufen in einem Ring von
    `0x8000` Wörtern (hergeleitet aus den Zeigerwerten 32768 bis 65535); zwei Starts, die sich um einige frühere Übertragungen unterscheiden,
    liegen an verschiedenen Stellen (Zeiger um 4096 versetzt, Puffer vertauscht). Mit dem alten
    Takt trafen sich die Phasen zufällig. `same_dsp` lässt einen Versatz für die ganze Liste zu;
    Befehle und alle übrigen Wörter müssen gleich sein.
  - Der Musterwechsel beim Spielen wirkt am Ende des Takts. Die Prüfung wartete 3 s; wann der
    Takt endet, hängt vom Start ab (zwischen 3,8 und 4,8 s nach dem Drehen). Sie wartet jetzt
    bis die Nummer wechselt (höchstens 15 s).
  - Die Startbild-Proben liegen bei 0,12 / 0,16 / 0,2 s; der Hauptbildschirm kommt jetzt bei
    0,26 s (vorher 0,36 s), 0,3 s lag dahinter.
- **Gerätedateien:** die Patches haben sich nicht geändert. Neu gebaut mit `tools/patch/apply.mjs`
  (wie `assets/blechy/README.md`) sind sie bytegleich, deshalb nichts umbenannt:

| Gerätedatei (eigene Firmware) | sha256 |
|---|---|
| `SYSTEM-ringtest-splash.VSB` | `66d705741dd7ecc80aa8f19c40b50925277d98f151fe0ac7937acf3fb4bca584` |
| `SYSTEM-ringtest-mfx2.VSB` | `8c924715a315256ebbac6f3d8538477e92533a02acfde0777fb846f0cf1dc761` |
| `SYSTEM-ringtest-mfx2-blech.VSB` | `5de4b5840e0f163689053990acdffa4b882a6f702833a9886cdeb9fdcc8efa02` |
| `SYSTEM-ringtest-splash-mfx2-blech.VSB` | `db22ca6ec42233b4a16e20c59cdf7e3497d397afcf29ff7d79b6bc8a3b383ff3` |

## Zeitmessungen in `docs/messungen/`, die mit dem falschen Takt entstanden

Betroffen sind Werte, die die Firmware aus ihren Timer-Interrupts ableitet (Raten, Dauern von
Bildschirm-, LED- und Sequencer-Abläufen). Gerätezeit-Werte aus UART- oder SPI-Byte-Zeiten und
Messungen am Gerät nicht.

Neu gemessen und in den Dateien auf den jetzigen Stand gesetzt (gemessen, richtiger Takt):

| Datei | Wert vorher | gilt jetzt |
|---|---|---|
| `2026-10-10-haenger.md` | 260 bis 268 Bedienfeld-Nachrichten je Sekunde | 305 |
| `2026-10-08-led-execute.md` | RGB-LEDs 21-mal je Sekunde neu gesetzt | 25 |
| `2026-10-10-startphase.md` | Kontrast `0x81 0x22` bei 332 ms | 138 ms |
| `2026-10-10-mfx-umschalter.md` | Panel 72, Weiche 75, Setter-Haken 99, Hauptbildschirm 400 ms | 69, 72, 95, 260 ms |
| `2026-10-10-startbild-editor.md` | Proben 0,12 / 0,2 / 0,3 s | 0,12 / 0,16 / 0,2 s |

Der Wert in `2026-10-10-startbild-editor.md` (DSP-Upload bei 68,7 ms Original, 56,1 ms Patch)
gilt weiter: 68,66 und 56,04 ms, er liegt vor dem ersten Timer-Takt.

**Offen**, mit dem alten Takt gemessen und nicht neu gemessen; Dauern von Abläufen, die der
Sequencer oder die Bildschirm-Ticks takten, laufen jetzt bis zu 21 % kürzer (Faktor 0,79 bis 0,87
des alten Werts), reine Byte-Zeiten ändern sich nicht:

- `2026-10-10-mfx-umschalter.md`: Tick-Haken ab 341 ms.
- `docs/tastenkombinationen.md`: Gate-Arpeggiator (5 Noten in 1,5 s bei x=100, 15 bei x=900),
  PART ERASE (1 Note nach 0,1 s, 26 Byte nach 1 s, 75 nach 3 s), TAP (4 Taps im Abstand 0,65 s: 92,3 BPM).
- `2026-10-10-pattern-kette-import.md`: "Working..." 20 bis 30 s.
- `2026-10-09-din-sysex.md`: 9,4 s Gerätezeit für 16 KiB lesen, 2,3 s auf der emulierten Leitung
  (UART-Byte-Zeiten, vermutlich kaum betroffen).
- `2026-10-10-startphase.md`: "Working..." rund 2 ms nach der Bestätigung für 48 ms.
- Die Messungen, die den Sequencer-Takt oder "NEXT" abhängig vom Taktende nennen
  (`2026-10-10-mfx-umschalter.md`, Musterwechsel beim Spielen), gelten der Reihenfolge nach, nicht den Zeiten.

Am Gerät gemessene Werte (`2026-10-09-menuezustand.md`, `2026-10-09-flash-dump.md`,
`2026-10-08-geraeteprotokoll.md`) sind nicht betroffen.
