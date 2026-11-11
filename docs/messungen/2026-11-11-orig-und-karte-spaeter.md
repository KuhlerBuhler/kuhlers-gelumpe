# ORIG im BLECH-Menü und die später eingesteckte Karte (11.11.)

Stand 11.11.2026, nur Emulator (Hacktribe 2.02, Korgs Original 2.02 rot und blau, je mit dem BLECH-Satz von `release/1.4.5`),
am Gerät nichts geprüft. Zwei Rückmeldungen vom Gerät. Marker: **gemessen** (im Emulator), **offline gelesen** (Disassembly),
**hergeleitet**, **offen**.

## Belegtabelle

| Behauptung | Beleg | Marker |
|---|---|---|
| Das Schildchen ORIG zeichnet das Textfeld der Seite (Konstruktor `0xC00856C0`, Zeichenfunktion `0xC00854B8`), wenn das Byte `+0x49` des Felds gesetzt ist: Symbol 16 bei x 36, y 55, davor wird dort ein Kasten 15 x 8 gelöscht | Disassembly von Korgs Original 2.02 rot, dazu ein Haken auf `0xC003F650`, der im Emulator Symbol 16 nur mit dem Aufruf aus `0xC00855D8` zeigt | offline gelesen, gemessen |
| Auf den Seiten von GLOBAL PARAMETERS erscheint das Schildchen beim gespeicherten Wert und verschwindet nach einem Schritt am Rad | Sonde im Emulator, Bildschirm 9, Seite 1 | gemessen |
| Die Seiten von BLECH setzen dieses Byte nie, darum zeigte keine das Schildchen | Ein Menü baut sein Textfeld mit demselben Konstruktor, `menu_show` schrieb das Byte nicht | offline gelesen |
| Jetzt setzt `menu_show` das Byte je Seite; das Schildchen steht an derselben Stelle und hat dieselben 65 Pixel wie das von GLOBAL PARAMETERS | `tools/emu/menu_cases.py:orig_cases`, Fall `look_of_the_firmware` | gemessen |
| Die Karte, die erst nach dem Einschalten steckt, schaltet PATTERN CONFIRM, TAP MOTION, NOTE ASSIST und das Würfeln auf dem Sampler nicht ein, bis das Dateisystem gemountet ist | Sonde: Typ-Byte des Volumes `0xC06A010C` bleibt 0, TAP ändert den Modus nicht | gemessen |
| Mit der Änderung wirken diese Funktionen mit der Karte sofort, ein im Menü geänderter Wert wirkt vor jedem Speichern | `tools/emu/tap_motion_cases.py:case_card_inserted_late` | gemessen |
| Auf der blauen Electribe war der Fehler nicht da (sie liest den Kartenkontakt schon) | `tools/patch/card_gate.py` | offline gelesen |

## ORIG

Die Firmware zeigt ORIG, wenn der Wert der Seite dem entspricht, der beim Start im Block stand
([Global-Felder](2026-10-14-global-felder.md)). Für BLECH heißt der gespeicherte Wert: der in der Einstellungsdatei, ohne
Datei der Standard. Dafür gibt es eine Kopie des Satzes, den `menu_settings_write` baut (24 Byte, in `MENU_FILE_B`, das nach
dem Lesen der Datei frei ist). Sie entsteht am Ende des Ladens (auch ohne Datei oder Karte) und nach jedem Speichern, WRITE
und AUTO SAVE. Auf jeder Seite vergleicht `menu_orig_flag` die Bits, die zur Seite gehören (die Tabelle `orig_masks` nach Art der
Seite), im Satz von jetzt gegen die Kopie. Ohne gespeicherten Wert ist es also der Standard, bei den Farbseiten (Farbton,
Sättigung, Helligkeit) der Satz der drei Pegel.

Gezeigt wird es auf PLUGIN RUNTIME, den Seiten von FEATURES, DISPLAY, LED, PAD COLOR und POWER SAVE. Keins haben die Aktionen und
Listen (EXPORT, SPLASH, VERSION, PLUGINS) und SYNC GROUP (das Pattern speichert es). Die Seiten der Plugins sind hier nicht
angefasst.

**Gemessen (`orig_cases`, 8 Fälle je Build).**

