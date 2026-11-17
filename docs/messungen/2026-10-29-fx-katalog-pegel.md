# FX-Katalog: Pegel gegen die Werkspresets (29.10.)

Rückmeldung zu 1.3.7: die Effekte aus dem Katalog des Baukastens (`data/fx/catalog.mjs`) sind viel zu laut, genannt waren
MFX, Short Delay, alle Delays und Loud Distortion. Grundlage hier: alle Presets aus Hacktribe 2.02 (81) und Korgs Original
2.02 rot (70), offline gelesen, und die Katalog-Records, wie `src/fx-append.mjs` sie in beide Dateien schreibt.
**Nichts davon ist am Gerät gehört.** Der Emulator rechnet kein Audio, den DSP-Code emuliert nichts
([2026-10-09-mfx-dsp.md](2026-10-09-mfx-dsp.md)). Die neuen Werte sind hergeleitet, die Hörprobe steht aus.

## 1. Steuerzeilen tragen ihr Von/Bis-Paar sechsmal (gemessen)

Eine Zeile der Steuerung ist 28 Byte lang. Hinter Quelle, Ziel und Parameter steht das Paar Von/Bis nicht einmal, sondern
sechsmal, je 4 Byte weiter (Byte 4/6, 8/10, ... 24/26 der Zeile), die Bytes dazwischen sind null. Geprüft mit
`factory-check:map-row-copies`:

| Firmware | Zeilen | alle sechs Paare gleich | Kopien 2 bis 6 auf null |
|---|---|---|---|
| Korg rot 2.02 | 259 | 259 | 0 |
| Hacktribe 2.02 | 286 | 242 | 44 (nur Hacktribes eigene Presets, etwa 9/32 Delay, Tube Drive) |

Der Baukasten schrieb bisher nur das erste Paar. Die übrigen fünf blieben, was die Zeile des Spenderpresets dort hatte.
Im Katalog hieß das zum Beispiel: Dub Echo, Touchpad Y auf `feedback`, erstes Paar 50 bis 88, Kopien 44 bis 123; Short
Delay, Y auf `fb_depth`, Kopien 80 bis 0; die Inserts trugen in den Kopien die Werte der ersten Zeile von Slot 1.

**Offen:** welche Kopie die Firmware liest. Hacktribes Presets mit Kopien auf null laufen am Gerät, das spricht dafür,
dass die erste gilt (hergeleitet, nicht geprüft). `src/record.mjs` schreibt das Paar jetzt in alle sechs Kopien, wie Korg.
Damit ist die Frage für die eigenen Records egal.

## 2. Werte gegen die Werkspresets derselben Einheit

"Werk" heißt: die Presets beider Firmwares mit derselben Einheit an derselben Stelle. Gelesen mit einem Skript über
`src/presets.mjs` und `src/fx-v2.mjs` (`fxFromRecord`), Werte als Klartext, keine Bytes im Repository.

| Effekt | Parameter | bisher | Werk | neu |
|---|---|---|---|---|
| Loud Distortion (`I_distortion`) | `output_level` | 40 | 11 (Distortion), Regler 13 bis 10 | 14 |
| Fuzz (`I_distortion`) | `output_level` | 30 | 11 | 12 |
| Crunch (`I_distortion`) | `output_level` | 35 | 11 | 16 |
| Hot Overdrive (`I_acid_driver`) | `output_level` | 40, fest bei Drive bis 100 | 65 bei Drive 0 (Overdrive, Regler nimmt den Pegel bis 13 zurück), 22 bei Drive 91, 11 bei Drive 127 | 22, neue Reglerzeile `output_level` 34 bis 14 |
| 1/6, 1/24, 5/32 Delay (`I_short_delay`) | `fb_depth` | 70, 60, 65 | 25 (Delay 1/4, 3/16, 1/8, 1/16), Regler links 28 bis 9 | 30, Regler ab 30 |
| 3/64 Delay | `fb_depth`, `wet_level`, Regler rechts | 80, 90, bis 88 | 25, 120 | 45, 70, bis 70 |
| Slap Delay | `fb_depth` | 35 | 25 bis 30 | 20 |
| Long Delay | `fb_depth` | 70 | 25 | 40 |
| Short Delay (`M_mod_delay`) | `dry_wet`, `input_trim`, `delay_lag` | 122, 95, 30 | 100, 80 bis 109, 0 bis 17 | 111, 95, 30 |
| Short Delay | Y auf `fb_depth` | 0 bis 127 | Mod Delay 44 bis 123 | 0 bis 127 |
| Short Delay | Touchpad auf `dry_wet` | 45 bis 122 | | 45 bis 122 |
| Tri Ping Pong (`M_mod_delay`) | Touchpad auf Eingangspegel | 0 bis 127 | Mod Delay 0 bis 88 | 0 bis 88 |
| Dub Echo (`M_tape_echo`) | `feedback`, `saturation` | 85, 80 | 70, 47 | 70, 55 |
| Dub Echo | Y auf `feedback` | 50 bis 88 | Tape Delay 29 bis 72 | 40 bis 72 |
| Master Pumper (`M_level_mod`) | `output_gain_adjust` | 30 | 24 (Slicer, Auto Pan) | 24 |

