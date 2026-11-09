# Osterei auf der Seite VERSION

Stand 2026-11-09. Emulator (`tools/emu`, Unicorn) mit Hacktribe 2.02, Korgs roter und Korgs blauer 2.02, jeweils mit dem
Satz BLECH (`blech.json`, blau `blech-synth.json`), Karte im Speicher. **Am Gerät nichts geprüft.** Markierungen: **gemessen**,
**offline** (Code gelesen), **hergeleitet**, **offen**. Für 1.5, der PR bleibt Entwurf.

Code: `tools/patch/script_egg.s`, Einstiege in `script_menu.s` (MENU, EXIT, Seitentexte), `script_hooks.s` (Frame),
`script_display.s` (Bild), `script_hw.s` (LED-Halt). Tests: `tools/emu/egg_cases.py`, als Teil von `menu_cases`.

## Was passiert

- BLECH, Liste, Zeile VERSION, fünfmal MENU hintereinander: die Show startet. Viermal tut nichts. Jede andere Taste dazwischen
  (EDIT, eine andere Zeile) zählt von vorn, MENU auf einer anderen Zeile zählt nicht.
- Alle LEDs der Tasten, Encoder und Pads blinken: 250 ms an, 250 ms aus. Pads und die Tasten mit zwei LEDs (PLAY, die Takte 1
  bis 4) wechseln bei jedem An die Farbe: rot, blau, lila (beide), rot, ... Die unteren RGB-LEDs bleiben, wie sie sind.
- Das Display-Licht läuft durch das Farbrad: ein Schritt von 96 alle 40 ms, eine Runde in 3,84 s, volle Sättigung und
  Helligkeit, über den Weg, den die Seiten DISPLAY nehmen (`look_hsv_rgb`, `menu_look_apply`).
- Der Bildschirm zeigt im Sekundenwechsel AUTISM groß und das Startbild (Bild 13, also Blechys Augen oder das eigene Bild des
  Startbild-Editors).
- EXIT: zurück auf VERSION, Licht und LEDs wie vorher. Beim ersten Mal steht zuerst zwei Sekunden NEW SAMPLE / Unlocked im
  Seitentext, dann wieder VERSION. Spätere Male kommt die Meldung nicht.
- Wechselt die Firmware selbst den Bildschirm (eine ihrer Tasten), endet die Show wie mit EXIT, ohne Meldung.

## Lichtgrenze (Fotosensibilität)

- **Hergeleitet:** 2 Blitze pro Sekunde (250 ms an, 250 ms aus). Die Grenze für Lichtblitze ist höchstens 3 pro Sekunde
  (WCAG 2.3.1, Three Flashes). Das Display-Licht blitzt nicht, es wechselt nur langsam den Farbton bei voller Helligkeit.
- **Gemessen:** REC blinkt im Emulator mit 2,0 pro Sekunde (Fall `egg_leds_blink_at_most_3_a_second`, 4 s in 50-ms-Schritten).
- **Offen:** Die LEDs gehen über die Warteschlange der Laufzeit, 16 Pakete pro Frame. 76 LEDs brauchen also 5 Frames pro Wechsel.
  Am Gerät ansehen, ob die Welle über das Panel stört.

## Wo die Freischaltung liegt

Wunsch: im internen Flash, nicht in der Einstellungsdatei auf der Karte.

- **Offline:** Im Globals-Block bei `0x230000` (256 Byte, Marke `GLED` bei `+0xFC`). Die Firmware speichert ihn selbst über
  `0xC004C1B4`: ein Löschen und 16 Seiten des 4-KiB-Sektors, beim Ausschalten (`0xC0038B4C`), bei WRITE auf Global, bei SysEx
  `0x51` und bei Import All Pattern ([Globals](2026-10-13-globals-zurueckgesetzt.md)). Laden prüft nur `GLED`.
- **Offline:** BLECH schreibt selbst nichts in den Flash. Es setzt nur das Byte im RAM-Objekt hinter `*0xC0691324`, Byte 251
  (im Flash Byte 247, `0x2300F7`), Wert `0x5A` heißt frei. Gleicher Weg wie Init-Pattern (247), letztes Pattern (248, 249) und
  Startlicht (250). Kein zusätzliches Löschen, kein zusätzlicher Schreibvorgang, keine Abnutzung über das hinaus, was die
  Firmware sowieso tut.
- **Gemessen:** Die Bytes 44 bis 251 ändert kein Menü der Firmware, die Vorgabe ist 0
  ([Global-Felder](2026-10-14-global-felder.md)).
