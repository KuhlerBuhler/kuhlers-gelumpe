# Notenassistent: Helligkeit nach Passung, stehen lassen und ausblenden (19.10., Stand 22.10.)

Wunsch vom 16.10. und 19.10.: die am besten passenden Noten heller als die weniger passenden. Der feste 1,5-s-Timer weg: gestoppt
oder pausiert bleiben die Hinweise stehen, beim Spielen blenden sie langsam aus, eine Note bei 0 verschwindet. So bleiben die
passenderen Noten länger zu sehen. Rückmeldung am Gerät vom 22.10.: drei Stufen (hell, etwas hell, aus) reichen nicht, die am besten
passende Note soll in voller Helligkeit leuchten, und die gespielte Note soll als Note erkennbar bleiben. Die rohen Notizen stehen
in der Git-Historie (`git show 03c7827adc7b:docs/messungen/2026-10-22-notenassistent-stufen.md` und `...-spielende-note.md`).

## Was gilt (`tools/patch/note_assist.py`)

- **Sechs Stufen bis voll:** 253, 181, 121, 81, 51, 33 (rote LED von 255, jede rund 0,7 der vorigen). Die blaue LED bekommt 5/8 davon,
  ungerade. Stufe je Pad nach dem Abstand zur gespielten Note (in Halbtönen, modulo 12):

  | Abstand | Stufe |
  |---|---|
  | Prim/Oktave (0) | 253 |
  | Quinte (7) | 181 |
  | Quarte (5), große Terz (4) | 121 |
  | kleine Terz (3) | 81 |
  | große Sexte (9) | 51 |
  | kleine Sexte (8) | 33 |
  | der Tonleiterschritt hoch und runter (Nachbar in der Tabelle der Tastatur) | mindestens 81 |
  | sonst | dunkel |

- **Eigene Werte** sind ungerade und nicht 255. Die Firmware schreibt nur 0, 192, 255 oder doppelte Velocity (gerade; gemessen im
  Emulator, `firmware_pad_values`, alle sechs Pad-Modi). Daran erkennt der Patch seine eigenen LEDs.
- **Transport** (`0xC06BC318`, gemessen): 0 Stop, 1 Play, 2 Pause, 3 Rec bereit, 4 Rec mit Play. Bei 0, 2 und 3 bleiben die
  Stufen stehen. Bei 1 und 4 verliert jede Stufe alle 3 Ticks (120 ms) ein Achtel und 2, unter 9 ist sie aus: 253 nach rund 2,6 s,
  33 nach rund 1 s (gerechnet, nicht gemessen).
- Eine neue Note ersetzt die Stufen sofort. Ein anderer Pad-Modus, ein anderer Bildschirm, eine andere Oktave, Tonart oder Skala
  beendet sie wie bisher. Ist das letzte Pad dunkel, bekommt das Pad des gewählten Parts das Blau der Firmware zurück.

### Die gespielte Note bleibt als Note erkennbar

- Die Firmware leuchtet das Pad der gespielten Note nur solange die Note klingt rot (192): bei kurzem Gate rund 10 ms, bei langem
  rund 70 ms (gemessen im Emulator, KEYBOARD, Part 5, Pad-LEDs alle 10 ms gelesen; ohne Notenassistent und mit gleich). Der
  Notenassistent überschreibt dieses Licht nicht.
- Die Pads der zuletzt gespielten Note des gewählten Parts (`S_PLAY`, eine Maske über die 16 Pads, Zustand `+0x1C`) bekommen nach
  dem Ende der Note Rot 65 und ein dunkles Blau, bis die nächste Note kommt. Klingt die Note, ist das Pad hell (192), danach dunkelrot.
- Nur solange das Pattern läuft (Transport 1 oder 4) und im KEYBOARD-Modus. Gestoppt, pausiert, in einem anderen Pad-Modus oder
  wenn die Hinweise enden, löscht der Takt der LEDs die Maske, und die Pads sind wie sonst.
- Liegt die Note auf dem Pad des gewählten Parts, zeigt es das Rot nur, solange Hinweise offen sind; sonst bekommt es das Blau der
  Firmware zurück.
- Zwischen dem Ende der Note und dem Rot liegen bis zu 40 ms (ein Takt der LEDs). Beim nächsten Notenbeginn nimmt der Patch sein Rot
  weg, damit die Firmware ihr eigenes Licht schreiben kann (sie schreibt nur ein dunkles Pad).
- Kein neuer RAM-Bereich, `S_PLAY` liegt im vorhandenen Zustand des Patches (`0xC0189F00`).

