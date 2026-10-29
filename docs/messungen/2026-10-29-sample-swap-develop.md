# Sample-Swap: Abgleich mit develop und dynamischer Projekt-RAM

Stand: 29.10.2026. Beleg: `measure:2026-10-29/sample-swap-develop`.
Fortsetzung der [Korrektur von Veröffentlichung und Cache-Deskriptor](2026-10-29-sample-swap-korrektur.md).
Die Integration verwendet den festen develop-Stand `4749d9f`.

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
