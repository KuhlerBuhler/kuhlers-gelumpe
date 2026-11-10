# Vorschau: schnelles Blättern durch die Patterns hält mit der Firmware mit

Stand 09.11.2026, nur Emulator (Hacktribe 2.02 von der Karte, Korgs Original 2.02 rot und blau, je mit dem BLECH-Satz von
`release/1.4.5`), kein Gerät. Meldung vom Gerät (1.4.5, Hacktribe): schnelles Drehen am Rad durch die Patterns hängt nach, beim
Abspielen und gestoppt mit einer ungespeicherten Änderung. Mit EXIT beim Einschalten hängt nichts. AUTO SAVE war an. Marker:
**gemessen** (im Emulator), **hergeleitet**, **Urteil**.

## Belegtabelle

| Behauptung | Beleg | Marker |
|---|---|---|
| Die Firmware ohne BLECH hängt nicht nach: nach 20 Klicks im Abstand von 30 ms ist die letzte Nummer 5 ms nach dem letzten Klick gewählt, kein Klick im Rückstand | Messung unten, Zeile "Firmware" | gemessen |
| BLECH mit EXIT beim Einschalten ist gleich der Firmware (dieselben Bytes zum Panel, dieselben Zeiten) | Zeile "EXIT gehalten" | gemessen |
| BLECH 1.4.5 hängt bis zu 4 Klicks hinterher, die letzte Nummer kommt erst 130 ms nach dem letzten Klick | Zeile "BLECH 1.4.5" | gemessen |
| Die Ursache ist die Vorschau: jeder Klick zeichnet alle Pads der Ansicht neu, rund 87 LED-Nachrichten, rund 435 Bytes | Zählung der Aufrufe von `LED_SEND` je Klick, Bytes zum Panel | gemessen |
| Die Leitung zum Panel schafft rund 11,5 kB/s, 435 Bytes sind rund 38 ms; bei 30 ms je Klick läuft die Warteschlange voll | 115200 Baud, 10 Bit je Byte | hergeleitet |
| Die Warteschlange der Firmware fasst 1024 Bytes, sie war voll (höchster Stand 1024), und der Sender wartet dann im UI-Task auf Platz | Stand des Rings `0xC033E648 + 0x14` während der Messung; Schreiber `0xC0024BF4` gelesen | gemessen |
| AUTO SAVE kostet je Klick nichts: `SWITCH_SCREEN` (`0xC0083D28`, dort hängt AUTO SAVE) wird beim Blättern kein einziges Mal gerufen | Zähler in der Messung, beide Szenen | gemessen |
| Mit dem Fix ist die letzte Nummer wie bei der Firmware nach 5 ms gewählt, kein Klick im Rückstand, die Warteschlange ist am Ende leer | Zeile "Fix" | gemessen |
| Was die Firmware beim Wechsel tut, bleibt gleich; der Fix ändert nur, wann die Pads der Vorschau neu gezeichnet werden | Diff in `tools/patch/pattern_switch.py`, Fälle der Gruppe pattern switch | Urteil |
| Am Gerät | nicht geprüft | offen |

## Messung

20 Klicks am Rad, je einer alle 30 ms (eine schnelle Hand), Hacktribe. "Abspielen": das Pattern läuft, das Rad blättert in der
Vorschau. "Gestoppt, ungespeichert": gestoppt, ein Regler geändert, dann blättern. Die Zeiten zählen ab dem letzten Klick. Der
Emulator rechnet die Zeit in Befehlen und gibt jedes Byte zum Panel mit 86,8 µs aus.

| Firmware | Szene | Bytes zum Panel | letzte Nummer gewählt | Klicks im Rückstand | Ring beim letzten Klick (höchster) | `SWITCH_SCREEN` |
|---|---|---|---|---|---|---|
| Firmware (ohne BLECH) | Abspielen | 7320 | 5 ms | 0 | 0 (70) | 0 |
| Firmware (ohne BLECH) | gestoppt, ungespeichert | 7548 | 5 ms | 0 | 0 (226) | 0 |
| EXIT gehalten | Abspielen | 7320 | 5 ms | 0 | 0 (67) | 0 |
| EXIT gehalten | gestoppt, ungespeichert | 7540 | 5 ms | 0 | 5 (269) | 0 |
| BLECH 1.4.5 | Abspielen | 16000 | 130 ms | 4 | 974 (1024) | 0 |
| BLECH 1.4.5 | gestoppt, ungespeichert | 16536 | 130 ms | 4 | 969 (1024) | 0 |
| Fix | Abspielen | 8170 | 5 ms | 0 | 0 (487) | 0 |
| Fix | gestoppt, ungespeichert | 8706 | 5 ms | 0 | 36 (469) | 0 |

