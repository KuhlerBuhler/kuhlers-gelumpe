# QEMU-Port gegen GNU-Simulator: DSP-Funktionen bit-gleich, Tempo, was zum schnellen Kern fehlt

Stand 16.11.2026. Alles offline im Simulator, kein Gerät. Gemessen auf einem Apple M5 unter
Last (Lastmittel 8 bis 11 auf 10 Kernen, andere Sessions liefen), die Zeiten schwanken darum um
etwa ein Drittel. Firmware 2.02 mit Hacktribe, DSP-Strom des roten Geräts, mit
`tools/dsp/dsp_extract.py` zerlegt. Frage aus [Idee 52](../ideen/52-ton-im-emulator.md): kann der
QEMU-Port der schnelle Kern für den DSP werden?

## Kurz

- Der QEMU-Port (github vapier/qemu, Zweig `bfin`, Commit `ae8fe9a`) rechnet DSP-Befehle der
  Effekte an mehreren Stellen falsch: nur 17 von 76 Vergleichen waren gleich. Mit
  `tools/dsp/qemu-bfin.patch` rechnet er alle 38 prüfbaren Funktionen (6 Filterkerne,
  Verstärkungskern, 17 Insert- und 14 Master-Effekte) bit-gleich zum GNU-Simulator, nach 1 und
  2 000 Aufrufen, 5 davon auch nach 100 000. **gemessen**
- Wo beide auseinanderlagen, lag jedes Mal QEMU falsch, nachgeprüft am Befehlssatz (Abschnitt 3).
  Die offene Frage aus Idee 52, welcher Simulator beim Filterkern richtig liegt, ist damit
  beantwortet: der GNU-Simulator. **hergeleitet** aus Befehlssatz und Einzelschritt, nicht am Gerät
- Mit allen Korrekturen schafft QEMU rund 55 bis 230 Millionen DSP-Takte je Sekunde, der
  GNU-Simulator 4 bis 9 Millionen. QEMU ist damit 10- bis 25-mal schneller als der
  GNU-Simulator, aber 2- bis 10-mal langsamer als der echte DSP (rund 525 MHz). **gemessen**
- Für den Einsatz als Kern fehlt QEMU die ganze Peripherie, die der GNU-Simulator inzwischen hat
  (HOSTDP, SPORT0, DMA, MDMA), und ein Taktzähler. Schätzung in Abschnitt 5: 4 bis 7 Arbeitstage, rund 1 bis 2 Wochen Kalenderzeit.

## 1. Aufbau

| Teil | Stand |
|---|---|
| GNU-Simulator | gdb 15.2, nur der Befehlsteil aus `patch_sources` von `tools/dsp/build_blackfin.py` (Zweig `feature/sample-swap-native-dsp`): `SIGNEXTEND`, verzögertes Zurückschreiben bei DSP32ALU-Add/Sub, SIGNBITS, Zeiger-Ladebefehlen und Einzelregister-Ergebnissen in Mehrfachbefehlen. Ohne die Peripherie-Patches, die den Prüfstand anhalten |
| QEMU-Port | `ae8fe9a` plus `tools/dsp/qemu-bfin.patch`, gebaut wie im Kopf von `tools/dsp/bfsim_bench.py` beschrieben |
| Binutils | 2.42 mit `ld` |
| Prüfstand | `tools/dsp/bfsim_bench.py`: Funktion N-mal auf dem synthetischen Kontext ("Suppe"), danach FNV-1a über die Suppe |
| Register beim Aufruf | R0, P0 bis P4, I0 bis I3 je eine eigene Suppenseite; R1 `0x00012345`, R2 `0x7FF01234`, R3 `0x80001000`, R4 `0x00400000`, R5 `0x12345678`, R6 `0x0000ABCD`, R7 `0x40000000`, M0 bis M3 `4` |
| Einzelschritt | GNU über libsim (`sim_resume` mit `step=1`), QEMU mit `-accel tcg,one-insn-per-tb=on -d cpu,nochain`; nach jedem Befehl alle Register außer ASTAT verglichen |

