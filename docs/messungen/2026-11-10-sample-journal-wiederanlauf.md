# Wiederanlauf mit einem unvollständigen Sample-Journal

Die [Kartenfehlerprobe](2026-11-10-sample-import-kartenfehler.md) beobachtet
ein 512 Byte langes `.txn` nach einem kurzen Schreibvorgang. Der Slot-Index
blieb unverändert, aber das Journal sperrte weitere WAV-Imports.

## Hergeleitet

Ein vollständiges Journal besteht aus 64 Byte Vorspann und dem 4.096 Byte
langen alten Dateikopf. Der Vorspann enthält die Prüfsumme des Journals
und die Prüfsummen des alten und des vorgesehenen neuen Dateikopfs.
Die Wiederherstellung öffnet die Bibliothek lesend. Alle noch
vorhandenen Kopfbytes im Journal müssen damit übereinstimmen. Mit dem
vollständigen Kopf im RAM prüft sie anschließend das rekonstruierte Journal,
einschließlich seiner gespeicherten Prüfsummen und Längengrenzen.

Nur wenn alles passt, wird das kurze Journal entfernt. Der vorhandene
Dateikopf und die Audiodaten bleiben unverändert. Die Wiederherstellung
übernimmt aus dem Fragment keinen neuen Slot. Ein vollständiges Journal
folgt weiterhin dem vorhandenen Wiederherstellungsweg.

## Gemessen im ARM-Modell

Fragmente von 64, 65, 512 und 4.159 Byte mit passendem altem Dateikopf
lassen sich entfernen. Ein zu kurzer Vorspann, ein verändertes Fragment,
ein bereits veränderter Slot-Index und eine Bibliothek, die kürzer als der
alte Bestand ist, werden abgewiesen. Ein Fehler beim Entfernen wird
weitergegeben. In allen Fällen bleibt die Bibliothek bytegleich; der
Wiederanlauf schreibt nicht in die `.all`.

## Gemessen im Menü auf Stock und Hacktribe

Die Gegenprobe verkürzt den Journal-Schreibvorgang von 4.160 auf 512 Byte.
Der erste Menüaufruf meldet Fehler 4; der Zielslot bleibt leer. Die Firmware
entfernt das geprüfte Fragment. Auch ein Neustart von der zuvor eingefrorenen
Karte mit dem Fragment entfernt es, ohne den alten Bestand zu ändern.
Der nächste Menüimport meldet Erfolg, hängt die exakten PCM am tatsächlichen
Dateiende an und zeigt den Namen. Ein von keinem Part verwendeter neuer
Slot bleibt zunächst ungeladen.

## Grenzen

Fehlen Teile des 64-Byte-Vorspanns und fehlt der
[Nachweis der Erstanlage](2026-11-10-sample-datei-erstanlage.md) oder
stimmt eine Prüfung nicht, bleibt das Journal erhalten. Ein abgebrochener Append kann weiterhin unverknüpfte Bytes am
Dateiende hinterlassen. Beim nächsten Import beginnt der neue Block am
tatsächlichen Dateiende. Der Wiederanlauf kürzt die Datei nicht.
