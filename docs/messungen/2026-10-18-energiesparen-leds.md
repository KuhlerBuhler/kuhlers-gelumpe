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

**Gemessen (Emulator, `menu:padcolor_power_save_*`, BLECH auf einer eigenen Hacktribe-Datei mit dem Flash-Abbild vom
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

## Einstellbar (19.10.)

Wunsch vom 19.10.: wie stark gedimmt wird, sucht man selbst aus. Die Seite BLECH, CUSTOMIZATION, POWER SAVE, LED DIMMING
geht von 0 % (gar nicht) bis 100 % (aus) in Zehnerschritten, dazu 75 %, die Vorgabe und das Viertel von oben. Gerechnet wird
`(Wert * behalten + 99) / 100`, aufgerundet, damit eine leuchtende LED an bleibt (bei 75 % genau `(Wert + 3) / 4`). Die
Regler-LEDs gehen weiter aus, außer bei 0 %; dann zeigen sie, was die Firmware im Power Save schickt (im Emulator für den
VALUE-Regler 75 statt 155). Gespeichert wird die Stufe in den vier freien Bits der Einstellungsdatei (Flags-Bits 6, 7 und 31,
Bit 31 des Look-Worts), im Patch steht sie in den Bits 12 bis 15 seines Einstellungsworts. Daneben liegt DISPLAY LIGHT, das
frühere SAVE LIGHT unter DISPLAY: 1 bis 15 leuchten jetzt mit 3 bis 15 von 15, weil 1 von 16 am Gerät auf Batterie dunkel war
(Rückmeldung 19.10.; im Emulator haben INTENSITY 1 und SAVE LIGHT 1 dasselbe Tastverhältnis von 1/16, der Unterschied am Gerät
ist nicht gemessen, vermutlich die niedrigere Spannung auf Batterie).

**Gemessen (Emulator, `menu:padcolor_power_save_led_dimming`, `_kept`, `menu:look_backlight_save_light`):** Vorgabe 75 %;
bei 0 % bleiben alle LEDs außer den Reglern, wie sie waren; bei 100 % sind alle aus; bei 70 % zeigt jede LED
`(Wert * 30 + 99) / 100`; nach WRITE und Neustart steht die Seite wieder auf 70 %. DISPLAY LIGHT 4 mit Blau 12: 4 von 16.

## Gerätetest 15.11.: Regler-LEDs, sofort im Menü, Stufen

Gerätetest 15.11. (rot, release/1.4.6 f56f4b7e), drei Befunde:

1. **Regler-LEDs:** im Power Save blieben sie dunkel, egal was KNOB LEDS sagte, und ON brachte sie nicht zurück. Ursache
   (offline gelesen): die Regel vom 18.10. setzte jede Nachricht an die LEDs `0x00` bis `0x04` im Power Save auf 0, also auch
   die, die ON neu schickt. Jetzt gilt KNOB LEDS auch im Power Save: ON gedimmt wie jede andere LED, OFF dunkel. Die alte Regel
   "Regler-LEDs aus im Power Save" entfällt, OFF deckt sie ab.
2. **Erst nach dem Menü:** eine neue Stufe auf LED DIMMING zeigte sich erst nach dem Verlassen des Menüs. Ursache (offline
   gelesen): die Seite merkte nur "neu senden fällig" (`S_PEND`), und das Neusenden wartet auf den Hauptbildschirm (siehe Blau
   oben). Jetzt schickt die Seite alle LEDs sofort über den Sendeweg der Firmware (neuer Eintrag +48 `pc_send_all`), ebenso
   OVERLAP. PAD COLOR, SELECT COLOR und KNOB LEDS schickten schon sofort.
3. **Keine Zwischenstufen:** am Gerät nur aus, ganz hell oder sehr dunkel, die Prozentzahl änderte dazwischen nichts. Im
   Emulator rechnet der Patch jede Stufe richtig (`(Wert * behalten + 99) / 100`), und die Firmware schickt beim Dimmen keinen
   eigenen Befehl ans Bedienfeld (**gemessen**: Schalter mit 1 auf dem Stand mit EXIT beim Einschalten, nur die zwölf
   Pegel-LEDs `0x4C` bis `0x57` mit 120, sonst nichts). Warum das Bedienfeld die Zwischenwerte nicht zeigt, ist **offen**:
   die Messung vom 16.10. (ein Wert je LED, alles ab 1 gleich hell) und die Beobachtung vom 18.10. (Pulsieren pulsiert flüssig)
   widersprechen sich. Ausgeschlossen (**gemessen** im Emulator): dass Bit 3 der Stufe beim Speichern verloren geht (das
   hätte 40 bis 70 % zu 75 bis 100 % gemacht); 70 % steht nach WRITE und Neustart wieder auf 70 %. Nächster Schritt am Gerät, nur mit Zustimmung: eine Pad-LED und eine Tasten-LED nacheinander auf
   255, 192, 128, 64, 32, 16, 8 setzen und ansehen, einmal mit und einmal ohne Power Save.