Zwei Fehler im Prüfstand selbst sind behoben, beide verfälschten frühere Vergleiche:

- Die Prüfsumme war eine 32-Bit-Summe. Die frische Suppe summiert sich zu 0, und Fehler, die
  sich aufheben, blieben unsichtbar. Jetzt FNV-1a. **gemessen**
- R6 kam mit dem Wert von CYCLES in die Funktion. In QEMU zählt CYCLES Nanosekunden, also bekam
  jede Funktion in beiden Simulatoren einen anderen R6. Die Vorbelegung steht jetzt nach dem
  Lesen von CYCLES; ihre Kosten stecken in den Takten (leerer Aufruf `0xFFA0010A` abziehen).
  **gemessen**

Ein Teil der Abweichung beim Filterkern aus Idee 52 kam daher und von nicht belegten P2 und P3
(der Kern schrieb dann außerhalb der Suppe). **hergeleitet**

## 2. Ergebnis je Funktion

"ohne Patch": QEMU nur mit `SIGNEXTEND` und `ASHIFT ... BY Rx.L (S)` (Stand Idee 52). "mit
Patch": mit dem ganzen `qemu-bfin.patch`. Gleich heißt: die Suppe ist nach N Aufrufen in beiden Simulatoren Byte für
Byte gleich (bis auf die Kollisionswahrscheinlichkeit von FNV-1a). Takte aus dem
GNU-Simulator, mit Aufruf und Vorbelegung (der leere Aufruf kostet 56). Alles **gemessen**.