| Fall | Ergebnis |
|---|---|
| alle Seiten (28 auf Hacktribe und rot, 27 auf blau) beim gespeicherten Wert | Schildchen da |
| Rad gedreht | auf allen weg |
| Rad zurück | wieder da, wo der Wert wieder der alte ist |
| Aussehen und Ort gegen GLOBAL PARAMETERS | gleiche 65 Pixel |
| TAP MOTION ändern, WRITE | neuer Wert hat das Schildchen, der alte nicht mehr |
| Datei mit PATTERN CONFIRM aus | die Seite zeigt OFF mit Schildchen, ON ohne |
| ohne Karte | Standard hat das Schildchen |
| Gruppenliste, PLUGINS, VERSION, SYNC GROUP, Ring | keins |

Bei den sechs Seiten Farbton, Sättigung und Helligkeit ist ein Schritt zurück am Rad nicht immer der Wert davor (die Seiten rechnen
aus drei Pegeln von 0 bis 15). Dann steht das Schildchen auch nicht, weil der Satz wirklich ein anderer ist.

## Die Karte, die später steckt

**Ursache (Code gelesen, dann gemessen).** Patternwechsel, TAP Motion, Notenassistent und Würfeln fragen mit
`tools/patch/card_gate.py` ab, ob eine Karte da ist ([Karte gezogen](2026-10-18-karte-gezogen-tap-blinkt.md)). Auf den beiden
Sampler-Builds war das Kriterium das Typ-Byte des FatFs-Volumes. FatFs mountet das Volume erst beim ersten Zugriff, und ohne
Karte beim Start gab es keinen. Steckt die Karte danach, bleibt das Byte 0 (gemessen: nach 1,5 s mit Karte noch 0), die Funktionen
bleiben aus und TAP macht, was die Firmware macht. Der erste Zugriff war dann das Speichern (WRITE oder AUTO SAVE beim Verlassen
des Menüs): es mountet, die Funktionen gehen an. Das sah aus wie "wirkt erst nach dem Speichern". Dass die Einstellung als Wort im
RAM sofort geschrieben wird, war in beiden Fällen gleich (`menu_value_*`); der Fehler lag in der Prüfung der Funktionen.

**Behoben.** Der Wächter liest auf allen Builds auch den Kartenkontakt (`0x01E26070`, Bit 1, wie ihn Korgs Firmware liest und wie ihn
die blaue schon nutzte). Auf den Sampler-Builds gilt ein gemountetes Volume weiter, der Wächter ist also nie strenger als vorher.
Die vier Patches (`tap-motion`, `note-assistant`, `pattern-switch`, `dice`) sind neu gebaut, die blauen Dateien sind byteweise gleich
geblieben.

**Gemessen (`case_card_inserted_late`).**

| Schritt | vor der Änderung | nach der Änderung |
|---|---|---|
| Start ohne Karte, TAP | Modus (1, 1), Firmware | (1, 1), Firmware |
| Karte eingesteckt, 1,5 s gewartet, Typ-Byte des Volumes | 0 | 0 |
| TAP | (1, 1), die Funktion ist aus | (0, 0), sie ist an |
| TAP noch einmal | (1, 1) | (1, 1) |
| im Menü TAP MOTION auf OFF, nichts gespeichert, TAP | (1, 1) | (1, 1), das Wort steht auf 0 |
| im Menü auf ON, TAP | (1, 1), keine Wirkung | (0, 0), das Wort steht auf 1, auf der Karte steht keine Datei |

Die Spalte "vor der Änderung" ist derselbe Fall auf Hacktribe mit dem Satz von vorher (der Fall schlägt dort fehl). Rot und
Hacktribe mit der Änderung: wie in der Spalte rechts. Blau: wie rechts, das Typ-Byte gibt es dort nicht, der Fall war auch vorher grün.

## Offen

- Am Gerät ist nichts geprüft. Dass der Kartenkontakt am echten Sampler bei eingelegter Karte tief ist, ist aus Korgs Lesezugriff
  und dem Emulator hergeleitet, nicht am Gerät gemessen. Der Wächter fällt nicht hinter den alten zurück, wenn es anders wäre.
- Das Schildchen am Gerät: das Zeichnen ist Korgs eigener Code, geprüft ist hier nur, dass das Byte stimmt und die Pixel
  denselben Ort haben.
