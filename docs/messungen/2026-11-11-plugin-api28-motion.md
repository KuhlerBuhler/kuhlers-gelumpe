# Plugin API 28: Motion-Spuren und Motion an/aus

Stand 11. November 2026. **Gemessen** im Emulator mit Hacktribe 2.02 (eigene Datei), Korgs Original 2.02 rot und blau, jeweils
mit dem BLECH-Satz (`data/patches/blech.json`, für blau `blech-synth.json`). Fälle: `tools/emu/plugin_api28_cases.py` (läuft
als Gruppe von `remote_cases`). **Am Gerät nicht geprüft.**

## Frage

Kann ein Plugin die 24 Motion-Spuren des bearbeiteten Patterns lesen, einzelne Werte schreiben, Spuren so löschen wie die
Firmware, lesen, was die Motion-Wiedergabe gerade sendet, und die Motion des gewählten Parts an- und ausschalten wie TAP mit
dem Patch tap-motion?

## Weg

**Spuren im Pattern-Objekt** (`HW_PATTERN_OBJECT`, RAM-Abstände; im Pattern-Block 4 weniger, siehe `PATTERN_MOTION` in
`data/script/contract.mjs`):

| Was | RAM-Abstand | Inhalt |
|---|---|---|
| Besitzer | `+0x104 + Spur` | 0 frei, 1 bis 16 Part 1 bis 16, 17 Master-Effekt |
| Ziel | `+0x11C + Spur` | Ziel nach der Korg-Liste (10 Amp Level, 15 und 16 Master FX X und Y, 19 MFX-Pad) |
| Werte | `+0x134 + 0x40 * Spur + Step` | 0 leer, sonst Wert + 1; ein Regler 0 bis 255 steht halbiert |

`korg.motion.lane`, `destination` und `value` lesen diese Bytes, `setValue` schreibt ein Wertbyte, aber nur auf einer Spur
mit Besitzer.

**Löschen** geht über die Funktionen der Firmware, damit Wiedergabe und Spurzähler mitgehen:

| Funktion | Hacktribe / rot | blau | Marker |
|---|---|---|---|
| `clear_lane(Spur)`: Eintrag der Wiedergabe zurück, Ausgang -1, Zähler -1, Besitzer, Ziel und 64 Werte 0; nichts, wenn die Spur nicht belegt ist | `0xC0058BD4` | `0xC004FB68` | gelesen und gemessen |
| `clear_lanes_of(Besitzer)`: `clear_lane` für jede belegte Spur mit diesem Besitzer | `0xC0058CA8` | `0xC004FC3C` | gelesen und gemessen |
| Part Util CLEAR MOTION ruft `clear_lanes_of(Part + 1)` | `0xC00660C8` | `0xC005C380` | gelesen, im Emulator nachgedrückt |
| CLEAR MFX MOTION im Pattern-Menü ruft `clear_lanes_of(17)` | `0xC0067470` | `0xC005D650` | gelesen, im Emulator nachgedrückt |

Die blauen Adressen stehen in `data/synth-map/script-runtime.json`, gefunden über die Code-Signatur.

**Wiedergabe:** Tabelle `0xC068DB0C` (blau `0xC0567E04`), `0x24` je Spur: `+0` belegt, `+4` Besitzer, `+5` Ziel, `+0x10`
Ausgang (`0xFFFFFFFF` still, sonst Spurbyte - 1). `korg.motion.output` liest `+0x10`.

**`korg.motion.enabled`** (Blatt 54, Basis `motion`): gelesen wird das Modusbyte des gewählten Parts
(`Pattern + 0x807 + 0x330 * Part`) != 0. Geschrieben wird mit einem TAP-Druck über die Panel-Queue, wenn der Wert sich ändert
und der Patch tap-motion aktiv ist: das Wort am TAP-Hook (`0xC0042CC0`, blau über `auto.json`) muss ein `b` in den Code des
Patches (`0xC0188000` bis `0xC0188800`) sein, und `tm_active` am Anfang dieses Codes muss 1 melden.

## Ergebnisse

| Befund | Marker |
|---|---|
| Alle zehn Fälle grün auf Hacktribe 2.02, rot 2.02 und blau 2.02 mit BLECH, keine Assertion der Maschine | gemessen |
| Regler in Part 1 und eine Master-FX-Geste aufgenommen: Besitzer 1, 17, 17, 17, Ziele 10, 15, 16, 19; die Aufrufe lesen genau das | gemessen |
| `value` liest in Step 16 bis 31 die halbierte Reglerfahrt 8, 12 ... 68 | gemessen |
| `output` gleicht in jeder Probe beim Abspielen dem Wort der Wiedergabe; Spur 1 bis 3 klingen auch; nach STOP -1 überall | gemessen |
| Der Ausgang gleitet (Modus Smooth) und liegt bis zu einen Step vor dem abgetasteten Step, darum prüft der Fall Gleichheit mit dem Wort und den Bereich, nicht Step für Step | gemessen |
| Spur i der Wiedergabe liegt bei `0xC068DB0C + 0x24 * i`, nicht `+4 * i` wie früher in `2026-10-15-tap-motion.md` (dort berichtigt) | gemessen (Spur 0 bis 3) |
| `setValue` 100 schreibt Byte 101, -1 Byte 0, 0 Byte 1; auf einer freien Spur bleibt alles 0 | gemessen |
| `clearMfx` leert die drei MFX-Spuren und ihre Wiedergabe, Part 1 bleibt | gemessen |
| `clearPart(1)` lässt Part 1 stehen, `clearPart(0)` leert dessen Spur | gemessen |
| `clearLane(2)` leert nur Spur 2, sie bleibt beim Abspielen still; die anderen Spuren rücken nicht nach | gemessen |
| `enabled = 0` schaltet aus, ein zweites `= 0` drückt nicht, `= 1` stellt den gemerkten Modus Trigger Hold (2) wieder her | gemessen |
| Mit EXIT beim Einschalten gehalten (Patch aus) ändert `enabled = 0` nichts | gemessen |
| Der Simulator im Editor hat keine Motion-Wiedergabe: `output` liefert dort immer -1 | hergeleitet (`src/script/hardware.mjs`) |

## Offen

- Am Gerät ist nichts davon geprüft.
- Ob die Stimme dem Ausgang der Wiedergabe folgt, sieht der Emulator nicht (kein DSP), wie schon in `2026-10-15-tap-motion.md`.