| Adresse | Funktion | Takte | ohne Patch, 1 | ohne Patch, 2 000 | mit Patch, 1 | mit Patch, 2 000 | Prüfsumme nach 2 000 |
|---|---|---|---|---|---|---|---|
| `0xFFA0383C` | Filterkern electribe | 193 | **abweichend** | **abweichend** | gleich | gleich | `bd87e44d` |
| `0xFFA03A1C` | Filterkern OB | 204 | **abweichend** | **abweichend** | gleich | gleich | `4104ba5c` |
| `0xFFA03C3C` | Filterkern Acid | 217 | **abweichend** | **abweichend** | gleich | gleich | `cb70c2c9` |
| `0xFFA03EAC` | Filterkern MS20 | 227 | **abweichend** | **abweichend** | gleich | gleich | `f91e5b2a` |
| `0xFFA0411E` | Filterkern MG | 215 | **abweichend** | **abweichend** | gleich | gleich | `16aefb37` |
| `0xFFA042DA` | Filterkern P5 | 221 | **abweichend** | **abweichend** | gleich | gleich | `2fe861b3` |
| `0xFFA03820` | Verstärkungskern | 64 | gleich | gleich | gleich | gleich | `546c9dc5` |
| `0xFFA078D8` | Insert mKP2 Comp | 211 | gleich | gleich | gleich | gleich | `927a6b37` |
| `0xFFA00AD0` | Insert SR1 Comp/Limiter | 202 | gleich | gleich | gleich | gleich | `d107ca85` |
| `0xFFA08D98` | Insert Cheap Comp | 110 | **abweichend** | **abweichend** | gleich | gleich | `e7c16f3f` |
| `0xFFA08508` | Insert 2 Band EQ | 173 | **abweichend** | **abweichend** | gleich | gleich | `c79677af` |
| `0xFFA086A8` | Insert 4 Band EQ | 237 | **abweichend** | **abweichend** | gleich | gleich | `e1fd92fd` |
| `0xFFA08B84` | Insert Exciter | 232 | **abweichend** | gleich | gleich | gleich | `76e0bf73` |
| `0xFFA00C80` | Insert Decimator | 234 | **abweichend** | **abweichend** | gleich | gleich | `7b0227c9` |
| `0xFFA075D0` | Insert Filter | 173 | **abweichend** | **abweichend** | gleich | gleich | `60ec08fc` |
| `0xFFA09138` | Insert Distortion | 245 | **abweichend** | **abweichend** | gleich | gleich | `c4d7b5ae` |
| `0xFFA08E7C` | Insert Acid Driver | 129 | **abweichend** | **abweichend** | gleich | gleich | `3824d491` |
| `0xFFA002B8` | Insert Chorus | 226 | **abweichend** | **abweichend** | gleich | gleich | `42bc0213` |
| `0xFFA0048C` | Insert Flanger | 250 | **abweichend** | **abweichend** | gleich | gleich | `7698859e` |
| `0xFFA08F48` | Insert Phaser | 244 | **abweichend** | **abweichend** | gleich | gleich | `4b4a7a1d` |
| `0xFFA00FE4` | Insert Tremolo | 178 | **abweichend** | **abweichend** | gleich | gleich | `352f96a8` |
| `0xFFA0777C` | Insert Level Mod | 177 | **abweichend** | **abweichend** | gleich | gleich | `7fac3b13` |
| `0xFFA007D0` | Insert Ring Mod | 277 | **abweichend** | **abweichend** | gleich | gleich | `4e63a786` |
| `0xFFA08998` | Insert Short Delay | 234 | gleich | gleich | gleich | gleich | `07edc61f` |
| `0x1C77E34` | Master mKP2 Comp | 293 | gleich | gleich | gleich | gleich | `a820a163` |
| `0xEE3C` | Master SR1 Comp/Limiter | 285 | gleich | gleich | gleich | gleich | `d107ca85` |
| `0x1C7D328` | Master 4 Band EQ | 405 | **abweichend** | gleich | gleich | gleich | `c82e2489` |
| `0x15FB4` | Master Wah | 343 | **abweichend** | **abweichend** | gleich | gleich | `7091ae62` |
| `0x1C7A908` | Master MultiModeFilter | 697 | **abweichend** | **abweichend** | gleich | gleich | `b948ef19` |
| `0x1C81068` | Master Distortion | 435 | **abweichend** | **abweichend** | gleich | gleich | `f520d4c2` |
| `0x15414` | Master TubePre | 381 | gleich | gleich | gleich | gleich | `0d000a85` |
| `0xDDF8` | Master Chorus | 418 | **abweichend** | **abweichend** | gleich | gleich | `5b09db81` |
| `0x10D2C` | Master Flanger | 401 | **abweichend** | **abweichend** | gleich | gleich | `21c693f4` |
| `0x1C8005C` | Master Phaser | 338 | **abweichend** | **abweichend** | gleich | gleich | `36c84fd5` |
| `0x1C7B5F0` | Master Level Mod | 326 | **abweichend** | **abweichend** | gleich | gleich | `d2975810` |
| `0x12ADC` | Master Hall/Plate Reverb | 488 | gleich | **abweichend** | gleich | gleich | `823ab80f` |
| `0x13FB8` | Master Room Reverb | 475 | **abweichend** | **abweichend** | gleich | gleich | `ac50d615` |
| `0x1C79B9C` | Master Mod.Delay | 435 | **abweichend** | **abweichend** | gleich | gleich | `cce23ba9` |

Nicht vergleichbar mit diesem Kontext: Master Tremolo `0xFFA0119C`, Tape Echo `0xFFA01260`,
Grain Shifter `0xFFA00728`, Decimator `0xFFA00EFC`, KPQ Looper `0xFFA07AF4` und Vinyl Break
`0xFFA0815C`. Sie springen nach 16 bis 21 Befehlen über einen Zeiger aus dem Kontext in die
Suppe (GNU: illegaler Befehl bei `0x1F7804` und ähnlich). **gemessen** Dafür braucht es einen
echten Kontext, ein Fehler eines Simulators ist es nicht.

## 3. Was QEMU falsch rechnete

Jede Stelle über die erste abweichende Instruktion im Einzelschritt gefunden, dann gegen die
Befehlssatz-Semantik und den Code des GNU-Simulators geprüft. Abweichung **gemessen**, welche
Seite richtig ist **hergeleitet**.