- **Gemessen:** SOFTWARE UPDATE schreibt nur `0x020000` bis `0x220000`, die Globals bleiben gleich
  ([Globals](2026-10-13-globals-zurueckgesetzt.md)). Die Freischaltung überlebt also ein Update.
- **Gemessen:** Nach der Show und dem Ausschalten steht im Flash `0x2300F7 = 0x5A`, nach dem Neustart ist Byte 251 wieder
  `0x5A`, auf allen drei Builds (Fälle `egg_unlock_kept_in_the_flash`, `egg_unlock_survives_a_restart`).
- **Hergeleitet, Grenzen:** Die Freischaltung landet erst beim Ausschalten oder bei WRITE auf Global im Flash. Strom weg
  ohne Ausschalten verliert sie. Import All Pattern, SysEx `0x51` und FACTORY RESET schreiben den ganzen Block neu, danach
  ist sie weg (gleich wie beim Init-Pattern).
- **Gemessen:** Blau hat dieselbe Lage (für Byte 250 gemessen, [Startlicht](2026-10-29-hintergrundlicht-beim-start.md)), der
  Fall läuft dort gleich.

## Speicher

- **Offline:** Der Menüzustand (`MENU_STATE`, 0x200 Byte) ist voll: `0x1C4` bis `0x1F7` belegt FILTER TOGGLE, `0x1F8` bis
  `0x1FF` belegt seit #414 AUTO SAVE (`M_SNAP`, `M_AS`). Das Osterei liegt deshalb ganz in `EGG_WORK`, den letzten 20 Byte der
  Reserve von MORE2 hinter `SIM_INPUT` (bis `MORE2_END`): Zustand, Zähler, Bild, erstes Mal, Farbton, Licht vorher, dann
  Startzeit, Blinkschritt und Bildschirmobjekt. `menu_arm` setzt sie auf 0. Vorher stehen dort FF, das zählt als aus (die
  Show läuft nur bei 1, die Meldung nur bei 2).

## AUTO SAVE

- **Offline:** AUTO SAVE schreibt beim Verlassen von GLOBAL PARAMETERS den ganzen Global-Block, wenn ein Byte vom gespeicherten
  Stand abweicht. Byte 251 gehört dazu. Ist das Ei schon freigeschaltet, landet die 0x5A dadurch früher im Flash als erst beim
  Ausschalten. Zurück auf 0 setzt AUTO SAVE das Byte nie, es schreibt nur den Stand aus dem RAM. Das Ei selbst schreibt
  weiterhin nichts.
- **Offline:** Beim Verlassen des BLECH-Bildschirms vergleicht AUTO SAVE die CRC der Einstellungen, dazu gehört die Farbe des
  Displaylichts. Läuft die Show noch (ein Schalter der Firmware wechselt den Bildschirm), beendet `autosave_leave` sie vorher
  und gibt die alte Farbe zurück. Die Farbe der Show landet so nie in der Einstellungsdatei.
- **Gemessen:** Fall `egg_auto_save_keeps_the_show_out` auf Hacktribe, Rot und Blau: Show läuft (Licht z. B. `(3, 15, 0)`),
  die Firmware wechselt auf Bildschirm 8, danach ist die Show aus, das Licht wieder wie vorher, die Karte unverändert und der
  Flash ohne Löschvorgang. Ohne das Beenden in `autosave_leave` hätte die abweichende Farbe die CRC geändert (hergeleitet,
  nicht gegengemessen).

## Startzeit

- **Gemessen:** `check.py --quick` auf allen drei Builds, siehe PR. Die Show hängt nur am Frame-Haken, der bei
  M_EGG = 0 nach fünf Befehlen zurückkehrt. Am Start ändert sich nichts.

## Sample 500 (offen, nicht gebaut)

Ziel: nach der Freischaltung liegt auf Platz 500 (Index 499) ein Sample BLECH, auf Rot, Hacktribe und Blau.

- **Gemessen:** Die eigenen Samples beginnen bei Index 500 (Anzeige 501), `src/sample-file.mjs` `FIRST_USER = 500`,
  `tools/emu/sampleset.py`. Index 499 heißt nach dem Start `Sample500`, Import-Nummer 549, Metadaten-Index 499, nicht
  geladen, auf Rot (mit ht-osc) und auf Hacktribe. ht-osc belegt 421 bis 496, 497 bis 499 bleiben leer (Fall
  `datei-497-bis-499-leer`).