Der Short Delay ist ein eigener, am Gerät eingestellter Effekt. Er bleibt, wie er war, nur `dry_wet` geht von 122 auf 111.

Unverändert, weil im Werksbereich oder ohne Werkspreset: Tremolo 1/8, Wah 1/8 (wie Touch Wah bis auf Sync und Tempo),
Small Plate, Master Limiter (`output_gain` 54, Vorgabe der Einheit 72). Die Notenwerte der Delays bleiben, sie machen nichts
lauter.

Warum die Delays laut wurden (hergeleitet): Die Wiederholungen summieren sich. Bei Rückkopplung 25 von 127 bleibt die
Summe nahe am Einzelecho, bei 60 bis 80 verdoppelt sie sich grob, beim sehr kurzen 3/64 Delay schaukelt sie sich zu einem
Kammfilter auf. Korgs eigene Short-Delay-Presets stehen alle auf 25 bis 30; nur Hacktribes 9/32, 3/32 und 1/12 Delay gehen
auf 82 bis 123.

**Widerspruch:** [2026-09-21-loudness.md](2026-09-21-loudness.md) nennt Ausgangspegel 38 bis 60 als spielbar. Für die
Distortion stimmt das nach der neuen Rückmeldung nicht, der Werkswert ist 11. Der Linter nimmt 38 bis 60 als brauchbar
(`usableLevel` in `data/findings.mjs`) und hat die alten Katalogwerte deshalb nicht gemeldet. Welche Einheit damals gehört
wurde, steht dort nicht.

## 3. Was geprüft ist

- `factory-check:map-row-copies` gegen beide Firmwares: grün (siehe Tabelle oben).
- Alle 18 Einträge bauen gegen Hacktribe und Korg rot ohne Fehler (`appendPresets`), die gebauten Steuerzeilen tragen
  sechs gleiche Paare.
- Der Linter meldet für alte und neue Katalogwerte dieselben Warnungen (Notenwerte, `low_damp`, Effekt schon vor dem
  Regler hörbar), keine zum Pegel.
- `test/fx-v2.test.mjs` hält die Pegelgrenzen fest: kein Katalogeffekt steht oder fährt über den Werkswert seiner Einheit
  (ohne den Mod Delay, siehe Short Delay oben).

Nicht geprüft: Klang und Lautstärke am Gerät.

## 4. Nach dem Hörtest am Gerät (31.10.)

Rückmeldung nach dem Hörtest am Gerät: die gesenkten Effekte sind jetzt "ein bisschen zu leise". Darum etwas angehoben,
etwa ein Viertel des Wegs von neu zurück zu bisher, höchstens aber 25 % vom neuen Wert, auf ganze Zahlen gerundet.
Rückkopplung und Wiederholungen bleiben, das ist keine Lautstärke. **Nach dem Hörtest am Gerät 31.10.: etwas angehoben,
nicht nachgehört.**

| Effekt | Parameter | bisher (1.3.7) | Werk | gesenkt (29.10.) | jetzt |
|---|---|---|---|---|---|
| Loud Distortion | `output_level` | 40 | 11 | 14 | 18 |
| Fuzz | `output_level` | 30 | 11 | 12 | 15 |
| Crunch | `output_level` | 35 | 11 | 16 | 20 |
| Hot Overdrive | `output_level` | 40 | 22 bei Drive 91 | 22 | 27 |
| Hot Overdrive | Regler auf `output_level` | fest 40 | | 34 bis 14 | 39 bis 19 |
| Master Pumper | `output_gain_adjust` | 30 | 24 | 24 | 26 |
| Tri Ping Pong | Touchpad auf Eingangspegel, bis | 127 | 88 | 88 | 98 |
| Short Delay (MFX) | `dry_wet` | 122 | 100 | 111 | 114 |

Die Pegelgrenzen in `test/fx-v2.test.mjs` liegen dafür für die Distortion (20) und den Master Pumper (26) knapp über
Werk. Die Reglerzeile des Hot Overdrive bleibt unter der Grenze der Einheit (65), der Mod Delay hat keine Grenze.

## 5. Nach den Gerätetests 14. und 15.11.

