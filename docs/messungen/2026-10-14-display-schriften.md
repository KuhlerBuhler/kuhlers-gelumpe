# Display: Schriften und Symbole der Firmware

Stand 2026-10-14. Basis ist eine eigene SYSTEM.VSB (Sampler 2.02 mit Hacktribe). Alles lief im
Emulator (`tools/emu/`, Unicorn) oder wurde offline gelesen; am Gerät ist nichts geprüft. Marker:
**gemessen** (im Emulator ausgeführt und beobachtet), **offline** (Code oder Tabellen gelesen),
**hergeleitet**, **offen**. Adressen sind RAM-Adressen, Datei-Offset in der VSB = RAM - `0xC0000000` + `0x100`.

Diese Seite hält nur Aufbau, Adressen, Formate und Maße fest, keine Glyph- und keine Symbolbytes.
Sie ist die Grundlage für das [BLECH Theme](../hintergrund/blech-theme.md) (Patch `blech-theme`).

## Wie die Firmware Text und Symbole zeichnet

Das Display ist ein Puffer mit 8 Seiten zu 128 Spalten (`0xC031B310`, Bit 0 der oberste Pixel einer
Seite). Alles, was die Firmware zeigt, kommt Pixel für Pixel durch dieselbe Stelle. **Gemessen:**
`0xC003F12C` (Pixel x, y) ruft `0xC0015824`, an einer Hauptbildschirm-Auffrischung rund 5500 Pixel, alle
von `0xC003F12C`. Daraus folgt: es gibt keinen zweiten Weg am Pixelsetzer vorbei, was Text oder
Symbole angeht. Linien, Rechtecke und Füllungen sind Code, keine Tabellen.

Der Zeichenzustand liegt bei `0xC03487CC` (**offline**): `+0` Schriftnummer, `+4` Farbe (0 oder 1), `+8`
und `+0xC` Fenster (128 und 64), `+0x10` das vorige Zeichen für das Kerning (-1: keines).

| Adresse | Aufgabe (offline gelesen) |
|---|---|
| `0xC003F0D4` | Zeichenzustand zurücksetzen: Schrift 0, Farbe 1, Fenster 128 x 64, Puffer löschen |
| `0xC003F730` | Schrift wählen (Zeiger auf die Nummer), setzt das vorige Zeichen zurück; 51 Aufrufer |
| `0xC003F74C` | Glyph zu einem Zeichencode suchen: binäre Suche im Feld der gewählten Schrift |
| `0xC003F04C` | Kerning: Wert für das Paar (voriges, aktuelles Zeichen) |
| `0xC003F1A4` | einen Glyph zeichnen (Beschreiber, x, y) |
| `0xC003F7D0` | Text zeichnen (Text, x, y, fett, optional fester Schritt) |
| `0xC003F89C`, `0xC003F904` | Textbreite, Text um x zentriert |
| `0xC003F650` | Bild aus der Bildtabelle zeichnen (Nummer, x, y) |

**Gemessen:** die Schriftnummer, die beim Zeichnen eines Glyphs gilt, und der Code des Glyphs, an `0xC003F1A4`
über alle Bildschirmnummern 0 bis 47 und die Seiten des Edit-Rings. Die Nummern 48 bis 89 zeichnen weder Text noch Bilder.

## Die vier Schriften

Die Tabelle der Schriften steht bei `0xC00C2818` (vier Zeiger, nach Schriftnummer), die der
Kerning-Köpfe bei `0xC00C2808` (vier Zeiger, Schrift 2 hat keinen). **Offline.**

| Nr | Schrift-Kopf | Höhe | Zeichen | Vorschub | Beschreiber und Daten (Spanne) | Kerning |
|---:|---|---:|---|---|---|---|
| 0 | `0xC00C375C` | 8 | 98: Code 0, 32 bis 127, 160 | 2 bis 8, proportional | `0xC00C32C8` bis `0xC00C3CEC` | 22 Paare |
| 1 | `0xC00C21FC` | 16 | 95: Code 32 bis 126 | 3 bis 11, proportional | `0xC00C1CCC` bis `0xC00C2808` | 348 Paare |
| 2 | `0xC00C50C8` | 12 | 224: Code 0 bis 127 und 160 bis 255 | 6, fest | `0xC00C3D00` bis `0xC00C560E` | keins |
| 3 | `0xC00C3208` | 16 | 95: Code 32 bis 126 | 2 bis 10, proportional | `0xC00C2828` bis `0xC00C32BF` | 26 Paare |

