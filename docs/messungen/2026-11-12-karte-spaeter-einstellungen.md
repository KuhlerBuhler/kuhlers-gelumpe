# Kartentausch bringt die ganze Einstellungsdatei mit (12.11.)

Stand 12.11.2026, Emulator (Hacktribe 2.02, Korgs Original 2.02 rot und blau, je mit dem BLECH-Satz dieses Stands) und Gerät
(Hacktribe 2.02, nur READ über BLECH SysEx). Ziel: Karte tauschen, und die Electribe hat sofort das Setup und das Aussehen dieser Karte.
Marker: **gemessen**, **offline gelesen** (Disassembly), **hergeleitet**, **offen**.

## Verhalten

- Steckte beim Einschalten eine Karte, liest `menu_card_watch` nach Ziehen und Stecken die Einstellungsdatei der neuen Karte, sobald
  der Kartenkontakt 8 Frames (320 ms) in Folge eine Karte zeigt, und wendet sie an wie der Start.
- Steckte beim Einschalten keine Karte, liest BLECH bis zum nächsten Start keine Karte. Grund: siehe [Hänger](#hänger-bei-der-ersten-karte-nach-einem-start-ohne-karte).

## Belegtabelle

| Behauptung | Beleg | Marker |
|---|---|---|
| Karte ziehen und eine andere stecken liest die andere: Unterleuchten, untere LEDs, Displaypolarität, Pad-Farben und alle Schalter gleich einem Gerät, das mit dieser Karte gestartet ist | `tools/emu/menu_cases.py:card_later_cases`, `swap_reads_the_other_card` | gemessen |
| Nach einem Start ohne Karte ändert eine gesteckte Karte nichts | `start_without_card_reads_none` | gemessen |
| Plugin-Runtime und MFX 2 laufen weiter wie seit dem Einschalten, der neue Wert wirkt beim nächsten Start (wie nach einer Änderung auf ihren Seiten) | `runtime_stays` | gemessen |
| Eine Karte ohne gültige Einstellungsdatei ändert nichts, auf die Karte wird nichts geschrieben | `card_without_file_keeps`, `card_not_written` | gemessen |
| Die Karte, die beim Start steckt, wird nicht ein zweites Mal gelesen | `card_at_start_read_once` | gemessen |
| Das blaue Display schreibt eine Seite nur, wo sie sich vom zuletzt gesendeten Stand unterscheidet (0xC0011370 vergleicht 128 Byte); bei stehendem Hauptbildschirm käme die neue Polarität erst beim nächsten Bildwechsel. Darum sendet der Wächter auf dem blauen danach alle acht Seiten (0xC001185C mit 1, wie das Display beim Start bei 0xC00117F4) | Disassembly Korg 2.02 blau, danach `swap_reads_the_other_card` auf blau grün | offline gelesen, gemessen |

## Ablauf

Der Frame-Hook (UI-Task, dort liest und schreibt auch WRITE die Karte) ruft `menu_card_watch` in jedem Frame. `M_CARD` (Wort `0x1B0`
im Menüzustand) setzt `menu_arm_load` am Ende des Starts: mit Karte auf `CARD_DONE`, ohne Karte auf `CARD_NEVER`. Bei `CARD_NEVER`
geht der Wächter sofort heraus. Sonst setzt ihn eine gezogene Karte auf 0, eine gesteckte zählt hoch; nach 8 Frames setzt er sich auf
`CARD_DONE` und ruft `menu_settings_load`, dieselbe Funktion wie der Start. Ohne Datei geht `menu_settings_load` beim Nachstecken
sofort heraus (beim Start setzt sie den Standard).
Sperrt Korgs SD-Treiber die Karte beim Lesen (`CARD_WAIT`, `CARD_STUCK`), siehe [Init-Sperre](2026-11-14-karte-init-sperre.md).

## Hänger bei der ersten Karte nach einem Start ohne Karte

- **Gemessen am Gerät (12.11.):** Start ohne Karte, Karte gesteckt: das Gerät steht 15 bis 60 s oder bis die Karte gezogen wird.
  Danach geht das nächste Stecken in 2 s. Hat das Gerät einmal eine Karte gelesen, hängt kein weiterer Tausch.
- **Offline gelesen:** Korgs Kartentask merkt das Stecken nur (`0xC001CF54` -> `0xC001D978`), die Karte initialisiert erst der
  erste Zugriff (`0xC001D2B8` -> `0xC001AE04`). Nach CMD0 und CMD8 schickt die Schleife bei `0xC001AE80` CMD55 und ACMD41
  (`0xC001BE34`), bis Bit 31 der Antwort (OCR, `0xC031BEA4`) gesetzt ist, bis zu 50000 Runden (Grenze `0xC34F` bei `0xC001B178`)
  oder bis die Karte gezogen wird (-13). Der Wächter liest im UI-Task, das Gerät steht so lange.
- **Gemessen am Gerät (READ):** beim Hänger steht das OCR 18 s lang auf `0x00FF8000`, die Karte meldet also durchgehend "busy".
  Beim Stecken danach ist sie in etwa 2 s bereit.
- **Gemessen am Gerät:** 2 s Wartezeit vor dem Lesen und eine Grenze von 4999 Runden mit erneutem Versuch helfen nicht. Ein
  Neuversuch in Software holt die Karte nicht zurück, nur Ziehen und Stecken. Nach dem Ziehen aktualisierte sich die Anzeige einmal nicht.
- **Offen:** warum die erste Initialisierung nach einem Start ohne Karte hängt (Vermutungen: CMD8 geht verloren, der Controller ist
  nach dem Startversuch ohne Karte in einem schlechten Zustand). Bis das geklärt ist, liest BLECH nach einem Start ohne Karte keine Karte.

## Offen

- Plugins und Effekte der neuen Karte werden nicht geladen (die lädt nur der Start).
