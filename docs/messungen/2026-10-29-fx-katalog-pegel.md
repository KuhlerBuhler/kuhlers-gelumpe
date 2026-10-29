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
