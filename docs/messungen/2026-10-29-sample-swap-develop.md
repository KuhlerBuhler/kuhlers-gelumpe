# Sample-Swap: Abgleich mit develop und dynamischer Projekt-RAM

Stand: 29.10.2026. Beleg: `measure:2026-10-29/sample-swap-develop`.
Fortsetzung der [Korrektur von Veröffentlichung und Cache-Deskriptor](2026-10-29-sample-swap-korrektur.md).
Der erste Abgleich verwendet den festen develop-Stand `4749d9f`.

## Hergeleitet: Risiko beim Zusammenführen

Der gefährlichste Integrationsfehler wäre gleichzeitig benutzter RAM:
Der obere Sample-Cache reicht bis `0xC4000000`, während die Projektforschung
ab `0xC3000000` einen möglichen Arbeitsbereich prüft. Ein Text-Merge
beweist deshalb keine sichere gemeinsame Nutzung.

Die dynamische Nutzung ist festgelegt. Ein Projektwechsel darf den
Cache nur nach exklusiver Übernahme, entwerteten Ladeaufträgen und
bestätigtem Leserabschluss ausleihen. Die großen Projektsicherungen sind
nur bis zum geprüften Abschluss oder Rückweg erforderlich. Bei einem
fehlgeschlagenen Rückweg bleiben Speicher und Sperre erhalten. Danach
muss der Swap den gültigen Index erneut lesen und den Cache neu aufbauen.
Es gibt keine feste Verkleinerung auf 31 MiB und keine zusätzliche
Begrenzung der Sampledatei auf der Karte.

## Gemessen im Modell: Überschneidung bleibt geschützt

Die strenge `project_area_errors`-Prüfung verweigert die Überschneidung
weiterhin. `project_area_requirements` unterscheidet davon die Planung
einer exklusiven Ausleihe: Der obere Cache wird als notwendiger Geber
benannt. Eine solche Planung erwirbt keinen RAM und umgeht keine
Laufzeitsperre. Andere Besitzer sowie Datei-Arbeitsbereiche sind weiterhin
verboten. Die gesperrte Bedienung ersetzt keinen Nachweis über noch
aktive CPU- oder DMA-Zugriffe.

Nach geprüfter Wiederherstellung hält das Projekt-Importmodell keine
zusätzlichen großen Sicherungskopien mehr. Eine unbestätigte
Wiederherstellung gibt sie nicht frei. Die gezielten Modellprüfungen
bestehen zusammen in 47 Tests.

Offen bleibt die tatsächliche Übergabe in der Firmware. Der Projektlader
ist auf diesem Stand weiterhin Forschung und Modell, keine installierte
Funktion. Die [Projektidee](../ideen/64-projekte.md) benennt diese Grenze
und die vereinbarte Reihenfolge.

## Gemessen: Textkonflikte und Prüfauswahl

Vier Textkonflikte werden zusammengeführt: die Patch-Freigabedaten,
die beiden Prüfungen des Patchsatzes und die zentrale Emulatorprüfung.
Die neuen Pattern-Startfunktionen und sämtliche Swap-Testgruppen bleiben
erhalten. Der Swap bekommt seine Beschriftung aus dem vorhandenen
mehrsprachigen Eintrag für zusätzlichen Sample-Platz.

Die gezielte Integration besteht mit 65 bestandenen und zwölf
übersprungenen Tests. Ein weiterer bestehender Test findet zunächst die
fehlende Swap-Gruppe in der neuen CI-Auswahl. Nach Ergänzung der beiden
Listen in Emulator und CI-Auswahl bestehen alle sechs Prüfungen dafür.
Unbekannte Änderungen wählen weiterhin alle Prüfgruppen aus.

Die drei Laufzeit-Builder für Stock, Synth und Hacktribe werden erneut
ausgeführt und ergeben den übernommenen Stand von develop. Der gesamte
kombinierte Patchsatz lässt sich für alle drei eigenen Originaldateien
erzeugen. Die Firmwaredateien bleiben außerhalb des Repos.

## Prüfstand

Der vollständige Unit-Lauf besteht mit 1348 bestandenen und 159
übersprungenen Tests, der Browserlauf mit 285 bestandenen und einem
übersprungenen Test. Die vollständigen Firmwareprüfungen bestehen mit
682 Checks für Stock, 657 für Hacktribe und 485 für Synth. Alle drei
Prozesse enden mit Status null.

