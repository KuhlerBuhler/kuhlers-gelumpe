# Menü-Anordnung 1.3.8: SYNC GROUP, GLOBAL PARAMETERS, DATA UTILITY (29.10.)

Wunsch vom 29.10.: SYNC GROUP hinter CHAIN REPEAT (16), PLUGIN RUNTIME in GLOBAL PARAMETERS, EXPORT ALL PLUGINS und
SET INIT PATTERN in DATA UTILITY, BLECH als vorletzte (31) und Blechy als letzte Seite (32) des Rings, unter PLUGINS die
Liste MANAGE PLUGINS. Gebaut und im Emulator geprüft (Hacktribe, rot, blau), am Gerät nicht.

## Die Stellen (gelesen in beiden Firmwares, im Emulator gespielt)

| Stelle (rot und Hacktribe) | blau | Was dort steht |
|---|---|---|
| `0xC0067720` | `0xC005D900` | Pattern Menü, EDIT rechts auf der letzten Seite (Index 14): `mov r0, #7`, dann der Wechsel ins Part Menü |
| `0xC0065B8C` | `0xC005BE04` | Part Menü, EDIT links auf der ersten Seite: setzt die Seite des Pattern Menüs auf 14, `mov r0, #3`, Wechsel |
| `0xC0064C20`, `0xC0064C28` | `0xC005B0BC`, `0xC005B0C4` | Slots 4 und 5 von Bildschirm 9 (GLOBAL PARAMETERS): `mvn r1, #0` bzw. `mov r1, #1`, dann der Schritt `0xC0064BD4` mit Umbruch bei 20 |
| `0xC00623C0`, `0xC0062448` | `0xC0058B78`, `0xC0058BF8` | Slots 4 und 5 von Bildschirm 15 (Funktionsliste von DATA UTILITY): `push {r4, lr}`, Frage `0xC00623A8`, Funktion in `+0x20`, Umbruch bei 13 (blau 10); Byte `+0x25` ist 0 in der verkürzten Liste |
| `0xC0691228` | `0xC056B508` | die Funktion, auf der Bildschirm 15 öffnet (sein Konstruktor lädt sie nach `+0x20`) |
| `0xC0691260`, `0xC007D3C0` | `0xC056B540`, `0xC006FCF4` | Seitenobjekt des Pattern Menüs und sein Setzer; nach dem Start vorhanden (im Emulator gelesen: gleich dem Objekt, das das Part Menü setzt) |
| `0xC03487E4`, `0xC007BFD0` | `0xC03484F8`, `0xC006E954` | Seitenobjekt des Part Menüs (erst beim ersten Gebrauch gebaut) und sein Setzer |

Die Seitenzähler bekommen ihre Summen nur als Immediate: 20 nur von GLOBAL PARAMETERS und seinen Fenstern, 14 (blau 11) nur von
DATA UTILITY und den Fenstern seiner Funktionen (alle Aufrufer von `0xC008A83C` und `0xC008A8A8` gelesen, beide Firmwares).
Das Part Menü zählt mit `Seite + 15`, also beginnt es mit SYNC GROUP bei 17.

## Gemessen (Emulator, `tools/emu/menu_cases.py`)

- Ring: CHAIN REPEAT 15/32, SYNC GROUP 16/32, erste Part-Seite 17/32 und zurück; Event 30/32, BLECH 31/32, Blechy 32/32, dann
  die erste Pattern-Seite; blau 16/31, 30/31, 31/31.
- GLOBAL PARAMETERS: erste Seite EDIT links auf PLUGIN RUNTIME (21/21), EDIT rechts wieder 1/21, letzte Seite (20/21) EDIT
  rechts auf PLUGIN RUNTIME, WRITE öffnet kein Fenster, EXIT auf Bildschirm 8.
- DATA UTILITY: erste Funktion EDIT links auf SET INIT PATTERN (18/18, blau 14/14), weiter EXPORT ALL EFFECTS (nur rot),
  EXPORT ALL PLUGINS, EXPORT ALL CUSTOM, dann SOFTWARE UPDATE (14/18), EXIT auf Bildschirm 14. Das Schild "Data Util" ist Pixel für Pixel das der Firmware.
- Mit EXIT beim Einschalten: Part links geht auf CHAIN REPEAT (15/29), Global und Data Util blättern im Kreis wie im Original.
- EXPORT ALL CUSTOMIZATIONS (`menu_cases.custom_export_cases`): `e2sCustom.all` ist der Einstellungssatz ohne Prüfsummen
  (CRC stimmt, die Einstellungsdateien bleiben); als `settings.a.bin` auf eine andere Karte gelegt, kommt die Anpassung zurück.
- EXPORT ALL EFFECTS (`fx_card_cases.case_export`, `test/emulator-fxcard.test.mjs`): ein im RAM geänderter Datensatz steht danach
  in der Datei, jeder Text bleibt, ein Eintrag ohne Text bleibt unverändert, die Prüfsumme stimmt; der nächste Start lädt sie,
  und `parseCollection` des Editors liest dieselben Einträge mit ihren Texten. Ohne geladene Datei und mit einer seit dem Start
  anderen Datei wird nichts geschrieben.
- Alle Menüfälle grün auf Hacktribe, rot und blau.
