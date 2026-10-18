# Energiesparmodus: LEDs gedimmt (18.10.)

Wunsch vom 18.10.: der Energiesparmodus soll mehr sparen als das gedimmte Licht. Grundlage: die Pad-LEDs kennen
Helligkeitsstufen (Pulsieren pulsiert am Gerät flüssig, [Korrektur](2026-10-16-pad-led-stufen.md)).

**Neu (`tools/patch/pad_colors.py`, nur auf der roten Electribe, Hacktribe und Korgs 2.02).**

- Solange die Firmware für Power Save dimmt (Flag `0xC00F9310`), geht jede LED-Nachricht des LED-Managers mit einem
  Viertel der Helligkeit raus (`(Wert + 3) / 4`, 255 wird 64, eine leuchtende LED bleibt an). Das sind Pads, Tasten
  und die Encoder-LEDs; die untere RGB-Leiste schaltet Power Save ohnehin ab.
- Ein Haken am Anfang des Schalters `0xC0028AB4` (Kette `backlight`, Stufe `power-save-switch`) lässt die Funktion der
  Firmware laufen und schickt danach alle 88 LEDs neu, wenn sich das Dimmen geändert hat. So werden sie sofort dunkel
  und wieder hell.
- Die Aufrufer des Schalters sind Funktionen der Oberfläche (`0xC00511A4`, `0xC00740B0`, `0xC007410C`, `0xC0075B3C`,
  `0xC007611C`, `0xC0076184`), kein Interrupt: hergeleitet aus dem Code.
- EXIT beim Einschalten: nichts davon. Die Werte im LED-Manager bleiben die der Firmware, nur was ans Bedienfeld geht,
  ändert sich.

**Gemessen (Emulator, `menu:padcolor_power_save_*`, BLECH auf Pascals Hacktribe-Datei mit dem Flash-Abbild vom
09.10.).** Schalter mit 1 gerufen: alle 14 leuchtenden LEDs von 255 auf 64, mit 0 wieder 255. Mit eigenen Farben (Pad
rot) Pad 1 auf (64, 0). Mit EXIT beim Einschalten bleibt das Blau von Pad 1 bei 255.

**Offen, am Gerät:** wie viel Strom das spart (Stromtest, Stufen 4 bis 6), ob ein Viertel gut sichtbar bleibt. Die
blaue Electribe hat den Patch nicht.