| Befehl | Beispiel | QEMU ohne Patch | richtig | Korrektur im Patch |
|---|---|---|---|---|
| `SIGNEXTEND` (16-Bit-Konstanten) | `R1 = 7 (X)` | auf arm64 falsch, wie im GNU-Simulator | 7 | Makro wie in `build_blackfin.py` |
| `Rx = ASHIFT Ry BY Rz.L (S)` | 5 Effekte | Ausnahme, Befehl fehlt | sättigend schieben | Hilfsfunktion `ashift32_sat` |
| Mehrfachbefehl mit Registerkonflikt | `R0 = [P0++] \|\| [I1++] = R0` | spätere Spalte sieht das neue R0 | alle Spalten lesen die alten Register | Datenregister vor dem Bündel sichern, jede Spalte gegen den alten Stand rechnen, Ergebnisse danach zusammenführen |
| MAC, Produkt ins Akku | `A0 = R1.H * R0.H` bei `0xFFA038A8` | A0 `00FFFFFB68` | `FFFFFFFB68` (-1176; Produkt ab Bit 31 vorzeichenerweitert) | MAC und MULT ganz als Hilfsfunktion aus dem GNU-Simulator portiert: Vorzeichen, Sättigung auf 40 und 32 Bit, Runden und Abschneiden in Halbregister, AV0/AV1/V/VS |
| MAC, Ergebnis in Halbregister | `R0.L = (A0 += ...)` | untere Bits des Akkus, ohne Runden und Sättigung | `rnd16`, Sättigung auf 16 Bit | wie oben |
| Akku arithmetisch schieben | `A1 = A1 >>> 15` bei `0xFFA03A70` | `1FFFFF8` (Akku war nicht vorzeichenerweitert) | `FFFFFFFFF8` | Akku vor `>>>` auf 40 Bit vorzeichenerweitern, vor `>>` auf 40 Bit maskieren; die MAC-Hilfsfunktion legt den Akku vorzeichenerweitert ab, wie der Rest des Ports es erwartet |
| `Rx = Ry << imm (S)` | `R4 = R4 << 6 (S)` bei `0xFFA03A96` | schob um `-imm`, Ergebnis 0 | `0x048A0000`, sättigend | über `ashift32_sat` |
| 32-Bit-Add/Sub mit `(S)` | `R0 = R2 + R6 (S)` bei `0xFFA077D4` | ohne Sättigung, `801E37FF` | `7FFFFFFF` | Sättigung in TCG für `+`, `-` und `+/-` |

Flags: der Patch setzt AV0/AV1/V/VS und AZ/AN bei MAC und MULT wie der GNU-Simulator.
Verglichen wurden Flags nicht: der Einzelschritt lässt ASTAT aus, die Prüfsumme sieht nur
Speicher. CC wirkt über Sprünge und `IF CC` auf Register und Speicher und ist damit
mitgeprüft. **offen**: V/VS/AC fehlen in QEMU bei vielen anderen Befehlen weiter (Kommentare
"Missing V/VS updates" im Port).

Im Port gar nicht umgesetzt und von keiner geprüften Funktion benutzt: `RND12`/`RND20`,
BYTEOP-Befehle, SAA, `A0 -= A1 (W32)`, 16-Bit-`>>>` mit `(S)`. **offline** gelesen
(`unhandled_instruction` in `target/bfin/bfin-sim.c`). Trifft eine Funktion darauf, hält QEMU
mit einer Ausnahme an, rechnet also nicht still falsch.

## 4. Tempo

Je Aufruf, aus 100 000 Aufrufen minus einem Lauf mit 1 Aufruf (Start und Laden). Takte aus dem
GNU-Simulator, Echtzeit = Takte bei 525 MHz. In Klammern Millionen DSP-Takte je Sekunde.
**gemessen**, unter Last.

| Funktion | Takte je Aufruf | DSP 525 MHz | GNU-Simulator | QEMU mit Patch |
|---|---|---|---|---|
| leerer Aufruf `0xFFA0010A` | 56 | 0,11 µs | 6,3 µs (9) | 0,24 µs (233) |
| Filterkern electribe | 193 | 0,37 µs | 30,8 µs (6) | 1,5 µs (131) |
| Short Delay (Insert) | 234 | 0,45 µs | 29,7 µs (8) | 1,2 µs (192) |
| Chorus (Insert) | 226 | 0,43 µs | 53,2 µs (4) | 2,9 µs (78) |
| Distortion (Insert) | 245 | 0,47 µs | 50,9 µs (5) | 2,5 µs (98) |
| Hall Reverb (Master) | 488 | 0,93 µs | 89,8 µs (5) | 8,8 µs (55) |

