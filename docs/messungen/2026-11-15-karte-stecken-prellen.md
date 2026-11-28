# Karte im Betrieb wieder gesteckt: Lesen, solange die Karte noch rutscht (15.11.)

Stand 15.11.2026. Gerät: rote Electribe, Firmware f56f4b7e (release/1.4.6 38b75dd1, Basis [Hacktribe](../glossary.md#hacktribe) 163d1d8d), nur READ über BLECH
[SysEx](../glossary.md#sysex) (`swappoll.py` auf linux, ~/gelumpe-probe, Log `reins-loop.log`). [Emulator](../glossary.md#emulator): dieselbe Firmware. Marker: **gemessen**,
**hergeleitet**, **offen**.

## Befund

Gerätetest 1.4.6: Start mit Karte A, A ziehen, am Rechner `e2sFx.all` ersetzen, A wieder stecken. Ziehen geht (Flash-Werte zurück),
nach dem Stecken steht das Gerät: Pattern-Bildschirm eingefroren, erst Aus/Ein hilft.

| Behauptung | Beleg | Marker |
|---|---|---|
| 17:16:20 Ziehen: `M_CARD` 0x82 bis 0x87, dann 0, `M_FL` 0x4, Flash-CRC 0x5aff3ac7 | READ-Poll | gemessen |
| 17:17:05,7 Stecken: Zähler 1 bis 7, nach 0,3 s gelesen (`M_CARD` 0xFF). Korgs Init läuft bis ACMD41 (OCR kurz 0x00FF8000, dann bereit), Init-Flag bleibt 0, `fs_type` 0, `M_FL` bleibt 0x4: das Lesen ist gescheitert | READ-Poll | gemessen |
| 0,2 s nach dem Lesen (0,5 s nach dem ersten Kontakt) meldet der Kartenschalter einmal "keine Karte", danach wieder "Karte" | READ-Poll, `pres` 0 bei 441,19 s | gemessen |
| Ab etwa 17:17:07 keine Antwort mehr, bis zum Aus- und Einschalten von Hand | READ-Poll, Tester | gemessen |
| Die Karte war beim Lesen noch nicht ganz drin: der Schalter prellt danach noch, und die Init scheitert nach ACMD41 | aus den Zeilen darüber | hergeleitet |
| `e2sFx.all` liest BLECH nur beim Start (`fx_card_load` aus `script_start_sampler.s`), nicht beim Stecken | Code | gemessen |
| Warum das Gerät nach dem gescheiterten Lesen hängt | Emulator: gescheiterte Init plus Prellen hängt nicht | offen |

## Fix in `menu_card_watch` (`tools/patch/script_menu.s`)

- Eine gesteckte Karte wird erst gelesen, wenn der Schalter sie `CARD_SETTLE_IN` = 15 Frames (0,6 s) am Stück zeigt, statt 8 Frames
  (0,32 s). Ein Prellen setzt den Zähler zurück. Beim Gerätefall hätte das Lesen nach dem Prellen begonnen.
- Das Ziehen zählt weiter `CARD_SETTLE` = 8 Frames.
- Beim Zurückstellen des Takts, solange keine Karte steckt, liegen Befehls- und Datenpfad des Controllers im Reset (`MMCCTL` CMDRST,
  DATRST), wie in Korgs Controller-Init beim Einschalten (`0xC00175AC`). Ob das für den Hänger nötig ist, ist offen: ohne Reset hing
  der Emulator auch nicht.

| Behauptung | Beleg | Marker |
|---|---|---|
| Fall `card_going_in_is_read_once_in`: Karte antwortet die ersten 0,5 s nicht, Schalter öffnet einmal für 40 ms, danach antwortet sie. Mit dem Fix wird sie gelesen | `menu_cases.py:card_later_cases` | gemessen |
| Am Gerät | | offen (Gerätetest) |
