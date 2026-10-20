# BLECH Theme: eigene Schriften und Symbole fürs Display

Stand 2026-10-14. Gebaut und im Emulator geprüft, am Gerät nichts. Marker: **gemessen** (im
Emulator), **hergeleitet**, **offen**. Der Aufbau von Schriften und Bildern in der Firmware steht in
[Display: Schriften und Symbole der Firmware](../messungen/2026-10-14-display-schriften.md).

## Was es ist

Der Patch `blech-theme` (`data/patches/blech-theme.json`, Teil des Satzes BLECH) tauscht die Bitmaps der
vier Schriften und von 17 Symbolen gegen eigene Zeichnungen. Es ist ein reiner Datenpatch, kein Code:
Zeichencodes, Vorschubweiten, Tabellen und Zeiger bleiben, deshalb verschiebt sich kein Text und kein
Layout. Die Zeichnungen stehen als Text in `tools/patch/blech_theme_art/` (`font0.mjs` bis `font3.mjs`,
`icons.mjs`), `#` ist Farbe, `.` ist leer, wie bei der Schrift des README-Banners. Der Patch enthält
nur diese Bytes und die Prüfsummen der Bereiche, die er überschreibt; keine Zeichen und keine Symbole von Korg
liegen im Repo.

## Aussehen

Blech, roh, einbittig. Ecken sind abgeschnitten wie bei gestanztem Blech, nicht gerundet. Das große O ist ein glatter Ring,
nur die Null trägt die Schlitzpupille, jede Zahl hat also ein Auge. Das A ist spitz, das Q tropft. Die
Schildchen (`EDIT`, `CLIP`, `ORIG` und so weiter) sind Platten mit abgeschnittenen Ecken und ausgestanzter
Schrift, die Batterie ist ein Blechkasten. Die Schrift 1 ist kräftig (Striche zwei Pixel breit), die Schrift 3 ist
dünn, die Schrift 2 hat Festbreite. So hält ein Name O und Null in jeder Schrift
auseinander. Alles bleibt auf 128 x 64 lesbar: keine Verzierung im
Zeichenkörper selbst, die Auffälligkeit sitzt in wenigen Formen.

Vorschau: [theme-preview.png](../../assets/blechy/theme-preview.png), die wichtigsten Bildschirme und alle
druckbaren Zeichen aller vier Schriften, aus dem Emulator. Das Bild zeigt nur die Seite mit Theme. Eine
Gegenüberstellung mit den Schriften der Firmware erzeugt `--compare` (siehe unten), sie enthält Bitmaps von
Korg und bleibt lokal.

## Regeln, die der Generator prüft

`node tools/patch/blech_theme.mjs --vsb SYSTEM.VSB --out data/patches/blech-theme.json` liest nur die Adressen der Tabellen
und die Prüfsummen und lehnt ab, was die Firmware stören würde:

| Regel | Grund |
|---|---|
| Zeichen bleibt über Code und Vorschub, die Tinte liegt innerhalb des Vorschubs | Textbreite und Kerning hängen nur am Vorschub |
| Tinte liegt in den Zeilen des Originals (nicht höher, nicht tiefer) | sonst stößt sie an die Nachbarzeile oder an den Rand |
| Eine Bitmap braucht nicht mehr Byte als der Platz des Originals | die Bitmaps liegen lückenlos im Pool, es gibt keinen Spielraum |
| Ein Symbol hat genau die Maße des Originals | Tabelle und Aufrufer legen die Größe fest |
| Alle 95 druckbaren ASCII-Zeichen sind in allen vier Schriften belegt (oder mit `null` als unberührt vermerkt) | Namen sind frei wählbar, die Firmware druckt jedes davon |
| Kein Zeichen sieht aus wie ein anderes, verwechselbare Paare (`O 0`, `I l 1`, `S 5` und so weiter) unterscheiden sich um mindestens zwei Pixel | Lesbarkeit |

