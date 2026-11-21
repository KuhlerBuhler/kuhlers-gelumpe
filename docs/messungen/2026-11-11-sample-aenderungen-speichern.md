# Sampleänderungen mit WRITE dauerhaft speichern

## Gemessen im Emulator

Alle Karten, Samples und PCM-Gegenwerte dieser Prüfungen sind erzeugt.
Die erste Aufnahme ohne vorhandene Bibliothek wurde mit WRITE bestätigt.
Nach Neustart wurde ihr PCM bytegenau aus der neu angelegten Datei geladen.
Die Gegenprobe vor der Startprüfung verweigerte die Aufnahme, weil der
Katalogbesitz noch ungeprüft war.

Der vollständige BLECH-Satz besteht auf Stock und Hacktribe jeweils
177 Prüfungen einschließlich Startfällen. Darin sind 18 native Menüfälle
für diese Speicheranbindung enthalten: Sample Edit WRITE und EXIT,
verschobene physische Zuordnung, Löschen und gemeinsam benutzte Zeilen,
Audio In und Resampling mono/stereo, Verwerfen, Schreibfehler mit
Wiederholung, ausgelagerte Slots und Erstanlage. Erfolgreich gespeichertes
PCM wird nach Neustart bytegenau geprüft. Der beobachtete Flash-Spiegel
wird in diesen Speicherwegen nicht aufgerufen.

158 ARM-Modulprüfungen bestehen. Die getrennte Nachprüfung der letzten
Ablaufänderungen besteht mit 21 gezielten Fällen. Die Speicher- und
Patchverträge bestehen mit 33 Prüfungen bei vier ausgelassenen Prüfungen.
Beide roten Originale erzeugen denselben validierten Patch.

`npm test`: 1536 bestanden, 168 ausgelassen, keine Fehler.
`npm run test:e2e`: 323 bestanden, eine ausgelassen, keine Fehler.

## Hergeleitet

Der [WAV-Import](2026-11-10-sample-import-karte.md) und der
[journalisierte Slot-Schreiber](2026-10-27-sample-store.md) bilden den
gemeinsamen Kartenweg. Das Format bleibt `e2sSample.all`.

Der neue Haken bei `0xC0039708` liegt in der nativen WRITE-Aufgabe,
nach der Ermittlung des logischen Slots und vor dem bisherigen
RAM-Snapshot und Flashabgleich. Er schreibt den vollständigen Eintrag
an das Dateiende. Erst nach der geprüften Veröffentlichung wird der
native Bestätigungssnapshot bei `0xC0345A2C` übernommen. Sein
Gültigkeitsbyte liegt bei `0xC0345A20`. Fehler werden in das bestehende
Statusbyte der Befehlsaufgabe gegeben.

Der Kartenrecord braucht eine normalisierte logische Zuordnung. Der
native Bestätigungssnapshot braucht dagegen die ursprüngliche physische
Zuordnung. Der Snapshot-Leser hält beide Deskriptoren getrennt. Er
streamt vollständige PCM in begrenzten Blöcken; die gesamte Bibliothek
wird nicht in den RAM geladen oder neu geschrieben.

Der Haken bei `0xC00395B8` ersetzt das bestätigte Löschen. Zuerst wird
der Slot aus dem Kartenindex entfernt und der Katalog geprüft. Danach
folgt die native CPU-Löschung. EXIT einer noch unbestätigten Aufnahme
verwirft nur deren DSP-Zeile und schreibt keinen neuen Karteneintrag.
Die ursprünglichen Flash-Spiegelaufrufe werden in diesen beiden
Speicherwegen nicht benutzt. EXIT beim Start behält den nativen Weg.

Die Aufnahmeplatzsuche berücksichtigt in beiden Bibliotheksmodi sowohl
den Kartenindex als auch geladene native Zeilen und Aliase. Sie prüft
alle Zwischenzeilen der dreistufigen Zuordnung, bevor die native
Aufnahme eine davon neu initialisiert. Die Suche läuft nach dem
DSP-Aufnahmestopp. Ein nur
ausgelagertes Sample ist damit kein freier Aufnahmeplatz. Ein
bestätigter, eindeutig zugeordneter Snapshot kann seinen Auslagerschutz
verlieren; eine weiterhin gemeinsam benutzte physische Zeile bleibt
geschützt. Bestätigtes Löschen einer gemeinsam benutzten Zeile wird
vor jeder Kartenänderung abgewiesen.

Fehlt die Bibliothek beim Start, prüft der vorhandene Befehlsauftrag
Journal und Dateiabwesenheit unter demselben Dateibesitz. Ein Fehler
hält die Aufnahmeplatzsuche gesperrt. Eine bestätigte erste Aufnahme
legt die Bibliothek über den Slot-Schreiber an.

Misslingt das Schreiben einer bestätigten Aufnahme, bleibt ihr PCM
im DSP als verändert geschützt. Die native Oberfläche hat die Aufnahme
zu diesem Zeitpunkt bereits angenommen. Nach Beheben des Kartenfehlers
kann WRITE in Sample Edit die Speicherung wiederholen. EXIT aus der
Fehlermeldung ist kein Verwerfen dieser bereits angenommenen Aufnahme.

## Hergeleitet: Speicherbesitz

Die zusätzlichen Speicherroutinen liegen bei `0xC0186800` bis vor
`0xC0188000`. Der Builder prüft die belegten Bytes gegen FF auf beiden
roten Originalen; das vollständige Patchset prüft die RAM-Reservierungen.
Der getrennte DSP-Messbereich bei `0xC019E000` bleibt frei.

Der Snapshot verwendet den zuvor verworfenen oberen Cache unter dem
exklusiven Dateibesitz. Er teilt keinen Dateihandle mit dem offenen
Sample-Leser. Die Sample-Aufnahme und der Kartenschreiber benutzen
dieselbe Eintrittssperre. Ein aktiver Transport lässt keinen neuen
Speicherauftrag beginnen.

## Offen

Die Prüfungen benutzen erzeugte Dateien und bei Aufnahme und Resampling
eingespeiste DSP-Daten. Klang und Aufnahme-DMA werden damit nicht
nachgebildet. Gerätetests mit WRITE, Kartenfehlern, ausklingenden Stimmen
und einem Stromausfall bleiben nötig. Alte Blöcke bleiben nach
Ersetzen und Löschen in der Datei; der Slot-Index entscheidet, welche
Version gilt.

## Gerätetest vorbereiten

1. Zur installierten Basis passenden Testbuild und separate Testkarte verwenden.
   Ein geladenes User-Sample in Sample Edit ändern, WRITE drücken und nach
   Neustart Startpunkt, Name und Ton prüfen. EXIT ohne WRITE getrennt prüfen.
2. Audio In und Resampling jeweils mono und stereo aufnehmen, mit WRITE
   bestätigen und nach Neustart prüfen. Eine weitere Aufnahme mit EXIT verwerfen.
3. Ein entbehrliches Sample bestätigt löschen. Nach Neustart müssen der freie
   Slot und die übrigen Samples erhalten sein.
4. Auf der Testkarte Schreibfehler und Wiederanlauf prüfen. Bei fehlgeschlagenem
   Aufnahme-WRITE darf das PCM bis zur erfolgreichen Wiederholung nicht
   ausgelagert werden. Stromunterbrechungen erst mit gesicherten Testdaten prüfen.

Der Nachweis für Aufnahme-DMA, Cachebesitz und Live-Wiedergabe bleibt davon
getrennt und wird durch diese Speicherprüfungen nicht ersetzt.
