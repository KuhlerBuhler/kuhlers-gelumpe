# Sample-Swap: Prüfung des Feature-Diffs

Stand: 29.10.2026. Beleg: `measure:2026-10-29/sample-swap-review`.
Geprüft ist der Feature-Stand `222a525` gegenüber dem gemeinsamen Ausgangspunkt
mit `origin/develop`. Der Zeiger der Zielbranch liegt bei `532059c`.
Der gemeinsame Vergleichspunkt liegt bei `ebf254a`. Die Prüfung umfasst
Codequalität, Architektur und Folgewirkungen.

Ergebnis: drei hohe und drei mittlere Befunde, keine Freigabe für das
Gerät oder für 1.4. Die vorbereitete Testdatei ist entsprechend gekennzeichnet.
Der Laufzeitcode wurde während dieser Prüfung nicht geändert.

## Gemessen im Emulator

Alle Sampledaten der zusätzlichen Fälle sind selbst erzeugt. Die eigenen
Firmwaredateien, ausführbaren Reproduktionen und Rohprotokolle bleiben
außerhalb des Repos.

### Hoch: ungültiger Ladeauftrag wird noch veröffentlicht

In [sample_swap.py](../../tools/patch/sample_swap.py), Zeilen 1857 bis 1865,
liegen die letzte Kontextprüfung und die native CPU-Veröffentlichung
auseinander. Die IRQs sind in diesem Abschnitt nicht gesperrt.

Eine gezielt eingeschobene Generationsänderung unmittelbar vor dem
vorübergehenden Setzen des DSP-Frei-Zeigers lässt den alten Auftrag trotzdem
seinen Eintrag veröffentlichen. Stock und Hacktribe zeigen anschließend
das neue Sample als resident und erhöhen den Abschlusszähler. Die
Auftragsgeneration ist dabei bereits veraltet. Die Gegenprüfung mit
Hacktribe reproduziert dasselbe Ergebnis ohne Firmware-Assertion.

Hergeleitet: Die Unterbrechung durch die UI ist erreichbar. Die
[Task-Prioritäten](../hintergrund/skript-laufzeit.md) ordnen die UI mit
Priorität 4 vor der Command-Task mit Priorität 6 ein. Der UI-Haken kann bei
Bildschirmwechsel oder Fensteröffnung die Generation ändern. Der Versuch
erzwingt den genauen Zeitpunkt; er misst nicht die natürliche Häufigkeit.

Korrektur: Prüfung, Frei-Zeiger und CPU-Veröffentlichung müssen eine kurze
atomare Operation bilden. DSP-Übertragung und Part-Aktualisierung gehören
weiterhin außerhalb dieses Abschnitts.

### Hoch: Cache-Metadaten sind nicht durch die Prüfsumme geschützt

In [sample_swap.py](../../tools/patch/sample_swap.py), Zeilen 1831 bis 1852,
vergleicht der Patch die PCM-Summe und übernimmt anschließend den
Deskriptor aus dem RAM-Cache. Der Deskriptor ist nicht Bestandteil dieser
Prüfung.

Im gefüllten Cache wird ausschließlich das Sample-Ende auf 8000000
geändert. PCM und Generation bleiben unverändert. Beide roten Builds laden
den Cache-Eintrag und veröffentlichen in der Wiedergabetabelle dieses Ende,
obwohl nur 80000 PCM-Bytes vorhanden sind; richtig wäre 79998. Die
Gegenprüfung reproduziert das Ergebnis ebenfalls.

Korrektur: Deskriptor und relevante Zuordnungsdaten müssen in die
Integritätsprüfung eingehen. End- und Schleifengrenzen sind vor der
Veröffentlichung gegen die tatsächlich übertragene PCM zu prüfen.

### Hoch, bereits bekannt: Gesamtexport verkürzt die Bibliothek

Der [normale Patchsatz](../../data/patches/blech.json) bindet den Swap ein,
während der native Gesamtexport weiterhin erreichbar ist. Dieser schreibt
nur den residenten DSP-Inhalt über die Quelldatei.

Die vollständigen aktuellen Emulatorberichte belegen es für beide Builds:
Aus ursprünglich sechs Slots und 491488 Byte werden beim Gesamtexport ein
Slot und 45328 Byte. Der bestehende Test besteht, weil er die rechtzeitige
Cache-Freigabe prüft. Er verlangt ausdrücklich keinen Erhalt aller Slots.

Das ist ein bereits dokumentierter Blocker. Vor der normalen Freigabe müssen
die vereinbarten dauerhaften Speicherwege den Gesamtexport vollständig
ersetzen. Ein bloßes Entfernen des Menüeintrags erfüllt diese Aufgabe nicht.

