# Karte steckt, aber "No Card.": die Init-Sperre in Korgs SD-Treiber (14.11.)

Stand 14.11.2026. Gerät: rote Electribe mit Hacktribe 2.02 + BLECH (Firmware ffc395bd), nur READ über BLECH SysEx. Emulator: Hacktribe 2.02,
Korgs Original 2.02 rot und blau. Marker: **gemessen**, **offline gelesen** (Disassembly), **hergeleitet**, **offen**.

## Befund

Die Karte war im Betrieb zum Mac gezogen und wieder gesteckt worden. Danach zeigte das Gerät das Kartensymbol, sagte aber "No Card.".

| Behauptung | Beleg | Marker |
|---|---|---|
| Am Gerät: Kartenkontakt da, Treiber "present" 1, "initialized" 0, Sperrwort `0xC031BEEC` = 1, FatFs `fs_type` 0, `M_CARD` = `CARD_DONE`, OCR 0x120 | READ über BLECH SysEx (`card_state_read.py` auf linux, ~/gelumpe-probe) | gemessen |
| Korgs Init (Controller-Tabelle +0x18 = `0xC001ACA0`) bricht sofort mit -1 ab, solange `[0xC031BEEC]` nicht 0 ist (gelesen von `0xC001DB3C`). Gesetzt wird das Wort von `0xC001DB18`, wenn die ACMD41-Schleife ab `0xC001AE80` ihre 0xC34F Runden aufgebraucht hat; gelöscht nur von `0xC001DB60` im MMC-Interrupt (`0xC0025BD0` -> `0xC001CFAC` -> `0xC001D290` -> `0xC001DEB4`) | Disassembly Korg 2.02 rot und Hacktribe | offline gelesen |
| Blau: dasselbe Wort, Setzen/Lesen/Löschen bei `0xC0019440`/`0xC0019464`/`0xC0019488` | Disassembly Korg 2.02 blau | offline gelesen |
| Der Interrupt kommt nur als Antwort auf einen Befehl. Ohne Init kein Befehl, also bleibt die Sperre: jeder weitere Mount scheitert sofort, auch nach Ziehen und Stecken einer guten Karte | Emulator: Karte, die nie fertig wird, stecken, Sperre nach ~6,5 s; danach gute Karte stecken: Sperre bleibt, `fs_type` 0 (BLECH-Stand vor dem Fix, HT) | gemessen |
| Ohne Fix hilft am Gerät nur ein Neustart | aus den zwei Zeilen darüber | hergeleitet |
| Die Sperre am Gerät von außen löschen ging nicht: BLECH WRITE auf `0xC031BEEC` lehnt die Schutztabelle ab (Status 2), nichts geschrieben | WRITE-Versuch 14.11. mit Pascals OK | gemessen |
| Das erklärt auch die Beobachtung aus #518, dass ein Wiederholen in Software nicht half: die Wiederholungen liefen in die Sperre | aus der Sperre | hergeleitet |

## Fix in `menu_card_watch` (`tools/patch/script_menu.s`)

- Bevor der Wächter eine gesteckte Karte liest, setzt er das Sperrwort auf 0. Damit liest Ziehen und Stecken wieder, auch nach einem Hänger.
- Ist das Sperrwort nach dem Lesen gesetzt, merkt sich `M_CARD` (`CARD_WAIT`) den OS-Tick 2 s später. Dann liest der Wächter die Karte
  ein zweites Mal, wieder mit gelöschter Sperre. Die Wartezeit läuft in OS-Ticks (1 ms), nicht in Frames: die Frames, die das gesperrte
  Lesen aufgehalten hat, laufen direkt danach nach (Emulator: 50 Frames in 0,1 s).
- Sperrt auch das zweite Lesen, geht `M_CARD` auf `CARD_STUCK`: kein weiterer Versuch, bis die Karte gezogen wird. Jeder Versuch hält den
  UI-Task, solange Korgs Schleife läuft (im Emulator ~6,5 s), darum nur einer.
- Steckt beim Start eine Karte und die Sperre ist schon gesetzt (die Karte hing beim Start), startet `M_CARD` auf `CARD_STUCK`, damit nach
  dem Start kein zweiter Hänger folgt.
- `CARD_NEVER` (Start ohne Karte, #518) bleibt unverändert: keine Karte, kein Versuch bis zum nächsten Start.

| Behauptung | Beleg | Marker |
|---|---|---|
| Karte beim ersten Lesen noch nicht fertig, danach fertig: das zweite Lesen nach 2 s liest die Einstellungsdatei, Sperre 0 | `tools/emu/menu_cases.py:card_later_cases`, `locked_card_read_again`, HT/rot/blau | gemessen |
| Karte bleibt nicht fertig: genau ein zweiter Versuch, dann `CARD_STUCK`, keine weiteren | `busy_card_read_once_more_only`, HT/rot/blau | gemessen |
| Danach eine andere Karte stecken liest sie | `stuck_card_swapped_reads`, HT/rot/blau | gemessen |
| Ob 2 s am Gerät reichen, hängt davon ab, wie lange die Karte busy bleibt (am 12.11. nach einem Start ohne Karte 18 s, das ist `CARD_NEVER`). Ziehen und Stecken hilft immer | | offen |
