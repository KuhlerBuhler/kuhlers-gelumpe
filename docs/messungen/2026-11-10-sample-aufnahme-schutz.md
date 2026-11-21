# Aufnahmeabschluss und vorbereitete Auslagerungen

## Gemessen: neuer Eintrag aus Aufnahme oder Resampling

Im Modell ist die physische Zeile 600 vor der Aufnahme frei. Ein vorbereiteter
Swap-Auftrag und seine bereits geprüfte Platzsuche liegen noch vor. Der bisherige
Pfad geht mit unveränderter Schutzrevision in den nativen Aufnahmeabschluss.
Die vorbereitete Entscheidung bleibt gültig, obwohl die neue Aufnahme danach
einen DSP-Bereich belegt.

Die Korrektur setzt das Schutzbit der **physischen** Zeile nach dem erfolgreichen
Lesen des DSP-Endzeigers und vor der ersten Änderung des freien DSP-Zeigers bei
`0xC004F188`. Die Schutzrevision steigt, der vorbereitete Auftrag und sein
bereitgestellter Puffer werden ungültig. Anschließend schreibt der native
Abschluss weiterhin die Aufnahme. Eine vorbereitete Prüfung lässt die neue
Zeile nicht mehr als Auslagerungskandidat zu.

Beide roten gepatchten Abbilder führen den nativen Abschluss mit denselben
Ergebnissen aus. Die Gegenprobe gibt einen erzeugten DSP-Endzeiger vor und
ersetzt die native Initialisierung der Zeile. Eine ergänzende ARM-Prüfung
deckt die unveränderte Rückkehr beim DSP-Fehler und den nativen Weg bei
uninitialisiertem Swap ab. Der Dateioffset eines Hakens ist
`file = ram - 0xC0000000 + 0x100`.

## Gemessen: Pattern-Import in der Cache-Prüfung

Der rote Cache-Fall schlägt vor und nach Anschluss des WAV-Imports gleich fehl.
Der Cache ist aufgebaut und wird verworfen. Die alte Folge von Tastendrücken
erreicht wegen der zusätzlichen Kartenordner nicht die exportierte Pattern-Datei.
Die Dateispur zeigt erst bei Auswahl des tatsächlichen Exports einen Leseaufruf
für `SD:/KORG/blechtribe/electribe_sampler_allpattern.e2sallpat`. Die Prüfung
ermittelt die Dateiposition aus den Verzeichniseinträgen der erzeugten Karte.
Der Anspruch an die Prüfung bleibt gleich: Der native Import muss tatsächlich
in den Arbeitsbereich schreiben, und der Cache muss vorher verworfen sein. Im
gezielten Stock-Fall sieht die Prüfung 1.041.408 native Schreibzugriffe in
diesem Bereich, keinen davon vor dem Verwerfen des Caches.

## Offen

Die Gegenprobe bildet den CPU-Abschluss ab. Sie misst weder den Klang noch
die echte DMA-Nutzung während der Aufnahme. Die gemeinsame Aufnahme- und
Resampling-Routine schützt neue DSP-Zeilen, speichert sie jedoch noch nicht
dauerhaft in der Bibliothek. Das Verhalten am Gerät bleibt gesondert zu prüfen.

Der spätere [Anschluss von WRITE und Löschen](2026-11-11-sample-aenderungen-speichern.md)
beschreibt die dauerhafte Speicherung der bestätigten Aufnahme getrennt.
