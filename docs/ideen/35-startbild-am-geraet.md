# Idee 35: Startbild am Gerät zeichnen

Stand: im Emulator gebaut und geprüft, am Gerät nicht; gespeichert wird auf der Karte. Zurück zu den [Ideen](../ideen.md).

Ein neuer Menüpunkt in Global Settings zeigt das Startbild und lässt es zeichnen.

## Bedienung

- Global, Seite 20 SPLASH SCREEN (nach XY CALIBRATION).
- MENU (am Gerät als ENTER beschriftet) öffnet den Editor mit dem aktuellen Startbild, Pixel (0, 0) blinkt.
- Das Rad, das auch die Patterns wechselt, bewegt den Cursor nach links oder rechts; am Zeilenende geht es in die nächste Zeile.
- MENU kehrt den Pixel unter dem Cursor um, WRITE speichert (auf die Karte), EXIT verlässt den Editor. Presets sind für später gedacht.

## Entscheidungen zum Start

Das Startbild wird vor allen Rettungswegen gezeichnet ([Startphase](../messungen/2026-10-10-startphase.md)). Ein gespeichertes Bild beim Start zu laden wäre Code vor den Rettungswegen (Regel 1 in [Patcher](../patcher.md)). Entschieden:

- Bis nach den Rettungswegen wird gar kein Startbild gezeichnet (der Aufruf `0xC002AC38` fällt weg). Das Display bleibt dabei hell, weil die Firmware das Licht vorher und unabhängig davon einschaltet.
- Danach zeichnet unser Code einmal das gespeicherte Bild oder das der VSB, und zwar hinter der Frage der Firmware nach der `e2sSample.all`, die die Karte mountet (etwa 20 bis 30 ms später als zuvor); mit EXIT beim Einschalten und im Panel-Update gleich das Bild der VSB.
- Beim Laden gilt ein Rückfall auf das Bild der VSB bei leerer, kaputter, halb geschriebener oder zu langer Datei und ohne Karte. Jeder dieser Fälle ist eine Pflichtprüfung.
- Notschalter: EXIT beim Einschalten.

## Stand

Gebaut als Patch `data/patches/splash-editor.json` (Bericht: [Startbild-Editor](../messungen/2026-10-10-startbild-editor.md)). Gespeichert wird seit dem 15.10. nicht mehr im Flash (Sektor `0x7F0000`), sondern auf der Karte in zwei Dateien im Wechsel, `KORG/blechtribe/splash.a.bin` und `splash.b.bin`, jede ein Satz mit Kennung, Version, Generation, Bild und Prüfsumme; beim Start gilt die gültige Datei mit der höchsten Generation, WRITE schreibt in die andere ([Messung](../messungen/2026-10-15-startbild-karte.md)). Alle Pflichtfälle bestanden, im Flash wird nichts mehr geschrieben. Am Gerät ist nur der Notschalter gemessen. Entwurf, Adressen und Herleitung des Editors: [Startbild-Editor, Hintergrund](../hintergrund/startbild-editor.md).
