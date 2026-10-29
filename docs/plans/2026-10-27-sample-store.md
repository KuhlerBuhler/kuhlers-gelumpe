---
revision: 2
---

# Samples dauerhaft auf der Karte speichern

Stand: 29.10.2026. Der Speicherweg ist abgestimmt. Ergänzung zum
[Sample-Swap für 1.4](2026-10-27-sample-swap-1-4.md).

## Ziel und Umfang

Die Karte ist der dauerhafte Sample-Speicher. Der DSP enthält den gerade
benötigten Satz. `IMPORT SAMPLE`, bestätigte Bearbeitungen, Löschen,
Sampling und Resampling speichern jeweils ihren betroffenen Slot in
`e2sSample.all`. Ein voller DSP verhindert keinen Kartenimport.
`EXPORT ALL SAMPLE` entfällt, sobald alle zugehörigen Speicherwege ersetzt
und geprüft sind. Es reicht nicht, nur den Menüpunkt auszublenden.

Es gibt keine zusätzliche Grenze aus DSP-Größe oder einer willkürlichen
Dateigröße. Die derzeitige Datei verwendet weiterhin 32-Bit-Offsets;
FAT32 und das Format begrenzen die einzelne Datei technisch auf höchstens
4294967295 Byte. Die normalen Nutzerplätze bleiben 501 bis 999.
Eine spätere gemeinsame Projektdatei bekommt in diesem Schritt kein
neues, vorweggenommenes Containerformat.

## Schreibfolge

1. Alle Schreiber der Sammlung benutzen denselben Besitzer des Dateizugriffs.
   Eine zurückgelassene Transaktion wird vor dem nächsten Auftrag aufgelöst.
   Vor jedem Schreibversuch werden laufende Ladeaufträge ungültig und offene
   Lesehandles geschlossen. Das gilt auch für einen später gescheiterten Versuch.
2. Neue oder geänderte Daten kommen als vollständiger, normalisierter
   RIFF/WAVE-Eintrag an das Dateiende. Ein bestehender Block bleibt erhalten.
   Übertragen wird blockweise, nicht als vollständige Sammlung im RAM.
3. Schreiben abschließen und die neuen Daten von Karte zurücklesen.
   Länge und CRC müssen stimmen, bevor sich der Index ändern darf.
4. Eine kleine Wiederherstellungsdatei mit altem Kopf, Änderungsziel und
   Prüfsummen schreiben, abschließen und zurücklesen.
5. Den vier Byte langen Offset des Slots ändern, abschließen und den
   vollständigen Kopf zurücklesen. Erst danach die Wiederherstellungsdatei
   dauerhaft entfernen und den Erfolg an den Aufrufer melden.
6. Erst jetzt Cache-Generation, Dateihandles und DSP-Belegung aktualisieren.
   Ein unvollständiger Karten- oder DSP-Transfer wird nicht als fertig geladen
   veröffentlicht.

Ein Fehler nach dem Index-Schreiben kann bereits dauerhaft gespeicherte Daten
bedeuten, etwa wenn das abschließende Schließen oder Entfernen fehlschlägt.
Der Besitzer hält den Katalog dann gesperrt, bis Wiederherstellung und erneutes
Einlesen den tatsächlichen Stand geklärt haben. Ein Fehler ist kein Nachweis
dafür, dass die Datei unverändert ist.

Löschen setzt den Offset auf null. Es verschiebt keine anderen Samples.
Ersetzen hängt die neue Version an und stellt den Offset um. Alte Blöcke
bleiben unreferenziert; eine spätere gezielte Bereinigung darf sie entfernen,
läuft aber nicht bei jedem Speichern.

## Wiederherstellung

Vor dem ersten Sample-Lesen beim Start und vor jedem neuen Schreibauftrag
wird die Wiederherstellungsdatei geprüft. Vollständige neue Daten erlauben
die Fertigstellung des neuen Index. Fehlen sie oder stimmt ihre CRC nicht,
wird der alte Index hergestellt. Fehler beim Kartenlesen sind keine
Bestätigung für beschädigte Daten: Sie lassen die Transaktion stehen.

Ein Indexeintrag hat vier Byte, der Kartenweg schreibt jedoch Sektoren.
Darum wird der vollständige alte Kopf gesichert. Ein beschädigter betroffener
Indexsektor lässt sich daraus wieder aufbauen. Ändert sich ein anderer
Indexsektor oder ist die Wiederherstellungsdatei ungültig, wird nicht blind
über eine möglicherweise andere Sammlung geschrieben.

