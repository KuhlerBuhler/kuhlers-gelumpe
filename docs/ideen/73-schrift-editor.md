# 73. Schrift-Editor in der App

Status: offen, nur untersucht, nichts gebaut. Zurück zu den [Ideen](../ideen.md).

Wunsch aus der Community: eine eigene Schrift Zeichen für Zeichen pixeln und auf die Electribe bringen. Entschieden: in der
App, die Schrift wird beim Patchen eingebaut. Laden von der Karte beim Start gibt es nicht. Marker: **gemessen**,
**hergeleitet**, **ungeprüft**.

## Befund

| Schrift | Höhe | Zeichen | Bitmap-Bytes |
|---|---|---|---|
| 0 | 8 | 98 (0, 32 bis 127, 160) | 588 |
| 1 | 16 | 95 (32 bis 126) | 928 |
| 2 | 12, feste Breite | 224 (0 bis 127, 160 bis 255) | 1832 |
| 3 | 16 | 95 (32 bis 126) | 748 |

- Je Zeichen ein Eintrag mit Code, Vorschub, Zeiger, Breite, Höhe, Versatz. Bitmaps zeilenweise, höchstes Bit links, ohne
  Lücken hintereinander. Rot und blau gleich (gemessen, [Display-Schriften](../messungen/2026-10-14-display-schriften.md)).
- Der Theme-Patch "BLECH Theme: Schriften und Symbole" ersetzt schon die Bitmaps aller vier Schriften an Ort und Stelle
  ([BLECH Theme](../hintergrund/blech-theme.md)). Die Planung dafür (`planFont` in `tools/patch/blech_theme.mjs`) läuft nur
  in Node.
- Einen Pixel-Editor gibt es in der App nicht; die Startbild-Seite wandelt nur ein Bild in 1 Bit um.

## Grenzen

- Jedes Zeichen darf nicht mehr Bytes brauchen als das Original, Vorschub und Zeilen bleiben, keine neuen Zeichen.
- Eine andere Schrift heißt neu patchen.
- Schrift 1 hat 348 Kerning-Paare, die zu neuen Formen schief aussehen können.

## Plan

1. `planFont` und seine Prüfungen nach `src/` für den Browser.
2. Editor-Seite: Raster je Zeichen, Vorschub- und Grundlinien-Marke, Byte-Budget sichtbar, Vorschau echter Menüseiten,
   Import und Export im Textformat der `font*.mjs`.
3. Der Patcher baut daraus einen Theme-Patch, Prüfung im Emulator auf allen drei Builds.

Risiko: eine kaputte Schrift macht auch die Rettungsbildschirme unlesbar, darum ist eine Prüfung vor dem Patchen Pflicht.
Am Gerät zu prüfen: Haupt- und Rettungsbildschirme lesbar, Namen in Schrift 2, Start bis zum Hauptbildschirm.
