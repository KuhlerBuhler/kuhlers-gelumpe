# QEMU als DSP-Kern: Hybrid-Worker hinter BFIN9

Alles lief im Simulator auf dem Mac. Kein Gerät wurde angesprochen.

Marker: **gemessen** (Befehl lief, Zahl abgelesen), **gelesen** (Quelltext),
**hergeleitet** (aus Gemessenem und Gelesenem geschlossen), **geschätzt**.

## Kurz

- Der QEMU-Worker ist ein Hybrid: QEMU führt die Blackfin-Befehle aus, der
  GNU-Simulator läuft im selben Prozess als Bibliothek und behält Geräte, CEC,
  Zeit und das Protokoll BFIN9. Speicher ist geteilt, nicht kopiert.
- Alle 175 Worker-Tests sind mit ihm grün (Gruppen kern 27, host 81, dma 58,
  fork 9), ohne Eintrag in `qemu_gnu_only.txt` (**gemessen**).
- Ein Fallauf (0,3 s Modellzeit) endet bit-gleich mit dem GNU-Worker: gleiche
  JSON-Ausgabe, 123520781 DSP-Zyklen, gleiche PC, gleicher SPORT-Hash
  (**gemessen**).
- Tempo im Fallauf: 6,7 s statt 13,6 s (**gemessen**, Last 8 bis 15 auf dem
  Mac). Mit GNUs dsp32-Decodern in QEMU (Abschnitt 5) 6,4 s statt 12,9 s, in
  den DSP-Kernen 7,7 bis 9,7 mal schneller als GNU (Abschnitt 6). Die
  Rechenzeit in QEMU ist dabei klein; den Rest teilen sich das
  Warten auf den ARM und der Aufwand je Anfrage im GNU-Simulator (Abschnitt 4).
- Dauervergleich: 210000 Fuzz-Programme ohne Abweichung, 38/38 Funktionen
  mit je 20000 Aufrufen gleich auf Hacktribe und Stock (Abschnitt 7,
  **gemessen**).
- Gekoppelt mit dem ARM-Emulator: Fälle und Sample-Swap gleich, 10000
  Blöcke und alle 32 MFX-Typen je Firmware Anfrage für Anfrage gleich; der
  MFX-Lauf fand einen Fehler (veraltete Übersetzung nach neuem L1-Code),
  behoben in 855d30fd (Abschnitt 8, **gemessen**).
- Tempo nach Phase 6, Worker allein gegen Echtzeit: QEMU 6,7x langsamer
  (Hacktribe), GNU 62,9x; DSP-Kerne 11x schneller als GNU; gekoppelt mit
  dem ARM-Emulator 5 bis 6x schneller als GNU (Abschnitt 9, **gemessen**).
- Ohne `--worker` und ohne `BFIN_WORKER` läuft der QEMU-Worker, GNU nur auf
  Wahl oder als Rückfall ohne QEMU-Build ([Emulator](../emulator.md)).

## 1. Weg: Hybrid statt neuer Geräte

Die Phasen 3 und 4 des Plans sahen vor, HOSTDP, SysControl, SIC/CEC, DMA,
MDMA und SPORT als QEMU-Geräte nachzubauen. Der Hybrid spart das: der
GNU-Simulator bleibt der Rahmen, nur die Befehlsausführung wandert.

- Der GNU-Motor (`blech_bfin_engine`, Takt je Zyklus, Ereignisse, Wächter)
  gibt die Befehle zwischen zwei GNU-Ereignissen an QEMU ab
  (`tools/dsp/blackfin_hybrid.c.inc`). Budget = Zyklen bis zum nächsten
  Ereignis, höchstens bis Ende der Anfrage.
- QEMU zieht je Befehl die GNU-Taktkosten ab (`CYCLE_DELAY` aus
  `bfin-sim.c` im Prädekoder nachgebaut, `qemu-worker.patch`) und hält vor dem
  ersten Befehl an, der das Budget nicht mehr hat, an der Halte-PC oder nach
  N Befehlen (Wächter). Ein Lauf überschreitet nie das nächste Ereignis, also
  liegen Interrupts, DMA und Gerätezugriffe auf denselben Zyklen wie bei GNU
  (**hergeleitet**, durch den bit-gleichen Fallauf gestützt).
- An GNU zurück gehen: Zugriffe außerhalb von RAM (MMRs, über einen
  `tlb_fill`-Haken), CEC-Rückkehr und Modi, Systemregister, `CYCLES`,
  Ausnahmen, unbekannte Befehle, Sprung in den ROM. GNU führt diesen einen
  Befehl aus, danach rechnet wieder QEMU.
- Beobachtete Speicherfenster (Op 16) mappt QEMU nur ausführbar, Daten
  laufen dort über GNU, das sie zählt.
- `CLI` immer und `STI`, solange kein gelatchter Interrupt frei wird, rechnet
  QEMU über einen Rückruf in den GNU-CEC (`blech_cec_fast`). Ohne den Rückruf
  gab es 4415006 Rückgaben an GNU in 0,3 s, mit ihm 511 (**gemessen**). Das ausgelassene GNU-Ereignis findet in diesem Fall nichts
  (**gelesen**, `_cec_raise` mit `ivg == -1`).

## 2. Entscheidungen zu Phase 0

| Punkt | Entscheidung | Beleg |
|---|---|---|
| 0.1 Schrittsteuerung | Eigene Schleife: das Board ruft `cpu_exec` aus dem GNU-Motor, Budget im TCG-Prolog jedes Befehls; kein `icount` | `run_stops_at_a_requested_pc`, `rom_entry_at_the_instruction_budget_is_still_a_failure` grün (**gemessen**) |
| 0.1 Overhead | rund 0,65 µs je QEMU-Lauf inklusive Rechnen | 1,13 Mio. Läufe, 159 von 1431 Samples des Hauptfadens in `cpu_exec` bei 6,7 s (**hergeleitet** aus `sample`) |
| 0.2 Fork | `fork()` des ganzen Prozesses wie bisher; QEMU läuft einfädig (`-accel tcg,thread=single`), der Motor auf dem Hauptfaden | Gruppe fork 9/9 grün (**gemessen**) |
| 0.3 Kanal | unverändert aus `blackfin_worker.c` auf dem Hauptfaden, stdin/stdout und `--channel` | Kanal-Test in Gruppe fork grün (**gemessen**) |
| 0.6 Taktmodell | GNU-Taktkosten in QEMU, gleiche Synchronpunkte | Fallauf bit-gleich, Abweichung 0 Zyklen (**gemessen**) |
| 0.7 Anfragegrößen | 1,13 Mio. QEMU-Läufe für 121,8 Mio. Zyklen, im Mittel 108 Zyklen je Lauf; eine Op-18-Verteilung wurde nicht aufgezeichnet | `BLECH_HYBRID_STATS` (**gemessen**) |

## 3. Was nur GNU kann

Nichts in den Worker-Tests. Im Hybrid bleibt GNU ohnehin für Geräte und
Sonderbefehle zuständig; `qemu_gnu_only.txt` ist leer.

Offen (**hergeleitet**, nicht getestet): QEMU prüft im Port keine
Ausrichtung (`gen_align_check` kehrt früh zurück). Ein falsch ausgerichteter
Zugriff auf RAM löst daher keine Ausnahme aus, GNU schon. Die Firmware tut das
im Fallauf nicht (sonst wäre der Lauf nicht bit-gleich), ein fehlerhafter
Patch aber vielleicht.

## 4. Wohin die Zeit geht

`sample` am QEMU-Prozess, 3 s mitten im Fallauf, Hauptfaden 1431 Samples
(**gemessen**):