Rückmeldung vom Gerät: Loud Distortion ist etwa doppelt so laut wie der Rest, das LEVEL des Samples dämpft es nicht (der
Verzerrer sättigt, sein Ausgang hängt an `output_level`). Bounce Gate, Warm Drive, Bit Grinder und Glue Comp sind zu leise.
Die neuen Werte kommen, wo es geht, aus den Werkspresets derselben Einheit (Korg rot und Hacktribe 2.02, offline gelesen
mit `firmwarePresets` aus `src/fx-collection.mjs`). **Nicht nachgehört.**

| Effekt | Parameter | bisher | Werk | jetzt | Herleitung |
|---|---|---|---|---|---|
| Loud Distortion | `output_level` | 20 | 11 | 15 | geschätzt: unter 18 (31.10. angehoben, weil 14 "ein bisschen zu leise" war), über Werk |
| Bit Grinder | `output_level`, Regler | 90, 90 bis 75 | Decimator und Bit Crusher 127 | 127, 127 bis 106 | Werkspegel des Decimators; der Regler nimmt wie bisher ein Sechstel zurück |
| Alias Crush | `output_level` | 90 | 127 | 127 | wie Bit Grinder, gleiche Einheit |
| Warm Drive | `output_level`, Regler | 42, 50 bis 27 | Acid Drive 65 bei Drive 0, 22 bei Drive 91, 11 bei Drive 127 | 46, 56 bis 32 | die Werkskurve, linear zwischen Drive 0 und 91 gelesen: Drive 40 gibt 46, Drive 20 gibt 56, Drive 70 gibt 32 |
| Glue Comp | Kompressor `output_gain`, Regler | 52, 50 bis 58 | kein Werkspreset mit dem SR1-Kompressor | 60, 58 bis 66 | geschätzt, wie am 31.10. um etwa ein Sechstel |
| Glue Comp | Limiter `output_gain` | 48 | Limiter 48 (der Regler des Werkspresets fährt die Schwelle, nicht den Ausgang) | 60 | geschätzt; ohne den Limiter höher bliebe der Kompressor an ihm hängen |
| Bounce Gate 16, 8 | `output_gain` | 36 | Off Beater, Pumper, Repeater 36, Slicer 32 | 45 | geschätzt, ein Viertel über Werk: das Gate schneidet jeder Note das Ende ab, es bleibt weniger Energie als bei den Werkspresets |

`test/fx-v2.test.mjs` lässt den Level Mod (`0x15`) dafür bis 45 zu, knapp über Werk wie die Distortion und der Master Pumper.
Die Master-Effekte aus dem Gerätetest 15.11. (Pumper, Multitap, Wow Tape, Dub Delay, Ping Pong zu leise, Letter Drive zu laut)
sind bis auf den Pumper Hacktribes eigene Presets (Plätze 37 bis 49: Ping Pong, Dub Delay, Wow Tape, Ladder Drive, Ring Crush,
Multi Tap). Werkspresets bleiben, wie sie sind.

## 6. Master-Effekte nach dem Gerätetest 15.11.

Angepasst sind nur die eigenen Master-Effekte. **Nicht nachgehört.**

| Effekt | Parameter | bisher | jetzt | Herleitung |
|---|---|---|---|---|
| Master Pumper | `output_gain_adjust` | 26 | 32 | geschätzt: Werk 24; das Pumpen nimmt der Summe Energie wie das Bounce Gate, das ein Viertel über Werk steht |
| Master Limiter | `threshold`, Regler | 48, 52 bis 30 | 64, 64 bis 40 | Urteil: er drückte so stark, dass er kurz aussetzte wie ein leichter Slicer |
| Master Limiter | `release` | 8 | 20 | Urteil; Korgs Preset "Limiter" (Platz 26, Einheit SR1-Kompressor, nicht `M_limiter`) hat 12 |
| Master Limiter | `hold_time` | 8 | 17 | wie Korgs Preset "Limiter" |

Master Tilt und Master Warmth sind aus dem Katalog genommen: am Gerät hörbar wirkungslos und nicht gebraucht. Master
Glue bleibt.

## 7. Nachmessung im DSP-Simulator (17.11.)

Gemessen mit Korgs DSP-Code im GNU-bfin-Simulator, Fall `tools/emu/fx_level_cases.py` (noch nicht in diesem Branch).
Testsignal, Fenster und Kennzahlen wie dort: 1-kHz-Sinus mit -12 dBFS Spitze, danach ein Rauschstoß, Touchpad in der Mitte.
Alle Werte in dB gegen trocken im selben Lauf, `einbr.` zählt 2-ms-Blöcke im Sinus unter der halben Medianleistung.
Firmware: Patcher dieses Branches auf Hacktribe 163d1d8d (HT) und Korgs rot 2.02. **Nicht nachgehört.**

### Ursachen (gemessen)