Die Abbruchtests bilden ausdrücklich die Zusagen des Dateiadapters ab.
Sie beweisen keine beliebige Stromausfallsicherheit des Kartencontrollers
oder der FAT. Der native Adapter muss seine dauerhaften Grenzen durch
Abschließen und erneutes Öffnen der Firmware-Dateifunktionen herstellen.

## Phase 1: Slot-Änderungen und Abbrüche reproduzieren

- [x] Anhängen und Ersetzen bei veränderter Reihenfolge mit beiden Lesern prüfen.
- [x] Normalen Lader und Swap mit eigenen Firmwaredateien und erzeugten Samples prüfen.
- [x] Gemeinsamen blockweisen Schreibkern mit Wiederherstellung bauen.
- [x] Hinzufügen, Ersetzen, Löschen, kurze Schreibzugriffe, CRC-Fehler,
  beschädigten Indexsektor und konkurrierende Aufträge prüfen.
- [x] Große Offsets ohne große RAM-Belegung und Überlaufverweigerung prüfen.
- [x] Nativen Dateiadapter und Wiederherstellung vor dem Boot-Lader anschließen.

Dateien: `src/sample-transaction.mjs`, `tools/patch/sample_store.py`,
`test/sample-transaction.test.mjs`, `test/sample-transaction-native.test.mjs`,
`test/sample-persistence.test.mjs`, `tools/emu/sample_persistence_cases.py`
und `tools/emu/sample_store_cases.py`. Der ARM-Schreibkern benutzt die nativen
Dateifunktionen. Seine Wiederherstellung ist vor dem Öffnen der Sammlung
eingehängt. Beide roten Builds sind im Emulator mit erzeugten Daten geprüft.
Am 28.10. besteht der eigene Kartentest für Anlegen, Ersetzen, Index-Löschen
und vollständiges Rücklesen. Testdatei und Journal sind entfernt, der
benutzte RAM ist wiederhergestellt. Stromunterbrechung und volle Karte
bleiben offen.

## Phase 2: IMPORT SAMPLE ist dauerhaft

- [ ] Den gemeinsamen geräteseitigen Dateibesitz vor dem ersten Menühaken
  anschließen: Ladeaufträge entwerten, Leser schließen, Puffer reservieren
  und nach jedem Ergebnis den tatsächlichen Index wieder einlesen.
- [ ] Den nativen Import vor der DSP-Platzvergabe abzweigen; Quelle und Zielslot erhalten.
- [ ] PCM und Metadaten des genau gewählten Slots normalisieren und über
  den gemeinsamen Schreibweg ablegen; vorhandene Slotbelegung aus dem
  Dateikopf statt nur aus der DSP-Tabelle ermitteln.
- [ ] Auch bei einer Sammlung über 25 MiB und einem vollen DSP importieren.
- [ ] Nach Neustart genau die neue Version laden, andere Slots unverändert lassen.
- [ ] Fehlende Karte, volle Karte und Abbruch melden, ohne Erfolg vorzutäuschen.
- [ ] Alias und DSP-Version getrennt veröffentlichen: Beim Ersetzen eines Slots
  bleiben andere Aliase und aktive Stimmen auf ihrer bisherigen PCM, bis der
  neue Platz vollständig geladen ist. Die native Reservierung allein genügt nicht.

Der gemessene Aufruf des Einzelimporters liegt bei `0xC0038DE0`, das Öffnen
der WAV bei `0xC003646C`, der Parseraufruf bei `0xC00364B4`. Der vorhandene
Haken `0xC003621C` liegt vor DSP-Reservierung und PCM-Schreiben.

Dateibesitz ist Voraussetzung für den Menühaken, nicht erst für die spätere
USB-Anbindung. Beim künftigen Projektladen wird Cache-RAM dynamisch und
exklusiv ausgeliehen. Die tatsächliche Übergabe und Rückgabe sind vor der
Projekt-Anbindung zu bauen; der Cache wird nicht dauerhaft verkleinert. Ein fehlgeschlagener Abschluss kann bereits einen neuen
Index hinterlassen. Deshalb bleiben Nachladen und Veröffentlichung
gesperrt, bis Wiederherstellung und Rücklesen den Kartenstand klären.
Dabei bleiben die bisherigen DSP-Tabellen erhalten; ein neuer Aufruf des
nativen Gesamtlades zum Aktualisieren wäre dafür ungeeignet.