| Teil | Samples |
|---|---:|
| Warten auf den ARM (`blech_ring_read`, `poll`) | 591 |
| `sim_resume` gesamt | 660 |
| davon `sim_module_resume` / `suspend` (`getrusage`, Uhr) | 255 |
| davon QEMU (`cpu_exec`) | 159 |

Der Aufwand je Anfrage (`setjmp` mit Signalmaske, `getrusage`) liegt im
GNU-Rahmen und trifft beide Worker gleich. Er ist die nächste Stellschraube
(Phase 6), nicht die Befehlsausführung.

## 5. Befehle wie GNU (Phase 2)

Prüfwerkzeug `tools/dsp/qemu_compare.py`:

- 38 DSP-Funktionen (Filterkerne, Inserts, Master-Effekte), je 2000 Aufrufe mit
  festen Registern auf einem gefüllten Kontext. Beide Worker müssen im Speicher
  (FNV-1a) und in jedem Register samt ASTAT und CYCLES gleich enden.
  Ergebnis: 38/38 gleich auf Hacktribe und Stock (**gemessen**, Build 25b608d2).
- `--fuzz N --fuzz-length L`: N kurze Programme aus zufälligen ALU-, Shift- und
  DSP-Befehlen ohne Speicherzugriff, zufällige Startregister. Ein Befehl, den
  GNU ablehnt, muss auch in QEMU eine Ausnahme werfen.

| Länge | Seeds | Programme je Seed | abweichend | nur GNU wirft |
|---:|---|---:|---:|---:|
| 1 | 21, 22 | 3000 | 0 | 0 |
| 4 | 21, 22 | 3000 | 0 | 0 |
| 8 | 21 | 3000 | 0 | 0 |

(**gemessen**, Build 25b608d2.) Fuzz-Zahlen von vor Commit c03cf455 gelten
nicht: eine Anfrage, die an einem Wächter-Halt endete, ließ den nächsten
Befehl in GNU laufen, der Vergleich lief also teils GNU gegen GNU.

Was in QEMU angeglichen ist (`qemu-worker.patch`, **gelesen** und per Fuzz
**gemessen**):

- `R += imm`: der Lazy-ASTAT-Weg las ein überschriebenes Argument und setzte VS.
- `CC = A0 <, <=, == A1`: setzt wie GNU AZ, AN, AC0; Bits x/y ungleich 0 sind illegal.
- `>>>=`, `>>=`, `<<=` mit Register-Count: GNUs C-Code als Helfer, auch für
  Counts über 31 und negative. Bei `>>=` mit Count über 31 lässt GNU die Flags
  stehen.
- ALU2op opc 6/7 und PTR2op opc 2 sind illegal wie in GNU.
- MAC und MULT: QEMU rechnet selbst, die Legalität kommt aus GNUs Decoder
  (Probe beim Übersetzen). Ohne Probe führt QEMU 1615 von 3000 zufälligen
  MAC-Kodierungen aus, die GNU ablehnt (**gemessen**).

### dsp32alu, dsp32shift, dsp32shiftimm: GNUs Decoder in QEMU

Diese drei Klassen rechnet QEMU mit GNUs eigenem C-Code. `build_qemu.py`
kopiert beim Bauen `decode_dsp32alu_0`, `decode_dsp32shift_0`,
`decode_dsp32shiftimm_0` und ihre Helfer (add16, lshift, saturate_s40 usw.)
aus `sim/bfin/bfin-sim.c` nach `target/bfin/bfin-gnu-dsp32-gen.c.inc`;
`tools/dsp/bfin_gnu_dsp32.c.inc` bildet GNUs Registerzugriffe auf den
QEMU-Zustand ab, auch das verzögerte Schreiben (`STORE`) bis zum Befehlsende.
QEMU ruft das je Befehl als `HELPER(dsp32_port)`, ohne die GNU-Bibliothek.

An GNU geht nur noch die Legalität: beim Übersetzen läuft GNUs Decoder einmal
als Probe; lehnt GNU ab, geht der Befehl als Ausnahme an GNU.

QEMUs eigener TCG-Code für diese Klassen bleibt für den Vergleich
(`BLECH_QEMU_DSP32=1`, Anhang), der Aufruf der GNU-Bibliothek je Befehl für die
Zeitmessung (`BLECH_QEMU_DSP32_GNU=1`).

Mit dem Standardweg (Build 892dfd39, **gemessen**):

| Prüfung | Ergebnis |
|---|---|
| `--fuzz-class` alu, shift, shiftimm, mac, mult, Seed 2, je 3000 | 0 abweichend, 0 nur GNU wirft |
| `--fuzz-class` alu, shift, shiftimm, Seed 7, je 3000 | 0 abweichend, 0 nur GNU wirft |
| `--fuzz 2000 --fuzz-length 4`, Seed 23 | 0 abweichend, 0 nur GNU wirft |
| `--fuzz 1000 --fuzz-length 8`, Seed 24 | 0 abweichend, 0 nur GNU wirft |
| 38 Funktionen, Hacktribe und Stock | 38/38 gleich |
| Worker-Tests `qemu_worker_tests.sh alle` | 175/175 grün |

## 6. Zeit je dsp32-Weg

Build 892dfd39, Hacktribe-VSB, je 3 Läufe, Median (**gemessen**, Last bis 8,8
auf 10 Kernen, Load-Gate davor). Wege für dsp32alu/shift/shiftimm:

- "GNU-Port" = Standard, GNUs Decoder in QEMU (Abschnitt 5);
- "TCG" = `BLECH_QEMU_DSP32=1`, QEMUs eigener Code, weicht ab (Anhang);
- "GNU-Bibliothek" = `BLECH_QEMU_DSP32_GNU=1`, Aufruf in die GNU-Bibliothek je
  Befehl mit Kopie von 16 Registern.

Fallauf 0,3 s Modellzeit (`blackfin_cases.py --seconds 0.3`, Wanduhr):

| Worker | Zeit | Ausgabe |
|---|---:|---|
| GNU | 12,9 s | Referenz |
| QEMU GNU-Port | 6,4 s | gleich wie GNU |
| QEMU TCG | 6,5 s | gleich wie GNU |
| QEMU GNU-Bibliothek | 7,6 s | gleich wie GNU |

Bench-Funktionen (`qemu_compare.py --calls 20000`, Rechenzeit im Worker, GNU
aus den Läufen des GNU-Port-Wegs):

| Funktion | GNU | GNU-Port | TCG | GNU-Bibliothek |
|---|---:|---:|---:|---:|
| Filterkern electribe | 0,566 s | 0,066 s (8,6x) | 0,050 s (11,3x) | 0,414 s (1,4x) |
| Filterkern OB | 0,607 s | 0,079 s (7,7x) | 0,055 s (11,0x) | 0,547 s (1,3x) |
| Master Hall/Plate Reverb | 1,556 s | 0,191 s (8,1x) | 0,170 s (9,1x) | 0,862 s (1,8x) |
| Master Room Reverb | 1,506 s | 0,156 s (9,7x) | 0,128 s (12,1x) | 0,843 s (1,8x) |

Der GNU-Port kostet gegenüber TCG 10 bis 40 % in den Kernen: ein Helferaufruf
je Befehl, der die Kodierung zur Laufzeit zerlegt, statt fest übersetztem Code
(**hergeleitet**). Für `--min-speedup 10` (Phase 6) fehlen in drei Kernen noch
bis zu 25 %; Weg dahin wäre, häufige Befehle dieser Klassen wieder als TCG zu
übersetzen, sobald ihr TCG-Code GNU-gleich ist (**Urteil**).

