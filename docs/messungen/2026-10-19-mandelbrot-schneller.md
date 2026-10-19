# Mandelbrot: nachgewiesene Innenflächen überspringen

Stand 2026-10-19. Gemessen in der JavaScript-Referenz der Plugin-Laufzeit.
Kein Gerät wurde angesprochen. Bilder und Messprogramme liegen außerhalb des Repositorys.

## Verfahren

Der bisherige Renderer erkennt bereits einzelne Punkte in Hauptkardioide und
Perioden-2-Kreis. Er durchläuft deren Pixel dennoch in allen Verfeinerungen.
Die neue Fassung füllt nachweislich innenliegende Rechtecke direkt. Im ersten
Durchgang merkt sie sich ganze 8-mal-8-Blöcke in acht Zeilenmasken. Die späteren
Durchgänge überspringen diese Blöcke, vollständig gefüllte Blockzeilen auf einmal.
In den feineren Durchgängen lassen sich außerdem weiße Zeilenstücke bis zur
nächsten 8-Pixel-Grenze zusammen füllen.

Der Nachweis verwendet Intervallgrenzen derselben Q14-Ganzzahl-Prädikate wie
der Einzelpunkttest. Beim Kreis wird die größte Entfernung des Rechtecks
verwendet. Bei der Kardioide begrenzen kleinste und größte Quadratsummen den
Ausdruck q * (q + x). Bei negativem zweitem Faktor gilt die kleinste Quadratsumme
als obere Produktgrenze, sonst die größte. Die kleinste Quadratsumme der
imaginären Koordinate begrenzt die rechte Vergleichsseite. Alle Verschiebungen
und Rundungen bleiben die der VM. Die Koordinatengrenzen halten die Produkte
unter der Grenze für vorzeichenbehaftete 32-Bit-Zahlen.

Es genügt nicht, dass nur die Ecken weiß sind. Nur ein Nachweis für das ganze
Rechteck erlaubt das Füllen. Unklare Bereiche behalten die ursprüngliche
Iterationsrechnung und das bisherige Streifenmuster. Nach jeder Eingabe werden
die Zeilenmasken gelöscht. Die Arbeitszählung gewichtet Iterationen, neue Punkte,
Flächenprüfungen und Zeichnen getrennt, damit kurze Außenpunkte mehr Platz im
Rahmen bekommen, ohne lange Randiterationen unbeschränkt laufen zu lassen.

## Zeit bis zum Ende der Berechnung

Rahmen bis zum Ende aller Verfeinerungen und der abschließenden Anzeige von Zoom
und Iterationszahl. Das ist nicht die Zeit bis zum ersten erkennbaren Bild. Die Ansichten werden nach
dem Öffnen mit denselben Werten über das Encoder-Ereignis neu gestartet.

| Ansicht | Vorher, Rahmen | Jetzt, Rahmen | Weniger Rahmen |
|---|---:|---:|---:|
| Gesamtansicht, 24 Iterationen | 3606 | 3065 | 15.0 % |
| Gesamtansicht, 64 Iterationen | 4190 | 3699 | 11.7 % |
| Rand, Zoom 4, 40 Iterationen | 3857 | 2512 | 34.9 % |
| Kardioide innen, Zoom 7 | 2048 | 44 | 97.9 % |
| Kreis innen, Zoom 4 | 2048 | 44 | 97.9 % |
| Spitze, Zoom 4, 64 Iterationen | 4867 | 3665 | 24.7 % |
| Außenbereich, Zoom 0 | 2386 | 1864 | 21.9 % |

Bei den beiden vollständig innenliegenden Ansichten endet die Berechnung nach
46,5-mal weniger Rahmen. Die weiße Fläche ist jedoch bereits nach dem groben
Durchgang sichtbar: vorher nach 32 Rahmen, jetzt nach 43. Dieser große Faktor
beschreibt also überwiegend das Wegfallen unsichtbarer Nacharbeit. Er ist keine
entsprechende Beschleunigung des sichtbaren Bildaufbaus. Das Grobbild der
Gesamtansicht ist vorher nach 60, jetzt nach 59 Rahmen da. Die Rückmeldung vom
Gerät, dass die Gesamtansicht kaum schneller erscheint, passt dazu.

Mit 25 Rahmen pro Sekunde entsprechen 2048 Rahmen rechnerisch 81,92 s
und 44 Rahmen 1,76 s. Das sind aus den Rahmenzahlen abgeleitete Zeiten, keine
Stoppuhrmessung am Gerät. Die Gesamtansicht bleibt aufwendig; ihre Randdetails
werden weiterhin einzeln berechnet.

Die sieben vollständigen 1024-Byte-Bilder stimmen mit dem bisherigen Renderer
überein, einschließlich der Anzeige unten rechts. Der Plugin-Block wächst von
2436 auf 3552 Byte. Der größte Handler in diesen sieben Läufen kostet 2443
VM-Einheiten. Weitere 100 reproduzierbare Zufallsansichten mit je 80 Rahmen
bleiben bei höchstens 2390 Einheiten. Die bestehende Warnschwelle von rund 2630
Einheiten wird auch in den erweiterten Bildtests eingehalten. Die Umrechnung
von VM-Kosten in Gerätezeit bleibt eine Schätzung.

## Prüfungen

- Beschleunigungstest für vollständig innenliegende Kardioide und Kreis: Die
  bisherige Fassung verletzt die Grenze von 100 Rahmen, die neue hält sie ein.
- Vollständiger Pixelvergleich in 13 aufeinanderfolgenden Ansichten, mit positiven
  und negativen imaginären Koordinaten, Grenzen beider Innenbereiche, allen
  betroffenen Zoomlagen und Iterationsgrenzen von 8 bis 64. Die Anzeige unten
  rechts wird separat durch den bestehenden Test geprüft.
- Rückkehr aus einer vollständig weißen Ansicht zu Rand- und Außenansichten;
  alte Flächenmasken dürfen dabei keine Pixel stehen lassen.
- Die vorhandenen Tests für Touchpad, Part-Tasten, Encoder, Iterationszahl, TAP
  und geschlossene Apps bestehen.
- Der native ARM-VM-Vergleich enthält zusätzlich eine vollständig innenliegende
  Ansicht mit sieben Zoomschritten und den Rückweg mit TAP. Variablen, API-Aufrufe,
  Fehlerstatus und VM-Kosten entsprechen der JavaScript-Referenz.

## Auslieferung

Nur das Karten-Plugin ändert sich. Ein Firmware-Update ist dafür nicht nötig.
Eine neue `mandelbrot.blech` kann importiert werden; die Sammeldatei `e2sPlugin.all`
lädt den aktuellen Zehn-Preset-Satz beim nächsten Start. Vorhandene gespeicherte
Deaktivierungen der Plugins bleiben erhalten.