- **Master Limiter.** `threshold` 64 und der Regler bis 64 lagen über dem Bereich der Einheit (0 bis 60), `release` 20 über
  0 bis 19. Mit `release` 19 und Schwelle 64 blieben die Einbrüche (26), mit dem Regler bis 60 und `release`/`hold_time` 8
  waren es null. Längere Release- oder Hold-Werte machen im Simulator Einbrüche: `release` 14 gibt 14, `release` 12 mit `hold_time` 17
  gibt 6. Die Gerätemeldung "setzt aus wie ein leichter Slicer" kam auf 1.4.6 (Schwelle 48, Release und Hold 8); im Simulator
  macht diese Einstellung keine Einbrüche (Urteil: die Meldung bleibt für 1.4.6 offen).
- **Glue Comp.** Der Limiter in Stufe 2 (`I_limiter`) macht leise Signale um bis zu 30 dB leiser, auch hinter Korgs eigenem
  Kompressor. Ohne ihn ist der SR1-Kompressor in Stufe 1 ein fester Pegel (+6,5 dB bei -12 und -3 dBFS, `threshold` 20 und
  28 gleich), Ratio 0, 14 und 18 (Hacktribes Preset "SR1 Comp") geben Stille. Korgs Kompressor-Baustein (`I_cheap_comp`,
  Werkspreset Sustainer) drückt: -0,3 dB bei -12 dBFS, -2,7 dB bei -3 dBFS.
- **Master Glue.** Die Ratio ändert nichts (2 bis 18), die Schwelle schon. Mit Schwelle 42 greift er bei diesem Pegel nicht.
- **Master Pumper.** `output_gain_adjust` 38 statt 32 hebt ihn um 2,9 dB, 42 wäre 2 dB über trocken.

### Änderungen

| Effekt | Parameter | bisher | jetzt | Herleitung |
|---|---|---|---|---|
| Master Limiter | `threshold`, Regler | 64, 64 bis 40 | 52, 60 bis 44 | gemessen: im Bereich der Einheit, Mitte 52 |
| Master Limiter | `release`, `hold_time` | 20, 17 | 8, 8 | gemessen: wie 1.4.6, keine Einbrüche |
| Master Pumper | `output_gain_adjust` | 32 | 38 | gemessen |
| Glue Comp | Stufe 1, Stufe 2 | SR1-Kompressor, Limiter | `I_cheap_comp` wie Sustainer, keine | gemessen; Regler wie Sustainer auf `env_bit_shift_amount` 35 bis 0 |
| Master Glue | `threshold`, `output_gain`, Regler | 42, 50, 46 bis 30 | 27, 53, 33 bis 21 | gemessen |

`test/fx-v2.test.mjs` prüft jetzt jeden Wert und jede Reglerzeile des Katalogs gegen den Bereich der Einheit und lässt den
Master Pumper bis 38 zu.

### Vorher und nachher, Sinus und Rauschstoß (gemessen)

| Effekt | HT vorher rms | HT vorher einbr. | HT nachher rms | HT nachher einbr. | rot vorher rms | rot nachher rms |
|---|---|---|---|---|---|---|
| Master Limiter | -9,5 | 26 | +1,5 | 0 | -9,5 (26) | +1,5 (0) |
| Master Pumper | -2,9 | 0 | 0,0 | 0 | -3,6 | -0,7 |
| Glue Comp | -6,3 | 0 | -3,2 | 0 | -6,3 | -3,2 |
| Master Glue | +0,1 | 0 | +0,4 | 0 | +0,1 | +0,4 |
| Loud Distortion (Kontrolle) | -2,3 | 0 | -2,3 | 0 | -2,3 | -2,3 |

### Nur Sinus, -12 gegen -3 dBFS (gemessen)

| Effekt | HT vorher | HT nachher | rot nachher |
|---|---|---|---|
| Glue Comp | -21,9 / +11,6 | -1,7 / -4,1 | -1,7 / -4,1 |
| Master Glue | +0,1 / +0,1 | +1,6 / -1,6 | +1,6 / -1,6 |

9 dB mehr Eingang ergeben jetzt 6,6 dB (Glue Comp) und 6,8 dB (Master Glue) mehr Ausgang: beide drücken sanft, statt zu
expandieren oder nichts zu tun.

### Nicht geändert

- Multi Tap, Wow Tape, Dub Delay, Ping Pong, Ladder Drive und Ring Crush sind Hacktribes eigene Presets, nicht Teil des
  Katalogs. Werkspresets bleiben, wie sie sind (Abschnitt 5). Am 16.11. gemessen 3,6 bis 6 dB leiser als trocken, Ring Crush
  dämpft den Sinus um 60 dB.
- Ladder Drive "zu laut" ist mit Touch in der Mitte nicht nachzustellen (-11 dB); andere Touch-Stellen sind nicht gemessen.
- Glue Comp liegt mit dem Rauschstoß 3,2 dB unter trocken. Ein höheres `output_level` ist nicht gemessen.