Alle vier Wege enden im Fallauf mit derselben Ausgabe (md5 gleich): die
Abweichungen aus dem Anhang treten in diesem Lauf nicht auf (**gemessen**).

## 7. Dauervergleich

Build 892dfd39 (Standardweg GNU-Port), alles gegen den GNU-Worker,
Load-Gate vor jedem Schritt (**gemessen**):

| Lauf | Programme | Abweichend | Nur in GNU illegal |
|---|---:|---:|---:|
| Klasse alu, Seed 101 | 30000 | 0 | 0 |
| Klasse shift, Seed 101 | 30000 | 0 | 0 |
| Klasse shiftimm, Seed 101 | 30000 | 0 | 0 |
| Klasse mac, Seed 101 | 30000 | 0 | 0 |
| Klasse mult, Seed 101 | 30000 | 0 | 0 |
| gemischt, 1 Befehl, Seed 201 | 10000 | 0 | 0 |
| gemischt, 4 Befehle, Seed 204 | 10000 | 0 | 0 |
| gemischt, 8 Befehle, Seed 208 | 10000 | 0 | 0 |
| gemischt, 16 Befehle, Seed 2016 | 10000 | 0 | 0 |

| Lauf | Ergebnis |
|---|---|
| 38 Funktionen Hacktribe, je 20000 Aufrufe | 38/38 gleich, Summe GNU 17,5 s, QEMU 2,1 s |
| 38 Funktionen Stock, je 20000 Aufrufe | 38/38 gleich, Summe GNU 17,3 s, QEMU 2,1 s |
| Worker-Tests `qemu_worker_tests.sh alle` | 175/175 grün |

Der Patch `tools/dsp/qemu-worker.patch` ist gleich `git diff` im
Entwicklungsbaum; `build_qemu.py` wendet ihn bei jedem Build auf einen frisch
ausgecheckten ae8fe9a an, der Build für diese Läufe lief so durch
(**gemessen**).

## 8. Gekoppelt mit dem ARM-Emulator (Phase 5)

Firmware: die Test-VSBs `BLECH-Sample-Swap-Native-DSP-2026-11-14-Guard`
(hacktribe, stock), ARM-Emulator mit DSP-Worker, Load-Gate vor jedem Lauf.

### Fälle und Sample-Swap

| Lauf | GNU | QEMU | Ergebnis |
|---|---:|---:|---|
| `blackfin_cases.py` 1 s, Hacktribe | 29,6 s | 15,8 s | JSON gleich |
| `blackfin_cases.py` 1 s, Stock | 27,7 s | 11,5 s | JSON gleich |
| `blackfin_swap_cases.py`, Hacktribe | 122,1 s | 35,1 s | JSON gleich |
| `blackfin_swap_cases.py`, Stock | 156,0 s | 45,5 s | JSON gleich |
| `blackfin_cases.py` 3 s, Rauschen, Hacktribe | 61,0 / 62,3 s | 18,6 bis 48,2 s (25 Läufe) | gleicher SPORT-Hash 1984276293, gleicher Verkehr |
| `blackfin_cases.py` 3 s, Rauschen, Stock | 59,4 / 60,2 s | 11,8 / 13,1 s | gleich |

Nach 1 s ist der Hauptbildschirm noch nicht erreicht; beide Worker melden
das gleich (`ok: false`, gleiche Ausgabe). Die QEMU-Zeiten im 3-s-Fall
schwanken mit der Last: 32 bis 48 s bei Last 5 bis 8, 19 bis 21 s bei Last 4
(**gemessen**).

### Ausfall im 3-s-Fall: Ruhezustand, kein Hänger

Ein Lauf (Hacktribe, QEMU) endete mit `Blackfin worker deadline exceeded`
bei ARM-Zeit 0,76 s nach 140,5 s. 25 Wiederholungen mit Zeitmessung jeder
Anfrage liefen durch; die längste Einzelanfrage je Lauf lag zwischen 0,010
und 0,126 s (Op 18 oder 20), keine über 1 s (**gemessen**). Das
Energieprotokoll (`pmset -g log`) zeigt den Grund: der Lauf begann
22:04:56, der Mac ging 22:05:01 in den Ruhezustand (Deckel zu) und wachte
22:07:16 auf, genau zur Fehlermeldung. `time.monotonic` zählt die
Ruhezeit mit, also lief die 15-s-Frist beim Aufwachen ab (**gemessen**).

### Blöcke

`qemu_blocks.py` zeichnet die gekoppelte Sitzung auf dem GNU-Worker auf:
jede Anfrage mit dem Hash ihrer Antwort, nach je 64 SPORT-TX-Frames
(1,33 ms) ein Abbild aus allen 54 Registern und L1, alle 1000 Blöcke und am
Ende auch 32 MiB SDRAM. Danach gehen dieselben Anfragen an den
QEMU-Worker; die erste abweichende Antwort beendet den Lauf. A0.X und A1.X
zählen nur mit 8 Bit: GNU legt nach manchen Befehlen 32 Bit ab
(`SET_AREG32` ergibt 0xffffffff), liest aber in jedem Befehl nur die unteren
8 Bit (**gelesen**, `get_extended_acc`, `get_allreg`, `bfin-sim.c`).

Build f43f9829 (vor dem Fix unten), Eingang Stille:

| Firmware | Blöcke | Anfragen | Ergebnis | Vergleich |
|---|---:|---:|---|---:|
| Hacktribe | 10000 | 2121005 | gleich | 362,7 s |
| Stock | 10000 | 2098568 | gleich | 381,8 s |

Gegenprobe: in einer Aufnahme von 50 Blöcken ein ASTAT-Hash bei Anfrage
35220 verfälscht; der Vergleich meldet genau diese Anfrage, Register
ASTAT, Block 1 (**gemessen**).

### Master-Effekte

`qemu_blocks.py --mfx 0-31`: nach dem Boot jeden MFX TYPE mit Korgs Setter
(0xC0048A64) setzen, Pad 1 auf Rauschen spielen, 0,4 s, Abbild je Typ.

Build 855d30fd:

| Firmware | Typen | Blöcke | Anfragen | Ergebnis |
|---|---:|---:|---:|---|
| Hacktribe | 32 | 10714 | 8650507 | gleich, SEQSTAT 0, 32 verschiedene TX-Hashes |
| Stock | 32 | 10714 | 8613030 | gleich, SEQSTAT 0, 32 verschiedene TX-Hashes |

Die 6 Effekte, die in den Code der Effekt-Bausteine springen, sind darin
enthalten, wenn ihre Einheiten (0x34, 0x3c bis 0x40) unter den Typen 0 bis
31 liegen (**hergeleitet**, Zuordnung Typ zu Einheit nicht gemessen).

Der erste Lauf fand einen Fehler im QEMU-Worker: beim Typwechsel lädt der
DSP neuen Code nach L1 (0xFFA0xxxx), QEMU lief weiter mit der alten
Übersetzung (Typ 1, Block 535, beide Firmwares). Gefunden mit
Einzelschritten im Gleichlauf: bei 0xffa04612 steht `I0 = R0` (0x3400),
GNU setzt I0, QEMU setzte P0. `tb_invalidate_phys_range` erwartet
ram-Adressen; der Worker gab Gastadressen weiter, die nur für das SDRAM
ab 0 gleich sind. Fix 855d30fd rechnet über die Speicherregion um; neuer
Worker-Test `test_rewritten_l1_code_runs_the_new_instructions` ist ohne
Fix rot bei 0xFFA00000 und grün im SDRAM, mit Fix grün; Worker-Tests
176/176 (**gemessen**).

### Zeit

