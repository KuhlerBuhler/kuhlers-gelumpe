# Notenassistent: die gespielte Note bleibt rot (22.10.)

Wunsch vom 22.10.: Spielt der Sequencer, sieht man nicht, welche Note gerade läuft. Gemessen im Emulator mit der eigenen
Hacktribe-2.02-Datei, Korgs Original 2.02 (rot) und dem blauen Synth 2.02, jeweils mit dem BLECH-Satz. **Am Gerät nicht geprüft.**

## Was vorher passierte (gemessen im Emulator)

KEYBOARD-Modus, Part 5, eine Note auf den Schritten 1, 5, 9 und 13, Pad-LEDs alle 10 ms gelesen.

| | ohne Notenassistent (EXIT beim Start) | mit Notenassistent |
|---|---|---|
| Licht der Firmware (Rot 192) auf dem Pad der Note | nur solange die Note klingt: bei kurzem Gate rund 10 ms, bei langem rund 70 ms | gleich lang, rund 10 ms später |
| danach | Pad dunkel | nach rund 30 ms der Hinweis der Prim, die hellste Stufe, gleich wie die Quinte |

Der Notenassistent überschreibt das Licht der Firmware also nicht. Die gespielte Note verschwindet aber zwischen den Hinweisen,
weil ihr eigenes Pad nach der Note den gleichen Hinweis bekommt wie die passenden Noten.

## Was neu ist (`tools/patch/note_assist.py`)

- Die Pads der zuletzt gespielten Note des gewählten Parts (`S_PLAY`, eine Maske über die 16 Pads) bekommen nach dem Ende der Note
  Rot 191 und ein dunkles Blau statt ihres Hinweises, bis die nächste Note kommt. 191 ist ungerade wie die anderen Werte des Patches;
  die Firmware schreibt nur 0, 192, 255 oder doppelte Velocity. Daran erkennt der Patch weiter seine eigenen LEDs.
- Nur solange das Pattern läuft (Transport 1 oder 4) und im KEYBOARD-Modus. Gestoppt, pausiert, in einem anderen Pad-Modus oder
  wenn die Hinweise enden, löscht der Takt der LEDs die Maske, und die Pads sind wie vorher.
- Liegt die Note auf dem Pad des gewählten Parts, zeigt es das Rot nur, solange Hinweise offen sind; sonst bekommt es wie bisher das
  Blau der Firmware zurück.
- Der Code wächst auf 0x754 Byte (Hacktribe und Korg rot, vorher 0x6D8) und 0x748 Byte (Synth), Platz bis 0x800. Kein neuer RAM-Bereich, `S_PLAY` liegt im
  vorhandenen Zustand bei +0x1C.

## Ergebnis (gemessen im Emulator)

| Fall | Hacktribe | Korg rot | Synth |
|---|---|---|---|
| Nach dem Licht der Firmware hält das Pad Rot 191 bis zur nächsten Note, gestoppt kommt der Hinweis zurück | ja | ja | ja |
| Eine zweite Note auf Schritt 5 übernimmt das Rot, das erste Pad bekommt wieder seinen Hinweis, gestoppt hält kein Pad mehr das Rot | ja | ja | ja |
| Alle 33 Fälle von `tools/emu/note_assist_cases.py` | 33/33 | 33/33 | 33/33 |
| Ganzer `tools/emu/check.py` mit dem BLECH-Satz | 459/459 | 484/484 | 348/348 |

Zwischen dem Ende der Note und dem Rot liegen bis zu 40 ms, ein Takt der LEDs. Beim nächsten Notenbeginn nimmt der Patch sein Rot
weg, damit die Firmware ihr eigenes Licht schreiben kann (sie schreibt nur ein dunkles Pad).

## Offen am Gerät

- Ob Rot 191 am Gerät gleich hell wirkt wie die 192 der Firmware.
- Ob das Rot bei schnellen Noten und mehreren Pads derselben Note ruhig bleibt.
