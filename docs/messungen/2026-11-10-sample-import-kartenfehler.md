# WAV-Import: Kartenfehler und Wiederanlauf

Die Prüfung benutzt das Gerätemenü des roten Samplers mit erzeugten WAVs und
einer erzeugten FAT32-Karte. Zwei Samples liegen vor dem Import in der
Bibliothek. Der Vergleich liest die alten Dateibytes und nach dem Neustart
die PCM beider alten DSP-Slots. Ein neuer Slot zählt nur, wenn sein Index
auf den vollständig angehängten Block zeigt und seine PCM bytegleich sind.

## Gemessen

| Fehler oder Neustartpunkt | Ergebnis |
|---|---|
| Karte mit nur vier freien Clustern, WAV passt nicht | Menü meldet Fehler. Die alten Samples bleiben erhalten, der neue Index bleibt leer. |
| Neustart nach dem Anhängen, vor dem Journal | Die alten Samples bleiben erhalten. Der neue Block ist noch nicht im Index sichtbar. |
| Neustart mit geprüftem Journal, vor der Indexänderung | Die Firmware stellt den Index wieder her und lädt das vollständige neue Sample. |
| Zwei von vier Bytes des neuen Indexeintrags geschrieben | Das Menü meldet den Schreibfehler. Das geprüfte Journal stellt den vollständigen Index wieder her, auch beim Neustart von diesem Kartenstand. |
| Einmaliger Fehler beim Entfernen des geprüften Journals | Das Menü meldet den Fehler. Nach der Wiederherstellung ist das neue Sample vollständig und das Journal entfernt. |
| 512 von 4.160 Journalbytes geschrieben | Die alten Samples bleiben bytegleich, der neue Index bleibt leer. Das unvollständige Journal bleibt liegen. Auch nach Neustart wird ein weiterer Import abgewiesen. |

Keiner der Importpfade belegt beim Import selbst einen neuen DSP-Slot. Die
Gegenproben liegen in
[`sample_import_card_cases.py`](../../tools/emu/sample_import_card_cases.py).
Die Neustarts beginnen mit Kopien der SD-Sektoren an den beobachteten
Schreibgrenzen. Die kurzen Schreibvorgänge sind echte kurze FatFs-Aufrufe
im Emulator; das Modell kann keine beliebigen Auswirkungen eines
Stromausfalls im Controller der Karte nachbilden.

## Folgestand und offene Gerätemessung

Der [Wiederanlauf nach einer unvollständigen Schreibung](2026-11-10-sample-journal-wiederanlauf.md)
beschreibt die Korrektur für den gemessenen Fehler.

Eine abgebrochene Transaktion kann unverknüpfte Bytes am Dateiende
hinterlassen. Das Format verweist dann nicht auf sie; die Prüfung
verlangt keine automatische Verdichtung. Verhalten echter Karten bei
Stromverlust, bei einem physischen Entfernen der Karte und bei Schreibfehlern
im Controller bleibt separat zu messen.