Ein Block hat bei 516,096 MHz und 48 kHz ein Budget von 10752 Takten je
Sample, 688128 je Block (**hergeleitet**). Gegen Echtzeit gemessen: die
Hacktribe-Aufnahme der 10000 Blöcke (14,84 s Modellzeit) noch einmal
abgespielt, gezählt nur die Zeit der Vorlauf-Anfragen (Op 18 und 20), ohne
ARM-Emulator, Last 6,7 bis 8 (**gemessen**):

| Worker | Zeit Vorlauf | Echtzeitfaktor | DSP-Takte je Sekunde |
|---|---:|---:|---:|
| GNU | 781,8 s | 52,7x langsamer | 9,8 Mio. |
| QEMU | 365,1 s | 24,6x langsamer | 21,0 Mio. |

Im Fallauf mit ARM-Emulator braucht QEMU für 3 s Modellzeit 12 bis 21 s
bei Last 2 bis 4 (Abschnitt Fälle), also 4 bis 7x Echtzeit; dort läuft der DSP
oft im Leerlauf, den GNU in einem Schritt überspringt (**hergeleitet**).
Gegenüber den DSP-Kernen allein (7,7 bis 9,7x, Abschnitt 6) gewinnt QEMU
hier nur 2,1x: 2,1 Mio. Anfragen kosten je etwa 0,17 ms, und jede läuft
durch den GNU-Simulator (Ereignisse, Geräte, Protokoll), siehe Abschnitt 4
(**hergeleitet**). Das ist der Ansatzpunkt für Phase 6.

Bei diesem Abspielen ohne die Abbild-Lesungen beendete sich der GNU-Worker
einmal ohne Antwort; mit Abbild-Lesungen lief er durch. Nicht weiter
verfolgt, das Messwerkzeug lag im Scratchpad (**gemessen**).

## 9. Tempo (Phase 6)

### Wo die Zeit hing

Ein Profil (`sample`, Hacktribe-Aufnahme 1000 Blöcke abgespielt) zeigte
nach Phase 5 nur 9 % der Worker-Zeit im DSP-Code. Der Rest war Verwaltung
je Anfrage in der GNU-Bibliothek: Wanduhr über `getrusage` 23 %,
`setjmp`/`longjmp` mit Signalmaske 20 %, JIT-Schreibschutz je übersetztem
Block 7 %, `getenv` 3 % (**gemessen**). Gekürzt in b1c14184 und cd0e8f47,
danach TB-Invalidierung nur für Seiten mit Code (ca953c74) und die
Speicherzuordnung einmal je Pufferlauf statt je Byte (4dd2e813). Das
Abspielen der 1000 Blöcke fiel von 50,8 s auf 21,7 s (**gemessen**).

Der Poll-Event der GNU-Bibliothek (`SIM_EVENTS_POLL_RATE` 0x1000, prüft nur
Strg-C) beendete alle 4096 Takte einen QEMU-Lauf. Mit 0x40000000
(2b8653f8) stieg der Kernvergleich auf Hacktribe von 3,6x auf 8,9x
(**gemessen**).

In den DSP-Kernen selbst (MultiModeFilter) lagen danach 48 % in GNUs
dsp32-Decoder und 18 % in MAC (**gemessen**). Ein Histogramm über 65 Mio.
dsp32-Befehle nannte drei Formen mit zusammen etwa 37 %:
`Rd = Rs +/- Rt (S)` (c404/cc04), `Rd = (A0 += A1)` (c40b/cc0b) und
`An >>>= imm` (c683). dc70acc3 rechnet die erste als TCG, die beiden
anderen als eigene Helper mit GNUs Code ohne den Decoder-Weg. Je Form lief
ein gezielter Fuzz, auch als Bündel, ohne Abweichung (**gemessen**).

Nicht umgesetzt: Register-Sicherung nur bei Bündeln mit Konflikt (6.1).
Selbst ganz ohne Sicherung liefen die 21 Kerne, die dabei gleich bleiben,
nicht schneller (0,465 s mit, 0,592 s ohne, unter Last, **gemessen**).
MAC/MULT als TCG (6.2) entfiel, weil die Helper im gekoppelten Abspielen
0,7 % der Worker-Zeit kosten (**gemessen**).

Prüfung nach jedem Schritt: Worker-Tests 176/176, Fuzz aller Klassen ohne
Abweichung, 38/38 Funktionen auf Hacktribe und Stock, 10000 Blöcke und
3-s-Fälle gleich GNU (**gemessen**).

### Endstand gegen Echtzeit

Gemessen nacheinander, jeder Lauf erst bei mehr als 70 % freier CPU laut
`top`; die Spalte nennt den Wert direkt vor dem Lauf. Die Load Average
blieb dabei bei 8 bis 18, sie zählt auf dem Mac wartende Threads mit
(**gemessen**).

Worker allein: die Aufnahme der 10000 Blöcke (14,84 s Modellzeit) noch
einmal abgespielt, gezählt nur die Vorlauf-Anfragen (Op 18 und 20), ohne
ARM-Emulator (`realtime.py`, **gemessen**):

| Firmware | Worker | Vorlauf | gegen Echtzeit | frei |
|---|---|---:|---:|---:|
| Hacktribe | GNU | 933,1 s | 62,9x langsamer | 77,8 % |
| Hacktribe | QEMU | 98,9 s | 6,7x langsamer | 70,7 % |
| Stock | GNU | 954,8 s | 64,3x langsamer | 74,2 % |
| Stock | QEMU | 152,2 s | 10,3x langsamer | 71,1 % |

QEMU ist hier 9,4x (Hacktribe) und 6,3x (Stock) schneller als GNU. Vor
Phase 6 brauchte QEMU für dieselbe Hacktribe-Aufnahme 365,1 s, also 24,6x
langsamer als Echtzeit (Abschnitt 8). Der Stock-Lauf endete mit Load 18;
ob die Lücke zu Hacktribe an der Last oder an der Firmware liegt, ist
nicht geprüft.

DSP-Kerne allein (`qemu_compare.py --bench --min-speedup 10`, 38
Funktionen, Prüfsummen gleich, **gemessen**):

| Firmware | GNU | QEMU | schneller | frei |
|---|---:|---:|---:|---:|
| Hacktribe | 1,797 s | 0,164 s | 10,96x | 77,9 % |
| Stock | 2,066 s | 0,183 s | 11,29x | 73,1 % |

Unter Last (Load 7 bis 10, vor der Ruhemessung) waren es 10,45x und 10,8x;
der Abstand zur Schwelle 10 ist klein (**gemessen**).

Gekoppelt mit dem ARM-Emulator: `blackfin_cases.py`, 3 s Modellzeit, je
Worker zweimal in der Folge GNU, QEMU, QEMU, GNU. Gemessen ist die ganze
Laufzeit des Befehls, also mit Start, Booten und ARM-Emulator. Alle acht
Ausgaben sind gleich und gleich der GNU-Referenz aus Phase 5 (**gemessen**):

| Firmware | Worker | Laufzeit | gegen Echtzeit | frei |
|---|---|---:|---:|---:|
| Hacktribe | GNU | 71,5 / 73,5 s | 24x langsamer | 79,0 / 74,5 % |
| Hacktribe | QEMU | 13,9 / 14,8 s | 4,8x langsamer | 72,5 / 79,5 % |
| Stock | GNU | 69,9 / 64,7 s | 22x langsamer | 72,7 / 82,8 % |
| Stock | QEMU | 12,5 / 9,4 s | 3,7x langsamer | 83,9 / 85,0 % |