Die Korrekturen kosten Tempo. Je 1 000 000 Aufrufe, zwei Läufe:

| Stand | Filterkern electribe | Hall Reverb |
|---|---|---|
| v1: nur `SIGNEXTEND` und `ASHIFT (S)`, rechnet falsch | 0,52 / 0,80 s | 1,38 / 1,45 s |
| v2: dazu Sicherung bei Mehrfachbefehlen | 0,95 / 1,13 s | 3,22 / 3,50 s |
| ganzer Patch | 1,81 / 2,01 s | 4,80 / 4,89 s |

Rund die Hälfte kostet die Sicherung der Datenregister bei jedem Mehrfachbefehl, den Rest die
Hilfsfunktionen für MAC und MULT und das Auflösen der verzögerten Flags davor. **gemessen**

Zurückholen lässt sich das so (**geschätzt**, nichts gebaut): die Sicherung nur für Bündel
erzeugen, in denen eine Spalte ein Datenregister schreibt, das eine spätere liest (beim
Übersetzen bekannt, für alle anderen Bündel kostenlos); MAC wieder in TCG statt als Aufruf, mit
der richtigen Semantik. Dann wäre das Tempo von v1 erreichbar, also etwa 1,5-mal langsamer als
der echte DSP.

## 5. Was der Umzug auf QEMU braucht

Der GNU-Simulator aus `build_blackfin.py` hat: HOSTDP mit FIFO und DMA1, SPORT0 mit Stereo-DMA
und Testtakt, MDMA mit Zeilen und Deskriptoren, DMA-Abschlussstatus und Interrupts, SIC/CEC
pegelgesteuert, Takt-Scheiben mit IDLE und Aufwachen, Beobachtungsfenster. Der QEMU-Port hat für
das Board BF537: UART über chardev (funktioniert, der Prüfstand liest seine Ergebnisse darüber,
also ohne den Dateideskriptor-Umweg des GNU-Simulators), PLL, SIC, EVT, MMU-Register und einen
DMA-Stub, der Schreibzugriffe verwirft und 0 liest. Kein SPORT, kein HOSTDP. **offline** gelesen
in `hw/bfin/`.

| Teil | Was | Arbeitstage (geschätzt) |
|---|---|---|
| Befehlssatz | Restliche Lücken (V/VS/AC-Flags, `RND12/20`, BYTEOP, SAA, W32), dazu ein Dauervergleich gegen den GNU-Simulator über ganze Audioblöcke statt Einzelfunktionen | 1 bis 2 |
| Tempo | Sicherung nur bei Konfliktbündeln, MAC in TCG | 0,5 |
| HOSTDP | Gerät mit FIFO und DMA1 nach Vorlage `tools/dsp/blackfin_hostdp.c` (461 Zeilen) auf die QEMU-Geräteschnittstelle (MemoryRegion, IRQ) umgeschrieben | 0,5 bis 1 |
| SPORT0, DMA, MDMA | Echter DMA-Controller statt Stub, MDMA, SPORT0 nach `tools/dsp/blackfin_sport.c` (404 Zeilen), Interrupts über SIC | 1 bis 1,5 |
| Takt | CYCLES zählt Nanosekunden der virtuellen Uhr. Für Zeitscheiben und das Budget je Block braucht es einen Befehlszähler: `-icount` mit fester Rate macht die Zeit proportional zu den Befehlen, kennt aber keine Blackfin-Takte (Stalls, Mehrtakt-Befehle). Für Klang reicht Befehle-als-Takte, für Taktmessungen bleibt der GNU-Simulator | 0,5 |
| Kopplung | QEMU läuft als eigener Prozess (System-Emulation), der ARM-Emulator in Python. Dazwischen ein Kanal für Host-Port-Zugriffe und Zeitscheiben, wie `blackfin_channel.c` beim GNU-Arbeiter | 0,5 bis 1,5 |

