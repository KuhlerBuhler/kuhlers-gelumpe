# 85. KEYBOARD + Pad wählt den KEY

Wunsch (31.10.): wie Transpose auf den alten Electribes (EA-1 mkII: TRANSPOSE gehalten, Step-Tasten wählen den
Wert), aber über den KEY der Electribe 2. KEYBOARD gehalten, ein Pad gedrückt: der KEY des Patterns springt auf den Ton
des Pads. Kein eigenes Verschieben der Noten, die Firmware macht mit dem neuen KEY, was sie am Menü auch macht.
Stand 2026-11-03: **gebaut als Plugin Key Pads im Katalog (API 15, `korg.keyHold`, `korg.pressKey`,
`korg.seq.setPatternValue`), im Simulator und Emulator geprüft (Hacktribe, rot, blau), am Gerät nichts.** Beschreibung in
[plugins.md](../plugins.md). Der Abschnitt zu API 14 unten ist der Stand davor. Marker: **gemessen**, **hergeleitet**, **ungeprüft**.

## Was es schon gibt

- KEY ist ein Wert des Patterns, Byte 39, 0 bis 11 für C bis B; daneben SCALE, Byte 40 (`data/map/pattern.mjs`). (gemessen)
- SCALE MODE ist ein Wert je Part, Byte 5 des Parts, ON/OFF. (gemessen)
- Welche Parts ein neuer KEY trifft (nur SCALE MODE ON?) und wie die Firmware ihre Noten dann rechnet. (**ungeprüft**)
- Auf dem EA-1 mkII blinkt TRANSPOSE, solange der Wert nicht 0 ist (Handbuch S. 30). (Quelle extern)

## Vorschlag

- KEYBOARD gehalten + Pad setzt den KEY. Belegung wie im KEYBOARD-Modus: untere Reihe C D E F G A B C, obere Reihe die
  schwarzen Tasten; jedes Pad wählt den Ton, den es dort spielt, das zweite C wieder C.
- Gesetzt wird über denselben Weg wie die Seite KEY im Pattern-Menü, damit Anzeige und Klang gleich reagieren.
- Optional: die KEYBOARD-LED blinkt, solange der KEY nicht C ist.

## Als Plugin geprüft (2026-11-03)

Geplant war ein Plugin im Katalog mit API 14. Es geht nicht, zwei Bausteine fehlen. (hergeleitet aus Vertrag, Laufzeit und
Eingangsfilter; nichts gebaut, kein Emulator, kein Gerät)

- **Der KEY lässt sich nicht setzen.** `korg.current.key` liest Byte 39, gesetzt wird es nirgends: die Werte eines Patterns
  sind nur lesbar (`data/script/properties.mjs` gibt `korg.current.*` keinen Setter), `korg.seq.setPartValue` nimmt nur
  `PART_FIELDS`, `korg.seq.writeSteps` nur Steps, der Objektbaum (`data/script/objects.mjs`) hat keinen Zweig für das Pattern.
  Fehlt: ein Setter für Werte des Patterns, mindestens `key`, über die Funktion der Firmware, die die Seite KEY im
  Pattern-Menü nimmt, damit Anzeige und Klang wie dort reagieren. Diese Funktion ist noch nicht vermessen.
- **KEYBOARD und die Pads lassen sich ohne App nicht abfangen.** `korg.passKeys` wirkt nur, solange eine App offen ist
  (`input_mask` in `tools/patch/script_hooks.s` prüft `APP_STATE`). Ohne App sieht die Firmware jeden Druck auf KEYBOARD und
  schaltet den Modus um. `korg.padHold` hält zwar Pads fern, das Plugin weiß aber nicht, ob KEYBOARD erst gehalten wird oder
  den Modus umschalten soll. Als App ginge es, nur ist das Display dann das der App, und es gibt keinen Aufruf, der
  KEYBOARD bei einem kurzen Druck an die Firmware weiterreicht (nur `korg.passKeys` für Druck und Loslassen zusammen).
  Fehlt: eine Taste ohne App zurückhalten können (ein `keyHold` wie `korg.padHold`), und ein Aufruf, der einen kurzen Druck
  nachträglich an die Firmware gibt.

Der Weg ist damit eine Erweiterung der Laufzeit (API 15), danach ein Plugin. Oder gleich in der Firmware, ohne Plugin.

## Offen

- Hat KEYBOARD gehalten + Pad in Korgs Firmware schon eine Bedeutung? (**ungeprüft**, erst im Emulator nachsehen)
- KEYBOARD kurz drücken schaltet den Modus; gehalten mit Pad darf ihn nicht umschalten.
- Was passiert mit klingenden Noten beim Wechsel? (**ungeprüft**)
- Gilt der neue KEY wie ein Dreh am Regler (WRITE atmet, ungespeichert)? (hergeleitet: ja, es ist ein Patternwert)