Gekoppelt ist QEMU damit 5,0x (Hacktribe) und 6,1x (Stock) schneller als
GNU (**hergeleitet** aus den Mittelwerten). Diese Fälle sind ein Start bis
zum Hauptbild, der DSP läuft dabei oft im Leerlauf; das Abspielen oben ist
Last mit Noten. Die beiden Zahlen gegen Echtzeit messen also verschiedene
Lasten und lassen sich nicht direkt verrechnen.

Bewertung des 10x-Ziels (**Urteil**): erreicht in den DSP-Kernen, knapp.
Der Worker allein liegt bei 6 bis 9x, gekoppelt bei 5 bis 6x. Wie viel
der gekoppelten Zeit auf ARM-Emulator und Python entfällt, ist in diesem
Lauf nicht gemessen. Echtzeit erreicht keiner der Wege.

## Nachstellen

```bash
python3 tools/dsp/build_qemu.py ~/gelumpe-dsp/worker --jobs 6
BFIN_WORKER=~/gelumpe-dsp/worker/qemu-bfin-worker tools/dsp/qemu_worker_tests.sh alle
tools/emu/.venv/bin/python tools/emu/blackfin_cases.py --vsb <hacktribe SYSTEM.VSB> \
  --worker ~/gelumpe-dsp/worker/qemu-bfin-worker --core-hz 516096000 --seconds 0.3
```

Vergleich und Fuzz (Abschnitt 5), Anhang mit QEMUs eigenem Code:

```bash
tools/emu/.venv/bin/python tools/dsp/qemu_compare.py <SYSTEM.VSB> --gnu ~/gelumpe-dsp/gnu/blackfin-worker \
  --qemu ~/gelumpe-dsp/worker/qemu-bfin-worker
tools/emu/.venv/bin/python tools/dsp/qemu_compare.py --fuzz 3000 --seed 21 --fuzz-length 4 --gnu ... --qemu ...
tools/emu/.venv/bin/python tools/dsp/qemu_compare.py --fuzz 3000 --seed 2 --fuzz-class alu --gnu ... --qemu ...
tools/emu/.venv/bin/python tools/dsp/qemu_compare.py <SYSTEM.VSB> --calls 20000 --gnu ... --qemu ...
tools/emu/.venv/bin/python tools/dsp/qemu_compare.py <SYSTEM.VSB> --blocks 10000 --gnu ... --qemu ...
tools/emu/.venv/bin/python tools/dsp/qemu_blocks.py <SYSTEM.VSB> --mfx 0-31 --gnu ... --qemu ...
tools/emu/.venv/bin/python tools/dsp/qemu_compare.py <SYSTEM.VSB> --gnu ... --qemu ... --bench --min-speedup 10
BLECH_QEMU_DSP32=1 tools/emu/.venv/bin/python tools/dsp/qemu_compare.py --fuzz 3000 --seed 2 --fuzz-class alu --gnu ... --qemu ...
```

`BLECH_HYBRID_STATS=<präfix>` schreibt je Worker-Prozess die Zähler (QEMU-Läufe,
QEMU-Zyklen, GNU-Schritte, Rückgaben) nach `<präfix>.<pid>`. Das kostet bei
jeder Anfrage einen Dateizugriff und verfälscht die Laufzeit (81 s statt
6,7 s), also nur zum Zählen.

## Anhang: Abweichungen von QEMUs eigenem dsp32-Code

`qemu_compare.py --fuzz 3000 --seed 2 --fuzz-class KLASSE` mit
`BLECH_QEMU_DSP32=1`, Build 25b608d2 (**gemessen**). Je Gruppe gleicher
Opcode-Felder ein Beispiel: n = Treffer der Gruppe, Eingabe = Startwerte der
im Befehl genannten Register und ASTAT, rechts GNU / QEMU, Flags als
`Name GNU/QEMU`. Die Spalte "nur in GNU illegal" gilt ohne Probe; mit Probe
(Build 892dfd39) ist sie 0, die Abweichungen sind dieselben 180/11/90. Der
Standardweg (GNU-Port) hat keine dieser Abweichungen (Abschnitt 5,
**gemessen**).

Weitere Klassen, gleicher Lauf: mac 0 abweichend, aber 1615 von 3000
Kodierungen nur in GNU illegal (mit GNU-Probe 0); mult 0 und 0.

### alu (180 von 3000 abweichend, 62 Gruppen; dazu 827 nur in GNU illegal)