Bei der Firmware lädt gestoppt jeder Klick das Pattern, BLECH blättert in der Vorschau (`VIEW:`). Das Bild der Vorschau steht mit
dem Fix 5 ms (Abspielen) und 35 ms (gestoppt) nach dem letzten Klick, bei 1.4.5 nach 165 ms und 155 ms. Je länger und schneller
gedreht wird, desto weiter läuft 1.4.5 hinterher, weil jeder Klick mehr schickt, als die Leitung in 30 ms schafft (hergeleitet).

## Ursache

Die Vorschau (`pc_led`, `pc_view_cells`, `pc_view_refresh`) zeichnet bei jedem Klick die Pads des angesehenen Patterns neu:
`PADS_REFRESH` `0xC00892D4`, das Blinken, dann alle 32 Pad-LEDs noch einmal erzwungen. Jede LED ist eine Nachricht von 5 Bytes
über UART0 zum Panel. Der Weg `0xC00875F4`, `0xC0087578`, `0xC0028600` schreibt in den Ring bei `0xC033E648` (1024 Bytes); ist er
voll, dreht der Schreiber `0xC0024BF4` in einer Schleife, bis Platz ist. Das passiert im UI-Task, also kommen die nächsten Klicks
erst danach dran.

## Der Fix

`pc_view_refresh` geht jetzt über `view_defer` (im Blink-Bereich, `@BLINK_CODE@ + 20`):

- Der erste Wechsel zeichnet sofort, wie bisher.
- Kommt der nächste innerhalb von 2 Takten des LED-Managers (2 mal 40 ms), merkt `view_defer` ihn nur vor (`V_DEFER`, 4 Bytes neu in
  `VIEW_W`, `VIEW_SIZE` 0x78).
- `view_tick` (läuft im Takt des LED-Managers, eigener Task) zeichnet ihn, sobald die Ansicht 2 Takte stillstand. Beim Drehen gibt
  es also ein Neuzeichnen statt eines je Klick, und das letzte kommt höchstens rund 80 ms nach dem letzten Klick.
- Die Nummer, das Display, MIDI Program Change und alles, was die Firmware beim Wechsel tut, laufen unverändert sofort.

Platz: Blink-Bereich 0x334 von 0x400 belegt (vorher 0x2A8), der Hauptbereich ist unverändert.

## Fälle

`tools/emu/pswitch_cases.py`, Gruppe 20 (`case_fast_steps`), `pswitch:fast_steps_playing_keep_up` und
`pswitch:fast_steps_stopped_unsaved_keep_up`. Vergleich mit derselben Firmware und EXIT beim Einschalten, 20 Klicks alle 30 ms.
Grenze:

- Klicks im Rückstand höchstens wie die Firmware (mindestens 1 erlaubt).
- Die letzte Nummer höchstens 30 ms nach dem letzten Klick gewählt.
- Bytes zum Panel bis 0,3 s nach dem letzten Klick höchstens 4 Neuzeichnungen der Ansicht (je 450 Bytes) mehr als die Firmware;
  1.4.5 schickte eine je Klick.
- 0,3 s danach wartet kein Neuzeichnen mehr, keine Asserts.
- Gestoppt: die Vorschau steht auf Pattern 21 und die Pads zeigen dessen Steps (1, 3, 5, 7).

| Build | Szene | Klicks im Rückstand | letzte Nummer | Bytes bis 0,3 s danach (Firmware) | Ergebnis | Marker |
|---|---|---|---|---|---|---|
| Fix Hacktribe | Abspielen | 0 | sofort | 2470 (1605) | grün | gemessen |
| Fix Hacktribe | gestoppt, ungespeichert | 0 | sofort | 2680 (1911) | grün | gemessen |
| BLECH 1.4.5 Hacktribe | Abspielen | 4 | 130 ms | 10272 (1605) | rot | gemessen |
| BLECH 1.4.5 Hacktribe | gestoppt, ungespeichert | 6 | 265 ms | 10276 (1911) | rot, die Pads noch dunkel | gemessen |
| Fix rot | Abspielen | 0 | sofort | 2410 (1595) | grün | gemessen |
| Fix rot | gestoppt, ungespeichert | 0 | sofort | 2704 (1875) | grün | gemessen |
| Fix blau | Abspielen | 0 | sofort | 2270 (1546) | grün | gemessen |
| Fix blau | gestoppt, ungespeichert | 0 | sofort | 2610 (1870) | grün | gemessen |

Die übrigen Gruppen der Vorschau (0 bis 3, 10, 14 bis 19) sind auf allen drei Builds grün, ebenso AUTO SAVE und die Farben der Pads aus `tools/emu/menu_cases.py` (`auto_save_cases`, `pad_colour_cases`, 104 Fälle) (gemessen).

## Offen

- Am Gerät nicht geprüft. Der Emulator hat dieselbe Baudrate, wie schnell das Panel am Gerät die Nachrichten abnimmt, ist nicht
  gemessen.
- Das letzte Neuzeichnen läuft jetzt im Task des LED-Managers. Im Emulator sind die Pads danach richtig; ob ein anderer Task zur
  selben Zeit Pads zeichnet und es sichtbar flackert, ist am Gerät zu sehen.
