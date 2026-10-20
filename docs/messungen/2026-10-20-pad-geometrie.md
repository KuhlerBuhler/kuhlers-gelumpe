# Gebundene Noten auf den Pads schneller auswerten

Gemessen im ARM-Emulator mit selbst erzeugten Steps. Keine Gerätemessung.
Untersucht werden Hacktribe, der rote Korg-Sampler und die blaue Electribe 2.

## Berechnung und Speicher

Die Pad-Darstellung verfolgt für jede Note höchstens 16 Schritte zurück und 16
Schritte vorwärts. Bei identischen Notenwörtern auf allen untersuchten Übergängen
haben die Noten dieselbe Bindungsgeometrie. Diese wird innerhalb eines Aufrufs
einmal berechnet und mit der Zahl der belegten Notenplätze gewichtet. Sobald ein
Notenwort abweicht, bleibt die getrennte Auswertung der einzelnen Noten erhalten.
Das gilt auch für unterschiedlich lange und überlappende Bindungen.

Die bisherige Division durch wiederholtes Subtrahieren entfällt. Eine Tabelle mit
272 mathematisch erzeugten Byte liefert genau dieselben abgerundeten Brüche:

`floor(256 * (vorwärts + 1) / (rückwärts + vorwärts + 1))`

Für Fortsetzungen liegt rückwärts zwischen 1 und 16, vorwärts zwischen 0 und 16.
Die Summe, ihre Begrenzung auf 256 und die anschließende Helligkeitsrundung bleiben
erhalten. Bei gleichen Ketten wird zuerst wie bisher abgerundet und danach mit der
Notenzahl multipliziert. Trigger und Poly-Stimmen werden wie bisher behandelt.

| Größe | Vorher | Danach |
|---|---:|---:|
| Pad-Code einschließlich Tabelle | 2732 Byte | 3124 Byte |
| Reservierter Pad-Zustand | 64 Byte | 64 Byte |
| Zusätzlicher Stack während der Berechnung | 0 Byte | 4 Byte |
| Einzelne Geometrie, vier gebundene Noten auf Step 17 | 7516 Befehle | 954 Befehle |
| Mittel über alle 64 Steps dieses eigenen Musters | 6732,25 Befehle | 833 Befehle |

Der Code wächst um 392 Byte, also rund 0,4 KiB, davon 272 Byte Tabelle. Es wird kein
zusätzliches RAM reserviert. Alle 64 Geometrieergebnisse des Musters stimmen überein. Die blaue
Firmware behält ihren bisherigen Pad-Code bytegenau.

## Aktualität der Daten

Die LED-Sendefunktion kann auf eine volle Warteschlange warten. Deshalb werden
keine Geometrieergebnisse über Sendefunktionen oder spätere Aufrufe hinweg behalten.
Das gemeinsame Ergebnis gilt ausschließlich innerhalb der gerade laufenden,
begrenzten Berechnung. Ein späterer Aufruf liest die aktuellen Stepdaten erneut.
Es gibt weder einen Dirty-Merker in einem fremden Modul noch eine zusätzliche
Interruptsperre. Native LED-Tabellen, Cursor, Farben und POWER SAVE bleiben live.

## Gleichheit und Rückstau

[Die nativen Tests](../../tools/patch/test_pad_colors.py) prüfen alle vier
Stimmenzuweisungen, alle 272 Brüche, zufällige und unterschiedlich lange
Notenketten, vertauschte Notenplätze, doppelte Noten, leere Steps, Gate 0/126/127,
Bargrenzen, Partwechsel und Änderungen bei gleichem Patternzeiger. Dazu kommen
Nullzeiger, ungültiger Modus und ungültiger Part. Register, Stack, Interruptstatus,
Eingabedaten und dauerhafter Pad-Zustand bleiben erhalten.

Der unveränderte Code liefert ebenfalls dieselben Referenzergebnisse, braucht
im teuren Test jedoch 7516 Befehle und überschreitet dessen Budget von 1500.
Die neue Fassung besteht das Budget und die Gleichheitsprüfung.

Ein zusätzlicher [Paneltest](../../tools/emu/menu_cases.py) füllt die echte
Firmware-Sendewarteschlange durch einen eigenen Aufrufer im Emulator. Während
einer späteren LED-Ausgabe ändert er das Gate eines unsichtbaren Steps. Nach dem
Leeren der Warteschlange zeigt das betroffene sichtbare Pad den erwarteten Wert
29/29. Im ersten Samplerlauf wurde der volle Puffer 330-mal erreicht. Die
Sendefunktion und der UART werden dabei von der Firmware selbst ausgeführt.

## Bildprüfung während der Übertragung