### Was am Gerät zu den früheren drei Stufen gemessen wurde

Hacktribe, nur gelesen über USB-MIDI alle 60 ms (LED-Manager `*0xC0345A1C`, Wert je LED bei `+0x4E + 8 * LED`, Zustand des Patches
`0xC0189F00`, Transport `0xC06BC318`), KEYBOARD, Pattern läuft, 22.10.: Hinweise Rot 63, 41 und 21, Blau 5/8 davon, beim Spielen je
120 ms um 2 dunkler. Das Pad der Note: Rot 192 (Firmware) solange sie klingt, danach Rot 191 (Patch) bis zur nächsten Note, Blau 0,
dazwischen rund 30 ms dunkel. Das Rot nach der Note war da, aber von den 192 der Firmware nicht zu unterscheiden, und die 21 las sich
am Gerät wie aus. Daraus folgen die sechs Stufen bis 253 und das dunklere Rot 65 für die gespielte Note.

## CHORD (19.10.)

Im CHORD-Modus (Pad-Modus 6) zeigen die Pads nach einem Akkord, welche Akkorde gut folgen, nach dem Abstand der Grundtöne, mit denselben
sechs Stufen: Quinte (V) 253, Quarte (IV) 181, Sekunde und große Sexte (ii, vi) 121, kleine Terz 81, derselbe Akkord und große Terz 51,
kleine Sexte und kleine Septime 33. Gestoppt bleiben sie, beim Spielen blenden sie aus wie bei KEYBOARD.

- **Gemessen:** im CHORD-Modus läuft ein Druck über den Pad-Handler `0xC0044874`, das Licht des Pads kommt aus der UI
  (`0xC0070680`, Rot 192), nicht über die Notenfunktion; die Akkorde stehen nirgends im RAM, die Firmware rechnet sie beim Drücken.
  Der Patch erkennt den gespielten Akkord am Rot 192 des gehaltenen Pads, ohne neuen Haken.
- **Gemessen (Grundton = tiefste Note am MIDI-Ausgang):** untere Reihe = Plätze 0 bis 7 der Tastatur-Tabelle, obere Reihe eine
  Tonleiterstufe weiter als die der Tastatur (Pad 1 = Platz 9, Pad 8 = letzte Note plus der erste Schritt der Oktave). Das stimmt für
  Dorisch und Äolisch auf C und A genau. Für Dur-Pentatonik, Moll-Pentatonik und Chromatisch rechnet CHORD mit eigenen Tonleitern
  (z. B. Dur-Pentatonik: Grundtöne der Dur-Tonleiter). Deshalb nur bei Skalen mit sieben Tönen, erkannt daran, dass die Tabelle der
  Tastatur die Oktave doppelt hat (Plätze 7 und 8 gleich). Sonst zeigt CHORD keine Hinweise.

## Emulator (`tools/emu/note_assist_cases.py`, 33 Fälle, Hacktribe, Korg rot und blauer Synth mit BLECH, Flash vom 09.10.)

Alle 33 Fälle laufen auf Hacktribe, Korg rot und Synth. Gestoppt und pausiert bleiben die Stufen stehen, beim Spielen blenden sie aus,
die schwachen zuerst, dann kommt das Blau des Parts zurück. Der Fall `next_note_takes_the_red` liest die Pads alle 20 ms und prüft nur
die Reihenfolge (erst Pad 2 rot, dann das Pad der zweiten Note), weil das Tempo des Patterns im Flash bestimmt, wann die Schritte
spielen. Weitere Fälle: eine zweite Note übernimmt das Rot, das erste Pad bekommt wieder seinen Hinweis, gestoppt hält kein Pad mehr
das Rot.

Fälle: `chord_hints_dorian`, `chord_hints_aeolian`, `chord_pentatonic_none`, `levels_by_fit`, `stopped_hints_stay`, `paused_hints_stay`, `playing_hints_fade_dim_first`, `new_note_hints_stay`.
Die Fälle beenden die Hinweise mit einem anderen Pad-Modus.

## Offen

- Am Gerät nicht geprüft: ob 253 neben dem 192 der gespielten Note gut zu unterscheiden ist (rosa gegen rot), ob die sechs Stufen
  einzeln zu sehen sind, ob Rot 65 sich von 192 und von aus abhebt.
- Ob das Rot bei schnellen Noten und mehreren Pads derselben Note ruhig bleibt.

Quelle: Messung 2026-10-22/notenassistent-stufen, Messung 2026-10-22/notenassistent-spielende-note