## Gemessen im Offline-Modell der Gerätewerkzeuge

### Mittel: bestätigter BUSY-Abbruch umgeht die Wiederherstellung

[sample_swap_paths.py](../../tools/device/sample_swap_paths.py), Zeile 607,
ruft den gemessenen Kartenweg auf, nachdem die Test-PCM verändert wurde.
Eine Ausnahme nach bestätigtem BUSY mit null übertragenen Wörtern erreicht
den vorhandenen Wiederherstellungsweg nicht.

Mit erzeugter PCM und einer simulierten Verbindung bleibt die DSP-Kopie
verändert. Der Transportfehler ist null, die Originalkopie liegt noch im
Sicherungspuffer. Die Gegenprüfung bestätigt dieses Ergebnis. Eine unbekannte
EXEC-Rückkehr oder ein Timeout bleibt davon zu unterscheiden: Dann darf
keine blinde Wiederholung oder Bereinigung gesendet werden.

Korrektur: bestätigte Fehler typisiert weiterreichen und den gesunden,
bestätigten Fall kontrolliert wiederherstellen oder als expliziten
Wiederherstellungszustand melden. Der Schreibversuch ist bis dahin nicht
für unbeaufsichtigte Messungen geeignet.

### Mittel: Statistik verschweigt fehlende Einzelmessungen

[sample_swap_stats.py](../../tools/device/sample_swap_stats.py), Zeilen 65
bis 68, gibt bei einem Zählersprung nur den letzten Datensatz aus. Der
gezielte Wechsel von Zähler 4 auf 7 liefert ausschließlich Datensatz 7;
5 und 6 fehlen ohne Hinweis. Die Gegenprüfung bestätigt dies.

Korrektur: ausgelassene Zählerwerte ausdrücklich melden. Vollständige
Einzelmessungen benötigen kontrollierte einzelne Ladevorgänge oder einen
Puffer mehrerer Abschlüsse.

### Mittel: Bestätigung ersetzt keine aktuelle Zustandsprüfung

Die Vorprüfung und `run` in
[sample_swap_paths.py](../../tools/device/sample_swap_paths.py) prüfen den
nativen Code und den Swap-Modus, aber weder Hauptseite noch Transport oder
Sampling-Zustand. Die Bezeichnung als gestoppt oder spielend stammt allein
aus dem Aufrufargument.

Hergeleitet: Ein Moduswechsel nach der Bedienbestätigung wird nicht erkannt.
Das ist ein fehlender aktueller Zustandsnachweis, kein gemessener
DMA-Schaden. Korrektur: Zustand vor den einzelnen Zugriffen erneut prüfen
und eine Änderung vor dem nächsten Schritt zurückweisen.

## Gemessen am Gerät: nur die Vorprüfung

Die Verbindung über den Linux-Rechner antwortet auf Suche, INFO und
CRC-geprüfte RAM-Lesezugriffe. Der gelesene Swap-Modus ist `0xFFFFFFFF`,
der Transport steht auf STOP, Sampling ist aus. Der Bildschirm steht auf
45 ohne Fenster, nicht auf der geforderten Hauptseite 1.

Es wurde kein EXEC und kein WRITE gesendet. Karte, Takt, Samples und Flash
wurden nicht verändert. Eine zunächst versuchte direkte Registerabfrage
wurde vom RAM-Leseweg zurückgewiesen; die anschließende Vorprüfung liest
nur RAM. Es gibt deshalb keinen neuen Durchsatzwert für 25 MHz.

Die [bisherige 25-MHz-Messung](2026-10-27-sample-swap-transfer.md) bleibt
unverändert: gestoppt vollständig, unter Wiedergabe nicht abgeschlossen.
Der vollständige Swap-Test benötigt außerdem die korrigierte Testfirmware.

## Prüfstand und offen

Die vorhandenen vollständigen Tests bestehen weiter: 1158 Unit-Tests bei
153 übersprungenen, 220 Browsertests bei einem übersprungenen sowie 609
Firmware-Checks für Stock und 584 für Hacktribe. Hinzu kommen 31 bestandene
gezielte Prüfungen der Sample- und Transaktionsformate. Diese Ergebnisse
werden durch die zusätzliche Fehlersuche nicht nachträglich umgedeutet.

Die Veröffentlichungslücke und die ungeschützten Cache-Metadaten sind vor
einem neuen Gerätetest zu korrigieren und mit den gezielten Fehlerfällen
zu prüfen. Danach müssen die gebauten Firmwaredateien und Gesamtprüfungen
erneuert werden. Native Import- und USB-Anbindung, sichere Versionsbindung,
weitere Ausklangfälle und DMA-Nachweise bleiben eigene offene Aufgaben.