| n | Befehl | Eingabe | GNU / QEMU |
|---:|---|---|---|
| 6 | `c422 45df` `R2.H = R3.L + R7.H (NS);` | R2=0x35335982 R3=0xdc493225 R7=0x158aae4b ASTAT=0x22143 | ASTAT AZ 0/1, AN 0/1 |
| 6 | `c404 8f73` `R5 = R6 + R3, R7 = R6 - R3 (NS);` | R3=0x24c35541 R5=0xd42d74c3 R6=0xb3f5b4cb R7=0x4bf8f253 ASTAT=0x301300e | ASTAT V_COPY 0/1, V 0/1 |
| 6 | `c423 a055` `R0.H = R2.H - R5.L (S);` | R0=0x46e4ddf7 R2=0xb2a02a3 R5=0x9387cc0 ASTAT=0x92001 | ASTAT AZ 0/1, AN 1/0 |
| 6 | `c400 85d8` `R2 = R3 -|+ R0;` | R0=0x98858e00 R2=0xcfebad98 R3=0xb7741292 ASTAT=0x104300e | ASTAT AC0_COPY 0/1, V_COPY 0/1, AC0 0/1, V 0/1 |
| 5 | `c40b 0e7a` `R7 = (A0 += A1);` | R7=0xd8aac397 A0.X=0x36 A0.W=0xfb52a649 A1.X=0xcc A1.W=0xc9828d5 ASTAT=0x3080008 | R7 0x7fffffff / 0x7eacf1e; ASTAT AC0_COPY 1/0, AC0 1/0 |
| 5 | `c403 67fb` `R3.L = R7.L - R3.H (S);` | R3=0xe322c08a R7=0xd3532bae ASTAT=0xc1105 | ASTAT AZ 0/1, AC0_COPY 0/1, AC0 0/1 |
| 4 | `c42e 4194` `A1 = -A1;` | A1.X=0xd A1.W=0xb630fafb ASTAT=0xc2001 | ASTAT AZ 0/1, AN 1/0, AC1 0/1, AV1 0/1 |
| 4 | `c402 ae9e` `R7.L = R3.H + R6.L (S);` | R3=0x3f4df7ed R6=0x78937a86 R7=0xce140339 ASTAT=0xb3105 | R7 0xce147fff / 0xce14b9d3; ASTAT AZ 0/1, AC0_COPY 0/1, V_COPY 1/0, AC0 0/1, V 1/0, VS 1/0 |
| 4 | `c422 69bc` `R4.H = R7.L + R4.H (S);` | R4=0x8ab873c5 R7=0x785b8688 ASTAT=0x10d316f | R4 0x800073c5 / 0x114073c5; ASTAT AZ 0/1, VS 1/0 |
| 4 | `c403 0a81` `R5.L = R0.L - R1.L (NS);` | R0=0xb28fc088 R1=0xf101a4ff R5=0x5eb9d9a9 ASTAT=0x303214a | ASTAT AN 0/1, AC0_COPY 1/0, V_COPY 0/1, AC0 1/0, V 0/1 |
| 4 | `c408 af1f` `A1 = A1 (S), A0 = A0 (S);` | A0.X=0xac A0.W=0x4cff1c32 A1.X=0x1f A1.W=0x83968b3f ASTAT=0xd2103 | ASTAT AZ 0/1, AV0S 1/0 |
| 4 | `c406 8839` `R4 = ABS R7 (V);` | R4=0x69699083 R7=0xa09f04b5 ASTAT=0x3052129 | ASTAT V_COPY 0/1, V 0/1 |
| 4 | `c40b 484a` `R4.L = (A0 += A1);` | R4=0xce5957f2 A0.X=0x9a A0.W=0x15e7691f A1.X=0x69 A1.W=0xaf347b0a ASTAT=0x2062021 | R4 0xce597fff / 0xce59e429; ASTAT AZ 0/1, AC0_COPY 1/0, V_COPY 1/0, AC0 1/0, V 1/0 |
| 4 | `c423 0b32` `R5.H = R6.L - R2.L (NS);` | R2=0x9f8233b5 R5=0xc760692a R6=0x8236107c ASTAT=0x2083105 | ASTAT AZ 0/1, AN 1/0, AC0_COPY 0/1, AC0 0/1 |
| 4 | `c403 8281` `R1.L = R0.H - R1.L (NS);` | R0=0xb89bfcb6 R1=0x512ae41b ASTAT=0x309114c | ASTAT AN 1/0, AC0_COPY 0/1, V_COPY 0/1, AC0 0/1, V 0/1 |
| 4 | `c410 c142` `A1 = ABS A1, A0 = ABS A0;` | A0.X=0x8c A0.W=0x76f76005 A1.X=0x66 A1.W=0xbba591e8 ASTAT=0x309100c | ASTAT AV0 0/1 |
| 4 | `c430 06b3` `A1 = ABS A0;` | A0.X=0x45 A0.W=0xe2b5b152 A1.X=0xec A1.W=0x49dca571 ASTAT=0x302116c | A1.X 0x45 / 0xec; A1.W 0xe2b5b152 / 0x49dca571 |
| 4 | `c423 ea54` `R5.H = R2.H - R4.H (S);` | R2=0x6a48125b R4=0xd9f27878 R5=0xe299fd9 ASTAT=0x103216b | R5 0x7fff9fd9 / 0x90569fd9; ASTAT AZ 0/1, AN 0/1, VS 1/0 |
| 4 | `c403 e934` `R4.L = R6.H - R4.H (S);` | R4=0x72bdf545 R6=0xf5aef465 ASTAT=0x10b300d | ASTAT AZ 0/1, AN 1/0, V_COPY 0/1, V 0/1 |
| 3 | `c408 6576` `A1 = A1 (S);` | A0.X=0x59 A1.X=0xc1 A1.W=0x2a9a6fa ASTAT=0xd1004 | A0.X 0x59 / 0xff; A1.X 0xff / 0x0; ASTAT AN 1/0 |
| 3 | `c402 65de` `R2.L = R3.L + R6.H (S);` | R2=0x2f1a4b2c R3=0x53750859 R6=0x91efe692 ASTAT=0x53106 | ASTAT AC0_COPY 0/1, AC0 0/1 |
| 3 | `c403 cc8d` `R6.L = R1.H - R5.H (NS);` | R1=0x334cbac3 R5=0x96f612b3 R6=0x5cd0dffc ASTAT=0x22000 | ASTAT AN 1/0, V_COPY 1/0, V 1/0, VS 1/0 |
| 3 | `c42e 0ed1` `A1 = -A0;` | A0.X=0x9e A0.W=0x136bdaff A1.X=0xea A1.W=0x7c76c91c ASTAT=0x301310f | ASTAT AZ 0/1, AN 0/1, AC1 0/1 |
| 3 | `c40b ced0` `A0 -= A1;` | A0.X=0x5c A0.W=0x40b48687 A1.X=0xe9 A1.W=0x495b91c5 ASTAT=0x30a304d | ASTAT AZ 0/1, AC0_COPY 0/1, AC0 0/1 |
| 3 | `c422 8b4d` `R5.H = R1.H + R5.L (NS);` | R1=0x6d414739 R5=0xb9e6ac7a ASTAT=0x72000 | ASTAT AC0_COPY 1/0, AC0 1/0 |
| 3 | `c402 06ce` `R3.L = R1.L + R6.L (NS);` | R1=0xe10fd108 R3=0x373554a4 R6=0xc6fe7549 ASTAT=0x304116f | ASTAT AZ 0/1, AN 0/1, V_COPY 0/1, V 0/1 |
| 3 | `c422 e33b` `R1.H = R7.H + R3.H (S);` | R1=0x111a0f10 R3=0x370284ea R7=0x71bbe312 ASTAT=0x107310e | R1 0x7fff0f10 / 0xa8bd0f10; ASTAT AN 0/1, AC0_COPY 0/1, AC0 0/1, VS 1/0 |
| 3 | `c40b 8c19` `A0 += A1;` | A0.X=0xf8 A0.W=0x7c709e51 A1.X=0x8d A1.W=0xe7f2ff36 ASTAT=0x100310d | ASTAT AZ 0/1, AN 1/0 |
| 3 | `c422 cd50` `R6.H = R2.H + R0.H (NS);` | R0=0xac2f5650 R2=0x9c4e5282 R6=0x51240427 ASTAT=0x2083124 | ASTAT V_COPY 1/0, V 1/0 |
| 3 | `c408 4094` `A1 = 0;` | A0.X=0xd5 A0.W=0x6cefa972 A1.X=0x25 A1.W=0xd93e9488 ASTAT=0x306302c | A0.X 0xd5 / 0x0; A0.W 0x6cefa972 / 0x0; A1.X 0x0 / 0x25; A1.W 0x0 / 0xd93e9488 |
| 3 | `c40d 459f` `(R6, R2) = SEARCH R3 (GE);` | R2=0xb77dba30 R3=0xb6591098 R6=0xce65b00c A0.X=0xe9 A0.W=0xa6da4365 A1.X=0x5e A1.W=0xe6bfd9d1 ASTAT=0xc2122 | A0.X 0x0 / 0xe9; A0.W 0x4365 / 0xa6da4365; A1.X 0xff / 0x5e; A1.W 0xffffd9d1 / 0xe6bfd9d1 |
| 3 | `c423 4d2c` `R6.H = R5.L - R4.H (NS);` | R4=0xd56e2a25 R5=0xe1d5df4e R6=0xa044fce1 ASTAT=0xd2061 | ASTAT AZ 0/1, AC0_COPY 1/0, AC0 1/0 |
| 3 | `c402 27fe` `R3.L = R7.L + R6.L (S);` | R3=0x1a5bef37 R6=0x93d0ae0c R7=0xfb90dc32 ASTAT=0x2042140 | ASTAT AN 1/0, AC0_COPY 1/0, AC0 1/0 |
| 3 | `c403 2f37` `R7.L = R6.L - R7.L (S);` | R6=0xffbd2f1a R7=0x93b172cb ASTAT=0x2010140 | ASTAT AN 1/0 |
| 3 | `c422 2e48` `R7.H = R1.L + R0.L (S);` | R0=0x9cff6200 R1=0xf9ec3e45 R7=0x49e507d2 ASTAT=0x60022 | R7 0x7fff07d2 / 0xa04507d2; ASTAT AN 0/1, V_COPY 1/0, V 1/0, VS 1/0 |
| 2 | `c40e 0a6a` `A0 = -A0;` | A0.X=0x33 A0.W=0x1d680149 ASTAT=0x309312f | ASTAT AZ 0/1, AC0_COPY 0/1, AC0 0/1, AV0 0/1 |
| 2 | `c403 a60d` `R3.L = R1.H - R5.L (S);` | R1=0x275e278d R3=0x8bc12ad4 R5=0x8f8ff248 ASTAT=0x106004b | ASTAT AZ 0/1, AN 0/1, V_COPY 0/1, V 0/1 |
| 2 | `c40d 8a42` `(R1, R5) = SEARCH R0 (LT);` | R0=0xc66b1e51 R1=0xe134bdf4 R5=0xed4fec7b A1.X=0x9a A1.W=0x3ef79053 ASTAT=0x30a006b | A1.X 0xff / 0x9a; A1.W 0xffff9053 / 0x3ef79053 |
| 2 | `c42b 43a8` `R1.H = (A0 += A1);` | R1=0xdda7e0b8 A0.X=0x16 A0.W=0x41011639 A1.X=0x59 A1.W=0x33faece1 ASTAT=0x20f3125 | R1 0x7fffe0b8 / 0xdda7031a; ASTAT AZ 0/1, AC0_COPY 0/1, V_COPY 1/0, AC0 0/1, AV0 0/1, V 1/0 |
| 2 | `c402 8cc0` `R6.L = R0.H + R0.L (NS);` | R0=0x935545c5 R6=0x9f760fd9 ASTAT=0x101214b | ASTAT AZ 0/1, V_COPY 0/1, V 0/1 |
| 2 | `c423 28ca` `R4.H = R1.L - R2.L (S);` | R1=0xaeb129fa R2=0xaeb5bea R4=0xb4532197 ASTAT=0x20a2103 | ASTAT AZ 0/1 |
| 2 | `c410 4aac` `A0 = ABS A1;` | A0.X=0xf6 A0.W=0x927999c4 A1.X=0xf6 A1.W=0x5254a778 ASTAT=0x2091025 | A0.X 0x9 / 0xf6; A0.W 0xadab5888 / 0x927999c4; A1.X 0xf6 / 0x9; A1.W 0x5254a778 / 0xadab5888; ASTAT AZ 0/1, AV0 0/1 |
| 2 | `c400 c76b` `R3 = R5 -|- R3;` | R3=0x13faa7d3 R5=0x981c2759 ASTAT=0x30c0168 | ASTAT AN 1/0, V_COPY 0/1, AC1 1/0, V 0/1 |
| 2 | `c407 80b4` `R0 = ABS R6;` | R0=0x1bb34e R6=0x3d4a8310 ASTAT=0x10b0109 | ASTAT V_COPY 0/1, V 0/1 |
| 2 | `c400 009f` `R0 = R3 +|+ R7;` | R0=0x3a1a5eb6 R3=0x2a2b4340 R7=0x38db4198 ASTAT=0x83047 | ASTAT AC0_COPY 0/1, V_COPY 1/0, AC0 0/1, AC1 0/1, V 1/0, VS 1/0 |
| 2 | `c400 4d70` `R6 = R6 +|- R0;` | R0=0x147d24b3 R6=0x87b8cfec ASTAT=0x108314c | ASTAT AN 1/0, V_COPY 0/1, AC1 0/1, V 0/1 |
| 2 | `c402 c9a9` `R4.L = R5.H + R1.H (NS);` | R1=0xb9b0cbea R4=0xe592ccd6 R5=0xfdebfb0c ASTAT=0x100104e | ASTAT V_COPY 0/1, V 0/1 |
| 2 | `c40d 0e34` `(R0, R7) = SEARCH R6 (GT);` | R0=0x4262e79f R6=0x3099a7ba R7=0x8197e78 A0.X=0x34 A0.W=0xd4c3ead4 A1.X=0xd8 A1.W=0xa768401a ASTAT=0x20b2020 | A0.X 0xff / 0x34; A0.W 0xffffead4 / 0xd4c3ead4; A1.X 0x0 / 0xd8; A1.W 0x401a / 0xa768401a |
| 2 | `c410 04b7` `A0 = ABS A0;` | A0.X=0x6b A0.W=0x88699db2 ASTAT=0xa0023 | ASTAT AZ 0/1, AN 0/1 |
| 2 | `c422 a7ff` `R3.H = R7.H + R7.L (S);` | R3=0x679af764 R7=0x94772fb6 ASTAT=0x100006b | ASTAT AZ 0/1, V_COPY 0/1, V 0/1 |
| 2 | `c423 60a0` `R0.H = R4.L - R0.H (S);` | R0=0x3cff2593 R4=0x2baa0fb7 ASTAT=0x30d100f | ASTAT AZ 0/1, AC0_COPY 0/1, V_COPY 0/1, AC0 0/1, V 0/1 |
| 2 | `c423 8d98` `R6.H = R3.H - R0.L (NS);` | R0=0x79e98cbc R3=0x9a04ab05 R6=0xfdb0d12c ASTAT=0x83125 | ASTAT AZ 0/1 |
| 2 | `c423 cac1` `R5.H = R0.H - R1.H (NS);` | R0=0x1f9da21e R1=0x2d0b3dd3 R5=0x3f9a824f ASTAT=0x3080149 | ASTAT AZ 0/1, AN 1/0, V_COPY 0/1, V 0/1 |
| 2 | `c403 40fd` `R0.L = R7.L - R5.H (NS);` | R0=0x68e6fe6b R5=0x3614bf9f R7=0x87e72b5f ASTAT=0x20e3065 | ASTAT AZ 0/1, AN 1/0, AC0_COPY 0/1, AC0 0/1 |
| 1 | `c404 461c` `R3 = R3 - R4 (NS);` | R3=0x529fe216 R4=0xad070f90 ASTAT=0xe1007 | ASTAT V_COPY 1/0, V 1/0, VS 1/0 |
| 1 | `c40e 4b44` `A0 = -A1;` | A0.X=0xfc A0.W=0x2aca5306 A1.X=0x7 A1.W=0xa3b8f848 ASTAT=0x20c1047 | ASTAT AZ 0/1, AC0_COPY 0/1, AC0 0/1 |
| 1 | `c402 474b` `R3.L = R1.L + R3.H (NS);` | R1=0xd77b5cd8 R3=0x65de14d4 ASTAT=0x2081027 | ASTAT AZ 0/1, AC0_COPY 0/1, V_COPY 1/0, AC0 0/1, V 1/0 |
| 1 | `c430 4ac3` `A1 = ABS A1;` | A1.X=0x4e A1.W=0xced46cb6 ASTAT=0x104016b | ASTAT AZ 0/1, AN 0/1, AV1 0/1 |
| 1 | `c408 217c` `A0 = A0 (S);` | A0.X=0x3c A0.W=0xed9b5931 ASTAT=0x2003125 | ASTAT AZ 0/1, AV0 1/0, AV0S 1/0 |
| 1 | `c404 a06b` `R1 = R5 + R3, R0 = R5 - R3 (S);` | R0=0x1c5be0c0 R1=0x6404c6eb R3=0xd3ff05a8 R5=0x65229c0 ASTAT=0x10f006b | ASTAT AZ 0/1, V_COPY 0/1, V 0/1 |
| 1 | `c404 0b25` `R5 = R4 + R5 (NS);` | R4=0x3d1da392 R5=0xab978f9b ASTAT=0x30b012b | ASTAT AC0_COPY 0/1, AC0 0/1 |
| 1 | `c422 09f9` `R4.H = R7.L + R1.L (NS);` | R1=0xeeff9103 R4=0xab58284e R7=0xc4055df1 ASTAT=0x10f2029 | ASTAT AZ 0/1, AN 1/0, V_COPY 0/1, V 0/1 |

