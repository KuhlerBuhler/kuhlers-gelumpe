# Plugin API 32: eine Datendatei pro Plugin auf der Karte

Stand 11. November 2026. **Gemessen** im Emulator mit Hacktribe 2.02 (eigene Datei), Korgs Original 2.02 rot und blau, jeweils
mit dem BLECH-Satz (`data/patches/blech.json`, für blau `blech-synth.json`). Fälle: `tools/emu/plugin_api32_cases.py` (läuft
als Gruppe von `remote_cases`). **Am Gerät nicht geprüft.** Teil 7 des Plans.

## Frage

Kann ein Plugin eigene Bytes auf der Karte ablegen und nach dem Ausschalten wieder lesen, ohne die Firmware beim Laden oder
Speichern zu stören?

## Weg

- `korg.file.read(feld, offset)` und `korg.file.write(feld, offset)` arbeiten auf `SD:KORG/blechtribe/Plugin/Data/<name>.bin`.
  `<name>` ist der Programmname aus dem Kopf des Blocks; Zeichen außer A bis Z, a bis z, 0 bis 9 und `-` werden `_`
  (`dataFileName` in `data/script/contract.mjs`). (gelesen, eigener Code)
- Größe: höchstens `SCRIPT_DATA_FILE.maxBytes` = 4096 Byte. Eine Konstante; sie kann später wachsen. (Entscheidung, 4 KiB als
  vorsichtiger Anfang)
- Die Datei eines Plugins liegt in einem Block aus dem Heap der Firmware (`new` `0xC0028DCC`, blau `0xC0026240`): 16 Byte Name,
  dann die Daten. Der Block wird beim ersten Aufruf geholt und bis zum Ausschalten gehalten. Der Zeiger und drei Zustandsworte
  liegen in der Reserve hinter `SIM_INPUT_END` in MORE2 (16 Byte, beim Einschalten FF). (gelesen, eigener Code)
- Lesen von der Karte nur auf dem Hauptschirm oder im Menü BLECH, wie beim Store. Schreiben geht zuerst nur in den Block;
  `script_data_flush` schreibt ihn wie `script_store_flush`: auf dem Hauptschirm oder in BLECH und frühestens
  `STORE_MIN_PAUSE_FRAMES` (2 s) nach dem letzten Schreiben. (gelesen, eigener Code)
- Ohne Karte, auf einem anderen Bildschirm oder solange die Änderung eines anderen Plugins noch nicht auf der Karte ist, geben
  beide Aufrufe -1. (gelesen, eigener Code)

## Ergebnisse

| Befund | Marker |
|---|---|
| Ohne Datei liest `read` 0 Byte, `write` nimmt 8 Byte; nach der Pause steht `07 08 09 2c 01 00 00 ff` auf der Karte (300 wird 0x2C, nur das untere Byte) | gemessen |
| Neustart mit dem Kartenabbild: `read` gibt 8, die Werte kommen zurück | gemessen |
| Ohne Karte: `read` und `write` geben -1 | gemessen |
| Datei mit 5 Byte: ab 0 gibt 5, ab 2 gibt 3, ab 9 gibt 0; Plätze hinter dem Ende bleiben 0 | gemessen |
| `write` an Offset 10 auf die 5-Byte-Datei: auf der Karte 12 Byte, die Lücke 5 bis 9 ist 0 | gemessen |
| Gleiche Zahlen auf Hacktribe, rot und blau | gemessen |
| 4 KiB plus 16 Byte aus dem Heap sind 0,2 % der freien 1,9 MB nach dem Start | hergeleitet (`2026-11-11-spettro-worker-platz.md`) |

## Offen

- Gerät: wie lange das Schreiben von 4 KiB auf einer echten Karte dauert und ob es hörbar ist.
- Mehrere Plugins mit Datei abwechselnd: der Block hält immer nur eine Datei; wechselt das Plugin, wird neu gelesen, und ein
  anderes Plugin bekommt -1, bis die offene Änderung geschrieben ist. Im Emulator nicht getrennt gemessen.
- Eine Datei, die länger als 4 KiB ist, wird nur bis 4 KiB gelesen; das nächste Schreiben legt sie neu an (`card_create`,
  Modus 0x0A mit CREATE_ALWAYS) und kürzt sie damit auf 4 KiB. (hergeleitet, nicht gemessen)
