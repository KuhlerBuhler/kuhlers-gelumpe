# BLECH-Einstellungen ohne Karte im Flash (13.11.)

Stand 13.11.2026, nur Emulator (Hacktribe 2.02, Korgs Original 2.02 rot und blau, je mit dem BLECH-Satz dieses Stands), am Gerät
nichts geprüft. Ziel: eine Electribe ohne SD-Karte (vor allem die blaue) behält ihre BLECH-Einstellungen über den Neustart.
Marker: **gemessen** (im Emulator), **offline gelesen** (Disassembly), **hergeleitet**, **offen**.

## Verhalten

- Start: steckt eine Karte mit gültiger Einstellungsdatei, gilt die Karte. Sonst gilt die Kopie im Flash, sonst der Standard.
  Eine Karte ohne gültige Datei zählt wie keine Karte.
- Ohne Karte geht jede Änderung in den BLECH-Menüs (FEATURES, CUSTOMIZATION, PLUGINS) von selbst in den Flash. WRITE ohne
  Karte schreibt sofort und zeigt `saved in flash`.
- Mit Karte schreibt WRITE und AUTO SAVE wie bisher die Datei auf der Karte, der Flash bleibt.
- Kartentausch (#505): die Werte der Karte gelten sofort, aber nur im RAM. Der Flash bleibt, bis
  `Menü -> BLECH -> CUSTOMIZATION -> SAVE TO FLASH` (letzte Zeile, ENTER oder WRITE) sie fest übernimmt.
- Neustart ohne SAVE TO FLASH: Karte steckt, die Karte gilt; keine Karte, der Flash gilt.

## Belegtabelle

| Behauptung | Beleg | Marker |
|---|---|---|
| Ohne Karte schreibt eine Änderung (TAP MOTION auf OFF) einmal in Sektor `0x7FD000` (Generation 1), danach nichts mehr; kein anderer Sektor ändert sich | `tools/emu/menu_cases.py:flash_settings_cases`, `change_written`: Vergleich des ganzen Flash vor und nach, jede Löschung mitgeschrieben; HT, rot, blau | gemessen |
| Die Löschung kommt 1 bis 2 s nach dem Dreh (zwei Prüfungen im Abstand von 25 Frames, die zweite muss dieselbe Prüfsumme sehen) | `change_written`, Zeit der Löschung gegen die Zeit des Drehs (Werte unten) | gemessen |
| Der nächste Start ohne Karte liest den Flash; eine zweite Änderung geht in Sektor `0x7FE000` (Generation 2), `0x7FD000` bleibt Byte für Byte | `restart_reads_flash` | gemessen |
| Ein halb geschriebener Satz (ein Byte im neueren Sektor gekippt) fällt auf den älteren zurück; beide Sektoren gelöscht gibt den Standard | `torn_copy_falls_back` | gemessen |
| Karte mit Datei gewinnt beim Start, der Flash wird dabei und nach WRITE nicht angefasst, WRITE schreibt die Karte; eine Karte ohne Datei nimmt den Flash | `card_wins` | gemessen |
| Kartentausch: die Werte der Karte gelten, der Flash bleibt, auch nach Ziehen der Karte und einer Änderung ohne Karte; der nächste Start ohne Karte hat die alten Flash-Werte | `hot_swap_keeps_flash` | gemessen |
| SAVE TO FLASH übernimmt die Werte der Karte (Generation 3 in `0x7FD000`), der nächste Start ohne Karte hat sie | `save_to_flash` | gemessen |
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
Überlauf). Den Stand des Flash merkt sich die Laufzeit auch dann, wenn die Karte gewinnt, damit SAVE TO FLASH die ältere Kopie
überschreibt.

`menu_flash_watch` läuft im Frame-Hook hinter `menu_card_watch` (UI-Task, wie WRITE). Ohne Karte und ohne Sperre vergleicht er alle
25 Frames (1 s) die Prüfsumme der Einstellungen (`menu_settings_crc`) mit der des Flash. Schreibt erst, wenn die Änderung bei der
nächsten Prüfung noch dieselbe ist: ein Regler, der gerade gedreht wird, löst nicht jede Sekunde ein Löschen aus. Die Sperre
`FL_HOLD` (Bit 16 von `M_FL`, Wort `0x114` im Menüzustand) setzt jede Karte, deren Datei gelesen wurde (Start oder Tausch); SAVE
TO FLASH löst sie. `menu_flash_save` ruft die Schreibfunktion der Firmware (rot und HT `0xC0029AB8`, blau `0xC0026E24`), die unter
ihrer Sperre den Sektor liest, löscht und neu schreibt, wie der Startbild-Editor bei WRITE.

## Messwerte

Erste Änderung bis zur Löschung (`change_written`, Zeit des Drehs gegen Zeit der Löschung im Emulator):

| Build | Dreh | Löschung | Abstand |
|---|---|---|---|
| Hacktribe | 2016 ms | 3335 ms | 1,3 s |
| rot | 3580 ms | 5539 ms | 2,0 s |
| blau | 12303 ms | 13425 ms | 1,1 s |

Der Abstand liegt zwischen einer und zwei Prüfungen (je 1 s), je nachdem wo im Takt der Prüfung gedreht wird (hergeleitet).
Alle sechs Fälle in `flash_settings_cases` sind auf allen drei Builds grün, ebenso `settings_cases` (20), `page_cases` (3)
und `splash_menu_cases` (gemessen). In keinem Lauf wurde ein anderer Sektor als `0x7FD000` oder `0x7FE000` gelöscht.

Am Gerät (13.11.) ist der Bereich nicht gelesen: der Flash hängt an SPI1 und ist nicht in den Adressraum gelegt, lesen geht nur
über die Lesefunktion der Firmware (EXEC), und das ist eine Änderung am Gerät (offen).

## Offen

- **Nur BLECH-Einstellungen oder mehr?** Gesichert wird nur, was `settings.a.bin` hält (FEATURES, CUSTOMIZATION, die erlaubten
  Plugins). Plugins, Effekte, Samples und Patterns liegen weiter nur auf der Karte (Patterns und Globals der Firmware ohnehin im
  Flash). Noch zu entscheiden.
- Am Gerät ist nichts geprüft: Löschzeit eines Sektors (der UI-Task steht so lange, im Emulator ohne Zeit), Lebensdauer.
  Zwei Sektoren im Wechsel, höchstens ein Schreiben je Sekunde Ruhe nach einer Änderung (hergeleitet).
- Ändert man nach einem Kartentausch und gezogener Karte etwas, bleibt das nur im RAM (Sperre). Alternative wäre, beim Ziehen
  auf die Werte des Flash zurückzugehen. So gebaut, weil der Flash nach einem Tausch erst mit SAVE TO FLASH wechseln soll.
- AUTO SAVE OFF hält das Schreiben in den Flash nicht auf: "jede Änderung sofort" ist wörtlich umgesetzt.
- Ein Update von Korg, das `0x7F` anfasst, ist für rot und HT gelesen (keins), für die blaue über die Längen der Update-Bereiche
  hergeleitet, nicht mit einer echten Update-Datei gemessen.
