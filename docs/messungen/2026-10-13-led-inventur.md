# LED-Inventur am eigenen Gerät

Stand 2026-10-13. Eigenes Gerät, eigene Testfirmware (Fingerabdrücke von
`tools/device/led_inventory.py --identify` gleich der Datei), nur RAM über Hacktribes
Execute, Originalbytes danach zurück. Die LEDs wurden am Gerät beobachtet.
Markierungen: **gemessen**, **hergeleitet**, **offen**.

## Ablauf

`tools/device/led_inventory.py --hold 1.5` schaltet die LED-Nummern `0x00` bis `0x57`
einzeln über die LED-Funktion der Firmware (`0xC0028600`). LEDs, die die Firmware auf dem
Hauptbildschirm im Stand leuchten lässt (im Emulator bestimmt: `0x01` bis `0x04`, `0x0c`,
`0x0f`, `0x11`, `0x16`, `0x1b`, `0x22`, `0x28`, `0x2d`), gehen in ihrem Schritt aus und
danach wieder an; alle anderen gehen an und wieder aus.

## Ergebnis

- **Gemessen:** Die fünf Regler-LEDs `0x00` bis `0x04` (VALUE, SAMPLE/OSC, CUTOFF,
  MOD TYPE, IFX TYPE) sind verbaut und schaltbar. VALUE ist im Stand aus und leuchtet in
  der Firmware nur beim Drehen; die anderen vier sind im Stand an.
- **Gemessen:** Ein erster Lauf, der jede LED danach ausschaltete, ließ die vier Regler-LEDs
  aus; sie kamen erst mit einem eigenen Setzen auf 255 zurück. Die Firmware setzt LEDs nicht
  von selbst neu.
- **Gemessen:** Tasten `0x05` bis `0x2b`: alle sichtbar. Im ersten Durchlauf war
  bei einem Schritt keine Änderung zu sehen; welcher, ist **offen**.
- **Gemessen** (zweiter Lauf `--only 0x14-0x1a --hold 4`): die bisher unbekannten Nummern
  sind die blauen LEDs. `0x15` PLAY blau (zweite PLAY-LED), `0x16` bis `0x19` die Tasten
  1 bis 4 in Blau. `0x16` (Taste 1 blau) leuchtet im Stand. Die roten LEDs der Tasten 1 bis
  4 sind `0x28` bis `0x2b`. Eingetragen in `data/panel.mjs` als `ledBlue`.
- **Gemessen:** `0x09` und `0x15` lassen PLAY je allein blau leuchten. Im direkten Vergleich
  (nacheinander je 4 s, dann beide) ist `0x15` etwas dunkler als `0x09`; beide zusammen
  machen die Taste deutlich heller. PLAY hat damit drei Helligkeiten über zwei LEDs.
- **Gemessen:** Pads `0x2c` bis `0x4b`, je rot und blau, alle sichtbar.
- **Gemessen:** Untere RGB-LEDs `0x4c` bis `0x57`: alle sichtbar, nur kurz, weil die
  Pegelanzeige sie 25-mal pro Sekunde überschreibt.
- **Hergeleitet** aus dem Werkstatt-Testmodus der Firmware (Liste der LED-Namen): nur PLAY
  (zwei LEDs) und die Tasten 1 bis 4 haben Blau, alle anderen Tasten nur Rot.
