# Notenassistent: Helligkeit nach Passung, stehen lassen und ausblenden (19.10.)

Wunsch vom 16.10. und 19.10.: die am besten passenden Noten heller als die weniger passenden. Der feste 1,5-s-Timer weg: gestoppt
oder pausiert bleiben die Hinweise stehen, beim Spielen blenden sie langsam aus, eine Note bei 0 verschwindet. So bleiben die
passenderen Noten länger zu sehen.

## Was neu ist (`tools/patch/note_assist.py`)

- **Stufe je Pad** nach dem Abstand zur gespielten Note (in Halbtönen, modulo 12):

  | Abstand | Stufe (rote LED von 255) |
  |---|---|
  | Prim/Oktave (0), Quinte (7) | 63, hell |
  | kleine und große Terz (3, 4), Quarte (5) | 41, mittel |
  | kleine und große Sexte (8, 9) | 21, schwach (die bisherige Helligkeit) |
  | der Tonleiterschritt hoch und runter (Nachbar in der Tabelle der Tastatur) | mindestens 41 |
  | sonst | dunkel |

  Die blaue LED bekommt 5/8 davon, ungerade. Die Werte des Patches sind ungerade und unter 128, die Firmware schreibt nur 0, 192,
  255 oder doppelte Velocity (gerade). Daran erkennt der Patch weiter seine eigenen LEDs.
- **Transport** (`0xC06BC318`, gemessen): 0 Stop, 1 Play, 2 Pause, 3 Rec bereit, 4 Rec mit Play. Bei 0, 2 und 3 bleiben die
  Stufen stehen. Bei 1 und 4 verliert jede Stufe alle 3 Ticks (120 ms) 2, bis 0: hell nach etwa 3,7 s weg, mittel nach 2,5 s,
  schwach nach 1,3 s.
- Eine neue Note ersetzt die Stufen sofort. Ein anderer Pad-Modus, ein anderer Bildschirm, eine andere Oktave, Tonart oder Skala
  beendet sie wie bisher. Ist das letzte Pad dunkel, bekommt das Pad des gewählten Parts das Blau der Firmware zurück.

## Emulator (`tools/emu/note_assist_cases.py`, 29 von 29, Hacktribe mit BLECH, Flash vom 09.10.)

Pad 3 (F, Dorisch auf C) gespielt: Prim und Quinten 63, Terzen, Quarte und die Nachbarn E und G 41, Sexten 21. Gestoppt nach 4 s
unverändert. Beim Spielen: nach 0,5 s 55/33/13, die schwachen bei 1,3 s weg, die mittleren bei 2,5 s, die hellen bei 3,8 s, dann
das Blau des Parts zurück. In der Pause (1 s) bleiben die Werte stehen.

Neu bei den Fällen: `levels_by_fit`, `stopped_hints_stay`, `paused_hints_stay`, `playing_hints_fade_dim_first`, `new_note_hints_stay`.
Die Fälle, die bisher auf das Ende nach 1,5 s gewartet haben, beenden die Hinweise jetzt mit einem anderen Pad-Modus.

## Offen

- Am Gerät nicht geprüft, auch nicht, ob die drei Stufen am Bedienfeld gut zu unterscheiden sind (ein Helligkeitstest im RAM ist
  der nächste Schritt).
