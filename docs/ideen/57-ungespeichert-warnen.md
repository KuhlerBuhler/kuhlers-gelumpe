# 57. Ungespeicherte Änderungen: vor dem Patternwechsel fragen

Wunsch vom 18.10.: Ist das Pattern bearbeitet und nicht gespeichert, und spielt es gerade nicht, soll ein Wechsel nicht
sofort passieren. Das Gerät fragt "Ungespeicherte Änderungen verwerfen?": MENU/ENTER wechselt, EXIT bleibt.

## Was wir wissen

| Aussage | Status |
|---|---|
| "Ungespeichert" lässt sich erkennen: das Pattern im Arbeitsspeicher (Zeiger `0xC033E6A4`, ab `+4`, 0x4000 Byte) gleicht nach dem Start seinem Platz in der Pattern-Bank im RAM (`0xC08B2940 + Nummer * 0x4000`); ein Reglerdreh ändert ein Byte (`+2072`), nach einem vollständigen WRITE sind beide wieder gleich | gemessen im Emulator (eigene Hacktribe-Datei, Flash-Abbild 09.10.) |
| Der Patch Patternwechsel hängt schon an Rad, Pad-Auswahl, MIDI Program Change, MENU, EXIT und der unteren Zeile des Hauptbildschirms | gebaut (`tools/patch/pattern_switch.py`) |
| Die Firmware hat eigene Bestätigungstexte und -seiten: "Are You Sure ?", "Stop Sequencer. OK?", " Cancel Rec? Press [Enter]", "Canceled" (gesetzt über `0xC008CB10` in Bildschirm-Widgets, z. B. `0xC0062504`) | gelesen |

## Wege

| Weg | Aufwand |
|---|---|
| **In der unteren Zeile wie PATTERN CONFIRM:** gestoppt und ungespeichert blättert das Rad nur, die Zeile zeigt z. B. `DISCARD?` mit der Nummer, MENU lädt, EXIT bleibt; Pad-Auswahl und MIDI ebenso | mittel, ein Arbeitsblock: dieselben Haken, ein zweiter Zustand |
| **Eigene Seite** wie die Bestätigungen der Firmware, ganzer Bildschirm mit Text | größer: Seiten- und Fenstermechanik der Firmware erst messen |

Offen: ob Pad-Auswahl und MIDI Program Change auch fragen sollen (Vorschlag: ja, Pad ja, MIDI nein, weil ein Rechner
das Gerät fernsteuert), und der Text (die Oberfläche ist englisch).

## Sync Group

Gestoppt und ungespeichert lädt das Rad ein Pattern derselben Sync Group sofort, ohne VIEW: und ohne MENU; ein Pattern, das nur durch den Abgleich der Gruppe hereinkam, gilt nicht als ungespeichert ([Messung](../messungen/2026-10-25-sync-ungespeichert.md)). Gebaut und im Emulator geprüft, am Gerät offen.
