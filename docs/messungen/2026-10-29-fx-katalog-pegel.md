# FX-Katalog: Pegel gegen die Werkspresets

Rückmeldung zu 1.3.7: die Effekte aus dem Katalog des [Baukastens](../glossary.md#baukasten) (`data/fx/catalog.mjs`) sind viel zu laut, genannt waren
MFX, Short Delay, alle Delays und Loud Distortion. Grundlage hier: alle Presets aus Hacktribe 2.02 (81) und Korgs Original
2.02 rot (70), offline gelesen, und die Katalog-Records, wie `src/fx-append.mjs` sie in beide Dateien schreibt.
**Nichts davon ist am Gerät gehört.** Der Emulator rechnet kein Audio, den [DSP](../glossary.md#dsp)-Code emuliert nichts
([2026-10-09-mfx-dsp.md](2026-10-09-mfx-dsp.md)). Die Werte in Abschnitt 2 sind hergeleitet.

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

"Werk" heißt: die Presets beider Firmwares mit derselben Einheit an derselben Stelle (gelesen über `src/presets.mjs` und
`src/fx-v2.mjs`). Die Katalogwerte stehen in `data/fx/catalog.mjs`, die Obergrenzen in `test/fx-v2.test.mjs` (`LEVEL_CAPS`).
Befunde (**hergeleitet**, Werkswerte offline gelesen):

- Distortion (`I_distortion`): `output_level` im Werk 11, Regler 13 bis 10; der Katalog lag bei 30 bis 40.
- Acid Driver (`I_acid_driver`): `output_level` 65 bei Drive 0, 22 bei Drive 91, 11 bei Drive 127; ein fester Wert von 40 ist bei
  hoher Verzerrung viel zu laut, der Pegel gehört an den Regler.
- Short Delay (`I_short_delay`): `fb_depth` im Werk 25 bis 30 (nur Hacktribes 9/32, 3/32 und 1/12 Delay gehen auf 82 bis 123).
- Mod Delay, Tape Delay, Level Mod: Werkswerte `dry_wet` 100, Tape-Rückkopplung 70, `output_gain_adjust` 24.

Warum die Delays laut wurden: die Wiederholungen summieren sich. Bei Rückkopplung 25 von 127 bleibt die Summe nahe am Einzelecho,
bei 60 bis 80 verdoppelt sie sich grob, beim sehr kurzen 3/64 Delay schaukelt sie sich zu einem Kammfilter auf.

Der Short Delay (MFX) ist ein eigener, am Gerät eingestellter Effekt und bleibt bei seinen Werten.

**Widerspruch:** [2026-09-21-loudness.md](2026-09-21-loudness.md) nennt Ausgangspegel 38 bis 60 als spielbar. Für die Distortion
stimmt das nicht, der Werkswert ist 11. Der Linter nimmt 38 bis 60 als brauchbar (`usableLevel` in `data/findings.mjs`) und meldet
zu hohe Katalogwerte deshalb nicht.

## 3. Was geprüft ist

- `factory-check:map-row-copies` gegen beide Firmwares: grün (Tabelle in Abschnitt 1).
- Alle Katalogeinträge bauen gegen Hacktribe und Korg rot ohne Fehler (`appendPresets`), die gebauten Steuerzeilen tragen
  sechs gleiche Paare.
- `test/fx-v2.test.mjs` hält die Pegelgrenzen fest: kein Katalogeffekt steht oder fährt über den Werkswert seiner Einheit,
  mit den dort genannten Ausnahmen (Distortion, Master Pumper, Level Mod), die nach Hörtests am Gerät höher liegen.

## 4. Hörtest am Gerät (31.10.)

Die auf Werk gesenkten Effekte waren "ein bisschen zu leise" und wurden um etwa ein Viertel des Wegs zurück angehoben
(**nicht nachgehört**). Rückkopplung und Wiederholungen blieben.

## 5. Gerätetests 14. und 15.11.: Insert- und Level-Mod-Effekte

Loud Distortion war etwa doppelt so laut wie der Rest (das LEVEL des Samples dämpft sie nicht, der Verzerrer sättigt und sein
Ausgang hängt an `output_level`); Bounce Gate, Warm Drive, Bit Grinder und Glue Comp waren zu leise. Die Werte sind danach angepasst,
wo es ging nach den Werkspresets derselben Einheit, sonst geschätzt (**nicht nachgehört**).

## 6. Master-Effekte

Master Pumper zu leise, Master Limiter setzte aus; beide sind angepasst. Master Tilt und Master Warmth sind aus dem Katalog genommen
(am Gerät wirkungslos). Multi Tap, Wow Tape, Dub Delay, Ping Pong, Ladder Drive und Ring Crush sind Hacktribes eigene Presets
(Plätze 37 bis 49), nicht Teil des Katalogs, und bleiben wie sie sind.

## 7. Nachmessung im DSP-Simulator (17.11.)

Gemessen mit Korgs DSP-Code im GNU-bfin-Simulator, Fall `tools/emu/fx_level_cases.py`.
Testsignal, Fenster und Kennzahlen wie dort: 1-kHz-Sinus mit -12 dBFS Spitze, danach ein Rauschstoß, Touchpad in der Mitte.
Alle Werte in dB gegen trocken im selben Lauf, `einbr.` zählt 2-ms-Blöcke im Sinus unter der halben Medianleistung.
Firmware: der Patcher auf Hacktribe 163d1d8d (HT) und Korgs rot 2.02. **Nicht nachgehört.**

### Ursachen (gemessen)

- **Master Limiter.** `threshold` 64 und der Regler bis 64 lagen über dem Bereich der Einheit (0 bis 60), `release` 20 über
  0 bis 19. Mit `release` 19 und Schwelle 64 blieben die Einbrüche (26), mit dem Regler bis 60 und `release`/`hold_time` 8
  waren es null. Längere Release- oder Hold-Werte machen im Simulator Einbrüche: `release` 14 gibt 14, `release` 12 mit `hold_time` 17
  gibt 6. Die Gerätemeldung "setzt aus wie ein leichter Slicer" kam auf 1.4.6 (Schwelle 48, Release und Hold 8); im Simulator
  macht diese Einstellung keine Einbrüche (Urteil: die Meldung bleibt für 1.4.6 offen).
  Gemessen am 23.11. im Blackfin-Simulator mit einer Drumloop: mit `attack` 0 wirkt `M_limiter` wie ein schnelles Gate
  (164 Pegelsprünge über 3 dB/s, bis 27 dB), und Schwelle 52 erreicht das Signal nie. Korgs `attack` 10 mit Schwelle 30,
  `output_gain` 60 und X von 36 bis 24 nimmt die Sprünge weg und begrenzt wirklich (#735). Die Limiter-Werte der Tabelle
  unten sind damit überholt.
- **Glue Comp.** Der Limiter in Stufe 2 (`I_limiter`) macht leise Signale um bis zu 30 dB leiser, auch hinter Korgs eigenem
  Kompressor. Ohne ihn ist der SR1-Kompressor in Stufe 1 ein fester Pegel (+6,5 dB bei -12 und -3 dBFS, `threshold` 20 und
  28 gleich), Ratio 0, 14 und 18 (Hacktribes Preset "SR1 Comp") geben Stille. Korgs Kompressor-Baustein (`I_cheap_comp`,
  Werkspreset Sustainer) drückt: -0,3 dB bei -12 dBFS, -2,7 dB bei -3 dBFS.
- **Master Glue.** Die Ratio ändert nichts (2 bis 18), die Schwelle schon. Mit Schwelle 42 greift er bei diesem Pegel nicht.
- **Master Pumper.** `output_gain_adjust` 38 statt 32 hebt ihn um 2,9 dB, 42 wäre 2 dB über trocken.

### Änderungen (Stand der Messung, aktuelle Werte: `data/fx/catalog.mjs`)

| Effekt | Parameter | bisher | jetzt | Herleitung |
|---|---|---|---|---|
| Master Limiter | `threshold`, Regler | 64, 64 bis 40 | 52, 60 bis 44 | gemessen: im Bereich der Einheit, Mitte 52; überholt, seit #735 30, 36 bis 24 mit `attack` 10 |
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
