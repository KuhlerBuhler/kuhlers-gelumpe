# Wiederanlauf nach abgebrochener Erstanlage der Sample-Datei

## Hergeleitet

Das [FatFs der Firmware](../hintergrund/sample-datei.md) kann Dateien nicht
umbenennen. Vor dem ersten Schreibzugriff legt der Patch deshalb eine leere
Statusdatei an und schließt sie. `.txh` gehört zum neuen Bibliothekskopf,
`.txp` zum Journal. Beide Endungen sind für den Patch reserviert. Bestehende
Dateien werden beim Anlegen nicht überschrieben.

Der Patch öffnet eine so markierte Bibliothek lesend. Entsprechen die
vorhandenen Bytes exakt dem Anfang eines leeren Kopfs, ergänzt er nur die
fehlenden Bytes. Ohne passende Markierung wird ein unvollständiger Kopf
nicht verändert. Nach der erneuten Prüfung des vollständigen Kopfs entfernt
der Patch `.txh`, bevor er Samples anhängt.

Bei einem Journal unter 64 Byte prüft der Patch die Markierung, den
vorhandenen Anfang der Signatur und der Version sowie den gültigen
Bibliothekskopf. Soweit vorhanden, vergleicht er die Bytes der alten
Kopfprüfsumme. Ohne diese Übereinstimmung bleiben die Dateien erhalten.
Der Patch entfernt `.txp` nach der vollständigen Journalprüfung und
bevor er erstmals den Index ändert. Darum kann ein markiertes, sehr kurzes
Journal keinen begonnenen Indexwechsel belegen. Seine Bereinigung schreibt
keine Bytes in die Bibliothek. Ein vollständiges Journal kann weiterhin
einen begonnenen Indexwechsel zu Ende bringen.

Beim Laden prüft der Patch zuerst das Journal. Fehlt es, öffnet die
Firmware die Bibliothek direkt. Nur für einen vorhandenen Kopf unter
4.096 Byte schließt sie die Datei, prüft die Statusdateien und öffnet
die Bibliothek anschließend einmal neu. Eine Statusdatei ohne ihr Ziel
und die Statusdatei eines bereits vollständigen Kopfs können bis zum
nächsten Schreibvorgang liegen bleiben. Vor dem Schreiben wird der
Wiederanlauf weiterhin vollständig geprüft.

## Gemessen im Menü auf Stock und Hacktribe

Der Emulator begrenzt den ersten Schreibvorgang des Bibliothekskopfs auf
0 oder 512 Byte und den des Journals auf 0 oder 63 Byte. Der Menüimport
meldet jeweils Fehler 4. Für den Neustart verwendet der Test das
Kartenabbild von vor der Bereinigung im laufenden Menü. Auf der Karte
liegen zu diesem Zeitpunkt die passende leere Statusdatei und genau die
erwartete Zahl geschriebener Bytes.

Alle vier Fälle kommen auf beiden roten Firmwares wieder ins Menü.
Die Statusdatei ist entfernt. Bei abgebrochenem Journal bleiben der alte
Index und die alten Audiodaten bytegleich. Der nächste WAV-Import meldet
Erfolg, verweist im Index auf die exakten neuen PCM und lässt den neuen
Slot zunächst ungeladen. Im ARM-Modell lässt sich auch nach einem zweiten
Schreibabbruch beim Ergänzen des Kopfs weiterarbeiten. Fremde Dateianfänge,
unmarkierte Fragmente und eine abweichende alte Kopfprüfsumme werden
abgewiesen.

## Gemessen: Kartenfehler vor der Eingrenzung der Startabfragen

Mit einer erzeugten Bibliothek von 50.680.384 Byte startet Hacktribe mit
Slot 500. Beim ersten PLAY meldet das erneute Öffnen der `.all` den
FatFs-Status 1. Swap sperrt den Wechsel. Der Fall ist mit dem Patch für
die Erstanlage und mit der späteren Korrektur des Importabschlusses
reproduzierbar. Die ältere Fassung ohne Statusdateien wechselt auf
Pattern 2. Stock wechselt auch mit der späteren Fassung.

Die Gegenprobe behandelt nur die beiden Statusdateien im Emulator als
fehlend, ohne deren Dateipfade an FatFs weiterzureichen. Die erzeugte
Karte enthält beide tatsächlich nicht. Mit demselben Hacktribe-Build
erreicht der Wechsel dann Pattern 2 und die Slots 500, 501 und 502 liegen
im DSP. Das grenzt den Auslöser auf die zusätzlichen Kartenabfragen ein.
Warum die Folgeabfrage fehlschlägt und ob das am Gerät auftritt, bleibt
offen.

## Gemessen: Patternwechsel mit gezielten Startabfragen

Mit der Prüfung nur bei vorhandenem Journal oder zu kurzem Kopf
wechselt derselbe Hacktribe-Fall wieder. Stock und Hacktribe starten mit
Slot 500 aus der 50.680.384 Byte großen Datei. Nach dem Wechsel auf
Pattern 2 liegen die Slots 500, 501 und 502 im DSP. Auch alle vier
Neustartfälle mit 0 oder 512 Byte Kopf und 0 oder 63 Byte Journal
bestehen auf beiden Varianten. Die Prüfungen verwenden erzeugte Samples
und echte Firmware im Emulator.

## Offen

Der Neustart im Emulator verwendet ein eingefrorenes FAT32-Abbild. Ein
echter Stromausfall, die Reihenfolge dauerhaft geschriebener SD-Sektoren
und ein defektes Dateisystem sind damit nicht nachgebildet. Ohne passende
Statusdatei lassen sich alte Fragmente unter 64 Byte weiterhin nicht
automatisch bereinigen.