**Schrift-Kopf** (`+0` erster Code, `+4` Anzahl, `+8` Höhe in Zeilen, `+0xC` Zeiger auf das Feld). Das Feld
hat je Zeichen einen Zeiger auf einen **Beschreiber**, aufsteigend nach Code (darauf läuft die binäre Suche).

**Beschreiber** (16 Byte, **offline**, die Zeichnung in `0xC003F1A4` bestätigt es):

| Offset | Inhalt |
|---|---|
| `+0` | Zeichencode (Wort) |
| `+4` | Vorschub in Pixeln (Wort, gelesen wird ein Byte) |
| `+8` | Zeiger auf die Bitmap |
| `+0xC` | Breite der Bitmap |
| `+0xD` | Höhe der Bitmap |
| `+0xE` | x-Versatz (vorzeichenbehaftet) |
| `+0xF` | y-Versatz unter der Grundlinie (vorzeichenbehaftet, negativ heißt unter der Zeile) |

**Bitmap:** zeilenweise, `(Breite + 7) / 8` Byte je Zeile, Bit 7 ist der linkste Pixel. Gesetzte Bits
werden gemalt, gelöschte bleiben, wie sie sind. Die Bitmap ist die kleinste Hülle der Zeichnung, nicht die Zelle.
Das Pixel (Spalte, Zeile) landet bei `x + Spalte + x-Versatz` und
`y + Schrifthöhe - (Höhe + y-Versatz) + Zeile`. Spalten hinter dem Vorschub werden nicht gemalt
(`0xC003F1A4` vergleicht die Spalte mit dem Vorschubbyte). Der Text rückt um Vorschub plus Kerning
vor. **Gemessen** an den Glyphen der vier Schriften.

**Platz.** Die Bitmaps liegen lückenlos hintereinander in einem Pool, durchsetzt mit den Beschreibern,
und jede belegt genau `(Breite + 7) / 8 * Höhe` Byte (**gemessen:** keine zwei Zeiger gleich, keine Überlappung). Es gibt
keinen Spielraum, ein Ersatz passt nur, wenn er nicht mehr Byte braucht. Bis acht Pixel Breite ist das die
Zeilenzahl. Zusammen: Schrift 0 588 Byte, Schrift 1 928, Schrift 2 1832, Schrift 3 748.

**Besonderheiten.**

