# BLECH-Einstellungen ohne Karte im Flash (13.11.)

Stand 13.11.2026 auf `release/1.4.6` (mit #518), nur Emulator (Hacktribe 2.02, Korgs Original 2.02 rot und blau, je mit dem BLECH-Satz dieses Stands), am Gerät
nichts geprüft. Ziel: eine Electribe ohne SD-Karte (vor allem die blaue) behält ihre BLECH-Einstellungen über den Neustart.
Marker: **gemessen** (im Emulator), **offline gelesen** (Disassembly), **hergeleitet**, **offen**.

## Verhalten

- Start: steckt eine Karte mit gültiger Einstellungsdatei, gilt die Karte. Sonst gilt die Kopie im Flash, sonst der Standard.
  Eine Karte ohne gültige Datei zählt wie keine Karte.
- Ohne Karte gehen Änderungen in den BLECH-Menüs (FEATURES, CUSTOMIZATION, PLUGINS) in den Flash, sobald man das BLECH-Menü
  verlässt (AUTO SAVE, wie mit Karte; nicht schon während man dreht). Mit AUTO SAVE OFF erst mit WRITE. WRITE ohne
  Karte schreibt sofort und zeigt `saved in flash`.
- Mit Karte schreibt WRITE und AUTO SAVE wie bisher die Datei auf der Karte, der Flash bleibt.
- Nach einem Start ohne Karte liest BLECH keine Karte bis zum nächsten Start (#518, sonst kann Korgs Karten-Init hängen): die
  Werte kommen aus dem Flash, eine gesteckte Karte zählt nicht, Änderungen und WRITE gehen in den Flash, die Karte wird nicht
  angefasst.
- Karte tauschen nach einem Start mit Karte (#505): die Werte der neuen Karte gelten sofort
  im RAM, danach fragt das Display `CARD SETTINGS` / `SAVE TO FLASH?` / `MENU: SAVE` / `EXIT: ONLY FOR NOW`. MENU schreibt sie in
  den Flash, EXIT lässt sie nur im RAM. Solange die Frage steht, nimmt sie alle Tasten, Pads, Regler und das Touchpad (wie die
  Frage der Migration).
- Karte ungespeichert wieder ziehen (8 Frames ohne Karte, dann gilt sie als gezogen): die Kopie im Flash gilt wieder. Nach MENU
  bleibt alles, wie es ist. Das gilt auch für eine Karte, die schon beim Start steckte.
- Vor dem Lesen der neuen Karte schreibt das Einstecken offene Änderungen ohne Karte (seit dem Ziehen) in den Flash, damit es
  beim Ziehen etwas gibt, wohin es zurückgeht. Hat die Karte dieselben Werte wie der Flash, kommt keine
  Frage.
- Eine Menüzeile SAVE TO FLASH gibt es nicht: in den Flash geht es von selbst ohne Karte, mit WRITE ohne Karte
  oder mit MENU auf die Frage einer getauschten Karte.
- Neustart: Karte steckt, die Karte gilt; keine Karte, der Flash gilt.

## Belegtabelle

| Behauptung | Beleg | Marker |
|---|---|---|
| Ohne Karte schreibt eine Änderung (TAP MOTION auf OFF) nichts, solange das BLECH-Menü offen ist (3 s gewartet); beim Verlassen einmal in Sektor `0x7FD000` (Generation 1), danach nichts mehr; kein anderer Sektor ändert sich | `tools/emu/menu_cases.py:flash_settings_cases`, `change_written_on_leave`: Vergleich des ganzen Flash vor und nach, jede Löschung mitgeschrieben; HT, rot, blau | gemessen |
| AUTO SAVE OFF ohne Karte: Verlassen schreibt nichts, WRITE schreibt | `auto_save_off_waits_for_write` | gemessen |
| Der nächste Start ohne Karte liest den Flash; eine zweite Änderung geht in Sektor `0x7FE000` (Generation 2), `0x7FD000` bleibt Byte für Byte | `restart_reads_flash` | gemessen |
| Ein halb geschriebener Satz (ein Byte im neueren Sektor gekippt) fällt auf den älteren zurück; beide Sektoren gelöscht gibt den Standard | `torn_copy_falls_back` | gemessen |
| Karte mit Datei gewinnt beim Start, der Flash wird dabei und nach WRITE nicht angefasst, WRITE schreibt die Karte; eine Karte ohne Datei nimmt den Flash | `card_wins` | gemessen |
| Start mit Karte, Karte gezogen (Werte des Flash), Karte wieder gesteckt: die Werte der Karte gelten sofort, das Display fragt (Bit 17 von `M_FL`, Pixel der zwei Titelzeilen), der Flash bleibt; EXIT löst die Frage, die Werte bleiben; Ziehen bringt die Werte des Flash zurück, eine Änderung danach geht beim Verlassen wieder in den Flash (Generation 3) | `hot_swap_asks_exit_keeps_ram` | gemessen |
| MENU auf der Frage schreibt die Werte der Karte (Generation 3 in `0x7FD000`, kein anderer Sektor), Ziehen ändert nichts, der nächste Start ohne Karte hat sie | `hot_swap_menu_saves` | gemessen |
| Karte beim Start: keine Frage; gezogen gelten die Werte des Flash, der Flash wird nicht angefasst | `start_card_pulled_reverts` | gemessen |
| Getauschte Karte mit denselben Werten wie der Flash: keine Frage, keine Sperre, nichts geschrieben | `same_settings_no_question` | gemessen |
| Start ohne Karte: eine gesteckte Karte wird nicht gelesen, keine Frage, eine Änderung geht beim Verlassen weiter in den Flash (Generation 3), WRITE zeigt `saved in flash` und schreibt Generation 4, die Karte bleibt Byte für Byte | `cardless_start_ignores_card` | gemessen |
| Karte ziehen und eine andere stecken (#505, [Messung](2026-11-12-karte-spaeter-einstellungen.md)) mit leerem Flash: beim Ziehen bleiben die Werte der ersten Karte (keine Kopie im Flash), die zweite wird ganz gelesen | `card_later_cases`, `swap_reads_the_other_card` (unverändert) | gemessen |
| CUSTOMIZATION hat keine Zeile SAVE TO FLASH, nach einem Start mit Karte schreibt das Durchblättern nichts in den Flash | `no_save_to_flash_row` | gemessen |
| WRITE ohne Karte zeigt `saved in flash` und legt einen gültigen Satz in `0x7FD000` | `settings_cases`, `menu:settings_without_card` | gemessen |
| Rot und Hacktribe: `[0x7F0000, 0x7FF000)` hat keinen Schreiber in der Firmware und liegt in keinem Bereich, den ein Update schreibt | [Flash-Karte](2026-10-24-flash-karte.md) | offline gelesen |
| Blau (Korg 2.02, sha256 `41fc5f1c...`): alle Aufrufer der Schreibfunktion `0xC0026E24` schreiben `0x230000` (Globals), `0x240000 + n * 0x4000` (Pattern), `0x7EF000`, `0x7FF000` und über `0xC0027000` die Update-Bereiche 0 (bis `0x20000`), 2 (bis `0x200000`), `0x22` (bis Bereich `0x7E`, also unter `0x7E0000`) und `0x80` (genau `0x800000`); der Sektorschreiber `0xC0019EA4` wird nur aus `0xC0026E24` gerufen. `0x7FD000` und `0x7FE000` schreibt nichts davon | Disassembly mit capstone, jeder `bl`/`b` auf beide Adressen mit den Befehlen davor | offline gelesen |
| Die Schreibfunktion der blauen hat dieselbe Belegung wie die rote (`r0` Objekt, `r1` Adresse, `r2` Länge, `r3` Quelle) | dieselbe Disassembly (Aufrufer bei `0xC0027304`, `0xC0027384`), danach alle Fälle auf blau grün | offline gelesen, gemessen |

## Format und Ablauf

Zwei 4-KiB-Sektoren, `0x7FD000` (ungerade Generation) und `0x7FE000` (gerade). Jeder hält den Satz wie `settings.a.bin`
(Version 3, 24 bis 280 Byte mit seiner CRC), dahinter das Wort `0x4C46` << 16 | Generation (16 Bit, "FL") und eine CRC-32 über
Satz und Wort. Geschrieben wird immer in den Sektor, in dem die neuere Kopie nicht liegt; ein abgerissenes Schreiben trifft
also nur die ältere, die neuere bleibt ganz. Beim Start liest `menu_flash_read` beide Sektoren, prüft Version, Kennung, beide
CRCs und den Satz selbst wie eine Datei (`menu_record_check`) und nimmt die neuere gültige (16-Bit-Abstand, zählt über den
Überlauf). Den Stand des Flash merkt sich die Laufzeit auch dann, wenn die Karte gewinnt, damit ein späteres Schreiben die ältere
Kopie überschreibt.

Geschrieben wird wie mit Karte: `autosave_leave` beim Verlassen des BLECH-Menüs, wenn sich die Prüfsumme der Einstellungen
(`menu_settings_crc`) seit dem Betreten geändert hat und AUTO SAVE an ist, ruft `menu_settings_save`; ohne Karte und ohne Sperre
geht das in den Flash (`menu_flash_save`, UI-Task, wie WRITE). Bis 14.11. schrieb ein Takt im Frame-Hook schon 1 bis 2 s nach dem
letzten Dreh (`menu_flash_watch`, entfernt). Die Sperre `FL_HOLD` (Bit 16 von `M_FL`, Wort `0x114` im Menüzustand) setzt jede
Karte, deren Datei gelesen wurde (Start oder Tausch); MENU auf der Frage löst sie, ebenso eine Karte mit denselben Werten wie
der Flash.

`menu_card_watch` zählt beim Einstecken wie bisher 8 Frames, schreibt ohne Sperre erst offene Änderungen in den Flash
(`menu_flash_sync`), liest dann die Karte und setzt `FL_ASK` (Bit 17), wenn ihre Prüfsumme nicht die des Flash ist. Die Frage
zeichnet `menu_ask_frame` im Frame-Hook wie die Frage der Migration (eigener Puffer, in den Bildspeicher der Firmware kopiert,
neu markiert); `menu_ask_input` vor der Eingabe der Firmware merkt EXIT oder MENU im Byte `0x157` und verwirft alle Eingaben bis
Typ 5. Ist die Karte 8 Frames weg (`M_CARD` `0x80 + n`), löst das die Frage, und mit Sperre liest `menu_settings_load` nur den
Flash (`M_CARD` = `0xFE`), ohne Karte. `menu_flash_save` ruft die Schreibfunktion der Firmware (rot und HT `0xC0029AB8`, blau `0xC0026E24`), die unter
ihrer Sperre den Sektor liest, löscht und neu schreibt, wie der Startbild-Editor bei WRITE.

## Messwerte

Alle elf Fälle in `flash_settings_cases` sind auf allen drei Builds grün, ebenso `settings_cases` (20), `page_cases` (3)
und `splash_menu_cases` (gemessen). In keinem Lauf wurde ein anderer Sektor als `0x7FD000` oder `0x7FE000` gelöscht.

Der Flash hängt an SPI1 und ist nicht in den Adressraum gelegt. Am Gerät (14.11.) hat BLECH FLASH READ (`0x64`, ohne EXEC)
`0x7FD000` und `0x7FE000` in zwei Läufen mit gleichem sha256 als lauter FF gelesen (gemessen).

## Offen

- Die Schreibfunktion `0xC0029AB8` aus einem EXEC-Stub aufzurufen, um ein Löschen zu timen, hat das rote Gerät abstürzen lassen
  (Display rot und stehend, kein Assert-Text), im Emulator lief derselbe Stub durch; `0x7F0000` bis `0x800000` war danach
  unverändert (gemessen 14.11.). Die Löschzeit wird darum nur über den eigenen Speicherweg der Firmware gemessen.

- Am Gerät ist nichts geprüft: Löschzeit eines Sektors (der UI-Task steht so lange, im Emulator ohne Zeit), Lebensdauer.
  Zwei Sektoren im Wechsel, höchstens ein Schreiben je Verlassen des BLECH-Menüs mit einer Änderung (hergeleitet).
- Das Einstecken kann einen Sektor löschen (offene Änderungen ohne Karte seit dem Ziehen), bevor die Frage kommt. Ohne das gäbe
  es beim Ziehen nichts, wohin es zurückgeht.
- Gibt es beim Ziehen keine gültige Kopie im Flash (ein Gerät, das immer mit Karte lief, oder beide Sektoren kaputt), bleiben die
  Werte der Karte im RAM und die Sperre steht bis WRITE oder bis zum nächsten Start (gemessen mit leerem Flash in `swap_reads_the_other_card`).
- Die Frage nimmt alle Eingaben, auch Pads; ein laufendes Pattern spielt weiter, lässt sich aber erst nach EXIT oder MENU
  bedienen.
- Zu den gesicherten Werten gehören auch die erlaubten Plugins (Prüfsummen in `settings.a.bin`). Plugins, Effekte, Samples und
  Patterns selbst liegen weiter nur auf der Karte.
- Mit AUTO SAVE OFF schreibt ohne Karte erst WRITE in den Flash, Verlassen des Menüs schreibt nichts
  (`auto_save_off_waits_for_write`).
- Ein Update von Korg, das `0x7F` anfasst, ist für rot und HT gelesen (keins), für die blaue über die Längen der Update-Bereiche
  hergeleitet, nicht mit einer echten Update-Datei gemessen.
