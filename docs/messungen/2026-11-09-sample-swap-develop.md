# Sample-Swap mit dem aktuellen BLECH-Satz

Stand: 2026-11-09. **Gemessen im Emulator** und mit erzeugten WAVs.
Kein Gerätezugriff, kein Klang- oder DMA-Nachweis. Untersucht werden die
rote Sampler-Firmware 2.02, Stock und Hacktribe, sowie der unveränderte
Ausschluss des Sample-Swap auf der blauen Synth-Firmware.

## Zusammenführung

Der zusammengeführte Stand enthält sowohl den Sample-Swap einschließlich
[Besitzerprüfung](2026-11-09-native-dsp-besitz.md) als auch die aktuellen
Oszillator-, Touch-Scale- und Bedienkorrekturen von `develop`.

Die Konflikte betreffen fünf Dateien:

| Datei | Auflösung |
|---|---|
| `test/blech-set.test.mjs` | Swap und beide neuen Patches bleiben in der erwarteten Reihenfolge |
| `test/patcher.test.mjs` | Die Auswahl pro Build enthält Swap; die beiden Stock-Erweiterungen bleiben berücksichtigt |
| `tools/ci/verify-scope.mjs` | Swap-, Oszillator- und Touch-Scale-Fälle bleiben Teil der Prüfgruppen |
| `tools/emu/check.py` | Dieselben Prüfgruppen und ihre Beschreibungen bleiben erhalten |
| `data/patches/verified.json` | Die vorhandenen Nachweise von `develop` bleiben unverändert; kein Nachweis für die neue Ausgabe wird behauptet |

**Gemessen:** Die gezielten Listen-, Patchsatz- und Prüfumfangstests bestehen
mit 55 erfolgreichen und zehn mangels eigener Eingaben übersprungenen Fällen.

## Gemessen: Kollision der Codeflächen

Die reine Textzusammenführung verdeckt noch eine Überschneidung. Der aktuelle
Splash-Editor belegt ab `0xC01A2500` insgesamt 2.772 Bytes und endet damit bei
`0xC01A2FD4`. Der bisherige Swap-Code beginnt bei `0xC01A2FD0`. Vier Bytes
würden gleichzeitig zu beiden gehören; der Patcher lehnt den vollständigen
Satz deshalb ab.

Der Swap beginnt jetzt ausgerichtet bei `0xC01A2FE0`. Das Ende der bestehenden
Reservierung bleibt `0xC01A3C00`. Der Code wird neu assembliert und alle Haken
werden neu berechnet. Es entsteht kein neuer RAM-Bereich. Der bisherige
Codeumfang von 2.896 Bytes passt weiter in die Fläche; 208 Bytes bleiben frei.
Für die Dateiposition gilt `file = ram - 0xC0000000 + 0x100`.

Ein eigener Test prüft die tatsächlichen erzeugten Codeflächen gegen den
aktuellen Splash-Editor. Er scheitert vor der Verschiebung und besteht danach.
Anschließend lassen sich die vollständigen Sätze für Stock, Hacktribe und
Synth wieder ohne Überschneidung bauen. Die drei erzeugten Plugin-Laufzeiten
wurden ebenfalls mit ihren Buildern geprüft.

Ein weiterer Integrationstest meldet zunächst die fehlende Zuordnung der
Prüfgruppe `swap` in der neuen Rettungsseite. Die Gruppe gehört nun wie die
übrigen Sample-Prüfungen zum Sample-Bereich. Die bestehende Vollständigkeits-
und Verhaltensprüfung besteht anschließend; ihre Erwartungen bleiben erhalten.

## Gemessen: große Sample-Dateien

Die bestehende Dateiverarbeitung in `src/sample-file.mjs` hat keine Grenze
bei 25 MiB. Eine zusätzliche Gegenprobe erzeugt 24 WAV-Einträge mit je zwei
MiB PCM. In diese über 48 MiB große `.all` wird ein weiterer Eintrag angehängt.
Die Datei ist anschließend über 50 MiB groß; vorhandene Audiodaten sind
unverändert und es muss kein bestehender Eintrag verschoben werden.

