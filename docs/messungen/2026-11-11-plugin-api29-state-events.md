# Plugin API 29: Zustand lesen und Events für Sequencer-Plugins

Stand 11. November 2026. **Gemessen** im Emulator mit Hacktribe 2.02 (eigene Datei), Korgs Original 2.02 rot und blau, jeweils
mit dem BLECH-Satz (`data/patches/blech.json`, für blau `blech-synth.json`). Fälle: `tools/emu/plugin_api29_cases.py` (läuft
als Gruppe von `remote_cases`). **Am Gerät nicht geprüft.**

## Frage

Kann ein Plugin den Pad-Modus, den gezeigten Takt auf den Pads und die Nummer des Bildschirms lesen, Änderungen davon und jedes
WRITE als Ereignis bekommen, den Namen eines Patterns lesen und Bytes eines Arrays als Text zeichnen?

## Weg

**Lesen** (neue Basis `state` im Objektbaum, Blätter 55 bis 57, nur lesbar):

| Blatt | Wort | blau |
|---|---|---|
| `korg.pads.mode` | `[0xC0345A1C] + 0xB58` (LED-Manager) | über `data/synth-map/auto.json` |
| `korg.pads.bar` | `[0xC0348884] + 0x344` (Modell) | `0xC034858C` |
| `korg.screen` | `[0xC03404C0] + 0x2C` (Screen-Manager) | `0xC03406B0` |

Die Adressen stammen aus `2026-10-19-poly-pads-pink.md` (Pad-Modus, Takt) und dem Screen-Manager, den die Laufzeit schon nutzt.
Ist der Zeiger 0 oder -1 (früh beim Start), liest das Plugin -1.

**Ereignisse** `padMode(mode)` und `screen(number)`: der Frame-Hook vergleicht die Worte mit dem letzten Stand und meldet jede
Änderung, wie `touchpadMode`. Werte ab 256 meldet er nicht.

**Ereignis `write(pattern)`**: ein Hook am Anfang der Schreibfunktion der Firmware (`0xC004C28C`, blau `0xC0046090`, gleiche 22
Befehle, per Disassembly verglichen), r1 ist die Pattern-Nummer. Der Plan sah den Kopieraufruf `0xC004C2BC` vor, den auch
mfx-switch nutzt. Am Funktionsanfang teilt sich der Hook die Stelle mit keinem anderen Patch und braucht keine Verkettung.

**`korg.read.patternName(array, pattern)`**: wie `patternBytes` ab Byte 16 des Blocks, höchstens 16 Bytes. -1 ist das Pattern
im RAM, 0 bis 249 die Bank.

**`korg.display.chars(array, x, y, count)`**: das untere Byte jedes Slots als Zeichen, bis `count` (höchstens 31), Array-Ende
oder 0, dann wie `korg.display.text`.

## Ergebnisse

| Befund | Marker |
|---|---|
| Alle sechs Fälle grün auf Hacktribe 2.02, rot 2.02 und blau 2.02 mit BLECH, keine Assertion der Maschine | gemessen |
| Nach dem Start: Pad-Modus 3 (TRIGGER), Takt 0, Bildschirm 1 | gemessen (Hacktribe) |
| Pad-Modus nach den Tasten: TRIGGER 3, SEQUENCER 4, KEYBOARD 5, CHORD 6, STEP JUMP 7, PATTERN SET 9; Blatt = Wort | gemessen |
| PATTERN SET geht über einen Zwischenmodus: zwei `padMode`-Ereignisse, das letzte mit 9 | gemessen |
| Gleicher Modus noch einmal (TRIGGER zweimal): kein Ereignis | gemessen |
| Takt im SEQUENCER-Modus bei 4 Takten: BAR 4 bis 1 geben 3 bis 0, BAR 1 bis 4 geben 0 bis 3; Blatt = Wort | gemessen |
| Bildschirm: Hauptbild 1, nach MENU 3, nach EXIT wieder 1; je ein `screen`-Ereignis | gemessen |
| WRITE mit Bestätigung: genau ein `write`-Ereignis mit dem geschriebenen Pattern (0) | gemessen |
| `patternName` liest 16 Bytes aus dem RAM und aus der Bank (Pattern 5), wie die Bytes im Speicher | gemessen |
| `chars` mit `[72, 105, 289, 0, 65]` zeichnet dieselben Pixel wie `text("Hi!")` | gemessen |
| Gleiche Zahlen auf blau | gemessen |

## Offen

- Am Gerät ist nichts davon geprüft.
- 4.4 Ein gemeinsamer Setter für Part- und Pattern-Werte (Regler, Menü, Motion, MIDI) ist nicht untersucht. Ohne ihn kein
  Ereignis `partValue`/`patternValue`; nicht gesucht, nicht geraten.
- 4.5 Die Oktave der KEYBOARD-Pads: `touch_scale_zero_cases` misst, dass KEYBOARD + BAR 1/4 das Oktavwort des Touch-Scale-Objekts
  (`+0x18`) verschiebt. Ob das dieselbe Oktave ist, die die Pads spielen, ist hergeleitet, nicht gemessen; daher noch kein Blatt.
- Die Bildschirmnummern außer Hauptbild (1) und Menü (3) sind nicht vermessen.
