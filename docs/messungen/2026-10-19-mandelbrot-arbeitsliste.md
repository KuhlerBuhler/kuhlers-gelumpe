# Mandelbrot: offene Rechtecke in einer Arbeitsliste

Stand 2026-10-19. Gemessen im Referenzmodell der Plugin-Laufzeit, zusätzlich
mit der nativen ARM-VM und den nativen Zeichenfunktionen geprüft. Kein Gerätetest.
Die bisherige Fassung ist der Innenflächen-Port aus
[der ersten Messung](2026-10-19-mandelbrot-schneller.md).

## Verfahren

Zwei offene 64-mal-64-Rechtecke decken das Display ab. Eine Ringliste enthält
Rechtecke mit Position und Größe. Ein geometrisch nachgewiesenes Innenrechteck
wird einmal weiß gefüllt und aus der Liste entfernt. Unklare Rechtecke werden
in vier Kinder geteilt. In 2-mal-2-Blöcken werden die vier Pixel einzeln mit
derselben Q14-Rechnung und demselben Streifenmuster wie zuvor berechnet.
Ein angefangener Orbit bleibt über Rahmen erhalten.

Die Liste arbeitet zuerst die größeren Rechtecke ab. Ihre größte mögliche
Front besteht aus 2048 Rechtecken zu je 2 mal 2 Pixeln. Die Liste hat genau
2048 Einträge, Indizes laufen mit einer Maske um. Einträge belegter Flächen
werden nicht als Ergebnis-Cache behalten. Bei Touchpad, Zoom, Iterationszahl
und TAP werden die laufende Aufgabe, die Liste und das Bild verworfen.
Es gibt keinen Koordinaten-Cache über Ansichtsänderungen hinweg.

Die Ausgabe enthält ausschließlich endgültige Pixel. Ein Bildpixel außerhalb
der Statusanzeige wird genau einmal gezeichnet. Es gibt weder geschätzte
Großpixel noch nachträgliche Verfeinerungsdurchgänge. Zum Abschluss wird die
Statusanzeige gezeichnet; passt sie nicht mehr in das Rahmenbudget, geschieht
das im nächsten Rahmen.

## Innenflächen

Der Kreisnachweis bleibt unverändert. Für die Kardioide wird der Faktor
q + X enger begrenzt: Mit X = cr - 4096 ist
`X * X / 16384 + X` konvex. Sein Maximum über einem Intervall liegt an einem
der Enden. Weil X ganzzahlig ist, gilt diese obere Grenze auch nach dem
Abrunden des gesamten Ausdrucks. Dazu kommt die größte
abgerundete Quadratsumme der imaginären Koordinate. So werden Abhängigkeiten
zwischen X und seinem Quadrat erhalten, die die bisherige Intervallgrenze
verlor. Für einen negativen oberen Faktor begrenzt die kleinste Quadratsumme
das Produkt nach oben, sonst die größte. Die Koordinatengrenzen halten alle
Produkte im vorzeichenbehafteten 32-Bit-Bereich.

Nur dieser Nachweis erlaubt das Füllen eines ganzen Rechtecks. Die Farbe
einiger Ecken genügt nicht. Randpixel behalten die ursprüngliche Rechnung.

## Messwerte

Rahmen bis alle Arbeit erledigt und die Anzeige wiederhergestellt ist:

| Ansicht | Bisher | Arbeitsliste |
|---|---:|---:|
| Gesamtansicht, 24 Iterationen | 3065 | 2594 |
| Gesamtansicht, 64 Iterationen | 3699 | 3201 |
| Rand, Zoom 4, 40 Iterationen | 2512 | 2167 |
| Kardioide innen, Zoom 7 | 44 | 1 |
| Kreis innen, Zoom 4 | 44 | 1 |
| Spitze, Zoom 4, 64 Iterationen | 3665 | 3385 |
| Außenbereich, Zoom 0 | 1864 | 1706 |

Die Gesamtansicht braucht damit 15,4 Prozent weniger Rahmen als der bisherige
Innenflächen-Port. Die Randdetails bleiben aufwendig. Die neue Arbeitsliste
macht diese Rechnung nicht überflüssig. Die sieben vollständigen
1024-Byte-Bilder stimmen einschließlich der Statusanzeige bytegenau überein.

In der Gesamtansicht wird Pixel 64,32 nach sieben statt 35 Rahmen weiß. Das
ist ein sichtbarer Messpunkt, keine Aussage über das ganze fertige Bild.
Ohne die Statusanzeige ist die Gesamtansicht ab Rahmen 2532 statt 3037
dauerhaft pixelgleich zum Endbild. Vollständig weiße Ansichten sind schon ab
Rahmen 1 statt 41 sichtbar fertig. Das wird getrennt vom Ende der Berechnung
gemessen.

Einzelne Randpunkte können wegen der geänderten Reihenfolge später erscheinen:
In der Spitzenansicht wird dieser Punkt erst nach 1791 statt 47 Rahmen weiß,
während das Gesamtbild früher fertig ist. Diese Zahlen sind keine Gerätezeiten.

Der Block wird mit 3452 statt 3552 Byte etwas kleiner. Die Arbeitsliste benötigt
8192 Byte. Insgesamt belegt das Plugin 2112 Variablenplätze. Alle zehn
aktuellen Presets zusammen passen mit 36060 von 131072 Byte in die Laufzeit.
Der teuerste Handler der sieben Messungen kostet 2441 VM-Einheiten. Weitere
200 Ansichten mit je 120 Rahmen erreichen höchstens 2429. Die bisherige
Warnschwelle von 2631 wird eingehalten.

## Prüfungen

- Ein neuer Test zählt jeden Schreibzugriff auf einen Bildpixel und vergleicht
  sofort seine Farbe mit der Referenz. Die alte Vorschau scheitert; die
  Arbeitsliste schreibt jeden Pixel genau einmal mit seiner endgültigen Farbe.
- Vollständiger Pixelvergleich in 13 aufeinanderfolgenden Ansichten, mit
  Grenzen von Kardioide und Kreis, positiven und negativen Koordinaten,
  Zoomlagen und 8 bis 64 Iterationen.
- Wechsel aus einer unfertigen Ansicht in eine weiße Zoomansicht, weiter in
  eine schwarze Außenansicht und mit TAP zurück. Alte Aufträge und Pixel
  dürfen nicht stehen bleiben.
- Der native VM-Korpus enthält das Füllen und Umlaufen der Ringliste und
  verwirft anschließend die offene Arbeit durch neue Eingaben. Variablen,
  API-Aufrufe, Fehler und Kosten entsprechen dem Referenzmodell.
- Zusätzlich werden die echten nativen Zeichenfunktionen auf eigenem RAM
  ausgeführt: 16 Rahmen einer Gesamtansicht und je ein Rahmen der beiden
  weißen Ansichten. Die Framebuffer sind bytegleich zur Referenz. Gezählt
  werden bis zu 135928 ARM-Instruktionen pro geprüftem Rahmen. Die großen
  weißen Rechtecke brauchen 72668 beziehungsweise 51861 Instruktionen.
  Daraus wird keine am Gerät gemessene Laufzeit abgeleitet.

## Auslieferung

Es ändert sich ausschließlich das Karten-Plugin. Eine neue mandelbrot.blech
und die vollständige e2sPlugin.all lassen sich ohne Firmware-Update verwenden.
Die anderen neun Blöcke bleiben unverändert.
