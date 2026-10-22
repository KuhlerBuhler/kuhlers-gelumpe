# FX-Katalog neu: Notenwerte der Delays, unbenutzte Bausteine, laute Distortion (22.10.)

Grundlage für den neuen Katalog des Baukastens (`data/fx/catalog.mjs`). Offline gelesen in der eigenen Hacktribe-2.02-Datei
und in Korgs Original 2.02 (rot), dazu der Emulator. **Kein Eintrag ist am Gerät gehört.** Keine Firmwarebytes und keine
Werte aus Werkspresets im Repository. Die Katalogwerte sind die Vorgaben aus `data/units.json` plus eigene Änderungen.

## 1. Notenwerte der Delays (offline, hergeleitet)

Im DSP-Strom (geladen wie in `tools/fx-tables.py`, `load_sdram`) liegt ab DSP `0x9470` eine Folge von Records zu 6 Byte:
Zähler und Nenner als 16-Bit-Zahlen und eine Null. Die LFO-Tabelle bei `0x97A0` aus
[2026-10-14-offene-fragen.md](2026-10-14-offene-fragen.md) (Abschnitt 8) ist ein Teil davon, Eintrag 136 bis 177. Davor liegen
zwei weitere Tabellen zu je 64 Einträgen:

- **Notenwert** (`on_syncnote` im Short Delay, `on_l_syncnote` und `on_r_syncnote` im Mod Delay, Spanne 0 bis 63): Eintrag 8 bis 71.
- **Zeitfaktor** (`on_time_ratio`, Spanne 0 bis 63): Eintrag 72 bis 135. Die Verzögerung ist Notenwert mal Faktor.

| Wert | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Notenwert | 1/64 | 1/32 | 1/24 | 1/16 | 1/12 | 1/8 | 1/6 | 3/16 | 1/4 | 1/3 | 3/8 | 1/2 | 3/4 | 1 |
| Faktor | 1/8 | 1/6 | 1/4 | 1/3 | 1/2 | 2/3 | 3/4 | 1 | 5/4 | 4/3 | 3/2 | 2 | 5/2 | 3 |

Ab Wert 14 wiederholen sich die Notenwerte in kürzeren Gruppen (14 bis 23: 1/64, 1/32, 1/16, 1/8, 1/6, 3/16, 1/4, 3/8, 1/2, 1;
24 bis 31: 1/64, 1/32, 1/16, 1/8, 1/6, 3/16, 1/4, 1/2; und so weiter), die Faktoren ebenso (35 ist 1, 62 ist 3/2).

**Warum diese Grenzen.** Die Tabellen schließen nahtlos an die bekannte LFO-Tabelle an (`0x9470 + 136 * 6 = 0x97A0`), und
alle Delay-Presets beider Firmwares passen, ohne Ausnahme:

| Preset | Notenwert | Faktor | ergibt |
|---|---|---|---|
| Korg Delay 1/4, 3/16, 1/8, 1/16, Roller 1/32 | 20, 19, 17, 16, 15 | 35 (1) | 1/4, 3/16, 1/8, 1/16, 1/32 |
| Hacktribe 1/12 Delay | 4 (1/12) | 35 (1) | 1/12 |
| Hacktribe 9/32 Delay | 7 (3/16) | 62 (3/2) | 9/32 |
| Hacktribe 3/32 Delay | 60 (1/16) | 62 (3/2) | 3/32 |
| Korg High Pass Delay (Mod Delay) | 17 und 19 | 35 (1) | 1/8 und 3/16 |

**Offen:** ob "1" ein Takt oder eine Viertel ist (Hörprobe), wie lang ein Delay höchstens werden darf, bevor der Puffer endet
(die Werkspresets gehen im Insert bis 9/32), und welche Tabellen Tape Echo (`s_note1`, `time_ratio`) benutzt. Dessen Werkspreset
passt nicht auf diese Tabellen, der Katalog ändert dort deshalb keinen Notenwert.

## 2. Unbenutzte Bausteine einsetzen (gemessen an den Werkspresets)

Sieben Master-Bausteine stehen in Hacktribe in keinem Preset: mKP2 Comp, Limiter, 4 Band EQ, Wah, Tremolo, Level Mod und
Dry Plate Reverb. Der Baukasten konnte sie bisher nicht einsetzen, weil ein Baustein immer mit dem Stufenblock eines Presets
kommt, in dem er an derselben Stelle steht ("Records are edited, never built").

Der Stufenblock (74 Byte ab dem Baustein-Byte) ist in allen Werkspresets beider Firmwares an jeder Stelle gleich, bis auf
das Baustein-Byte, das Byte danach (sonst `0x40`, bei einigen Filtern und dem Mute anders) und die Parameterwerte. Die
ungeraden Bytes zwischen den Parametern und die 15 Bytes dahinter sind überall null. Geprüft mit
`factory-check:stage-block-shared` (Hacktribe: Master 32, Insert Stufe 1 49, Stufe 2 8 Presets; Korg rot: 32, 38, 2).

Deshalb nimmt `fxToRecord` für einen Baustein, den kein Preset trägt, den Stufenblock, den die meisten Presets an dieser
Stelle teilen, und ändert nur das Baustein-Byte. **Offen:** ob die sieben Bausteine am Gerät so klingen wie gedacht. Wah und
Level Mod hat Korgs Original in Presets, die übrigen fünf stehen in keiner der beiden Firmwares in einem Preset.

## 3. Lautstärke der Distortion (gemessen am Gerät, 21.09.)

Der Insert-Distortion-Baustein (`0x0F`) liefert mit Korgs Werkspreset `output_level` 11. Spielbar waren 38 bis 60, 124 war
unspielbar laut ([2026-09-21-loudness.md](2026-09-21-loudness.md)). Die Verzerrer bleiben nah am Werkswert von `gain` (64): Loud Distortion 64 bei Ausgangspegel 40, Fuzz 80 bei 30, Crunch 40 bei 35. Der Acid Driver von Hot Overdrive hat Drive 70 und den Werkspegel 40. Der Regler fährt `gain` höchstens bis 100, Loud Distortion bis 96.

## 4. Der Katalog im Emulator (gemessen)

Alle 18 Einträge (16 Effekte, 2 Modulationen) bauen gegen Hacktribe und Korg rot ohne Fehler. Der Linter meldet nur
Warnungen und Hinweise. Die häufigste, `rest-not-silent`, kommt auch bei 61 von 81 Werkspresets. Mit dem aktuellen
BLECH-Satz von develop und der Sammeldatei auf der Karte meldet `tools/emu/fx_card_cases.py load` auf beiden Builds
`loaded` mit 18 Einträgen, und alle 18 Records im RAM sind byte-gleich mit der Datei.

Nicht geprüft: Klang, Pegel und ob die Steuerung am Gerät tut, was die Beschreibung sagt. Der Emulator rechnet kein Audio.
