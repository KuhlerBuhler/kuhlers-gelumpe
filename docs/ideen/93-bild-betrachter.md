# 93. Bild-Betrachter für mehrere BMPs

Wunsch aus der Community (Oktober 2026). Stand 2026-11-03: **gebaut als Katalog-Plugin BMP Viewer, im Simulator
geprüft, am Gerät offen.** Marker: **gemessen**, **hergeleitet**, **ungeprüft**.

## Wunsch

Mehrere Bilder von der Karte nacheinander am Display ansehen, etwa BMPs, und mit einer Taste weiterblättern.

## Wie es gebaut ist

- Die Laufzeit liest Bilder nur über `korg.file.frame` aus `KORG/blechtribe/Gif/GIF00.E2G` bis `GIF99.E2G` (Format in
  [Plugins, Karte und Dateiformat](../plugins.md#karte-und-dateiformat)). Ein eigener BMP-Leser in der Firmware wäre ein
  neuer Patch; den braucht es nicht, denn eine Datei hält beliebig viele Bilder. (hergeleitet)
- `tools/gif/gif2e2g.py` nimmt deshalb auch mehrere Bilder: `python3 tools/gif/gif2e2g.py a.bmp b.bmp c.bmp 4` macht
  `GIF04.E2G` mit einem Bild je Eingabe in dieser Reihenfolge. Pillow liest die BMPs, es gibt keinen zweiten Decoder. Hell
  wird zum leuchtenden Pixel, `--invert` dreht das um (für schwarze Zeichnung auf weißem Grund).
- Das Plugin BMP Viewer (TOOLS) zeigt ein Bild der Datei: Part rechts und links blättern, nach dem letzten kommt wieder
  das erste, der Encoder wählt die Datei, TAP lässt die Nummer oben links stehen oder blendet sie aus. Sonst steht sie nach
  jedem Wechsel zwei Sekunden da.
- Die Zahl der Bilder sagt die Laufzeit nicht vorher, `korg.file.frame` gibt erst hinter dem letzten Bild 0 zurück. Der
  Betrachter merkt sie sich beim ersten Durchlauf; erst dann geht es vom ersten Bild rückwärts zum letzten und die Nummer
  zeigt die Gesamtzahl (`2/3`).
- Tests: `test/script-file.test.mjs` blättert im Simulator durch drei Bilder (vor, zurück, Umlauf, Nummer, TAP, fehlende
  Datei) und prüft, dass `gif2e2g.py` drei BMPs Pixel für Pixel in eine Datei legt. (gemessen, Simulator)

## Offen

- Am Gerät nicht ausprobiert. Wie lange ein Lesevorgang von 1 KiB dort dauert, ist nicht gemessen. Der teuerste
  Tastendruck (über das letzte Bild hinaus) liest zweimal und kostet 4414 Einheiten, im Simulator über der Warnschwelle von
  0,5 ms. (**ungeprüft** am Gerät)
- Ein Weg im Editor, Bilder auszuwählen und die Datei zu packen, fehlt; `src/script/gif.mjs` könnte sie mit `packGif` im
  Browser schreiben. Bis dahin bleibt das Werkzeug in `tools/gif/`.