Der getrennte Leseweg listet alle 25 Namen und Formate mit weniger als
16 KiB gelesenen Daten. Die Audiodaten werden dafür nicht gelesen.
Der vollständige Dateitest besteht mit 14 Fällen.

Die native Gegenprobe `case_long_set` verwendet auf beiden roten Builds eine
Datei mit über 50 Millionen Bytes und dem echten DSP-Budget. Beim Start wird
nur der vom ersten Pattern benötigte Slot geladen. Ein Patternwechsel lädt
die neuen benötigten Slots nach; die großen unbenutzten Einträge bleiben
außerhalb des DSP. Beide Gegenproben bestehen im Emulator.

## Abschlussprüfung

Die funktionalen Gegenproben bestehen auf beiden roten Builds mit je 64
Fällen: 45 Besitzer-/DSP-/PCM-Fälle und 19 Fälle für große Bibliothek,
Pattern-/Chain-Sperre, Auswahl, Namen, Stimmenmodell und Speicherdienst.
Die Startprüfung besteht für Stock, Hacktribe und Synth jeweils mit 21 Fällen.
Der Browser-Gesamtlauf besteht mit 324 erfolgreichen Tests ohne Auslassung.

Ein erster Unit-Lauf findet die fehlende Rettungszuordnung. Nach deren
Korrektur endet eine native Laufzeitgruppe im Zeitlimit; isoliert bestehen
alle 54 Fälle in etwa 218 Sekunden bei unveränderter 900-Sekunden-Grenze.
Die genaue Ursache dieses Zeitfehlers ist nicht nachgewiesen.

Ein weiterer Gesamtlauf bleibt im Transport synthetischer JSON-Prüfdaten
stehen. Die Prozessprobe zeigt, dass der Python-Unterprozess bei `stdin.read`
auf das Eingabeende wartet; beide beteiligten Prozesse verbrauchen keine
Rechenzeit. Dieselbe Gruppe besteht isoliert. Die JSON-Aufrufe verwenden
jetzt den bestehenden asynchronen Prozesshelfer, der die Eingabe ausdrücklich
beendet und den Kindprozess begrenzt. Ein neuer Test für leere Eingabe,
300-KB-UTF-8-Eingabe und Binärdaten scheitert vor der Erweiterung und besteht
danach. Alle 20 zugehörigen Prüfungen bestehen mit unveränderten fachlichen
Erwartungen. Für die JSON-Aufrufe wird eine 30-Sekunden-Grenze ergänzt;
die bisherigen nativen Prüfgrenzen werden nicht erhöht.

Der abschließende vollständige Unit-Lauf besteht mit 1.491 erfolgreichen
und 168 übersprungenen Tests ohne Fehler. Die
anschließend verschärfte Behandlung von Transportfehlern besteht zusätzlich
in der gezielten Wiederholung: Ein getöteter Vergleichsprozess darf nicht
als erwartete fachliche Ablehnung gelten.

Das Systemprotokoll zeigt lange Ruhephasen des Macs während der Zeitfehler.
Die Python-Laufzeitmessung nutzt `mach_absolute_time()`; die protokollierten
Fristen und Laufzeiten laufen dabei auseinander. Ein auf die Dauer des letzten
Prüfprozesses begrenzter Leerlaufschutz hält den Rechner für die Prüfung wach.
Der Nachweis einer einzelnen alleinigen Ursache des Zeitfehlers bleibt offen.

