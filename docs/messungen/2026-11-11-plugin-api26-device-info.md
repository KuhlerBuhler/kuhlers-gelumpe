# Plugin API 26: Gerät, Version und Grenzen lesen

Stand 11. November 2026. **Gemessen** im Emulator mit Hacktribe 2.02 (eigene Datei), Korgs Original 2.02 rot und blau, jeweils
mit dem BLECH-Satz (`data/patches/blech.json`, für blau `blech-synth.json`). Fälle: `tools/emu/plugin_api26_cases.py` (läuft
als Gruppe von `remote_cases`). **Am Gerät nicht geprüft.**

## Frage

Ein Plugin wusste bisher nicht, auf welcher Electribe es läuft, und musste die Zahl der Effekte und Sample-Plätze fest
eintragen. Lässt sich das zur Laufzeit lesen, ohne neue Adressen zu raten?

## Weg

Die fünf neuen Blätter liegen auf einer eigenen Basis `info` (5) im Objektbaum der Laufzeit (`tools/patch/script_objects.s`,
`objects_info_get`). Keins davon ist eine neue RAM-Adresse:

| Blatt | Quelle |
|---|---|
| `korg.system.device` | Konstante beim Bau der Laufzeit: 0 hacktribe, 1 stock (rot), 2 synth (blau), `BUILD_DEVICES` in `tools/patch/script_hooks.py` |
| `korg.system.version` | der Text des Patches blech-version bei 0xC014FCF0 ("BLECH x.y.z"), gelesen als x * 10000 + y * 100 + z; 0, wenn dort nicht "B" steht |
| `korg.system.limits.ifxTypes` | Rückgabe der Zählfunktion der Firmware 0xC003EFDC (blau 0xC0039BFC, über `data/synth-map`) |
| `korg.system.limits.mfxTypes` | Rückgabe der Zählfunktion der Firmware 0xC003EFE4 (blau 0xC0039C04) |
| `korg.system.limits.samples` | Konstante beim Bau: 1000 auf dem Sampler, 0 auf dem blauen Synth |

Die Zählfunktionen sind dieselben, die die Firmware für ihre Effektlisten ruft. Ein Effekt-Katalog, der Effekte anhängt,
erhöht die Zahl also ohne Änderung an der Laufzeit.

Die Fälle rufen `script_object_get_glue` direkt mit den Blättern 48 bis 52 und lassen außerdem ein Plugin die Blätter beim
Ereignis `ready` lesen. Erwartet wird, was der Fall selbst ausrechnet: die Gerätekonstante, die 16 Byte bei 0xC014FCF0 und die
Rückgabe der Zählfunktionen. Danach versucht `korg.set` auf jedes Blatt den Wert 7 zu schreiben, und danach muss alles gleich
sein.

## Ergebnisse

| Befund | Marker |
|---|---|
| Hacktribe 2.02 + BLECH: device 0, version 10405, ifx 73, mfx 43, samples 1000 | gemessen |
| Korg 2.02 rot + BLECH: device 1, version 10405, ifx 62, mfx 43, samples 1000 | gemessen |
| Korg 2.02 blau + BLECH: device 2, version 10405, ifx 38, mfx 32, samples 0 | gemessen |
| Glue und Plugin lesen auf allen drei Builds dieselben Werte; keine Assertion der Maschine | gemessen |
| `korg.set` ändert keins der fünf Blätter | gemessen |
| Die Effektzahlen enthalten den Effekt-Katalog des BLECH-Satzes; ohne Katalog wären sie kleiner | hergeleitet |

Die Standardwerte des Browser-Simulators (`factory` in `data/script/objects.mjs`) sind die Hacktribe-Werte von oben: 73 und 43.

## Offen

- Am Gerät gelesen ist keiner der Werte.
- `version` setzt voraus, dass der Patch blech-version im Satz ist. Ohne ihn liest ein Plugin 0.
