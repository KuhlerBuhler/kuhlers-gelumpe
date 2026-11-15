# Kartentausch: Hänger, SAVE TO FLASH und Knopf-LEDs (15.11.)

Rote Electribe, Test-VSB 599f7486 (release/1.4.6), Geräteliste `2026-11-14-geraetetest-1.4.6` Punkte 2.5, 2.6, 3.2, 5.2.

## 1. Hänger beim Stecken einer anderen Karte

- **Gemessen am Gerät:** andere Karte gesteckt, das Gerät steht. Ziehen beendet den Hänger, erneutes Stecken hängt wieder.
  Kurz danach ging dieselbe Karte und fragte SAVE TO FLASH?. Der Hänger kam beim ersten Tausch nach dem Einschalten,
  der zweite Versuch ohne Neustart ging. Dasselbe Muster wie beim ersten Stecken nach einem Start ohne Karte.
- **Hergeleitet, offen:** Korg prüft die Antwort auf CMD8 nicht (`0xC001AE50`, das Ergebnis wird überschrieben) und
  setzt in ACMD41 immer HCS (`0xC001BE48`). Eine SDHC-Karte, die CMD8 nicht bekommen hat, bleibt bei HCS laut SD-Spec
  dauerhaft busy. Warum gerade der erste Init nach dem Einschalten das trifft, ist am Gerät nicht gemessen.
- **Hergeleitet:** derselbe Weg wie bei der [Init-Sperre](2026-11-14-karte-init-sperre.md). Meldet die Karte nach ACMD41
  "busy", dreht Korgs Schleife bei `0xC001AE80` bis zu 50000 Runden im UI-Task (Grenze `0xC34F` bei `0xC001AE98`).
- **Gemessen im Emulator** (Karte, die nie bereit wird, `hold.py`): ohne Fix 6 s Hänger je Init, zwei Inits, Sperre
  (`CARD_STUCK`) nach 14,6 s. Mit Fix 2,1 s je Init, Sperre nach 6,7 s.
- **Fix:** `acmd41_round_hook` ersetzt den Aufruf `bl 0xC001CAE8` bei `0xC001AEB4` (blau `0xC00167DC`). In Runde 1 merkt
  er sich den Tick, ab 2 s nach der ersten Runde springt er in Korgs eigenen Abbruchweg (`0xC001AEA4`, -13 und Sperre).
  Nur aktiv, wenn das Menü läuft (`M_ON`). Danach liest der Kartenwächter die Karte nach `CARD_RETRY_MS` (2 s) noch
  einmal mit neuem Init, so wie am Gerät der zweite Versuch ging. Bleibt auch der busy, steht `CARD_STUCK` bis zum Ziehen.
- **Test:** `menu:card_later_busy_card_holds_the_ui_briefly` (Halt bis zur Sperre höchstens 2,5 s, danach liest der
  zweite Init die Karte).

## 2. Nach SAVE TO FLASH zurück auf die alte Karte

- **Gemessen am Gerät (READ, Flash 0x7FD000/0x7FE000):** Satz B gen 4 und Satz A gen 5, beide gelb (Karte A). Blau
  (Karte B) stand nie im Flash, obwohl MENU gedrückt wurde. Flash-Schreiben an sich geht (gen 4 und 5 gültig).
- **Offen:** warum genau nicht geschrieben wurde. Möglich: `FLASH_WRITE` lieferte 0, das Schreiben ging still verloren,
  oder MENU kam nicht an. Im Emulator lässt sich der Fall ohne Störung nicht nachstellen.
- **Fix:** `menu_flash_save` liest den Satz nach dem Schreiben zurück und vergleicht ihn. Klappt das nicht, bleibt
  `FL_SAVE` gesetzt und `menu_ask_frame` versucht es nach `CARD_RETRY_MS` erneut. Wird die Karte gezogen, solange das
  Speichern noch offen ist, bleiben die laufenden Einstellungen (keine Rückkehr zum alten Flash-Stand).
- **Tests:** `menu:flash_settings_menu_write_lost_is_tried_again` (Seiten gehen verloren) und
  `menu:flash_settings_menu_write_failed_is_tried_again` (`FLASH_WRITE` meldet 0). Danach Ziehen: blau bleibt,
  Neustart ohne Karte: blau.

## 3. KNOB LEDS OFF wird beim Tausch nicht übernommen

- **Hergeleitet:** `menu_settings_load` setzte die Knopf-LEDs mit "später senden" (`S_PEND`), das wartet auf den
  Hauptscreen. Nach dem Ziehen kam der Flash-Stand zurück, und der hatte die Knopf-LEDs an (passt zu Punkt 2).
- **Fix:** beim Laden nach einem Tausch oder Ziehen (`CARD_DONE`, `CARD_PULL`) gehen die Knopf-LEDs sofort raus.
- **Test:** `menu:card_later_swap_knob_leds_at_once` (Tausch im Menü, nach 1 s sind die Knopf-LEDs aus).

## Bleibt so

Dieselbe Karte ziehen und wieder stecken fragt erneut SAVE TO FLASH?.