`node tools/patch/blech_theme.mjs --check` prüft die Zeichnungen allein, ohne Firmware. Der Patch besteht aus rohen Änderungen,
je Glyph-Bitmap, je geändertem Maßfeld und je Symbol eine, jede mit der Prüfsumme der Bytes, die sie ersetzt. Eine
`copy`-Änderung auf sich selbst wäre kürzer, aber `patchesPresent` erkennt ein angewendetes BLECH dann nicht mehr (die
Quelle hat sich ja geändert).

Unberührt bleiben das Leerzeichen und der Backslash (ein Pixel, Trenner der Statusleiste), die Codes außerhalb von ASCII
(Schrift 0: 0, 127, 160; Schrift 2: 0 bis 31 und 160 bis 255), das Startbild (Bild 13, das der Patch `splash` setzt) und
Bild 0. In Schrift 3 ist `~` der Pfeil nach rechts, er bleibt einer.

## Startphase, EXIT beim Einschalten

Das Theme ändert Bytes, die schon beim Start gelesen werden: der Hauptbildschirm und die Rettungsbildschirme (Update-Abfrage,
Startmodi, Panel-Update) zeichnen mit denselben Schriften, die Batterie und das Schildchen `EDIT` mit den Symbolen
([Messung](../messungen/2026-10-14-display-schriften.md), Abschnitt "Was beim Start gelesen wird"). Der Patch nennt
deshalb unter `startPhase` diese Bereiche, mit Begründung, und `check.py` lässt genau sie zu (vier Schriften, ein Symbolbereich).
**Gemessen:** der Satz BLECH mit Theme besteht alle 68 Prüfungen von `tools/emu/check.py` (Start auf allen Wegen, Update-Abfrage,
Startmodi, Panel-Update, Notschalter, DSP-Strom).

Die Notschalter-Regel (EXIT beim Einschalten) schaltet nur Code ab. Das Theme ist Daten und bleibt bei gehaltenem
EXIT sichtbar (**gemessen** im Emulator: auch mit gehaltenem EXIT unterscheidet sich das Display einer Kopie mit Theme von dem
einer Kopie ohne). Das ist gewollt. Die Rettungswege bleiben lesbar, weil
jede Schrift Maße, Vorschub und alle Zeichen der Firmware behält; ein fehlerhaftes Zeichen kann das Aussehen stören, aber
keinen Ablauf, denn kein Zeiger und kein Code ändert sich. Zum alten Aussehen zurück führt nur der normale Weg: die
unveränderte SYSTEM.VSB aufspielen ([Rückweg](../messungen/2026-10-10-rueckweg-geuebt.md)).

## Vorschau und Werkzeuge

```bash
E2_VSB=SYSTEM.VSB node tools/patch/blech_theme_preview.mjs [--flash dump.bin] [--compare dist-release/theme-compare.png]
```

Das Werkzeug wendet den Satz mit und ohne Theme an, startet beide Kopien in `tools/emu/theme_screens.py`, fährt beide
zu denselben Bildschirmen und lässt die Firmware jedes druckbare Zeichen mit ihrer eigenen Textfunktion zeichnen (damit die
Vorschübe die der Firmware sind). Tests: `test/blech-theme.test.mjs` (mit `E2_VSB` auch: der eingecheckte Patch ist, was der Generator
aus der Firmware baut, der Satz lässt sich mit dem Theme anwenden, und jedes Zeichen der Textbereiche der Firmware hat einen Eintrag).

## Offen

- Das Theme am Gerät: ob das LCD die Zeichnungen so lesbar zeigt wie der Emulator, ist nicht gemessen.
- Die Schildchen und Symbole, die in den durchgesehenen Bildschirmen nicht vorkamen (Karte, große Symbole, Marker, `CLIP`, `L`,
  `M.REC`, `ST`, `SLICE`), sind nach Form zugeordnet und nur als Bitmap geprüft, nicht an ihrem Bildschirm gesehen.
- Die Codes 0 bis 31 und 160 bis 255 der Schrift 2 bleiben von Korg, bis ein Bildschirm sie zeigt.
