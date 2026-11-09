# Sample-Swap: Namen vor dem Laden der Audiodaten

## Gemessen im Emulator

Die Gegenprobe benutzt erzeugte Samples in den Slots 501, 502, 504 und
999, intern 500, 501, 503 und 998. Nur Slot 501 gehört zum Startpattern.
Mit dem vorherigen Patch liefert die native Namensabfrage für die drei
übrigen, nicht residenten Samples keinen Namen. Mit der Namenserweiterung
liefert sie deren tatsächliche Namen, während weiterhin nur das Sample
des Startpatterns im DSP liegt. Stock und Hacktribe zeigen dasselbe Ergebnis.

Der native Parser wird für die drei übrigen Einträge im Metadatenmodus
aufgerufen. Zu Beginn jedes dieser Aufrufe ist der aktive Satz bereits
geladen. Die 27 beobachteten Datei-Leseanforderungen überschneiden sich
mit keinem PCM-Bereich. Die Namen benötigen damit zusätzliche
Metadatenlesungen, aber kein Vorladen der übrigen Audiodaten.

Eine zusätzliche native Bedienprobe hält die Dateileihe vorübergehend
belegt. Nach Drehen des OSC-Rads fordert der Part intern Slot 501 an,
sein tatsächlicher Slot bleibt 500 und Slot 501 ist noch nicht resident.
Die echte UI fragt in diesem Zustand bereits dessen richtigen Namen ab.
Nach Freigabe der Leihe wird der angeforderte Slot geladen und gebunden.
Diese Probe beobachtet die UI-Aufrufe und ist kein physischer Displaytest.

Die Modellprüfungen führen den erzeugten ARM-Code aus. Sie prüfen:

- Nur die 16 Namensbytes eines indizierten, nicht residenten Slots ändern
  sich. Metadaten, Playback und die drei Importzuordnungen bleiben gleich.
- Bereits geladene Namen und eine während der Lesung neu geladene Zeile
  werden nicht durch den Dateinamen überschrieben.
- Fehlgeschlagene Lese-/Seek-Aufrufe, falsche Slotnummern und gewechselte
  Generationen veröffentlichen keinen Namen.
- Die Anzeigeprüfung verändert keine tatsächliche PCM-Residenz. Außerhalb
  des Swap-Modus gelten die nativen Ergebnisse weiter.
- Ein reparierter Dateieintrag verliert nach erneuter Prüfung die alte
  Quellen-Fehlermarke und wird wieder auswählbar.

Die Gegenprobe zur letzten Eigenschaft scheiterte zunächst: Die erste
Katalogprüfung markierte den alten fehlerhaften Eintrag; nach seinem
Ersetzen blieb die Marke stehen. Vor der abschließenden Prüfung werden
die Quellenmarken jetzt zurückgesetzt. Noch ungültige Einträge werden
dabei erneut markiert. Die separate DSP-Fehlersperre bleibt bestehen.

## Hergeleitet aus beiden Originalen und dem Patch

Der 4096-Byte-Kopf der `.all` enthält die Slot-Offsets. Die einzelnen Namen
stehen in den Sample-Metadaten. Die vorhandene
[RAM-Namenstabelle](2026-10-07-sample-name-ram.md) wird als Katalog benutzt:
`0xC047B080 + Slot * 0x20 + 12`, jeweils 16 Bytes. Importnummer, Kategorie
und Belegung werden durch die Namenslesung nicht verändert.

Die Reihenfolge beim Start ist Kopf, PCM des aktiven Patterns, danach
Metadaten der übrigen indizierten Slots. Der Durchlauf erfolgt vor dem
Schließen der noch geöffneten Startbibliothek. Vor dem Namensdurchlauf
wird ihr aktueller 4-KiB-Index erneut vollständig gelesen und geprüft.
Die vorhandene Parserprobe
`PREP=1` beendet den Parser vor dem Eintragen oder Übertragen von PCM.
Die Namensveröffentlichung prüft die Generation und Residenz erneut unter
einer kurzen IRQ-Sperre. Dateioperationen laufen außerhalb dieser Sperre
unter dem bestehenden Bibliotheksbesitz. Es gibt keinen zusätzlichen
RAM-Bereich für einen zweiten Namenskatalog.

Die native Namensabfrage `0xC0099788` verwirft normalerweise Namen, wenn
`0xC0099634` keine residente physische Zeile findet. Nur der Aufruf an
`0xC00997CC` bekommt im Swap-Modus eine zusätzliche Prüfung des
indizierten, nicht gescheiterten Slots. Die echten PCM- und Part-Prüfungen
behalten ihre Aufgabe: Der bisherige Part bleibt gebunden, bis die
angeforderten Audiodaten bereit sind.

