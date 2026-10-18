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

## Die blaue Electribe (18.10., Abend)

Der Patch hat jetzt auch einen Build für Blau (`--build synth`, `data/patches/pad-colors-synth.json`, im blauen Satz). Die
Stellen sind Befehl für Befehl die roten (`data/synth-map/pad-colors.json`): Sendefunktion `0xC00776B0` mit dem Sprung zum
Sender `0xC0077634` an ihrem Ende `0xC0077764`, Power-Save-Schalter `0xC0025F28`, Flag `0xC00DF0CC`.

**Gemessen:** Die erste Fassung ließ Blau mit Karte am Start hängen (Bildschirm 0, keine Ticks des Bildschirm-Managers,
nur noch Interrupts; ohne Karte und ohne den Patch lief es). Ursache: alle LEDs wurden beim Start neu gesendet, einmal beim
Einlesen der Einstellungen und einmal beim ersten Aufruf des Power-Save-Schalters; auf Blau kam ein Senden aus dem Start nie
zurück. Jetzt wird beim Start nichts gesendet; der Patch merkt sich "neu senden fällig" (`S_PEND`) und schickt alle LEDs
außer der Pegelanzeige beim nächsten Durchlauf durch den eigenen Sendeweg der Firmware neu, aber erst, wenn der
Hauptbildschirm da ist (auch aus dem Sendeweg hing es während des Starts). Rot und Blau je 12 von 12 in
`menu:padcolor_*`. Ob die blaue Firmware auf Batterie dimmt, hängt an POWER SAVE im Flash: im leeren blauen Flash dimmt sie
nicht, der Fall prüft darum, dass die LEDs genau dann gedimmt sind, wenn die Firmware dimmt.

**Offen, am Gerät:** wie viel Strom das spart (Stromtest, Stufen 4 bis 6), ob ein Viertel gut sichtbar bleibt, Blau ganz.
