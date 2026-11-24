# Image Viewer: Zeiten auf Hacktribe, Korg rot und blau

16.11.2026, **gemessen im [Emulator](../glossary.md#emulator)** (`tools/emu`), am Gerät nicht. Firmware: [Hacktribe](../glossary.md#hacktribe) 2.02, Korg 2.02 rot (Sampler)
und Korg 2.02 blau (Synth), jeweils mit dem BLECH-Satz gepatcht wie die Seite (`applyPatches`, `data/patches/blech.json`
bzw. `blech-synth.json`), Laufzeit aus Commit `c1a71017`. Uhr: die Emulator-Zeit (`Machine.time_ns`), Timer3 150 MHz.

Befehl je Build:

```
PYTHONPATH=tools/patch tools/emu/.venv/bin/python tools/emu/plugin_api38_cases.py --vsb PATCHED.VSB
```

Ergebnis: 40 von 40 Fällen auf allen drei Builds. Die Zahlen stehen im Detail des Falls
`plugin_api38:viewer_plays_loading_blla_at_48_ms_and_stays_on`.

## Aufbau

Karte mit `Media/`: `marker.bmp`, `loading.blla` (Blechy, 109 Bilder, `assets/blechy/loading.blla`),
`top-down-picture-long.bmp` (Höhe -64), `broken.bmp` (24 Bit), `small.blla` (3 + 2 Bilder). Die Zeiten kommen aus
Hooks in der Laufzeit (`Probe` in `tools/emu/plugin_api38_cases.py`):

- **Kartenzeit**: von `card_timed` (`tools/patch/script_media.s`) bis zur Rückkehr des Glue, je Aufruf.
- **Rahmen**: ein Lauf von `script_frame_hook`, alle Plugins eines Rahmens samt Kartenzeit.
- **Handler**: `SCRIPT_ENTRY` +40, der langsamste Handler des Plugins in Ticks, ohne Kartenzeit (`CARD_READS`).

## Zeiten

| Was | Hacktribe | Korg rot | Korg blau |
|---|---|---|---|
| langsamster Handler (ohne Kartenzeit) | 0,37 ms | 0,44 ms | 0,44 ms |
| `korg.file.count`, 5 Dateien in `Media/` | 4,1 ms | 4,0 ms | 3,9 ms |
| `korg.file.count`, 70 BMP in `Media/` (64 gelistet) | 20,1 ms | 20,1 ms | 20,1 ms |
| `korg.file.name` | 0,1 ms | 0,0 ms | 0,1 ms |
| `korg.file.picture`, BMP 1 KiB | 9,3 ms | 9,2 ms | 9,4 ms |
| `korg.file.picture`, kaputte BMP (24 Bit) | 5,1 ms | 5,0 ms | 5,0 ms |
| `.blla`, erstes Bild nach Dateiwechsel (ganze Datei geprüft) | 24,9 ms | 24,1 ms | 24,1 ms |
| `.blla`, Sprung auf das letzte Bild (Bild 108) | 21,3 ms | 21,3 ms | 21,3 ms |
| `.blla`, ein Bild weiter | 7,0 ms | 6,6 ms | 6,9 ms |
| `.blla` beim Abspielen mit 48 ms, langsamstes Bild | 23,2 ms | 22,7 ms | 22,7 ms |
| Rahmen beim Abspielen mit 96 ms (`small.blla`), Mittel / Max | 4,0 / 13,3 ms | 3,9 / 12,8 ms | 3,9 / 12,8 ms |
| Rahmen beim Abspielen mit 48 ms (`loading.blla`), Mittel / Max | 6,9 / 23,4 ms | 6,7 / 22,9 ms | 6,8 / 22,9 ms |
| Bilder gelesen in 5 s bei 48 ms | 104 | 104 | 104 |

Die Zeile mit 70 BMP kommt aus einem eigenen Lauf (Skript nur im Scratchpad: ein Plugin ruft `korg.file.count(0)` einmal
in einem `frame`-Handler, Karte mit `pic00.bmp` bis `pic69.bmp`, gleiche `Probe`); er gibt 64 zurück, das Plugin bleibt an.

**gemessen im Emulator.** Das langsamste Bild beim Abspielen ist der Umlauf vom letzten Bild auf Bild 0. Der
Max-Wert bei 96 ms enthält das Umschalten auf `loading.blla` mitten im Abschnitt (die Datei wird beim Wechsel einmal
ganz geprüft).

## Was daraus folgt

- Kein Handler kommt an die Warnung von 0,5 ms, das Plugin bleibt bei 48 ms an (Zustand 2, kein Fehler, keine
  Assertion). Ohne die Regel aus `CARD_READS` wäre jedes Bild über dem Rahmenbudget von 5 ms.
- Die Kartenzeit je Rahmen bleibt mit höchstens 25 ms unter `CARD_READS.cardMs` (50 ms).
- Ein Rahmen mit Kartenlesen dauert bis 23 ms statt 40 ms Rahmenabstand: der Rahmen wird nicht übersprungen, aber
  am Gerät ist das Lesen nicht gemessen (**offen**).
- `korg.file.write` geht seit `c1a71017` auch durch `card_timed`; ein `write` je Rahmen bleibt an
  (`plugin_api38:write_every_frame`, alle drei Builds).
