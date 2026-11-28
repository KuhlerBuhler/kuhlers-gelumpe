# Vorschau-BPM: die BPM oben zeigt beim Ansehen das Tempo des angesehenen Patterns

Stand 20.11.2026, [Emulator](../glossary.md#emulator) ([Hacktribe](../glossary.md#hacktribe) 2.02, Korgs Original 2.02 rot und blau, je nur mit dem Patch `pattern-switch`). Marker:
**gemessen** (im Emulator), **gelesen** (im Disassemblat), **hergeleitet**. Am Gerät ungeprüft.

## Was gebaut ist (Entscheidung 20.11.)

- Solange `VIEW:` gilt (gedreht, noch nicht mit MENU bestätigt; spielend oder gestoppt mit ungespeicherten Änderungen), zeigt die BPM
  der Statusleiste das Tempo des angesehenen Patterns aus seinem Block der Pattern-Bank, an derselben Stelle in derselben Schrift.
- Nach MENU (`NEXT:`), EXIT, Pad, Program Change und STOP steht sofort wieder das laufende Tempo da.
- Gleiche Sync Group wie das laufende Pattern (nicht OFF): das laufende Tempo, es wird beim Wechsel mitgenommen.
- Kein eigener Menüschalter: aus mit PATTERN CONFIRM OFF, ohne Karte und mit EXIT beim Einschalten, wie der ganze Patch.
- Nur RAM, keine Flash- oder Kartenschreibvorgänge.

## Befunde

| Befund | Beleg | Marker |
|---|---|---|
| Die BPM oben ist ein eigenes Widget der Statusleiste (Klasse mit vtable `0xC00E4D00`, 0x70 Byte): x bei +4 (50), y bei +8 (0), Wert in Zehnteln bei +0x48, Text bei +0x4E, Neuzeichnen-Byte bei +0x14; gezeichnet von `0xC0084430` | Haken an der Text-Routine `0xC003F7D0` bei x 50, y 0, Rückverfolgung zum Widget | gemessen, gelesen |
| Setter `0xC008463C` (Widget, Tempo in Zehnteln): erste Anweisung `str r1, [r0, #0x48]`, dann `b 0xC00845A4` (Text formatieren, Neuzeichnen markieren). Das Tempo-Signal ruft ihn als Member-Zeiger | Disassemblat HT/rot; blau `0xC0074C10` | gelesen |
| Der Zeiger auf die Statusleiste steht fest bei `0xC0691248` (blau `0xC056B528`), +0x24 ist das Tempo-Widget | Speicher nach dem Start auf allen drei Builds | gemessen |
| Das laufende Tempo steht in `HW_TEMPO` `0xC0691518` (blau `0xC056B780`) | schon in `auto.json` | gelesen |
| Das Tempo eines Patterns der Bank: Halbwort bei Block-Offset 34, Bank `0xC08B2940 + n << 14` | `pattern_switch.py:sg_head`, `pswitch_cases.py:SLOTS` | gelesen |

## Wie

- Haken `tempo_view` an der ersten Anweisung des Setters: solange `V_BPM` (`VIEW_W + 0x78`) ein Tempo hält, bekommt das Widget der
  Statusleiste das Tempo des angesehenen Patterns statt des übergebenen. Ein anderes Widget dieser Klasse und jeder andere Wert gehen
  unverändert durch. Bis zur ersten Verzweigung kein Literal (der Setter läuft schon beim Start, `V_BPM` ist dann `FF`).
- `tempo_update` läuft aus `pc_led` (UI-Task) bei jeder Änderung von Blättern oder Bestätigung: ändert sich das zu zeigende Tempo, ruft
  es den Setter mit dem laufenden Tempo, `tempo_view` setzt ein, was `V_BPM` sagt.
- Ändert sich das laufende Tempo während `VIEW:` (TAP, Regler), bleibt das angesehene sichtbar.
- Der Code liegt im Blink-Bereich, der dafür bis `0xC0178000` reicht (davor bis `0xC0177E00`); `FF` ab `0xC0177950` in allen drei Builds,
  dahinter die Reserve `RES_MFX` der Preset-Tabellen.

## Geprüft (`tools/emu/pswitch_cases.py`, `case_view_bpm`)

Pattern 1 spielt mit 120.0, Pattern 6 hat 132.5 in der Bank. Gelesen wird der Text, den die Firmware bei x 50, y 0 zeichnet.

| Fall | Erwartung |
|---|---|
| `view_bpm_shows_the_browsed_tempo` | `VIEW:006`: oben 132.5 |
| `view_bpm_gone_after_menu` | laufendes Tempo beim Ansehen auf 140.0 gestellt: oben bleibt 132.5; MENU: 140.0; nach dem Wechsel 132.5 |
| `view_bpm_gone_after_exit`, `_pad`, `_program_change`, `_stop` | oben wieder das laufende Tempo |
| `view_bpm_sync_group_shows_the_running_tempo` | gleiche Sync Group: 120.0 |
| `view_bpm_stopped_unsaved` | gestoppt mit ungespeicherten Änderungen, `VIEW:006`: 132.5 |
| `view_bpm_exit_held_is_stock`, `view_bpm_setting_off_is_stock` | 120.0 wie ohne Patch |

Ergebnis 20.11.: grün auf Hacktribe, rot und blau; mit dem Patch von develop schlagen die Fälle, die 132.5 erwarten, fehl.

## Am Gerät prüfen

- Pattern mit anderem Tempo ansehen: oben dessen BPM; MENU: sofort das laufende.
- EXIT, Pad, Program Change, STOP: das laufende.
- TAP während `VIEW:`: oben bleibt das angesehene, nach EXIT das neue laufende.
- Pattern derselben Sync Group: das laufende.