### shift (11 von 3000 abweichend, 10 Gruppen; dazu 45 nur in GNU illegal)

| n | Befehl | Eingabe | GNU / QEMU |
|---:|---|---|---|
| 2 | `c609 4c00` `R6.L = VIT_MAX (R0) (ASR);` | R0=0x9dc628a0 R6=0xc4bd783f A0.X=0xc0 ASTAT=0x2030062 | A0.X 0x60 / 0xe0 |
| 1 | `c603 920c` `A1 = ROT A1 BY R1.L;` | R1=0x107222e9 A1.X=0x85 A1.W=0x7fb00d2d ASTAT=0x70121 | A1.X 0xc0 / 0x85; A1.W 0x34b70aff / 0x7fb00d2d; ASTAT CC 0/1 |
| 1 | `c600 902f` `R0.L = LSHIFT R7.H BY R5.L;` | R0=0x1fdf453f R5=0xe454b802 R7=0x8f4b759e ASTAT=0x81005 | ASTAT AN 0/1 |
| 1 | `c603 841a` `A0 = ROT A0 BY R3.L;` | R3=0x62e9b046 A0.X=0x97 A0.W=0xe5d73ec6 ASTAT=0x109104e | A0.X 0xf9 / 0x0; A0.W 0x75cfb192 / 0x3f |
| 1 | `c600 5224` `R1.L = ASHIFT R4.H BY R4.L (S);` | R1=0x4e1db948 R4=0x691febcb ASTAT=0x90161 | R1 0x4e1d7fff / 0x4e1df800; ASTAT AN 0/1, V_COPY 1/0, V 1/0, VS 1/0 |
| 1 | `c600 2a0a` `R5.H = ASHIFT R2.L BY R1.L;` | R1=0xa7643ad9 R2=0xf9979c57 R5=0x745bf3a3 ASTAT=0x80040 | ASTAT AZ 1/0, AN 0/1, V_COPY 1/0, V 1/0, VS 1/0 |
| 1 | `c600 0617` `R3.L = ASHIFT R7.L BY R2.L;` | R2=0xb3c0e4b R3=0x31956615 R7=0x164f84ed ASTAT=0x3042128 | ASTAT AN 0/1, V_COPY 1/0, V 1/0 |
| 1 | `c600 7a05` `R5.H = ASHIFT R5.H BY R0.L (S);` | R0=0x56de2458 R5=0xad584619 ASTAT=0x103116c | R5 0x80004619 / 0x4619; ASTAT V_COPY 1/0, V 1/0, VS 1/0 |
| 1 | `c600 a020` `R0.H = LSHIFT R0.L BY R4.L;` | R0=0x86a33216 R4=0xc8470555 ASTAT=0x10d012b | ASTAT AZ 1/0, AN 0/1 |
| 1 | `c600 6213` `R1.H = ASHIFT R3.L BY R2.L (S);` | R1=0xdb4b24f3 R2=0x25acf6d5 R3=0x23eba00d ASTAT=0x2073027 | R1 0x800024f3 / 0x24f3; ASTAT V_COPY 1/0, V 1/0 |