**Gemessen nach der zweiten Zusammenführung:** Die neue Teststeuerung von
`develop` beendet den Unit-Lauf mit 1.529 erfolgreichen und 168 übersprungenen
Tests sowie den Browserlauf mit 324 erfolgreichen Tests ohne Auslassung. Die
gezielte Prüfung der drei aufgelösten Konflikte besteht mit 28 Fällen. Die
je 64 Swap-Fälle auf beiden roten Builds und die je 21 Startprüfungen auf
allen drei Builds bestehen erneut. Die drei neu assemblierten Plugin-Laufzeiten
sind bytegleich zu den erzeugten Dateien aus `develop`.

Die folgende Zusammenführung der Auslastungsprüfung hat nur einen Konflikt
in der Entwicklungsdokumentation. Firmware-Patches und Patchdaten bleiben
dabei unverändert. Die 23 gezielten Prüfungen für Auslastungsprüfung,
Teststeuerung und Dokumente bestehen. Die Merge-Vorschau gegen den geprüften
Stand von `develop` meldet keine Konflikte.

## Grenzen und kürzester Weg zum Gerätetest

Die Seite `BLECHTRIBE -> Samples` kann vorhandene `.all`-Dateien am Rechner
bearbeiten und WAVs hinzufügen. Die Datei kann mit einem Kartenleser auf die
Testkarte kopiert werden. Dafür ist kein neues Dateiformat erforderlich.
Die Slots 501 bis 999 bleiben die vorhandenen Nutzerplätze. Die endliche
Slotzahl und die Karten-/Dateisystemgrenzen verschwinden durch Swap nicht.
Der USB-Dateiweg hat weiterhin seine eigene 256-MiB-Grenze.

**Offen beim Develop-Abgleich:** Der normale Gerätebefehl `Menü -> DATA UTILITY -> IMPORT SAMPLE`
verwendet weiterhin den nativen DSP-Import. Der vorhandene dauerhafte Dienst
`store_import` ist noch nicht an diesen Bedienpfad angeschlossen. Eine große
vorbereitete Datei und ein im Gerät über die DSP-Grenze hinaus importiertes
Sample sind deshalb zwei getrennte Nachweise. Der normale Import darf nicht
als unbegrenzt oder dauerhaft angeschlossen bezeichnet werden.

**Gemessen und hergeleitet für den nächsten Anschluss:** Der native WAV-Import
beginnt bei `0xC003644C`, mit dem Pfad in `r0` und dem Zielslot oder -1 in `r1`.
Im erzeugten Stock-Fall wird `SD:/imp.wav` über `f_open` geöffnet, Rückkehr bei
`0xC0036470`, und dem Parser mit Rückkehr bei `0xC00364B8` übergeben. Der
164-Byte-Bereich bis zum folgenden Lader ist in Stock und Hacktribe bytegleich.
Der bisherige Wrapper liefert 0 bei Erfolg und 4 bei Dateiöffnungs- oder
Schließfehlern; Parserfehler gibt er weiter. An dieser Stelle ist noch kein
neuer Haken eingebaut.

Der nächste Anschluss muss die Dateibesitzprüfung, den nativen Command-Task,
das geprüfte Anhängen mit Journal und die anschließende Katalogaktualisierung
zusammenführen. Ein fehlgeschlagener Import darf weder einen falschen Index
noch eine Erfolgsmeldung hinterlassen. Die neue Schutzrevision bei Aufnahme
und Resampling und der vollständige RAM-/DMA-Besitznachweis bleiben daneben
offen.

Die vollständige Firmware kann vor einer Übernahme nach `develop` aus diesem
zusammengeführten Stand gebaut und im Emulator geprüft werden. Eine bestandene
Emulatorprüfung ist keine Freigabe für Klang, echte Stimmenlaufzeit oder
unterbrechungsfreie Live-Wechsel. Das bleibt mit normalen Samples am Gerät
zu prüfen. Die vorhandene `verified.json` wird durch diese Teilprüfung nicht
als vollständiger Release-Nachweis erneuert.

Der spätere [WAV-Import in die Sample-Datei](2026-11-10-sample-import-karte.md)
ist separat gemessen.