- **Offline:** Der Import eines Samples ist `0xC004EDF0(rec)`: `rec+0` Platz, `rec+2` der 32-Byte-Namenseintrag, `rec+0x22`,
  `rec+0x24`, Start/Loop/Ende bei `+0x28`/`+0x2C`/`+0x30`, One-Shot `+0x34`, danach `0x45C` Byte Metadaten ab `+0x38`
  (Länge bei `+0x3C`). Die Funktion holt den DSP-Speicher vom Zeiger `0xC00F9C80`, prüft vorher den freien Platz
  (`0xC004E218`), und lehnt ab, wenn der Platz schon geladen ist (`+0x0B` der Metadaten). Das PCM schreibt der Aufrufer
  danach über `0xC004EF28` in den DSP.
- **Offline:** Die Stimme fragt den Platz über `0xC0099788` ab, die Plätze 421 bis 499 geben dort nichts. Auf Rot hebt ht-osc
  die Grenze auf 496 (`ho_voice`), für 499 muss die Zahl dort auf 499. Hacktribe braucht an seiner Stelle einen eigenen Haken.
- **Hergeleitet:** Ein Placeholder von 1 s, 16 kHz, 16 Bit mono sind 32 KB. Platz dafür: MORE3 (gleich auf allen drei Builds).
  Austausch der Aufnahme wäre dann eine Datei (`data/egg/blech.wav` o. ä.), die der Build einliest.
- **Offen, deshalb nicht gebaut:**
  - Das Firmware-Export `0xC004EBD4` lässt nur DSP-Oszillatoren aus. Ein geladenes Sample auf 499 käme beim nächsten
    Speichern der Samples in die `e2sSample.all` des Nutzers. Das widerspricht "Samples des Nutzers nicht anfassen"; der
    Export müsste 499 auslassen.
  - Der DSP im Emulator ist ein Stummel: ob es klingt, lässt sich nur am Gerät prüfen.
  - Das Sample nimmt DSP-Speicher hinter den eigenen Samples. Ist der voll, lehnt der Import ab (gewollt, aber zu testen).
- **Blau:** keine Nutzer-Samples. Möglich wäre es über einen der elf doppelten Einträge der Oszillatorliste (409 Einträge
  zu 32 Byte bei `0xC00BEB48`, PCM ab Wellen-Nummer `0x32`), das PCM mit dem DSP-Schreiber `0xC00105A4` hinter das Ende der
  Bank, dazu die Tabellen MSVS/MSPR/MSRL/SMPR ([Synth-Samples](2026-10-15-synth-samples.md)). Nur die ARM-Seite ist im
  Emulator gezeigt (`synth_probe.py`). Offen und nur am Gerät prüfbar: ob der DSP von dort spielt, wo sein Speicher endet,
  welche Tonhöhe. PR #400 lädt nur FX-Records, kein PCM.

## Fälle

`tools/emu/egg_cases.py --patched X.VSB`, in `check.py` als Teil von `menu_cases`:

| Fall | Prüft |
|---|---|
| `egg_four_presses_do_nothing` | viermal MENU: keine Show, Texte gleich, Byte 251 gleich |
| `egg_count_starts_again_after_another_key` | 4x, EDIT weg und zurück, 1x: keine Show |
| `egg_five_presses_start_and_unlock` | fünfmal MENU: Show, Byte 251 = `0x5A`, Seite bleibt VERSION |
| `egg_leds_blink_at_most_3_a_second` | REC 0 und 255, höchstens 3 An pro Sekunde |
| `egg_pads_red_blue_purple` | Pad 1: rot, blau, lila, ... |
| `egg_display_light_walks_the_wheel` | mindestens 20 Farben in 4 s, immer volle Helligkeit |
| `egg_word_and_start_image_by_turns` | zwei Bilder im Sekundenwechsel |
| `egg_exit_first_time_new_sample_message` | EXIT: NEW SAMPLE / Unlocked, nach 2,2 s wieder VERSION |
| `egg_exit_gives_the_light_back` | danach steht alles still |
| `egg_later_shows_skip_the_message` | zweites Mal ohne Meldung |
| `egg_unlock_kept_in_the_flash` | `0x2300F7 = 0x5A` nach dem Ausschalten |
| `egg_unlock_survives_a_restart` | Byte 251 nach Neustart, Show ohne Meldung |
| `egg_auto_save_keeps_the_show_out` | Bildschirmwechsel der Firmware während der Show: Show aus, Licht wie vorher, Karte unverändert, kein Löschen im Flash |

Ergebnisse je Build: siehe PR.