Die geprüften Dateien werden nochmals mit dem aktuellen Patchsatz
verglichen. Erst danach werden ihre Hashwerte und Prüfzahlen über den
normalen Freigabedaten-Schreiber übernommen. Ein alter Hardwareeintrag
für Hacktribe auf dem blauen Gerät wird nicht ungeprüft übernommen.
Ein fehlerfreier Patch-Merge ist weiterhin keine Freigabe für die bekannten
offenen Speicherwege.

Während der Prüfung ist develop bis `ba5d348` weitergelaufen. Die obigen
Ergebnisse gelten für den genannten geprüften Stand `4749d9f` samt
Integration. Weitere Unterschiede werden getrennt geprüft.

Gesamtexport, Pufferübergabe, EXIT vor zusätzlichen Kartenzugriffen,
kontrollierter Abbruch unerfüllbarer Wechselziele und die übrigen Punkte
im [Korrekturbericht](2026-10-29-sample-swap-korrektur.md) bleiben offen.
Für die Integration wird nichts an das Gerät gesendet und nichts geflasht.

## Weiterer Abgleich mit develop

Der zweite Abgleich verwendet den festen Stand `ba5d348`. Die fünf
Textkonflikte betreffen die Patchsatzprüfungen, die RAM-Prüfung sowie
die Prüflisten von Emulator und CI. Sample-Swap bleibt neben den neuen
Prüfgruppen für Stereo-Pad und Doom registriert. Die gezielte Prüfung
besteht mit 62 bestandenen und zwölf übersprungenen Tests.

Hergeleitet: Der Stereo-Pad-Hook bei `0xC0099E2C` liegt hinter dem
Swap-Bereitschaftsschutz bei `0xC0099D88`. Seine Code- und
Einstellungsbereiche überschneiden sich nicht mit Sample-Swap. Das ist
kein Nachweis für unterbrechungsfreien Klang oder DMA-Zugriffe.

Der vollständige Unit-Lauf dieses Abgleichs besteht auf einem getrennten
Linux-Testrechner mit 1359 bestandenen und 159 übersprungenen Tests.
Drei Zeitlimitfehler auf dem stark belasteten Entwicklungsrechner werden
nicht als bestandene Prüfung gewertet. Der erste Linux-Lauf findet zwei
fehlende Voraussetzungen der Quellkopie: Ohne Git-Metadaten können weder
die Liste der versionierten Dateien noch der Schutz gegen Testdateien im
Repo geprüft werden. Nach Ergänzung des Index besteht der vollständige
Lauf mit unveränderten Prüfgrenzen und unverändertem Firmwarecode.

Der vollständige Browserlauf auf Linux besteht mit 285 bestandenen und
einem übersprungenen Test. Beide Prozesse enden mit Status null.

Ein Zwischenlauf der Firmwareprüfung meldet zwei abgebrochene
Fernsteuerungsgruppen: Der externe Compiler kann Node im Suchpfad des
Starters nicht finden. Derselbe Compileraufruf besteht mit ergänztem
Suchpfad. Der vollständige Wiederholungslauf verwendet bei unverändertem
Quellstand und denselben Abbildern den vorhandenen Aufgabencache. Abgebrochene
Aufgaben werden darin nicht als bestandene Ergebnisse übernommen.

Die vollständigen Firmwareprüfungen bestehen für diesen zweiten Abgleich
mit 712 Checks für Stock, 687 für Hacktribe und 494 für Synth. Alle drei
Prozesse enden mit Status null. Der vollständige Quellstand der
Linux-Prüfung umfasst 1424 versionierte Dateien. Vor und nach den Läufen
werden seine Hashwerte geprüft. Die drei dort erzeugten Firmwaredateien
stimmen mit den lokal erzeugten Abbildern überein.

Vor dem Schreiben der Prüfdaten wird der aktuelle lokale Patchsatz erneut
auf dieselben Originaldateien angewendet und mit den geprüften Abbildern
verglichen. Der normale Prüfdaten-Schreiber übernimmt danach genau diese
drei bestandenen vollständigen Ergebnisse.

Offen: Die dynamische Projekt-Ausleihe bleibt eine Modellanforderung;
eine native Speicherübergabe wird hier nicht ergänzt. Die oben genannten
Speicherblocker sowie Geräte-, Klang- und DMA-Nachweise bleiben offen.
