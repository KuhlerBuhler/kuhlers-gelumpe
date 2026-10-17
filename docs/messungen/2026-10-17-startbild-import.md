# Startbild: Rad im Editor, Bild von der Karte

Stand 2026-10-17. Alles im Emulator (`tools/emu/splash_cases.py run`), eigene `SYSTEM.VSB` mit Hacktribe, mit dem Startbild-Patch allein
und mit dem ganzen BLECH-Satz. Am Gerät ist nichts geprüft. Markierungen: **gemessen**, **hergeleitet**, **offen**.

## Das Rad im Editor

Gemeldet vom Gerät: im Editor (Global, Seite SPLASH SCREEN, MENU) verschwindet das Bild, sobald man am Rad dreht, die Menüseite steht
wieder da, nur der Cursor bewegt sich.

- **Gemessen:** im Emulator genauso. Nach VALUE setzt die Firmware das Flag "alles neu zeichnen" am Bildschirm-Manager (`+0x5C`,
  geschrieben bei `0xC006F00C`, gelöscht im nächsten Takt bei `0xC006F1B8`). Der Takt malt dann die Widgets der Seite neu, also Titel
  und "press [Enter]".
- **Behebung:** nach einer Cursorbewegung zeichnet das Widget des Editors im nächsten Takt das Bild neu. Es hängt als letztes im
  Widget-Vektor, malt also nach der Seite.
- **Gemessen:** neue Prüfung "the image stays on the display after VALUE": mit dem alten Patch weichen 941 von 1024 Byte ab, mit dem
  neuen nur das Byte unter dem Cursor.

Bedienung im Editor: Rad bewegt den Cursor (zeilenweise, am Zeilenende in die nächste Zeile), MENU kippt das Pixel unter dem Cursor,
WRITE speichert, EXIT verlässt den Editor.

## Bild von der Karte

`KORG/blechtribe/splash.bmp`, 128 x 64 Pixel, 1 Bit je Pixel, unkomprimiert (so speichern Bildprogramme "monochromes BMP"). Gezeichnet
wird die dunklere der beiden Farben. Der Import liest die Datei über die FatFs-Funktionen der Firmware, prüft den Kopf, wandelt die
Zeilen ins Format des Startbilds und speichert es wie WRITE im Editor (Flash-Sektor `0x7F0000`, Satz mit CRC). Einsprung für das Menü
ist `0xC01A2500` (`IMPORT_ENTRY`): Rückgabe 0 gespeichert, 1 keine Datei, 2 kein solches BMP (nichts gespeichert), 3 Flash-Fehler.

- **Gemessen:** der Datei-Puffer (FIL) der Firmware belegt 0x224 Byte; er liegt hinter dem Bildpuffer des Editors (`0xC0182D20`).
- **Gemessen (`import: ...`):** von unten nach oben gespeichert, von oben nach unten mit Schwarz als Index 1, mit einem Kopf von 124 Byte
  (BITMAPV5HEADER): gespeichert, Bild Pixel für Pixel wie gezeichnet. 100 Pixel breit und 4 Bit je Pixel: 2, nichts gespeichert.
  Ohne Datei: 1.
- **Gemessen:** nach einem Neustart zeigt das Display das importierte Bild (alle Proben während des Startbilds).
- **Offen:** der Menüpunkt dafür im BLECH-Menü; eine Rückmeldung auf dem Display.
