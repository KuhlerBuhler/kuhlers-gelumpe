# Plugin API 33: Samples lesen, Pattern speichern, Part kopieren

Stand 11. November 2026. **Gemessen** im Emulator mit Hacktribe 2.02 (eigene Datei), Korgs Original 2.02 rot und blau, jeweils
mit dem BLECH-Satz (`data/patches/blech.json`, für blau `blech-synth.json`). Fälle: `tools/emu/plugin_api33_cases.py` (läuft
als Gruppe von `remote_cases`). **Am Gerät nicht geprüft.** Teil 8 des Plans.

## Frage

Kann ein Plugin Namen und Daten der Samples lesen, das laufende Pattern speichern und einen Part kopieren, jeweils mit dem, was die
Firmware selbst hat?

## Weg

- `korg.read.sampleName(feld, slot)` liest die Namenstabelle `0xC047B080 + slot * 0x20`, Name bei +12, 16 Byte
  (`data/map/sample.mjs`, Messung `2026-10-07-sample-name-ram.md`). (gelesen, eigener Code)
- `korg.read.sampleInfo(slot, wert)` liest die Wiedergabetabelle `0xC0362EE8 + slot * 0x10` (Start +0, Loop +4, Ende +8, One-Shot
  +14) und die Metadaten `0xC036AD88 + slot * 0x45C` (Länge +4, Stereo +9, Samplerate +16, Tune +21 mit Vorzeichen). Die
  Tabellen liegen auf Hacktribe und rot an denselben Adressen. (gelesen, `data/map/sample.mjs`)
- Der Start in der Wiedergabetabelle ist Audio-Offset plus Startwert der Sample-Datei; `sampleInfo` zieht das vermutete
  Audio-Offset der Metadaten (+0) ab. (hergeleitet aus `data/map/sample.mjs`, am Gerät nicht verglichen)
- Blau hat keinen Sampler: beide Aufrufe geben -1 (`tools/patch/script_sample_none.s`). (gelesen, eigener Code)
- `korg.pattern.write()` macht, was EXIT + WRITE macht (`tools/patch/script_shortcuts.s`, Messung
  `2026-10-19-exit-shortcuts.md`): WRITE drücken, `shortcut_tick` gibt dem Fenster der Firmware das zweite WRITE. Nur auf dem
  Hauptbildschirm; solange ein Speichern noch auf sein Fenster wartet, gibt der Aufruf 0. (gelesen, eigener Code)
- `korg.part.copy(pattern, von, nach)` ruft Copy Part der Firmware (`0xC00667D4`, blau `0xC005C49C`) mit einem Objekt auf dem
  Stapel: +0x40 Quell-Pattern, +0x41 Quell-Part, +0x42 Ziel-Part, der Ziel-Part zusätzlich in r1 (Messung
  `2026-10-30-vorschau-part-reinholen.md`, dort ruft die Vorschau dieselbe Funktion so). (gelesen)

## Ergebnisse

| Befund | Marker |
|---|---|
| Der Part-Wert `sample` ist der Index in den Tabellen: SAMPLE/OSC eine Raste weiter, Wert 1, 2, 3; die Firmware zeichnet `002 PULSE`, `003 TRIANGLE`, `004 SINE`, die Namen an Index 1, 2, 3 | gemessen (Hacktribe und rot, Text-Hook an `0xC003F7D0`) |
| `sampleName` mit dem Sample von Part 1 gibt `SAW`, 3 Zeichen; Slot 400 in ein Feld mit 4 Plätzen gibt 4 Zeichen | gemessen (Hacktribe, rot) |
| Eigene Werte in den drei Tabellen von Slot 900: `sampleInfo` gibt Start ohne Offset, Ende, Loop, Tune -12, Stereo 1, Länge, One-Shot 1, 44100 Hz | gemessen (Hacktribe, rot) |
| Blau: `sampleName` und alle acht Werte von `sampleInfo` geben -1 | gemessen |
| `pattern.write` nach einer Änderung von Part 1: erster Aufruf 1, zweiter gleich danach 0, das Ereignis `write` kommt mit der laufenden Nummer, danach ist die Bank gleich dem RAM, Bildschirm 1, andere Plätze unverändert | gemessen (Hacktribe, rot, blau) |
| `part.copy(1, 3, 0)` mit geändertem Part 4 von Pattern 2 in der Bank: alle 0x330 Byte von Part 1 im RAM gleich der Quelle, die anderen Parts unverändert | gemessen (Hacktribe, rot, blau) |
| EXIT + WRITE und WRITE allein verhalten sich wie vorher (`shortcut_cases.case_save`) | gemessen (Hacktribe) |

## Pattern-Name schreiben

Keine eigene Funktion der Firmware gefunden: der Name steht im Pattern im RAM ab +16 (16 Byte), die Firmware schreibt ihn beim
Eingeben Zeichen für Zeichen aus dem Edit-Bildschirm. Ein direkter Schreibzugriff ginge, aber ob und wann der Hauptbildschirm den
neuen Namen zeichnet und ob die Änderung als ungespeichert zählt, ist nicht gemessen. Darum gibt es in API 33 keinen Aufruf dafür.
(gelesen, nicht gebaut)

## Part initialisieren

Part Util hat keine eigene Seite zum Initialisieren eines Parts, die in den Messungen vorkommt; nicht weiter gesucht. Ein Plugin
kann einen Part aus einem Init-Pattern der Bank mit `korg.part.copy` holen. (Urteil)

## Offen

- Gerät: alles oben; ob der Start ohne Audio-Offset dem Startwert im Sample-Menü entspricht.
- Die Einheit von Start, Loop und Ende ist nicht gemessen (Rohwerte wie in der Sample-Datei).
- `part.copy` mit Stereo-Paaren nicht geprüft.
