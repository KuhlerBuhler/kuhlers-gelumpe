# Step-Trigger (Byte 3): wann er zählt, mit Voice Assign, im Emulator

Stand 2026-11-06. Anlass: die Frage, ob ein Step mit Trigger 0 klingt und ob Voice Assign dabei eine Rolle spielt.
Gemessen im Emulator auf Hacktribe 2.02 (rot). Am Gerät nichts ausgeführt, die blaue nicht geprüft.

## Aufbau

- Part 5, Step 1 an (Note C4, Gate 72, Trigger 1), Step 2 an mit Gate 72, Velocity 100, Note C4 oder E4, Trigger 0 oder 1.
- Gate von Step 1 einmal 72 (normal), einmal 127 und 255 (TIE).
- Voice Assign über den Setter der Firmware (`0xC00493A0`): Mono1, Mono2, Poly1, Poly2.
- Tempo 120, PLAY, nach 0,6 s STOP. Mitgeschrieben wurden die Aufrufe von Note-on (`0xC005AD44`) und Note-off
  (`0xC005A20C`) für den Part und der Step-Abspieler (`0xC005F70C`), der Byte 3 liest.

## Ergebnis

**gemessen**, 48 Läufe, für alle vier Voice Assigns gleich bis auf eine Zeile:

| Step davor | Trigger 0 | Trigger 1 |
|---|---|---|
| normaler Step (Gate 72) | neuer Anschlag | neuer Anschlag |
| TIE (Gate 127 oder 255), gleiche Note | kein neuer Anschlag, die Note läuft weiter | neuer Anschlag |
| TIE, andere Note | Mono1 und Poly1: Legato, das Note-on der neuen Note kommt vor dem Note-off der alten. Mono2 und Poly2: neuer Anschlag | neuer Anschlag |

- Trigger 0 zählt nur hinter einem TIE. Ein Step mit Trigger 0 hinter einem normalen Step klingt genau wie mit Trigger 1.
- Gate 127 und 255 verhalten sich gleich. **offline (Code):** der Abspieler wertet ein Gate über 96 als TIE (`0xC005FC40`).
- **offline (Code):** Mono1 und Poly1 tragen im Klang des Parts ein Legato-Flag (`0xC068E83C + Part * 0xCC`, Byte `+0xC7`),
  Mono2 und Poly2 nicht; Byte `+0xC2` ist die Stimmenzahl (1 oder 4).

## Werks-Patterns

**gemessen** (Skript über die Werks-Patterns der Sampler-Firmware, 25209 aktive Steps):

- Trigger 0 steht fast nur hinter einem TIE: 5959 Steps mit Trigger 0 gegen 85 mit Trigger 1.
- Gate kommt nur als 0 bis 96, 127 und 255 vor.
- Mono2 und Poly2 haben in der Verteilung keine Sonderrolle.
- 954 Steps mit Trigger 0 folgen auf einen ausgeschalteten Step. Nach der Messung oben klingen sie normal.

## Was die Bedienung schreibt

- **offline (Code):** Ein Step, der per Pad entsteht, bekommt Trigger 1.
- **hergeleitet:** Setzt man einen TIE, schreibt der Setter des Gates (`0xC0049214`) beim nächsten Step Trigger 0.

## Folgen

- Die Warnung "Step an ohne Trigger klingt nicht" im Linter war falsch und ist entfernt ([Linter](../linter.md)).
- Der Step-Editor zeigt Trigger 0 nur noch als Hinweis, wenn der Step davor ein TIE ist.

## Offen

- Welche Hüllkurve bei Legato weiterläuft, geht nur per Hörtest am Gerät.
- Die blaue Electribe.
- Am Gerät selbst nichts nachgeprüft.
