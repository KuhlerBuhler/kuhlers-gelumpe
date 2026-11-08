# Plugin API 25: Tasten, Pads, Encoder und Touchpad wie ein Finger

Stand 8. November 2026. **Gemessen** im Emulator mit Hacktribe 2.02 (eigene Datei), Korgs Original 2.02 rot und blau, jeweils
mit dem BLECH-Satz. Fälle: `tools/emu/plugin_api25_cases.py` (läuft als Gruppe von `remote_cases`), dazu
`tools/patch/test_script_hooks.py` für die Glue-Funktionen. **Am Gerät nicht geprüft.**

## Frage

Bis API 23 konnte ein Plugin Tasten nur kurz drücken (`korg.pressKey`) und Regler setzen (`korg.knob`). Pads, Encoder, das
Touchpad, lange Drücke und SHIFT-Kombinationen fehlten. Lässt sich alles, was am Gerät mit Taste, Pad, Encoder oder Touchpad
geht, aus einem Plugin genauso auslösen? Und gleicht `korg.knob` dem echten Regler?

## Weg

Die neuen Aufrufe schreiben die Nachricht, die das Panel selbst schickt (5 Byte, [Panel](2026-10-08-panel-bedienung.md)), in
die Warteschlange des Panels, wie `korg.pressKey` seit API 15: Taste `00 nn 1|0`, Encoder `01 nn 00 dd`, Pad
`04 nn 00 vv 1|0`, Touchpad Taste 0x22 und `05 xh xl yh yl`. Das letzte Byte trägt die Markierung 0xB7, mit der der
Eingangsfilter die Nachricht ohne Umbelegung, Halt, App oder Ereignis an die Firmware gibt.

Jeder Fall läuft als Zwillingsprobe: zwei Welten, gleich gebootet, mit demselben Plugin. In der einen schickt das Panel die
Nachrichten (`Machine.send`), in der anderen macht das Plugin die Aufrufe, ausgelöst über ein Kommandobyte in einem
gespeicherten Pattern. Nach jedem Schritt müssen beide gleich sein in: Pattern-Objekt (0x4274 Byte), Bildschirm, LEDs,
Pad-Modus (LED-Manager +0xB58), gewähltem Part, Stummschaltung aller Parts, Transport und dem MIDI am Ausgang. Am Ende
laufen beide 2 s weiter und werden noch einmal verglichen.

## Ergebnisse

| Befund | Marker |
|---|---|
| Pad in TRIGGER, SEQUENCER, KEYBOARD und CHORD (Pad 4 mit 100, Pad 10 mit 40, je gedrückt und losgelassen): alles gleich wie mit dem Panel. TRIGGER wählt den Part und spielt, SEQUENCER schaltet den Step im Pattern, KEYBOARD und CHORD schicken Noten | gemessen |
| PART MUTE mit `korg.keyDown` gehalten: Pad-Modus 0 solange gehalten, das Pad schaltet die Stummschaltung des Parts, gleich wie mit dem Panel | gemessen |
| Encoder 0 bis 4, je +1, -2, +1: gleich wie mit dem Panel. SHIFT mit `korg.keyDown` gehalten und Encoder 0 oder 2 gedreht: gleich | gemessen |
| Touchpad in Master FX und Touch Scale (Finger bei 400/500, bewegt nach 600/300, abgehoben): gleich, auch das X, das die Firmware daraus macht (Haken aus `plugin_api15_cases.py`: 50 und 74) | gemessen |
| SHIFT gehalten, TOUCH SCALE gedrückt und losgelassen, SHIFT losgelassen: gleich wie mit dem Panel | gemessen |
| PLAY und STOP mit `korg.keyDown` und `korg.keyUp`: Transport und MIDI (Start, Note) gleich | gemessen |
| EXIT mit `korg.keyDown`/`korg.keyUp` und mit `korg.pressKey` verlässt MENU gleich wie die Taste | gemessen |
| `korg.knob(i, v)` gegen den Regler `02 i 00 v` für LEVEL, RESONANCE und ATTACK mit 77 und 200: Pattern, Bildschirm, LEDs und MIDI-CC gleich | gemessen |
| Das Plugin bekommt seine eigenen Tasten, Pads und Finger nicht als `buttonPress`, `pad` oder `touch` | gemessen |
| `korg.padHold(1)`: ein Pad des Panels ändert nichts an der Firmware und kommt zweimal (an, aus) als `pad` beim Plugin an; `korg.padDown` des Plugins geht trotzdem durch und wirkt wie das Pad des Panels ohne Halt | gemessen |
| Das Plugin hält SHIFT und endet mit einem Fehler: am Ende des Frames geht `00 0a 00` mit Markierung an die Firmware, der Merker ist leer | gemessen |
| Die Nachricht des Plugins kommt einen Frame nach der des Panels an: im MIDI steht ein Clock-Byte (0xF8) mehr davor, eine LED, die nach dem Drehen verlischt, ist eine Stufe heller, ein blinkender Text oder eine blinkende LED blinkt um diesen Frame versetzt (auf blau nach SHIFT und CUTOFF so gesehen: beide blinken mit rund 0,55 s, eine Probe von 50 ms auseinander). Darum vergleicht der Fall zwischen den Schritten die Helligkeit der Encoder-LEDs nur als an oder aus, jedes Feld muss innerhalb von 0,6 s einmal gleich sein, und die Clock-Bytes fallen weg; nach dem Auslaufen gilt dasselbe ohne die Ausnahme für die Encoder-LEDs | gemessen |
| Ein zweites Drücken derselben Taste oder desselben Pads sendet nichts, ein Loslassen ohne Drücken auch nicht; eine volle Warteschlange verwirft die Nachricht und das Drücken zählt nicht; Encoder mit 0 sendet nichts | gemessen (Unittest) |
| Die Nachrichten der Plugins merkt sich die Fernbedienung nicht (`rm_post_quiet`), sie lässt sie also nicht nach 10 s Ruhe los. Das Loslassen übernimmt die Laufzeit, wenn das Plugin aufhört | offline gelesen |

## Entscheidungen

- **`korg.padHold`:** der Halt gilt den Pads des Panels. Ein Pad des Plugins ist markiert, geht am Halt vorbei und ist kein
  `pad` für Plugins. So spielt ein Plugin, das die Pads abfängt, seine eigenen Anschläge, ohne sich selbst wieder zu hören.
- **EXIT:** erlaubt in `korg.keyDown` und `korg.pressKey`. Ist eine App offen, schließt die Laufzeit sie zuerst
  (`script_app_close`, wie der Eingangsfilter bei der echten Taste), dann bekommt die Firmware EXIT. Die Laufzeit läuft
  danach weiter. `korg.keyHold`, `korg.keyMask` und `korg.remapKey` lehnen EXIT weiter ab, damit eine App immer schließbar
  bleibt.
- **Tastenkürzel von BLECH** (EXIT-Kombinationen, KEY PADS über langes KEYBOARD) sitzen im Eingangsfilter und sehen die
  markierten Nachrichten nicht.
- **Besitzer:** es gilt das Plugin, das zuletzt etwas gedrückt hat; hört es auf, lässt die Laufzeit alles los.

## Offen

- **Am Gerät**: keine Zeile.
- **EXIT bei offener App** im Emulator: nur im Unittest (die Glue-Funktion ruft `script_app_close`), nicht als Zwillingsprobe.
- **Lange Drücke mit eigener Zeitschwelle** außer PART MUTE (etwa KEYBOARD für KEY PADS) gehen am Eingangsfilter vorbei und
  sind damit nicht die Kürzel von BLECH, sondern nur, was die Firmware selbst daraus macht.