Der [Besitzerbaustein und der Leserabschluss](../messungen/2026-10-29-sample-dateibesitz.md)
sind geprüft und im gebauten Patch an Boot-Lader und Swap-Ladeschritte
angeschlossen. Bei konkurrierendem Besitz bleiben Tabellen und Generation
erhalten; ein ungeklärter Katalog sperrt weitere Leser. Native Menüs,
dauerhafte Slot-Schreiber, USB und das erneute Indexlesen nach Änderungen
sind noch anzuschließen. Dieser Arbeitspunkt bleibt deshalb offen.

Die DSP-Belegung braucht zusätzlich eine Bindung an die gespeicherte
Slot-Version. Eine aktive Metadatenzeile allein beweist nicht, dass sie
die neue Version enthält. Eine neue Version bekommt einen unbenutzten
Platz; ihr Name wird erst nach vollständigem PCM-Transfer umgebunden.
Andere Aliase und noch aktive Stimmen schützen den bisherigen Platz.
Die reale Partauswahl ist dabei getrennt vom gewünschten Wert zu prüfen.
Tabellenindex 999 ist kein freier Ersatzplatz; die gültigen Tabellen enden
bei 998. Ein interner unbenutzter Platz darf keine zusätzliche Begrenzung
der Kartenslots verursachen.

## Phase 3: Jede Sample-Aktion ist dauerhaft

- [x] Begrenztes DSP-Rücklesen für nicht auf 32 Byte ausgerichtete Aufnahmegrenzen
  und den letzten Block der DSP-Bank im ARM-Modell prüfen; die tatsächliche
  Firmware mit erzeugter Aufnahme-PCM in beiden roten Builds prüfen.
- [ ] Bestehende Abschlussstellen für Name, Loop, Slice und destruktive
  Bearbeitung erfassen. Zusammengehörige Eingaben bilden eine Änderung,
  statt jeden einzelnen Drehgeberschritt auf die Karte zu schreiben.
- [ ] Metadaten und Audio eines geänderten Slots vollständig erhalten.
- [ ] Sample-Löschen am Gerät an denselben Index-Schreibweg anschließen.
- [ ] Neue Aufnahmen und Resampling nach dem bestätigten Abschluss speichern.
- [ ] Auch Aufnahme-Stop und DSP-Endzeigerlesen begrenzen; bei Fehler weder
  einen fertigen Slot noch eine gesicherte Aufnahme melden.
- [ ] Fehlgeschlagene Speicherung sichtbar machen und eine noch nicht
  gesicherte Aufnahme nicht still verwerfen.

## Phase 4: USB und laufender Swap benutzen denselben Besitzer

- [ ] Native Zugriffe, USB-Änderungen und Cache-Füllung geräteseitig koordinieren.
- [ ] Transaktion und Wiederherstellung über USB zugänglich machen; alte
  Komplettkopien und Verdichtung nicht als normalen Speicherweg verwenden.
- [ ] Datei-Auswahl und vollständigen Offset im Protokoll trennen. Die alten
  Befehle kodieren die Auswahl in den oberen zwei Bits; das 256-MiB-Limit
  lässt sich deshalb nicht einfach durch eine größere Konstante ersetzen.
- [ ] Alte Clients durch klar erkennbare Fähigkeiten begrenzen, damit kein
  alter Vollschreibweg eine aktive Bibliothek verkürzt.
- [ ] Nach gespeichertem Slot den Cache und offene Dateiobjekte invalidieren.

## Phase 5: Gesamtexport entfällt

- [ ] `EXPORT ALL SAMPLE` aus den unterstützten BLECH-Menüs entfernen.
- [ ] Den nativen überschreibenden Weg auch gegen direkte Aufrufe absichern.
- [ ] Vorgaben, Hilfetexte, App und Regressionen auf den neuen Speicherweg umstellen.
- [ ] Nach jeder Sample-Aktion ohne Gesamtexport neu starten und Inhalt prüfen.

## Phase 6: Prüfung und Veröffentlichung

- [ ] Erzeugte Samples in beiden roten Builds über den gesamten Ablauf prüfen.
- [ ] `npm test`, `npm run test:e2e` und die vollständigen Patch-Prüfungen bestehen.
- [ ] Geänderte Patchdateien vor Veröffentlichung für alle drei Builds neu verifizieren.
- [ ] Am Gerät: Speichern, echte Abbrüche, Stimmen und echte Aufnahme mit DMA prüfen.

Keine neuen Flash-Schreibzugriffe. Keine Korg-Daten im Repo. Kein Commit,
Push oder Release ohne gesonderten Auftrag. Die Freigabe für 1.4 bleibt offen.

## Unbekannte Stellen und größte Risiken

