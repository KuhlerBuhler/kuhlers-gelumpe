# Die später gesteckte Karte bringt ihre ganze Einstellungsdatei mit (12.11.)

Stand 12.11.2026, nur Emulator (Hacktribe 2.02, Korgs Original 2.02 rot und blau, je mit dem BLECH-Satz dieses Stands), am Gerät
nichts geprüft. Wunsch von Pascal (11.11.): Karte tauschen, und die Electribe hat sofort das Setup und das Aussehen dieser Karte.
Marker: **gemessen** (im Emulator), **offline gelesen** (Disassembly), **hergeleitet**, **offen**.

## Belegtabelle

| Behauptung | Beleg | Marker |
|---|---|---|
| Ohne Karte beim Start las BLECH die Einstellungsdatei nie, auch nicht, wenn die Karte danach steckte; nur die Spielhilfen gingen an ([Karte später](2026-11-11-orig-und-karte-spaeter.md)) | `card_later_cases` mit dem Satz von `release/1.4.6`: `reads_the_whole_file` und `swap_reads_the_other_card` schlagen fehl, alle Werte bleiben beim Standard | gemessen |
| Jetzt liest `menu_card_watch` die Datei, sobald der Kartenkontakt 8 Frames (320 ms) in Folge eine Karte zeigt, und wendet sie an wie der Start | `tools/emu/menu_cases.py:card_later_cases`, `reads_the_whole_file`: Unterleuchten, untere LEDs, Displaypolarität, Pad-Farben und alle Schalter gleich einem Gerät, das mit dieser Karte gestartet ist | gemessen |
| Karte ziehen und eine andere stecken liest die andere | `swap_reads_the_other_card` | gemessen |
| Plugin-Runtime und MFX 2 laufen weiter wie seit dem Einschalten, der neue Wert wirkt beim nächsten Start (wie nach einer Änderung auf ihren Seiten) | `runtime_stays` | gemessen |
| Eine Karte ohne gültige Einstellungsdatei ändert nichts, auf die Karte wird nichts geschrieben | `card_without_file_keeps`, `card_not_written` | gemessen |
| Die Karte, die beim Start steckt, wird nicht ein zweites Mal gelesen | `card_at_start_read_once` | gemessen |
| Das blaue Display schreibt eine Seite nur, wo sie sich vom zuletzt gesendeten Stand unterscheidet (0xC0011370 vergleicht 128 Byte); bei stehendem Hauptbildschirm käme die neue Polarität erst beim nächsten Bildwechsel. Darum sendet der Wächter auf dem blauen danach alle acht Seiten (0xC001185C mit 1, wie das Display beim Start bei 0xC00117F4) | Disassembly Korg 2.02 blau, danach `reads_the_whole_file` auf blau grün | offline gelesen, gemessen |

## Ablauf

Der Frame-Hook (UI-Task, dort liest und schreibt auch WRITE die Karte) ruft `menu_card_watch` in jedem Frame. Ohne Karte steht der
Zähler `M_CARD` (Wort `0x1B0` im Menüzustand) auf 0. Steckt eine Karte, zählt er hoch; nach 8 Frames setzt er sich auf
`CARD_DONE` und ruft `menu_settings_load`, dieselbe Funktion wie der Start. Am Ende des Starts steht er schon auf `CARD_DONE`, eine
Karte, die dann steckt, gilt als gelesen; ohne Karte setzt ihn der erste Frame auf 0. Ohne Datei geht `menu_settings_load` beim
Nachstecken sofort heraus (beim Start setzt sie wie bisher den Standard).

## Offen

- Am Gerät ist nichts geprüft. Ob Korgs Kartentreiber nach einem Kartentausch das Dateisystem neu mountet, ist im Emulator so,
  am Gerät nicht gemessen. Wenn nicht, liest der Wächter die Datei nicht oder eine falsche, dann gilt sie als ungültig (CRC) und
  es ändert sich nichts.
- Plugins und Effekte der neuen Karte werden nicht geladen (die lädt nur der Start).
