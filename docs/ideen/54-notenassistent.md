# Idee 54: Notenassistent im KEYBOARD-Modus

Stand: gebaut und im Emulator geprüft, am Gerät nicht; Code-Patch. Zurück zu den [Ideen](../ideen.md).

Wer im KEYBOARD-Modus auf den Pads spielt, sieht nach einer Note, was dazu passt: gleich danach (im nächsten Takt des LED-Managers) leuchten die Pads der Noten, die zur gespielten in einem
konsonanten Abstand stehen (Prim und Oktave, kleine und große Terz, Quarte, Quinte, kleine und große Sexte), in einem schwachen Rosa, der blauen und der roten LED des Pads zusammen,
niedrig gedimmt, und gehen nach 1,5 s ohne neue Note wieder aus. Pads, deren Note nicht passt, bleiben dunkel. Jede neue Note ersetzt die Hinweise sofort. Das Licht der Firmware gewinnt: das gedrückte Pad, das Blau des gewählten Parts und
alles, was die Firmware selbst auf den Pads zeigt, bleibt, wie es ist; in den anderen Pad-Modi und außerhalb des Hauptbildschirms zeigt der Patch nichts.

## Stand

- Die Pads des KEYBOARD-Modus sind schon die Tonleiter des Patterns (die Firmware baut das Layout aus Tonart, Tonleiter und Oktave), also reicht die Abstandsregel, um "passt in die Tonart" und "klingt dazu" zusammen zu bekommen.
- Gebaut als Patch `data/patches/note-assistant.json` (812 Byte Code, drei Einhängestellen, Patch-Satz BLECH, beide Builds): [Messung](../messungen/2026-10-15-note-assistant.md) mit den Entscheidungen, der Helligkeit der Pad-LEDs
  und allen Prüfungen.
- Aus ist er mit EXIT beim Einschalten, ohne Karte und mit dem Wort `NA_SETTING` auf 0; die Menüseite NOTE ASSIST in der Liste des Menüs BLECH schaltet ihn (ON ist die Vorgabe, OFF steht als Bit 4 der Flags der Einstellungsdatei, [Patcher](../patcher.md), "Schalter, die das Menü ergänzen muss").
- Offen am Gerät: ob die Pad-LEDs Zwischenhelligkeiten zeigen und ob das Rosa so wirkt; die Schritte stehen in den [Gerätetests](../geraetetests/live.md), Punkt 5.
