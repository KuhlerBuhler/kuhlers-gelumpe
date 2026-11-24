# Karte im Betrieb getauscht: neue Karte wird mit 12,5 MHz identifiziert (14.11.)

Stand 14.11.2026. Gerät: rote Electribe, Firmware 93073c42 (release/1.4.6 785fc2a8, Basis [Hacktribe](../glossary.md#hacktribe) 163d1d8d), nur READ über BLECH
[SysEx](../glossary.md#sysex). [Emulator](../glossary.md#emulator): Hacktribe 2.02, Korgs Original 2.02 rot und blau. Marker: **gemessen**, **offline gelesen** (Disassembly),
**hergeleitet**, **offen**.

## Befund

Gerätetest 1.4.6, Punkte 2.5 und 3.2: Start mit Karte A (gelb), A im Betrieb ziehen, Karte B (blau) stecken. Beim Ziehen springt das
Display auf die Flash-Werte (2.7 geht). Nach dem Stecken passiert nichts: keine Frage SAVE TO FLASH?, Displayfarbe, LEDs und Pads
bleiben. Nach Aus/Ein mit B gelten die Werte von B.

| Behauptung | Beleg | Marker |
|---|---|---|
| Vor dem Tausch: `M_CARD` 0xFF, `M_FL` 0x10003, Sperre 0, init 1, OCR 0xC0FF8000, `fs_type` 3 | READ-Poll (`swappoll.py` auf linux, ~/gelumpe-probe) | gemessen |
| Nach dem Stecken von B: SysEx mehrere Minuten ohne Antwort (UI-Task hängt), danach `M_CARD` 0xFC (`CARD_STUCK`), Sperre `0xC031BEEC` = 1, present 1, init 0, OCR 0, `fs_type` 0 | READ-Poll ab 17:56, Stand 18:03 | gemessen |
| OCR 0 heißt: B hat auf ACMD41 gar nicht geantwortet, nicht "busy". Korgs Init setzt OCR `0xC031BEA4` vor der Schleife auf 0 (`0xC001AE6C`), jede Runde speichert die Antwort von ACMD41 dort, auch eine leere (`0xC001BE34`) | Disassembly | offline gelesen |
| Korgs Karten-Init (`0xC001AE04`: CMD0, CMD8, ACMD41-Schleife, CMD2/3/9/10/7/16, ACMD6) stellt den MMC-Takt nicht ein. Den Identifikations-Takt (`MMCCLK` 0x35D = 0,4 MHz, `MMCCTL` 1-bit) setzt nur die Controller-Init beim Einschalten (`0xC00175AC`, Takt `0xC0017670`). Nach ACMD6 schaltet Korg auf 0x105 (12,5 MHz) und 4-bit | Emulator-Spur der MMC-Register beim Start, Disassembly | gemessen, offline gelesen |
| Eine im Betrieb gesteckte Karte wird deshalb mit dem Takt der Karte davor identifiziert: 12,5 MHz, 4-bit. Das SD-Protokoll verlangt dafür höchstens 400 kHz | Emulator-Spur: CMD0 bis ACMD6 der zweiten Karte laufen bei `MMCCLK` 0x105, `MMCCTL` 0x4 | gemessen |
| Viele Karten vertragen das, B nicht. Das passt dazu, dass #581 (dieselbe Karte zurückgesteckt) am Gerät ging | aus den Zeilen darüber | hergeleitet |
| Das Kartenmodell ohne `slow_ident` antwortet bei jedem Takt, darum war der Emulator beim Tausch grün | `tools/emu/sdcard.py` | gemessen |

## Fix in `menu_card_watch` (`tools/patch/script_menu.s`)

- Solange keine Karte steckt, setzt der Wächter den MMC-Controller auf den Einschalt-Takt zurück: `MMCCLK` 0x35D (Takt beim Umstellen
  aus, wie das TRM verlangt), `MMCCTL` WIDTH auf 1-bit. Einmal, danach nur ein Registerlesen pro Frame.
- Damit läuft jede Identifikation nach einem Tausch wie beim Einschalten, egal ob BLECH liest oder Korg selbst (FatFs-Zugriff).
  Korg schaltet nach ACMD6 selbst wieder auf 12,5 MHz/4-bit.
- `CARD_NEVER` (Start ohne Karte) bleibt unverändert: dort hat nie eine Karte den Takt hochgesetzt.

| Behauptung | Beleg | Marker |
|---|---|---|
| Kartenmodell `SDCard(slow_ident=True)`: antwortet vor CMD3 nur bei CLKRT >= 0x5D. Mit der Firmware 93073c42 bleibt das Display gelb, Sperre 1, `M_CARD` 0xFC: genau der Gerätebefund | Emulator, scratchpad `one.py` | gemessen |
| Mit dem Fix: Karte draußen `MMCCLK` 0x35D, `MMCCTL` 0; B wird gelesen (blau), Sperre 0, `M_CARD` 0xFF, danach wieder 0x105 | `menu_cases.py:card_later_cases`, `swap_identifies_at_the_start_clock`, HT/rot/blau | gemessen |
| Am Gerät mit Karte B | | offen (Gerätetest) |