- Eine FAT- oder Controller-Störung kann weiter reichen als der beschriebene
  Indexsektor. Die Modelltests sind dafür kein Hardwarebeweis.
- Die bestehende Firmware schreibt den Import noch nicht auf die Karte.
  Das Entfernen des Exports vor vollständiger Anbindung würde Daten verlieren.
- Die Abschlussstellen aller Bearbeitungen und echter Aufnahme sind noch
  nicht vollständig kartiert.
- Nebenläufige USB-Schreiber müssen dieselbe geräteseitige Sperre benutzen;
  die exklusive Sitzung eines einzelnen Clients genügt nicht.
- Die physische DSP-Grenze und ausklingende Stimmen bleiben aus der
  bisherigen Untersuchung offen.

## Umsetzungsprotokoll

27.10.: Speicherweg und Dauerhaftigkeit aller Sample-Aktionen festgelegt.
Anhängen und Ersetzen mit beiden App-Lesern sowie normalem und Swap-Lader
reproduziert. Schreibkern, Abbruchmodell und nativen Dateiadapter gebaut.
Der Startlader stellt einen beschädigten Indexsektor vor dem Laden wieder her.
Ein eigener Importdienst normalisiert WAVs mit dem Firmware-Parser und schreibt
ohne vorherige DSP-Platzvergabe. Der Emulator prüft Import bei vollem DSP und
Neustart ohne Gesamtexport. Dieser Dienst ist noch nicht mit der normalen
Bedienung verbunden. Slotwahl, Cache-Besitz und Nachladen sind daher weiter offen.

28.10.: Eigener Kartentest nach Neustart mit 13 bestätigten Aufrufen bestanden;
Testdatei und Journal entfernt, benutzten RAM zurückgelesen und wiederhergestellt.
Der Bibliothekslader verweigert einen gesetzten DSP-Protokollfehler jetzt vor
dem nativen Löschen der Metadatentabelle. Der gemeinsame Schutz liegt nach
dem Registerprolog und verträgt sich mit dem vorhandenen Ladefehler-Patch.

Die normale Import-Bedienung samt Fehlerfenster ist in beiden roten Builds
erfasst. Ihre anschließende Part-Aktualisierung veröffentlicht auch einen
noch fehlenden Slot; sie kann nicht unverändert hinter den neuen
Kartenschreiber übernommen werden. Der nächste Bauabschnitt verbindet
Dateibesitz, Slot-Version und bedarfsgesteuertes Nachladen mit diesem
Kommando. Ein geänderter Offset darf eine noch alte DSP-Version nicht
als aktuell bestätigen.

Der Aufnahmeabschluss und der gemeinsame native Exportleser sind erfasst.
Die PCM liegt im DSP. Ein eigener Emulatorfall prüft synthetischen Abschluss,
Rücklesen und Einzel-Export; echte Aufnahme und DMA bleiben offen. Vor dem
Anschluss braucht der Rückleser eine begrenzte Wartezeit und geklärte
Behandlung von nicht auf 32 Byte ausgerichteten Aufnahmegrenzen.

## Belege

- [Untersuchung des dauerhaften Speicherwegs](../messungen/2026-10-27-sample-store.md)
- [Bisherige Swap-Prüfungen](../messungen/2026-10-27-sample-swap-1-4.md)
- [Dateiformat](../hintergrund/sample-datei.md)

## Zwischenstand: Schutz der laufenden Wiedergabe

Der [Stimmen- und Part-Versuch](../messungen/2026-10-28-sample-swap-stimmen.md)
prüft die alte Importbindung aktiver Stimmen, die tatsächliche Part-Auswahl
und Moduswechsel während eines Ladeauftrags. Eine belegte Stimme schützt
auch nach einer Namensumbindung ihre alte PCM. Ein Part übernimmt eine neue
indizierte Auswahl erst nach vollständigem Nachladen. Das ersetzt noch
keinen gemeinsamen Dateibesitzer und keine Versionsverwaltung beim
Speichern. Die offenen Aufgaben der Phase 2 bleiben deshalb offen.

Ein getrennter Abbruchbaustein prüft inzwischen den Stack und den Besitz
der DSP-Sperre für native Aufträge. Die native Part-Aktualisierung schreibt
selbst über den Host-Port; sie darf nicht als reiner Tabellenzugriff in den
IRQ-geschützten Namenswechsel übernommen werden. Der Baustein ist noch
nicht im Laufzeitpatch eingebunden. Die Begrenzung aller nativen
Aufnahme- und Speicherpfade bleibt offen.