Eine Prüfung des roten Samplers traf bei 892,9 ms eine laufende LCD-Übertragung:
Auf Seite 3 waren 66 Spalten bereits neu, die übrigen Spalten noch vom vorigen
Animationsbild. Beide Teile stimmten exakt mit den berechneten Bildern überein.
Der bisherige Prüfer erlaubte verschiedene fertige Seiten, aber keine angefangene
Seite. Die Firmwaredatei wurde für diese Korrektur nicht verändert.

Der Beobachter zeichnet nun LCD-Seite und Spalte zum Snapshot auf.
[Der Bildvergleich](../../tools/emu/frame_match.py) erlaubt auf genau dieser Seite
den bekannten neuen Präfix und alten Suffix an der aufgezeichneten Spalte. Andere
Seiten müssen weiterhin vollständig einem bekannten Bild entsprechen. Alle 138
Snapshots desselben Laufs bestehen damit, ohne einen Snapshot auszulassen.
[Vier eigene Tests](../../tools/emu/test_frame_match.py) verwerfen fremde Pixel,
eine falsche Spalte, eine falsche Seite und eine zweite angefangene Seite.

## Vollständige Sätze und Gesamtmessung

Beide Stände bestehen alle vollständigen Satzprüfungen ohne ausgelassene Prüfung.
Die folgende Befehlszahl ist jeweils der Median aus drei unabhängigen Läufen des
Zwei-Sekunden-Falls mit vier lang gebundenen Noten:

| Firmware | Satzprüfungen je Stand | ARM-Befehle vorher | ARM-Befehle danach | Weniger Befehle |
|---|---:|---:|---:|---:|
| Hacktribe | 434/434 | 88359858 | 73724639 | 16,56 % |
| Korg rot | 459/459 | 88319110 | 73712225 | 16,54 % |
| Synth | 338/338 | 72691790 | 72691790 | 0,00 % |

Alle gewöhnlichen Szenen bleiben innerhalb des Budgets von höchstens einem
Prozent Mehrarbeit. Lange Bindungen liegen innerhalb von 105 Prozent der Arbeit
des jeweiligen Originals. Bei Mandelbrot, Life und Pong stimmen die vollständigen
Anfangs- und Endzustände sowie die Bilder überein. Die Synth-Pad-Berechnung bleibt
bytegleich; ihr Messergebnis dient als Kontrolle.

Der abschließende Unit-Lauf umfasst 1080 Tests: 937 bestanden,
143 erwartete Auslassungen für nicht bereitgestellte lokale Voraussetzungen,
kein Fehler. Im Browser bestehen 162 von 163 Tests bei einer erwarteten
Auslassung und keinem Fehler. Dazu bestehen sieben native Pad-Tests, elf
Prüfungen des Messwerkzeugs und vier Tests des LCD-Seitenvergleichs.

Die Befehlszahlen sind keine gemessenen Prozessorzyklen und keine Zusage derselben
Beschleunigung des gesamten Geräts. Audioauswirkung und Gerätetest sind offen.

Die Vergleichsbasis enthält dieselben Änderungen aus `develop`, einschließlich
GIF-Player, langsamerem Ladefinale und sichtbarem Akkordcursor. Nur die
Pad-Berechnung unterscheidet sich. Beide Stände enthalten bereits den nativen
Multiplikationsbefehl der Skript-Laufzeit.

Die App-Messung verwendet acht vollständig abgeschlossene Aufwärmframes und
anschließend 50 vollständig abgeschlossene Frames. Beim Öffnen erhalten Life und
Pong dieselbe Uhrzeiteingabe. Dafür setzt der Emulator vor dem lesenden
`millis`-Aufruf den vorhandenen Uhrzustand; der native Uhrcode läuft unverändert.
Anfangszustand, Endzustand, Fortschritt und Bild werden vollständig verglichen.
Jede Messung startet dreimal unabhängig.

Der feste Laufzeittest lädt acht Benutzer-Apps, entsprechend der Kapazität der
nativen App-Tabelle. Der neue GIF-Player bleibt außerhalb dieses festen
Vergleichssatzes und wird durch die eigenen Dateizugriffs- und Browsertests
geprüft. Der getrennte Lader-Benchmark prüft weiterhin alle elf Presets einzeln.

Ein früherer Vergleich wurde verworfen: Sein direkt gesetzter Zufallswert wurde
vom später abgearbeiteten Öffnungsereignis mit der echten Uhrzeit überschrieben.
Damit waren die Spieleingaben unterschiedlich. Das korrigierte Messformat
verlangt ausdrücklich die gemeinsame Uhrzeiteingabe und lehnt alte Aufnahmen ab.

Messwerte: [pad-geometrie-zahlen.json](2026-10-20-pad-geometrie-zahlen.json).