- Der Glyph Code 126 (`~`) der Schrift 3 ist ein Pfeil nach rechts, kein Tilde. Form gemessen, Verwendung am Bildschirm nicht gesehen.
- Code 92 (`\`) ist in den Schriften 0, 1 und 3 ein einzelnes Pixel und steht in der Statusleiste zwischen Seitentitel und Seitenzähler.
- Der Leerschritt hat ein Pixel Bitmap, der Vorschub trägt die Weite.
- In Schrift 2 liegen die Zeichen 0 bis 31 (Bild- und Rahmenzeichen) und 160 bis 255 (Latin-1). Am Bildschirm gesehen wurde keines davon.
- Schrift 0 hat dazu die Codes 0, 127 und 160.

## Wo welche Schrift steht

**Gemessen** an den Zeichenfolgen, die `0xC003F1A4` je Bildschirm bekommt:

| Nr | Rolle | Beispiele |
|---:|---|---|
| 0 | kleine Zeile: Statusleiste, Hinweise, Fehlertext | `Pattern`, `Global`, `1/29`, `press  [ Enter ]`, `No Card.`, `Part:01` |
| 3 | Titel und Wahlzeilen, 16er Zeile mit Versalhöhe 9 | `GLOBAL PARAMETER`, `select DESTINATION`, `1: Touch Bottom Left`, `SOFTWARE UPDATE`, `B P M` |
| 1 | große Werte, kräftig, Versalhöhe 11 | `160.0`, `Error` |
| 2 | Festbreite 12 Zeilen: Namen und Zahlenfelder | `001 Init Pattern`, `no sample`, `X:    , Y:` |

Die Schriften 0, 1 und 3 kommen auf den meisten Bildschirmen vor, Schrift 2 nur auf der Zielwahl (18), der
XY-Kalibrierung (32) und der Namenseingabe (40). Dort stehen vom Nutzer gewählte Namen.

**Zeichenvorrat.** Die Zeichenketten der Firmware liegen in drei Bereichen: `0xC00A3000` bis `0xC00A8000`
(942 Ketten, 93 verschiedene Zeichen), `0xC00DA000` bis `0xC00DC000` (FX-Plätze, 28 Zeichen) und `0xC011F000`
bis `0xC0124000` (Hacktribe, 95 Zeichen). Zusammen kommt jedes druckbare ASCII-Zeichen von 0x20 bis 0x7E vor
(**offline**, Ketten ab drei Zeichen). Ein Theme muss also alle 95 abdecken, in allen vier Schriften (Namen sind frei wählbar).

## Symbole: die Bildtabelle

Die Tabelle liegt bei `0xC00C1C2C`: 19 Zeiger auf Beschreiber zu 12 Byte (`+0` Breite, `+4` Höhe, `+8` Zeiger auf
die Daten). Die Daten sind spaltenweise in Seiten zu 8 Zeilen, Byte `(y / 8) * Breite + x`, Bit `7 - y % 8`; die
Daten liegen im Pool `0xC00F94FC` bis `0xC00F9C77`, um das Startbild (`0xC00F9854`, Bild 13) herum.
`0xC003F650` malt nur gesetzte Pixel, die Farbe ist 1. **Offline**, die Maße **gemessen**.

| Nr | Maße | Rolle (nach Form und Bildschirm, **hergeleitet**) |
|---:|---|---|
| 0 | 66 x 64 | nicht gesehen |
| 1 | 10 x 8 | Batterie, mit Blitz (lädt) |
| 2, 3, 4 | 10 x 8 | Batterie mit drei, zwei, einem Balken (Nr. 4 steht auf jedem Bildschirm) |
| 5 | 11 x 8 | Batterie leer |
| 6 | 6 x 8 | SD-Karte |
| 7, 8, 9 | 11 x 16 | große Symbole: Pfeil nach oben, Blatt, Ordner |
| 10 | 4 x 8 | Dreieck nach rechts (Marker) |
| 11 | 14 x 8 | Schildchen `EDIT` (weiß auf Schwarz, auf den Pattern- und Menüseiten) |
| 12 | 13 x 8 | Schildchen `CLIP` |
| 13 | 128 x 64 | Startbild |
| 14 | 5 x 8 | Schildchen `L` |
| 15 | 22 x 8 | Schildchen `M.REC` |
| 16 | 15 x 8 | Schildchen `ORIG` (Hauptbildschirm) |
| 17 | 8 x 8 | Schildchen `ST` |
| 18 | 15 x 8 | Schildchen `SLICE` |

Die Schildchen sind Bilder mit ausgesparter Schrift: der gesetzte Teil ist der schwarze Kasten, die Buchstaben
sind die Löcher. Alles, was nicht in dieser Tabelle liegt (Balken, Pegelanzeigen, Rahmen, Wellenform), zeichnet Code.

## Was beim Start gelesen wird

Die Startphase (alle Bytes, die auf den 17 Startwegen vor dem Hauptbildschirm gelesen werden,
`tools/emu/bootmap.py`, [Startphase](2026-10-10-startphase.md)) berührt diese Daten:

| Bereich | Gelesen im Start |
|---|---|
| Schrift 0 | 29 von 98 Glyphen: `-`, `/`, Ziffern, `:`, `D`, `E`, `U`, `[`, `\`, `]`, `a`, `e`, `i`, `l`, `n`, `p`, `r`, `s`, `t` |
| Schrift 1 | 8 von 95: `.`, `W`, `g`, `i`, `k`, `n`, `o`, `r` |
| Schrift 2 | 45 von 224 |
| Schrift 3 | 15 von 95: `A`, `D`, `E`, `F`, `I`, `M`, `N`, `O`, `P`, `R`, `S`, `T`, `U`, `W` |
| Bildtabelle | Bild 4 (Batterie) und Bild 11 (`EDIT`) mit ihren Beschreibern, dazu Bild 13 (Startbild) |

Das sind der Hauptbildschirm und die Rettungsbildschirme (Update-Abfrage, Startmodi, Panel-Update, die
`SOFTWARE UPDATE` und `press  [ Enter ]` zeigen). Ein Patch, der diese Bytes ändert, braucht eine
`startPhase`-Ausnahme wie das Startbild ([Patcher](../patcher.md), Regel 1).

## Offen

- Am Gerät ist nichts gemessen, auch nicht, dass das LCD diese Bitmaps so zeigt wie der Emulator.
- Wofür Bild 0 steht, und welche Bildschirme die Bilder 6, 7, 8, 9, 10, 12, 14, 15, 17 und 18 zeichnen
  (sie kamen in den durchgesehenen Bildschirmen nicht vor, ohne Karte und Sample).
- Ob die Codes 0 bis 31 und 160 bis 255 der Schrift 2 irgendwo erscheinen.
- Ob Hacktribe-Code (ab `0xC0150000`) eigene Schriften oder Symbole mitbringt.
