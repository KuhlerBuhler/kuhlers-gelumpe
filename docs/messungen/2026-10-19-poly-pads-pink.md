# Poly-Steps mit mehreren Noten in Pink (19.10.)

Wunsch vom 18.10.: hat ein Part Voice Assign Poly und spielt ein Step mehr als eine Note, soll sein Pad pink statt rot
leuchten, damit man sieht, wo 2+ Noten laufen und wo eine.

## Was die Firmware zeigt (Hacktribe 2.02, Emulator)

- **SEQUENCER-Modus**: die Pads sind die 16 Steps des gewählten Parts im gezeigten Taktabschnitt. Rot (LED `0x2C + 2n`) heißt
  Step an, Blau (`0x2D + 2n`) ist die Abspielposition. Beim Abspielen schickt die Firmware bei jedem Step alle roten Pads neu.
- TRIGGER-Modus: beim Abspielen leuchtet kein Pad rot (gemessen, 1,5 s Wiedergabe). Der Wunsch passt also zum SEQUENCER-Modus.
- Pad-Modus `[0xC0345A1C] + 0xB58` (4 SEQUENCER), gewählter Part `+0xB60`, gezeigter Taktabschnitt `[0xC0348884] + 0x344`
  (Tasten 1 bis 4 setzen 0 bis 3; folgt beim Abspielen nicht der Position). Voice Assign ist Byte 2 des Parts
  (0 Mono 1, 1 Mono 2, 2 Poly 1, 3 Poly 2), die vier Noten eines Steps die Bytes 4 bis 7 (0 leer).

## Der Patch (`tools/patch/pad_colors.py`)

Am Sender der LED-Nachrichten, wo die Pad-Farben schon umgerechnet werden: im SEQUENCER-Modus, bei einem Poly-Part und einem
Step mit 2 oder mehr Noten nimmt das Pad Pink als Part-Farbe. Ist Part- oder Select-Farbe selbst Pink, die übrige Farbe. Fällt
der Cursor auf so einen Step, gilt die Überlappung wie sonst (mit Rot und Blau: Rot). Mit den Farben der Firmware gehen die
Pads jetzt auch durch die Umrechnung, alle anderen Pads bekommen dabei genau die Werte der Firmware. Nicht mit EXIT beim
Einschalten, nicht auf der blauen (dort nicht gemessen).

## Emulator (`tools/emu/menu_cases.py`, `pad_colour_cases`, Hacktribe mit BLECH, am Netzteil)

| Fall | Ergebnis |
|---|---|
| Poly 1, Akkorde auf Step 5, 9, 13, eine Note auf 3, 7, 11, 15 | Pad 5, 9, 13 pink, 3, 7, 11, 15 rot |
| dasselbe mit Mono 1 | alle sieben rot |
| Poly 1 mit EXIT beim Einschalten | alle sieben rot |
| die übrigen Pad-Farben-Fälle (Seiten, Überlappung, Datei, Power Save) | unverändert bestanden |

## Offen

- Am Gerät nicht geprüft.
- Im Stand schickt die Firmware ein Pad nur bei einer Änderung neu. Kommt die zweite Note eines Steps über STEP EDIT dazu,
  ohne dass das Pad neu geschickt wird, wird es erst beim nächsten Neuschicken pink.
