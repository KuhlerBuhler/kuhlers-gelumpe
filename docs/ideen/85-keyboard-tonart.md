# 85. KEYBOARD + Pad wählt den KEY

Wunsch (Pascal, 31.10.): wie Transpose auf den alten Electribes (EA-1 mkII: TRANSPOSE gehalten, Step-Tasten wählen den
Wert), aber über den KEY der Electribe 2. KEYBOARD gehalten, ein Pad gedrückt: der KEY des Patterns springt auf den Ton
des Pads. Kein eigenes Verschieben der Noten, die Firmware macht mit dem neuen KEY, was sie am Menü auch macht.
Stand 2026-10-31: **aufgeschrieben, nichts gebaut, am Gerät nichts.** Marker: **gemessen**, **hergeleitet**, **ungeprüft**.

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

## Offen

- Hat KEYBOARD gehalten + Pad in Korgs Firmware schon eine Bedeutung? (**ungeprüft**, erst im Emulator nachsehen)
- KEYBOARD kurz drücken schaltet den Modus; gehalten mit Pad darf ihn nicht umschalten.
- Was passiert mit klingenden Noten beim Wechsel? (**ungeprüft**)
- Gilt der neue KEY wie ein Dreh am Regler (WRITE atmet, ungespeichert)? (hergeleitet: ja, es ist ein Patternwert)
