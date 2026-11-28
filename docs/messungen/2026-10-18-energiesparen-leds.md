# Energiesparmodus: LEDs gedimmt

Im Energiesparmodus (Power Save) dimmt die Firmware nur das Licht. [BLECH](../glossary.md#blech) dimmt zusätzlich alle LEDs. Grundlage:
die Pad-LEDs kennen Helligkeitsstufen ([Pad-LED-Stufen](2026-10-16-pad-led-stufen.md)). Der [Patch](../glossary.md#patch) ist
`tools/patch/pad_colors.py`, auf der roten Electribe ([Hacktribe](../glossary.md#hacktribe) und Korgs 2.02) und auf der blauen
(`--build synth`, `data/patches/pad-colors-synth.json`).

## Verhalten

- Solange die Firmware für Power Save dimmt (Flag `0xC00F9310`), geht jede LED-Nachricht des LED-Managers mit verminderter
  Helligkeit raus. Das sind Pads, Tasten und die Encoder-LEDs; die untere RGB-Leiste (Pegelanzeige, LEDs `0x4C` bis `0x57`)
  schaltet Power Save ohnehin ab.
- Ein Haken am Anfang des Schalters `0xC0028AB4` (Kette `backlight`, Stufe `power-save-switch`) lässt die Funktion der Firmware
  laufen und schickt danach alle LEDs neu, wenn sich das Dimmen geändert hat. So werden sie sofort dunkel und wieder hell.
  Die Aufrufer des Schalters sind Funktionen der Oberfläche, kein Interrupt (hergeleitet aus dem Code).
- EXIT beim Einschalten schaltet den Patch ab. Die Werte im LED-Manager bleiben die der Firmware, nur was ans Bedienfeld
  geht, ändert sich.
- Blau: Sendefunktion `0xC00776B0` mit dem Sprung zum Sender `0xC0077634` an ihrem Ende `0xC0077764`, Power-Save-Schalter
  `0xC0025F28`, Flag `0xC00DF0CC` (`data/synth-map/pad-colors.json`). Ob die blaue Firmware auf Batterie dimmt, hängt an POWER
  SAVE im Flash; im leeren blauen Flash dimmt sie nicht. Der Fall prüft darum, dass die LEDs genau dann gedimmt sind, wenn die
  Firmware dimmt.
- Beim Start wird nichts gesendet: der Patch merkt sich "neu senden fällig" (`S_PEND`) und schickt alle LEDs außer der
  Pegelanzeige beim nächsten Durchlauf durch den Sendeweg der Firmware, aber erst, wenn der Hauptbildschirm da ist.
  **Gemessen:** ein Senden aus dem Start oder aus dem Sendeweg während des Starts hängt die blaue Electribe mit Karte.

## Einstellbar

Die Seite BLECH, CUSTOMIZATION, POWER SAVE, LED DIMMING geht von 0 % (gar nicht) bis 100 % (aus) in Zehnerschritten, dazu 75 %
(die Vorgabe). Gerechnet wird `(Wert * behalten + 99) / 100`, aufgerundet, damit eine leuchtende LED an bleibt; bei 75 %
genau `(Wert + 3) / 4`. Gespeichert wird die Stufe in den vier freien Bits der Einstellungsdatei (Flags-Bits 6, 7 und 31,
Bit 31 des Look-Worts); im Patch steht sie in den Bits 12 bis 15 seines Einstellungsworts.

KNOB LEDS gilt auch im Power Save: ON gedimmt wie jede andere LED, OFF dunkel. Eine neue Stufe auf LED DIMMING (ebenso OVERLAP)
schickt alle LEDs sofort über den Sendeweg der Firmware (Eintrag `+48` `pc_send_all`), nicht erst nach dem Menü.

Daneben liegt DISPLAY LIGHT (unter DISPLAY): 1 bis 15 leuchten mit 3 bis 15 von 15, weil 1 von 16 am Gerät auf Batterie dunkel
war. Im [Emulator](../glossary.md#emulator) haben INTENSITY 1 und SAVE LIGHT 1 dasselbe Tastverhältnis von 1/16; der Unterschied am
Gerät ist nicht gemessen.

## Gemessen (Emulator, `menu:padcolor_power_save_*`, `menu:look_backlight_save_light`)

- Schalter mit 1 gerufen: alle 14 leuchtenden LEDs von 255 auf 64, mit 0 wieder 255. Mit eigenen Farben (Pad rot) Pad 1 auf
  (64, 0). Mit EXIT beim Einschalten bleibt das Blau von Pad 1 bei 255.
- Vorgabe 75 %; bei 0 % bleiben alle LEDs wie sie waren; bei 100 % sind alle aus; bei 70 % zeigt jede LED
  `(Wert * 30 + 99) / 100`; nach WRITE und Neustart steht die Seite wieder auf 70 %. DISPLAY LIGHT 4 mit Blau 12: 4 von 16.
- Die Firmware schickt beim Dimmen keinen eigenen Befehl ans Bedienfeld (Schalter mit 1: nur die zwölf Pegel-LEDs `0x4C` bis
  `0x57` mit 120, sonst nichts). Dass Bit 3 der Stufe beim Speichern verloren geht, ist ausgeschlossen.
- Rot und Blau je 12 von 12 in `menu:padcolor_*`.

## Offen, am Gerät

- Am Gerät zeigen sich nur aus, ganz hell oder sehr dunkel, die Prozentzahl dazwischen ändert nichts. Der Patch rechnet jede
  Stufe richtig. Warum das Bedienfeld die Zwischenwerte nicht zeigt, ist **offen**: die Messung vom 16.10. (ein Wert je LED, alles
  ab 1 gleich hell) und die Beobachtung, dass Pulsieren flüssig pulsiert, widersprechen sich.
- Wie viel Strom das spart und ob ein Viertel gut sichtbar bleibt, ist nicht gemessen.
