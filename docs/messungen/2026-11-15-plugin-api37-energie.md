# Plugin API 37: Energiesparmodus und IDLE SAVE lesen, das Ereignis idle, die Schalter in Byte 7

Stand 15. November 2026. **Gemessen** im [Emulator](../glossary.md#emulator) mit [Hacktribe](../glossary.md#hacktribe) 2.02 (eigene Datei), Korgs Original 2.02 rot und blau, jeweils
mit dem BLECH-Satz (`data/patches/blech.json`, für blau `blech-synth.json`). Fälle: `tools/emu/plugin_api37_cases.py` (läuft
als Gruppe von `remote_cases`). **Am Gerät nicht geprüft.**

## Frage

Kann ein Plugin lesen, ob die Firmware gerade für ihren Energiesparmodus dimmt und in welcher Stufe IDLE SAVE steht, erfährt es
jede neue Stufe, und kann es LOAD METER, IDLE SAVE, GLIDE CHAIN und GLIDE SWITCH so schalten wie die Seiten im Menü BLECH?

## Lesen

- `korg.system.powerSave` (Blatt 61, Basis `state`, Wort 5) liest das Byte, das die Firmware beim Dimmen setzt
  (`BL_DIM_FLAG`, rot und Hacktribe `0xC00F9310`, blau `0xC00DF0CC` über `data/synth-map/script-runtime.json`), und gibt 1, wenn
  es nicht 0 ist. (eigener Code, `objects_state_own` in `tools/patch/script_objects.s`)
- `korg.system.idle` (Blatt 62, Basis `state`, Wort 6) liest die Stufe von IDLE POWER SAVE (`IS_STAGE` in
  `tools/patch/script_idle.s`). Vor `menu_arm` steht dort FF, das Blatt liest dann 0 und das Ereignis bleibt aus. (eigener Code)
- Das Ereignis `idle` (Nummer 28) entsteht wie `padMode` und `screen`: der Rahmenhaken vergleicht die Stufe mit der des vorigen
  Rahmens (`events_state` in `tools/patch/script_events.s`). Nur `idle_frame` schreibt die Stufe, also kommt jede Änderung, auch das
  Aufwachen durch eine Taste, MIDI oder `korg.system.keepAwake()`. (eigener Code, gemessen)

## Schalten

Byte 7 der Einstellungen (`MX_FLAGS2`) hat ein Bit je Seite. Die neue Basis `flags2` hat als Offset die Maske des Bits, 0x100
darüber heißt: gesetzt liest 0 (IDLE SAVE, gesetzt ist OFF). Schreiben setzt oder löscht nur dieses Bit, die übrigen, auch ein
reserviertes, bleiben. Wie bei den Seiten wirkt der Rahmen darauf (LOAD METER zeichnet oder nimmt die Ziffern weg, IDLE SAVE OFF
weckt), die Werte stehen im RAM bis WRITE. IDLE SAVE hat `apply: "keepAwake"`: jedes Schreiben startet die Zeit neu wie ein Dreh
am Rad, sonst würde ON nach langer Ruhe sofort dunkel.

| Blatt | Pfad | Maske |
|---|---|---|
| 63 | `korg.menu.blech.customizations.display.loadMeter` | 1 |
| 64 | `korg.menu.blech.customizations.powerSave.idleSave` | 2, umgedreht |
| 65 | `korg.menu.blech.features.glideChain` | 4 |
| 66 | `korg.menu.blech.features.glideSwitch` | 8 |

## Fälle

`tools/emu/plugin_api37_cases.py`, je Hacktribe, rot und blau, alle 10 Fälle grün (gemessen). Die Zeit wird im RAM vorgestellt
wie in `idle_save_cases.py`, nicht abgewartet.

| Fall | Ergebnis |
|---|---|
| `reads_at_start` | liest 0, 0, 0, 1, 0, 0, Byte 7 ist 0, kein Ereignis |
| `power_save_reads_the_firmware_dim` | mit dem Schalter der Firmware an liest es 1 (Byte 1), aus wieder 0 |
| `idle_reads_each_stage` | Stufe 1, 2, 3, 4 und wach: das Blatt liest jeweils dieselbe Zahl |
| `event_each_stage_and_wake` | Ereignisse 1, 2, 3, 4, 0 |
| `event_on_key_wake` | dunkel, eine Taste weckt: Stufe 0, Ereignis 0 |
| `idle_save_off_wakes` | dunkel, 0 geschrieben: wach, Ereignis 0, Byte 7 0x42 (reserviertes Bit 0x40 bleibt), 5 Minuten später weiter wach |
| `idle_save_on_starts_the_time` | 1 geschrieben nach 5 Minuten Ruhe: bleibt wach, Byte 7 0x40, 2 Minuten danach Stufe 1 |
| `load_meter_shows_at_once` | 1 geschrieben: Ziffern auf dem Hauptbildschirm, Byte 7 0x41; 0: Ziffern weg, 0x40 |
| `glide_bits` | GLIDE CHAIN und SWITCH nacheinander an und aus: 0x44, 0x4C, 0x48, 0x40 |
| `api36_loads_newer_refused` | ein Block mit API 36 lädt, derselbe als API 38 markiert gibt Fehler 19 (API_VERSION) |

Ganze Gruppe `remote_cases` mit API 37 (gemessen): Hacktribe 444 Prüfungen, rot 444, blau 438, keine rot. Daneben auf Hacktribe
`idle_save_cases.py` 25 von 25 und `load_meter_cases.py` 10 von 10 grün, die Seiten im Menü verhalten sich also wie vorher.

## Offen

- Am Gerät nicht geprüft, vor allem nicht, ob `korg.system.powerSave` auf Batterie mit dem Dimmen der Firmware kippt.
