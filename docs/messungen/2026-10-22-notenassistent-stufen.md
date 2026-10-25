# Notenassistent: volle Helligkeit, sechs Stufen, die gespielte Note gedimmt (22.10.)

Rückmeldung am Gerät vom 22.10.: die Hinweise zeigen nur drei Stufen (hell, etwas hell, aus), die am besten passende Note nicht
in voller Helligkeit. Und dass die gespielte Note rot bleibt, war nicht zu sehen.

## Am Gerät gemessen (Hacktribe, BLECH von develop `145fa90`)

Nur gelesen, über USB-MIDI alle 60 ms: der LED-Manager (`*0xC0345A1C`, Wert je LED bei `+0x4E + 8 * LED`), der Zustand des Patches
(`0xC0189F00`) und der Transport (`0xC06BC318`). KEYBOARD, Pattern läuft.

| Was | Wert |
|---|---|
| Hinweise | Rot 63, 41 und 21, Blau 5/8 davon; beim Spielen je 120 ms um 2 dunkler |
| Pad der Note, solange sie klingt | Rot 192 (die Firmware) |
| Dasselbe Pad nach der Note, bis zur nächsten | Rot 191 (der Patch), Blau 0 |
| Dazwischen | rund 30 ms dunkel |

Das Rot nach der Note war also da, nur von den 192 der Firmware nicht zu unterscheiden. So sah es aus wie dauerhaft rot, und wie
lange die Note klingt, war nicht zu erkennen. Die 21 der Hinweise liest sich am Gerät wie aus.

## Was neu ist (`tools/patch/note_assist.py`)

- **Sechs Stufen bis voll:** 253, 181, 121, 81, 51, 33 (jede rund 0,7 der vorigen). KEYBOARD nach dem Abstand zur Note: Prim 253,
  Quinte 181, Quarte und große Terz 121, kleine Terz 81, große Sexte 51, kleine Sexte 33; ein Tonleiterschritt mindestens 81.
  CHORD nach dem Abstand der Grundtöne: V 253, IV 181, ii und vi 121, kleine Terz 81, derselbe Akkord und große Terz 51, kleine
  Sexte und kleine Septime 33.
- **Ausblenden:** beim Spielen verliert jede Stufe je 120 ms ein Achtel und 2, unter 9 ist sie aus: 253 nach rund 2,6 s, 33 nach
  rund 1 s (gerechnet).
- **Gespielte Note gedimmt:** nach dem Ende der Note Rot 65 statt 191. Klingt die Note, ist das Pad hell (192), danach dunkelrot.
- **Eigene Werte:** ungerade und nicht 255 statt ungerade und unter 128. Die Firmware schreibt nur 0, 192, 255 oder doppelte
  Velocity (`firmware_pad_values` im Emulator, alle sechs Pad-Modi).

## Im Emulator (`tools/emu/note_assist_cases.py`, Hacktribe)

32 von 33 Fällen. `next_note_takes_the_red` scheitert auch mit develop (`145fa90`) gleich: das Rot ist nach 0,4 s schon auf dem Pad
der zweiten Note, der Fall erwartet es dort erst nach 0,8 s. Der Fall lag falsch: wann die Schritte spielen, folgt dem Tempo des Patterns im
Flash. Seit dem 23.10. liest er die Pads alle 20 ms und prüft nur die Reihenfolge (erst Pad 2 rot, dann das Pad der zweiten Note).

## Offen am Gerät

- Ob 253 neben dem 192 der gespielten Note gut zu unterscheiden ist (rosa gegen rot).
- Ob die sechs Stufen am Gerät einzeln zu sehen sind.
