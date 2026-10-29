# Sample-Datei: Leser schließen und Zugriffe besitzen

Stand: 29.10.2026. Ergänzung zur
[dauerhaften Speicherung](2026-10-27-sample-store.md) und zum
[Bauplan](../plans/2026-10-27-sample-store.md).

## Gemessen mit erzeugtem ARM-Code: exklusiver Dateibesitz

`tools/patch/sample_owner.py` enthält einen Besitzer für den gemeinsamen
Dateizugriff. Sein Zustand umfasst das aktuelle Token, den letzten
Tokenwert, einen ungeklärten Katalogstand und die Zugriffsart. Es gibt
Lesen, Schreiben und Wiederherstellung. Der aufrufende Speicherweg
initialisiert diesen Zustand ausdrücklich.

Die 13 ARM-Fälle benutzen keine Firmware. Sie prüfen:

- Nach dem Start sind Lesen und Schreiben bis zur bestätigten
  Wiederherstellung gesperrt.
- Während eines Besitzes bekommen weitere Aufrufer kein Token.
- Alte oder falsche Token können einen anderen Aufrufer weder freigeben
  noch dessen Katalog als geprüft markieren.
- Ein Schreibversuch macht den Katalog ungeklärt. Die Freigabe allein
  bestätigt weder gespeicherte Daten noch einen gültigen Index.
- Auch ein Leser kann nach einem Fehler seinen Katalog als ungeklärt
  markieren. Erst ein geprüfter Wiederherstellungsweg gibt ihn wieder frei.
- Nur der aktuelle Leser mit geklärtem Katalog darf den Ladeweg benutzen.
- Tokenwerte laufen nicht auf alte Werte über. Unzulässige Aufrufkontexte
  verändern den Zustand nicht.
- Register, Stack und vorhandene IRQ-Maske bleiben erhalten. Die atomare
  Anforderung benötigt weniger als 80 emulierte Befehle mit maskierten IRQs.

Der Baustein installiert keine Firmware-Haken und führt selbst keine
Dateizugriffe aus. Die Koordination von Swap, nativen Menüs und USB ist
weiterhin anzuschließen. Die Befehlszahl ist keine Zeitmessung am Gerät.

## Gemessen im ARM-Modell: fehlgeschlagener Leserabschluss

Der bisherige Ladeweg ignorierte einen Fehler von `F_CLOSE` beim Wechsel
der Cache-Generation und öffnete denselben Datei-Arbeitsbereich erneut.
Bei einem Fehler während des Kopflesens blieb außerdem ein offener
Dateihandle zurück, ohne als offen geführt zu werden.

Der gemeinsame Abschluss `close_reader` behält jetzt drei Zustände:
geschlossen, offen und ungeklärter Abschluss. Vor dem nativen Schließen
wird der letzte Zustand gesetzt. Erst eine erfolgreiche Rückgabe macht
den Datei-Arbeitsbereich wieder verwendbar. Ein Fehler verhindert das
nächste Öffnen. Auch ein unvollständiges Kopflesen versucht den Abschluss;
schlägt dieser fehl, bleibt der Handle als ungeklärt erhalten.

Der Boot-Lader benutzt denselben Abschluss für einen vorhandenen
Swap-Leser. Seine Zustandsinitialisierung verliert den noch offenen
Handle nicht mehr vor dem Schließen. Die drei gezielten Fehlerprüfungen
und die vorhandenen Fälle bestehen zusammen mit 53 ARM-Tests.

## Gemessen im Emulator: native FatFs und unveränderte Sammlung

`tools/emu/reader_lifecycle_cases.py` prüft vier Fälle in beiden roten
Builds mit einer erzeugten Sammlung und der nativen FatFs:

1. Kopf nach einem Generationswechsel erfolgreich erneut lesen.
2. Beim Schließen einen Fehler zurückgeben, ohne den nativen Handle
   tatsächlich zu schließen. Es folgt kein erneutes Öffnen.
3. Nur 4092 statt 4096 Kopfbytes lesen. Der neue Handle wird geschlossen.
4. Unvollständig lesen und anschließend den Abschluss fehlschlagen lassen.
   Der Handle bleibt bis zu einem bestätigten Abschluss ungeklärt.

Die Fehler werden im Emulator an den API-Grenzen eingeschoben. Der
gesonderte anschließende Abschluss benutzt wieder die native Funktion
und besteht. Alle acht Fälle erhalten die Sammlung bytegleich und
verändern keine Sample-Metadaten. Es gibt keine Firmware-Assertion.

Die Leserbereinigung ist im neu gebauten Swap-Patch enthalten. Der
Dateibesitzer bleibt ein getrennter, getesteter Baustein. Die neuen
Firmwaredateien liegen außerhalb des Repos; die zuvor vollständigen
Emulatorprüfungen des älteren Laufzeitstands ersetzen keine vollständige
Prüfung dieses neuen Stands.

## Offen

- Dateibesitz an alle Lese- und Schreibwege anschließen.
- Einen ungeklärten Index nach Fehlern wiederherstellen und erneut lesen,
  bevor Nachladen oder neue Veröffentlichung weiterläuft.
- Slot-Versionen unabhängig von noch spielenden DSP-Plätzen verwalten.
- Normalen Import, Bearbeitung, Löschen, Aufnahme und USB dauerhaft anbinden.
- Die neue Laufzeit vollständig sowie Stimmen, DMA und Stromunterbrechung
  am Gerät prüfen. Es ist weiterhin keine Freigabe für 1.4.