Die native Löschung beim Auslagern, `0xC004E558`, verändert die
Belegungsdaten, lässt die Namenszeile aber stehen. Ein zusätzlicher
Sicherungspuffer für den Namen ist deshalb nicht erforderlich.
Nach einer geprüften Dateiänderung werden die Namen der nicht residenten
Einträge erneut gelesen. Geladene, möglicherweise bearbeitete Namen
werden erhalten.

## Leerer Index und tatsächlicher Ladeabschluss

Eine weitere Gegenprobe verwendet eine große erzeugte Datei mit leeren
Slot-Offsets und weiterhin vorhandenen alten PCM-Blöcken. Vor dem Start
steht ein älterer, nicht leerer Index im RAM. Der frühere Durchlauf kopiert
den Index erst beim ersten belegten Slot; bei einem leeren Index fehlt
dieser Aufruf. Dadurch konnte die Namensabfrage einen Phantomnamen aus
dem alten RAM-Katalog liefern. Die native Gegenprobe reproduziert das.

Das erneute Lesen des aktuellen Headers beseitigt diesen Fall ohne eine
neue RAM-Fläche. Seek-, Read-, Kurzlese- oder Headerfehler schließen die
Datei und sperren den unsicheren Katalog. Ein gültiger leerer Index bleibt
leer, auch wenn die Datei wegen älterer Datenblöcke groß ist.

Beim großen Bibliothekstest war eine feste Wartezeit nach dem Start keine
gültige Fertigmeldung mehr: Die Metadatenlesungen liefen noch, die
Bedienseite war nicht freigegeben und PLAY wurde ignoriert. Die Probe
wartet jetzt begrenzt auf die freigegebene Bibliotheksleihe und ein
geschlossenes Fenster, verlangt danach PLAY und prüft erst dann den
Patternwechsel samt geladenem Satz. Das ist keine Messung der Startzeit
am Gerät.

## Kurze Leseantworten

Die native Fehlerprobe meldet auch eine Lücke des ursprünglichen Parsers:
Eine zu kurze Antwort mit Erfolgsstatus kann als gültiger Metadateninhalt
weiterlaufen. Die Prüfung sitzt deshalb an den sieben Datei-Lesestellen
des Metadatenteils:

`0xC0035B3C`, `0xC0035BA4`, `0xC0035C08`, `0xC0035CF8`,
`0xC0035DA8`, `0xC0035DE8`, `0xC0035E18`.

Bei `PREP=1` muss die tatsächliche Länge der angeforderten Länge
entsprechen. Andernfalls geht ein I/O-Fehler an den Parser zurück. Ein
bereits gemeldeter nativer Fehler bleibt erhalten. Die beiden späteren
PCM-Lesestellen gehören zum Ladebalken und werden hier nicht verändert.
Die vollständigen nativen Funktionen und alle Aufrufstellen werden beim
Bau gegen beide roten Originale geprüft.

## Prüfstand

Die abschließenden Prüfungen bestehen auf unverändertem Quellstand:

- 117 ARM-Modellprüfungen, darunter die Namen-, Leerindex- und
  Lesefehlerfälle.
- `npm test`: 1374 bestanden, 161 übersprungen, keine Fehler.
- `npm run test:e2e`: 285 bestanden, eine übersprungen, keine Fehler.
- Stock und Hacktribe: jeweils 161 Prüfungen des kombinierten Patchsatzes
  für Swap, Ladebalken und Start bestanden. Darin liegen 31 Swap-Gruppen,
  neun Ladebalkengruppen und 15 Startszenarien.

Die nativen Läufe verwenden `--cases swap_cases,loadbar_cases`. Das ist
eine gezielte Prüfung und keine vollständige Veröffentlichungsprüfung
aller Patches. `data/patches/verified.json` wird dabei nicht erneuert.

## Offen

Die Namenserweiterung wurde noch nicht auf dem Gerät installiert. Ein
physischer Displaytest und die zusätzliche Startzeit durch viele kleine
SD-Lesungen fehlen. Die Emulatorabfrage ist kein Nachweis der gemessenen
Gerätegeschwindigkeit oder einer vollständig geprüften LCD-Darstellung.

Die [RAM-Aufnahmeprüfungen](2026-11-06-sample-ram-aufnahme.md) sind eine
getrennte Messung mit der minimalen Messfirmware. Import, Export,
Bearbeiten, Löschen und der vollständige RAM-/DMA-Besitznachweis bleiben
offen. Die Namenserweiterung gibt den neuen Swap-Cache nicht frei.