Zusammen 4 bis 7 Arbeitstage, mit Wartezeiten für lange Vergleichsläufe unter Last rund 1 bis 2
Wochen Kalenderzeit. Maßstab ist das bisherige Tempo: die ganze Peripherie des GNU-Simulators
(SysControl, HOSTDP, SPORT0-DMA, Kopplung an den ARM-Emulator) entstand am 14.11. an einem Tag
(Commits `dab41585` bis `11cc6663` auf `feature/sample-swap-native-dsp`), der QEMU-Patch dieser
Messung mit fünf Fehlerklassen ebenfalls an einem Tag. Der größte unsichere Posten ist der
Befehlssatz: wie viele Fehler QEMU in den noch nicht verglichenen Befehlen hat, ist unbekannt.
Ergebnis wäre ein Kern, der einzelne Effekte nahe Echtzeit rechnet
und einen ganzen Patch (10 000 bis 15 000 Takte je Sample nach Idee 52) in ungefähr 2- bis
5-facher Echtzeit, also weiter nicht live, aber 10- bis 25-mal schneller als heute. **geschätzt**

Lizenz: die portierten MAC-Funktionen stammen aus dem GNU-Simulator (GPL 3 oder später), der
QEMU-Port steht unter LGPL 2 oder später. Für ein eigenes Werkzeug egal, ein weitergegebenes
QEMU-Binary wäre damit GPL 3. **hergeleitet**

## Nachstellen

Werkzeuge bauen wie im Kopf von `tools/dsp/bfsim_bench.py`. Dann, mit `$OUT` aus
`dsp_extract.py` und den Registern aus Abschnitt 1 als `--reg`-Liste `$REGS`:

```bash
python3 tools/dsp/bfsim_bench.py $OUT ffa0383c --calls 2000 $REGS --run $GNU/sim/bfin/run
```

```bash
python3 tools/dsp/bfsim_bench.py $OUT ffa0383c --calls 2000 $REGS --qemu $QEMU/build/qemu-system-bfin
```

Gleiche `soup_checksum` heißt gleiches Ergebnis. Die Vergleichs- und Einzelschritt-Skripte
(`compare.py`, `gnu_step.c`, `pair.sh`, `diff.py`) lagen im Arbeitsordner der Session und sind
nicht im Repository.

## Belegtabelle

| Behauptung | Status | Beleg |
|---|---|---|
| Ohne Patch 17 von 76, mit Patch 76 von 76 Vergleichen gleich | gemessen | `compare.py`, 38 Funktionen mit 1 und 2 000 Aufrufen, Tabelle in Abschnitt 2 |
| Filterkern electribe, Short Delay, Chorus, Distortion, Hall nach 100 000 Aufrufen gleich | gemessen | Tempo-Lauf, gleiche `soup_checksum` |
| Vor dem Patch rechnete QEMU falsch, nicht der GNU-Simulator | hergeleitet | Einzelschritt bis zur ersten Abweichung, Semantik nach Befehlssatz und GNU-Code, Abschnitt 3 |
| 6 Master-Effekte springen in die Suppe | gemessen | Einzelschritt im GNU-Simulator, letzter PC liegt in der Suppe und ist kein Befehl |
| QEMU 55 bis 233, GNU 4 bis 9 Millionen Takte je Sekunde | gemessen | Abschnitt 4, unter Last |
| Ohne Sicherung bei Nicht-Konfliktbündeln Tempo wie v1 | geschätzt | nicht gebaut |
| QEMU-DMA ist ein Stub, kein SPORT, kein HOSTDP | offline | `hw/bfin/bfin_dma.c`, Inhalt von `hw/bfin/` |
| Aufwand 4 bis 7 Arbeitstage | geschätzt | Urteil, Maßstab Commit-Zeiten vom 14.11. und diese Messung |
| Flags (ASTAT) gleich | offen | nicht verglichen |