### shiftimm (90 von 3000 abweichend, 18 Gruppen; dazu 114 nur in GNU illegal)

| n | Befehl | Eingabe | GNU / QEMU |
|---:|---|---|---|
| 13 | `c681 8801` `R4 = R1 << 0x0 (V);` | R1=0x562cb68c R4=0xf48cc4f1 ASTAT=0x2002160 | R4 0x562cb68c / 0xf48cc4f1; ASTAT AN 1/0 |
| 9 | `c680 5d16` `R6.L = R6.H >>> 0x1e (S);` | R6=0xec89a96f ASTAT=0x90161 | R6 0xec89b224 / 0xec893b22; ASTAT AN 1/0 |
| 8 | `c680 639f` `R1.H = R7.L >>> 0xd (S);` | R1=0x881db642 R7=0x169e4642 ASTAT=0x2083004 | R1 0x2b642 / 0xb642; ASTAT AZ 0/1 |
| 6 | `c680 269b` `R3.H = R3.L >>> 0x2d;` | R3=0xdb0bf404 ASTAT=0x2031046 | R3 0xa020f404 / 0xfffff404 |
| 5 | `c683 5645` `A1 = A1 >> 0x38;` | A1.X=0x71 A1.W=0xfc5ac515 ASTAT=0x300110e | A1.X 0xfc / 0x0; A1.W 0x5ac51500 / 0x0; ASTAT AZ 0/1, AN 1/0 |
| 5 | `c680 499e` `R4.L = R6.L >>> 0xd (S);` | R4=0x323ef6c0 R6=0xa2339f0a ASTAT=0x103016a | R4 0x323efffc / 0x323e0000; ASTAT AZ 0/1, AN 1/0 |
| 5 | `c680 774e` `R3.H = R6.H >>> 0x17 (S);` | R3=0x93b25f34 R6=0x4488ec49 ASTAT=0x2051065 | R3 0x10005f34 / 0x225f34 |
| 5 | `c680 009f` `R0.L = R7.L >>> 0x2d;` | R0=0x3a1a5eb6 R7=0x38db4198 ASTAT=0x83047 | R0 0x3a1a0cc0 / 0x3a1a0002; ASTAT V_COPY 1/0, V 1/0, VS 1/0 |
| 5 | `c683 9d08` `A1 = ROT A1 BY -0x1f;` | A1.X=0xd5 A1.W=0x8284479 ASTAT=0x50063 | A1.X 0x20 / 0x21; A1.W 0xa111e7aa / 0xffffffaa |
| 4 | `c680 82c2` `R1.L = R2.L << 0x18;` | R1=0x8d6f2746 R2=0x3fbe1112 ASTAT=0x30e314d | ASTAT AZ 1/0, AN 0/1, V_COPY 1/0, V 1/0 |
| 4 | `c683 87aa` `A0 = ROT A0 BY -0xb;` | A0.X=0x90 A0.W=0x4ffd68b ASTAT=0x303112e | A0.X 0xa2 / 0xff |
| 4 | `c683 4e31` `A0 = A0 >> 0x3a;` | A0.X=0xb A0.W=0xcf8ad2dd ASTAT=0x10c0009 | A0.X 0xf3 / 0x0; A0.W 0xe2b4b740 / 0x0; ASTAT AZ 0/1, AN 1/0 |
| 4 | `c680 32f6` `R1.H = R6.H >>> 0x22;` | R1=0x3c006d55 R6=0x4c94956d ASTAT=0x1090109 | R1 0x6d55 / 0x13256d55; ASTAT AZ 1/0, V_COPY 1/0, V 1/0, VS 1/0 |
| 3 | `c680 b67b` `R3.H = R3.H << 0xf;` | R3=0x98070d4c ASTAT=0x1082069 | ASTAT V_COPY 1/0, V 1/0, VS 1/0 |
| 3 | `c680 16d5` `R3.L = R5.H >>> 0x26;` | R3=0x1874c36e R5=0x3d9e4170 ASTAT=0x306100f | R3 0x18747800 / 0x187400f6; ASTAT V_COPY 1/0, V 1/0 |
| 3 | `c680 9e82` `R7.L = R2.H << 0x10;` | R2=0xc3f9a809 R7=0x60a1cd12 ASTAT=0x2021066 | ASTAT AZ 1/0, AN 0/1, V_COPY 1/0, V 1/0 |
| 3 | `c680 a107` `R0.H = R7.L >> 0x20;` | R0=0xad40d5 R7=0xb9de4442 ASTAT=0x105014b | R0 0x40d5 / 0x444240d5; ASTAT AZ 1/0 |
| 1 | `c681 018f` `R0 = R7 >>> 0xf (V);` | R0=0x15a28c61 R7=0x5f1e0187 ASTAT=0x30e100d | ASTAT V_COPY 0/1, V 0/1 |
