# 64. Projekte: Patterns und Samples zusammen laden

Stand: 29. Oktober 2026. **Aufbau festgelegt, bisherige Ladewege teilweise im Emulator geprüft,
gemeinsame Projektdatei nicht gebaut.** Am Gerät ist der Projektwechsel nicht geprüft.
Es gibt noch keinen gemeinsamen Projekt-Import und keinen dafür eingebauten Firmware-Patch.

## Gewünscht

Mehrere Projekte liegen nebeneinander auf der Karte. Ein Projekt besteht aus einem kompletten
Pattern-Satz und dem dazu passenden Sample-Satz in einer einzigen Datei. Der Wechsel aktiviert
beides ohne Neustart. Der Lader liest die benötigten Bereiche direkt aus dieser Datei, ohne sie
vorher in zwei Dateien oder den bisherigen Sample-Ordner zu entpacken. Das Laden in den
Arbeits- und Sample-Speicher ist davon unabhängig und weiterhin nötig.

**Festgelegt:** Ohne Karte startet das Gerät normal ohne Projektimport. Die vorhandenen Patterns
liegen im Flash und werden von dort geladen. Beim Projektladen werden die Projekt-Patterns mit
dem tatsächlichen Flash-Inhalt verglichen: Geänderte Patterns werden gespeichert, identische
übersprungen. WRITE bleibt normal nutzbar; eine zusätzliche Änderung seiner bisherigen Bedienung
ist nicht vereinbart. Die gezielten Pattern-Schreibvorgänge beim Projektladen erlauben keine
anderen neuen Flash-Schreibwege.

```text
KORG/blechtribe/Projects/
  Live A.<Projektendung>
  Live B.<Projektendung>
```

Die endgültige Dateiendung ist noch offen; `<Projektendung>` ist hier nur ein Platzhalter.
Am Gerät wählt `IMPORT PROJECT` eine gemeinsame Projektdatei. Einzeln importierte Samples
bleiben möglich und werden im aktiven Projekt dauerhaft gespeichert. Die bisherigen Gesamtimporte
dürfen Patterns und Sample-Zuordnung nicht unabhängig voneinander ersetzen. Ihre genaue
Menüeinbindung unter `Menü -> DATA UTILITY` bleibt Teil der Umsetzung.
Ein Projekt ist erst aktiv, wenn Pattern-Bank und Sample-Index geprüft und die Samples des
gewählten Startpatterns im DSP bereit sind. Die ganze Sample-Bibliothek wird dabei nicht geladen.
Das ist der gewünschte Ablauf, noch keine vorhandene Bedienung.

## Festgelegt am 29.10.: Eine Datei mit drei Bereichen

**Festgelegt, noch nicht umgesetzt:** Die Projektdatei ist ein unkomprimierter Container.
Sie braucht kein Archivformat. Zwei unveränderte Ausgangsdateien bilden zunächst die Nutzdaten;
ein eigener kleiner Kopf beschreibt ihre Lage innerhalb der gemeinsamen Datei.

```text
Projektdatei
  Dateikopf: Kennung, Version, Bereichspositionen und gültige Längen
  Patternbereich: Inhalt der bisherigen vollständigen Pattern-Datei
  Samplebereich: Kopf und Slot-Index der .all, danach Sampleblöcke
                und später angehängte neue Sampleblöcke
```

Der Patternbereich liegt vor dem Samplebereich. Neue Sampleblöcke können dadurch am Dateiende
hinzukommen, ohne die Pattern-Bank oder vorhandene Samples zu verschieben. Bestehende Pattern-
und Sample-Datensätze bleiben erhalten und werden gezielt bearbeitet, nicht aus bekannten Feldern
neu aufgebaut. Die Globals des Patternbereichs bleiben enthalten, werden aber nicht automatisch
als Geräteeinstellungen übernommen.

**Hergeleitet:** Die bisherigen Dateizugriffe brauchen einen begrenzten Blick auf den jeweiligen
Bereich. Eine Position innerhalb der bisherigen Datei wird zur Bereichsposition im Container
addiert. Jeder Zugriff muss gegen die gültige Bereichslänge und die tatsächliche Dateigröße
geprüft werden, einschließlich Überlauf und Überschneidung. Relative Sample-Offsets bleiben auf
den Beginn des Samplebereichs bezogen. Ein anderer Dateiname allein passt die nativen Lader nicht
an; ihre Zugriffe und Längenprüfungen müssen diesen Bezug durchgängig verwenden.

### Laden und Vorausladen

Beim Start werden der Containerkopf, der Sample-Index und die für die Pattern-Auswahl nötigen
Pattern-Daten gelesen. Beim Projektwechsel wird die Pattern-Bank geprüft und wie oben beschrieben
übernommen. Für den DSP lädt der Swap zunächst nur die Samples des tatsächlich gewählten
Startpatterns. Dieses Pattern ist dynamisch, nicht fest Pattern 1.
Samples der Nachbarpatterns und des Kettenziels werden vorausgeladen, bevorzugt in den ARM-Cache.
Weitere Samples kommen nach Bedarf aus dem Samplebereich derselben Projektdatei.

Ein Patternwechsel wartet auf seine vollständigen benötigten Samples. Sind sie noch nicht bereit,
läuft das bisherige Pattern noch einmal. Die Projektdatei bekommt keine künstliche Grenze durch
die etwa 25 MiB des DSP. Grenzen von Dateisystem, Slot-Anzahl und darstellbaren Offsets bleiben
zu prüfen; unbegrenzt große Einzeldateien sind damit nicht zugesagt.

### Einzelne Änderungen dauerhaft speichern

Import, Sample-Bearbeitung, Löschen, Aufnahme und Resampling schreiben durch denselben
abgesicherten Speicherweg in den Samplebereich des aktiven Projekts.
Änderungen in SAMPLE EDIT werden erst mit WRITE gesichert; Import, bestätigtes Löschen sowie
bestätigt abgeschlossene Aufnahme und Resampling speichern direkt. Abspielen, Auswahl,
Patternwechsel und Swap verändern die gespeicherten Samples nicht. Sample-WRITE ohne Änderung
hängt keinen unveränderten Block an. Neue oder ersetzte Sample-Inhalte werden hinten angehängt.
Erst nach geprüftem Schreiben dürfen Slot-Index und gültige
Längen auf den neuen Stand wechseln. Löschen ändert den betroffenen Indexeintrag; die bisherigen
Blöcke müssen dafür nicht verschoben werden. Unveränderte Samples werden nicht neu geschrieben.
Ein Gesamtexport ist danach kein erforderlicher Speicherschritt mehr. `EXPORT ALL SAMPLE` entfällt
erst, wenn alle genannten Änderungswege dauerhaft speichern.

Vor Änderungen am Index oder an den gültigen Längen wird das vereinbarte Wiederherstellungsjournal
gesichert. Es gehört eindeutig zum Projekt und muss beim Öffnen vor der Nutzung ausgewertet werden.
Die Projektdatei ist die einzige dauerhafte Inhaltsdatei; während eines Schreibvorgangs oder nach
einem Abbruch kann zusätzlich eine kleine Journaldatei bestehen. Nach nachgewiesenem Abschluss
oder vollständiger Wiederherstellung kann sie entfernt werden. Es gibt keine automatische
Verdichtung und kein vollständiges Neuschreiben bei jedem Speichern.
Nicht mehr referenzierte Sampleblöcke belegen deshalb weiterhin Kartenplatz. Eine spätere
gesonderte Verdichtung wäre ein eigener Speichervorgang.

Das Journal schützt die Veröffentlichung einer Änderung auf der Karte. Die vorübergehenden
RAM-Sicherungskopien weiter unten schützen einen fehlgeschlagenen Projektwechsel. Beides ist
unabhängig von einem möglichen Undo einzelner Bearbeitungen, für das die vorherigen Feldwerte
genügen können. Die Zuordnung des normalen Pattern-WRITE zur Projektdatei ist noch festzulegen;
sein bisheriges Verhalten wird durch diesen Dateiaufbau nicht verändert.

**Offen:** Die genauen Bytefelder und Feldbreiten des Containerkopfs, Erkennung beschädigter
oder veralteter Versionen, Schutz und Reihenfolge der Index- und Längenänderungen sowie die
Prüfung auf Stromausfall und Kartenfehler. Das Journal muss nach einem Abbruch einen eindeutigen
gültigen Stand herstellen. Diese Eigenschaften sind noch weder implementiert noch gemessen.

## Ergebnis

- **Offline im Emulator gemessen:** Die originale Sample-Importfunktion lädt eine ganze `.all`
  während des Betriebs. A, B und wieder A ersetzen jeweils den User-Sample-Satz; Samples, die nur
  zum vorherigen Satz gehören, bleiben nicht aktiv. Ein Neustart ist dafür nicht erforderlich.
- **Offline im Emulator gemessen:** Der originale Dateizugriff liest beide Dateinamen direkt aus
  Projekt-Unterordnern, auch aus `B live 02` mit Leerzeichen. Während der Laufzeitversuche bleibt
  das vollständige Kartenabbild unverändert. Es entstehen keine Dateikopien. Dieser Versuch
  benutzt noch zwei getrennte Dateien und prüft den gemeinsamen Container nicht.
- **Aus dem ARM-Code hergeleitet:** Der vorhandene Gesamtimport für Patterns schreibt zusätzlich
  Globals und die ganze Pattern-Bank in den Flash. Er ist deshalb kein unverändert nutzbarer
  Projektlader: Gewünscht sind nur die geänderten Patterns, keine Übernahme von Globals und kein
  erneutes Schreiben identischer Pattern-Daten.
- **Offen:** Der gemeinsame, gegen Abbruch und Fehler geschützte Wechsel von Samples und allen
  250 Patterns im RAM. Eine Pfadumleitung allein stellt diese Funktion nicht her.

Der wahrscheinlichste Fehler ist ein halber Wechsel: neue Samples bei alten Patterns oder
umgekehrt. Das ist kein theoretischer Sonderfall: Der native Sample-Import verwirft den alten
User-Sample-Satz auch dann, wenn die neue Datei fehlt. Ein fehlgeschlagener Projektwechsel braucht
deshalb einen ausdrücklich geprüften Rückweg.

## Welche Dateien die Firmware kennt

**Aus den Zeichenketten und Importfunktionen hergeleitet, Sampler 2.02:**

| Zweck | Vorhandener Name oder Aufbau |
|---|---|
| Sample-Satz beim Start | `SD:KORG/electribe sampler/Sample/e2sSample.all`, bei Hacktribe unter `KORG/hacktribe/` |
| Sample-Satz mit dem vorhandenen BLECH-Ordnerpatch | `SD:KORG/blechtribe/Sample/e2sSample.all` |
| Pattern-Gesamtexport | `electribe_sampler_allpattern.e2sallpat` im jeweiligen Geräteordner |
| Name im bisherigen Pfadversuch | `e2sPattern.all`, gleicher Inhalt wie eine `.e2sallpat`, kein nativer Dateiname |

`e2sPattern.all` ist keine gefundene Firmware-Zeichenkette und kein künftig separat erforderlicher
Projektbestandteil. Der native Pattern-Dateibrowser filtert nach `.e2sallpat`. Ein Projektlader
muss die neue Projektendung selbst auswählen und den Container prüfen; bloßes Umbenennen macht
die Datei nicht im bisherigen Importbrowser auswählbar.

Eine vollständige Sampler-Pattern-Datei hat einen Kopf von `0x100` Byte, danach `0x10000` Byte für
Globals und ab `0x10100` die 250 Pattern-Blöcke mit je `0x4000` Byte. Gesamtlänge: `0x3F8100` Byte.
Die Globals gehören damit zum Dateiformat, aber nicht automatisch zum gewünschten Projektumfang.
Ein künftiger Projektlader soll sie nicht nebenbei als globale Geräteeinstellungen übernehmen.
Aufbau und bestehende Importe: [Gerätekarte](../geraetekarte.md),
[Pattern-Import](../messungen/2026-10-10-pattern-kette-import.md).

## Pfadbesitz und Zeichenketten

**Offline am Abbild geprüft:** Die folgenden Stellen liegen bei Korgs rotem Sampler und Hacktribe
an denselben Adressen. Die Import-Codebereiche wurden zwischen beiden Abbildern verglichen.

| Adresse | Bedeutung |
|---|---|
| `0xC00A5656` | Geräteordnername: `electribe sampler` oder `hacktribe` |
| `0xC00A5678` | Relativer Stamm: `KORG/electribe sampler/` oder `KORG/hacktribe/` |
| `0xC00A56BC` | `Sample/`, acht Byte einschließlich NUL |
| `0xC00A56C4` | `e2sSample.all`, 14 Byte einschließlich NUL |
| `0xC00A56CD` | `.all`, ein Verweis mitten in den vorherigen Dateinamen |
| `0xC00A47C8` | Export-Basisname `electribe_sampler_allpattern.` |

Der vorhandene [Ordnerpatch](../../tools/patch/blechtribe.py) ersetzt nur den Geräteordnernamen und
den relativen Stamm durch `blechtribe`. Diese festen Textfenster reichen nicht für wechselnde
Projektnamen. Außerdem wird der innere `.all`-Verweis vom Sample-Importer und dessen Dateibrowser
benutzt. Einen längeren Projektpfad über die bisherige Zeichenkette zu schreiben würde fremde
Verweise und benachbarte Daten beschädigen.

`0xC0035A80` baut den vollständigen Sample-Pfad aus `SD:`, dem Stamm, `Sample/` und dem Dateinamen.
Dafür verwendet es die allgemeine Pfaderzeugung `0xC0035720` mit der Kennung `0x124`.
Die spezielle Sample-Pfaderzeugung wird beim Start zur Existenzprüfung, beim eigentlichen Laden
und beim Gesamtexport der Samples aufgerufen. Die allgemeine Pfaderzeugung hat mehr als zwanzig
Aufrufer, darunter Export und Update. Den globalen Stamm auf einen Projektordner umzubiegen wäre
deshalb eine Änderung an wesentlich mehr als dem Projekt-Import.

**Folgerung für eine spätere Umsetzung:** Der ausgewählte Projektname braucht einen eigenen,
begrenzten Pfadpuffer. Nur die zugehörigen Sample- und Pattern-Zugriffe dürfen diesen verwenden.
Ein gemeinsamer Verzeichniswechsel für die ganze Firmware ist nicht belegt und nicht vorgesehen.

## Die vorhandenen Importwege

Alle Adressen in diesem Abschnitt gelten für den roten Sampler 2.02 und den untersuchten
Hacktribe-Build. Sie sind keine automatisch gültigen Adressen für die blaue Electribe.

### Samples

**Offline im Emulator ausgeführt:** `0xC00364F0(r0 = Dateipfad)` lädt den ganzen Sample-Satz.
Der Startbefehl `0xC0038D34` baut den festen Pfad über `0xC0035A80` und ruft diesen Lader auf.
Der Import während des Betriebs hat dagegen bereits einen ausgewählten Dateipfad.

Der Laufzeitbefehl hat die Kennung `0x22`, seinen Einstieg bei `0xC0038D80` und liest den
ausgewählten Pfad aus dem Zeichenkettenobjekt bei `0xC0345A24`. Bei Endung `.all` erreicht er
den gleichen Gesamtlader über `0xC0038E0C`. Danach aktualisiert er die Sample-Verwaltung über
`0xC009A0A8(-1)` und `0xC004CC50(Zielplatz - 1)`. Ein einfacher WAV-Import ist also nicht der
einzige vorhandene Laufzeitweg. Zur bestehenden Fehlerbehandlung siehe
[Sample-Fehler](../messungen/2026-10-15-sample-fehler.md) und
[Sample-Lader](../../tools/patch/sample_errors.py).

### Patterns

**Aus dem ARM-Code hergeleitet:** Der Gesamtimport hat die Kennung `0x17`, den Einstieg
`0xC002E41C` und liest den Dateipfad aus dem Zeichenkettenobjekt `0xC0340588`.
Er prüft den Dateikopf, liest die Globals und danach die gesamte Pattern-Bank in den Arbeitspuffer
`0xC0D3A940`, den `0xC00369F0` liefert. Schon vor den Pattern-Daten ruft er die Speicherung der
Globals über `0xC004C1B4` auf.

Für die Patterns folgt `0xC004C2E4(Verwaltung, Daten, 1)`. Diese Funktion übernimmt alle 250
Blöcke in die Bank und läuft danach immer zur Speicherung weiter:

```text
0xC004C2E4
  -> 250 Pattern-Blöcke über 0xC004A350 und 0xC000985C übernehmen
  -> 0xC004C300
  -> 0xC002A0C4
  -> 0xC0029AB8
  -> 0xC001E57C, Flash-Sektoren schreiben
```

Der dritte Parameter `0` ist kein Modus für reines Laden ins RAM: Er überspringt das Übernehmen
der neuen Blöcke, führt die Speicherung aber trotzdem aus.

Die laufende Firmware benutzt die Pattern-Bank im RAM. Der Zugriff
`0xC004A350(Verwaltung, Index)` liefert für Index `0..249` den Slot
`0xC08B2940 + Index * 0x4000`. Der Verwaltungszeiger kommt über `0xC00263E0()`.
Nach dem nativen Gesamtimport lädt `0xC0079CF8(Bearbeitungsverwaltung, Index, 1)` das aktuelle
Pattern neu; der Verwaltungszeiger liegt bei `0xC034029C`, sein gewählter Index bei `+0x318`.
Ein Dateipfad ersetzt weder diese Bank noch den aktuellen Bearbeitungspuffer.
Siehe [Speicherbereiche](../speicherbereiche.md) und
[Patternwechsel](../hintergrund/patternwechsel.md).

**Aus dem ARM-Code hergeleitet, noch nicht im Emulator ausgeführt:** `0xC004C28C` ist der
native Speicherweg für ein einzelnes Pattern. Er übernimmt Index und optional Quelldaten,
verwendet bei ausgeschalteter Kopieroption den vorhandenen RAM-Slot und speichert über
`0xC002A0C4` genau einen `0x4000`-Byte-Block. Dieser Weg ist ein Kandidat für gezieltes Speichern;
Aufrufkontext, Rückgabe, bestehende WRITE-Hooks und tatsächliche Lösch-/Schreibgrenzen müssen
noch gemessen werden.

**Noch nicht ausgeführt:** Ein eigener Ladevorgang, der den Container und seinen Patternbereich prüft, die
Pattern-Bank im RAM ersetzt, nur gegenüber dem Flash geänderte Patterns nativ speichert und das
aktuelle Pattern neu lädt. Die Vergleichsprüfung gehört zum Pattern-Speicherweg. Der native
Gesamtimport darf nicht durch global unterdrückte Flash-Aufrufe passend gemacht werden.

## Emulatorversuche und Grenzen

Der wiederholbare Versuch liegt in [project_probe.py](../../tools/emu/project_probe.py).
Er erstellt eine virtuelle FAT32-Karte mit zwei eigenen Sample-Sätzen und vollständig künstlichen
Pattern-Dateien. Keine Firmwaredatei, kein Werkspattern und keine Aufnahme sind enthalten.
Die Ergebnisse und die beobachteten Dateiaufrufe stehen in
[64-projekte-emulator.json](64-projekte-emulator.json).
Auf Korgs rotem Sampler 2.02 und Hacktribe bestehen jeweils zwölf Prüfungen.
Die Versuche stammen aus dem Entwurf mit zwei Dateien. Sie sind kein Nachweis für das Lesen
aus einem gemeinsamen Container oder dessen sicheres Speichern.

```bash
tools/emu/.venv/bin/python tools/emu/project_probe.py \
  --vsb "$E2_VSB" --report /tmp/blech-project-report.json
```

| Prüfung | Beobachtung |
|---|---|
| Sample-Pfad beim Start auf Projekt A umleiten | Die originale Existenzprüfung und das originale Öffnen erreichen A; Plätze 501 und 502 heißen `A-501` und `A-502` |
| Im Betrieb den originalen Sample-Importbefehl auf B ausführen | Status 0, Plätze 501 und 503 heißen `B-501` und `B-503`; Platz 502 ist nicht mehr aktiv |
| Im gleichen Emulator nach A zurückwechseln | Status 0, wieder nur die beiden User-Samples von A aktiv |
| Fehlende Sample-Datei anfordern | Status 4, vorheriger User-Sample-Satz danach leer; kein Rücksetzen auf A |
| `e2sPattern.all` in beiden Ordnern über originale FatFs öffnen | Kopf sowie erster und letzter Pattern-Block werden bytegenau gelesen, auch bei Leerzeichen im Ordnernamen |
| Pattern-Bank vor und nach diesen Dateizugriffen vergleichen | Unverändert; Lesen aus dem neuen Pfad allein aktiviert keine neuen Patterns |
| Karte und Flash vergleichen | Karte ab Ende des Starts bytegleich, Flash ohne Firmwarebereich bytegleich; keine Firmware-Assertion |

**Modellannahmen:** Die Bootversuche ersetzen ausschließlich die Pfadargumente an den originalen
FatFs-Einstiegen `0xC009E7DC` und `0xC009DB60` durch einen Pfad im Emulator-RAM. Das ist der
Nachweis für das Lesen an diesem Ort, keine fertige Integration der Pfaderzeugung.
Die Laufzeitversuche rufen den originalen Importbefehl mit einem künstlichen Befehlsobjekt vom
Bildschirmtakt aus auf. Der normale Versand über die CommandTask und eine neue Menübedienung
sind damit nicht geprüft. Für die Patterns werden originale Dateioperationen benutzt, kein neuer
Projektlader und kein umgebauter Gesamtimport.

Die Samples gehen durch den originalen Parser und die originale Sample-Verwaltung. DSP und
Flash-Baustein sind emuliert, die Werksbank besteht aus den eigenen Testdaten des Emulators.
Das belegt weder Klang noch die vollständige Wiederherstellung einer realen Sample-Bank.
Ladezeiten sind keine Messung am Gerät. Die gültigen Sätze sind klein; eine volle Sample-Bank,
ein beschädigter Datensatz, eine entfernte Karte und parallele Bedienung bleiben gesonderte
Prüfungen. [Grenzen des Emulators](../emulator.md).

## Was vor einer Umsetzung klar sein muss

1. **Projektumfang:** Patterns und Samples gehören zusammen. Globale Einstellungen aus dem
   Pattern-Dateiformat werden nicht automatisch übernommen. Speicherfunktionen wie WRITE und
   Export brauchen eine eigene Betrachtung; aus einem funktionierenden Import folgt keine
   Speicherung zurück in die Projektdatei.
2. **Fehler und Rückweg:** Containerkopf, beide Bereiche, ein vorhandenes Journal und alle
   erforderlichen Grenzen vor dem ersten
   zustandsändernden Schritt prüfen. Das reicht bei einem späteren Kartenlesefehler allein nicht.
   Ein Abbruch nach begonnenem Sample-Laden braucht einen nachgewiesenen Wiederherstellungsweg;
   der alte Sample-Satz bleibt im nativen Import nicht erhalten.
3. **Ausführung:** Laden bei gestopptem Sequencer, serialisiert gegen andere Datei- und
   Sample-Aktionen, im passenden Firmware-Befehlskontext. Ein gemeinsamer Erfolg wird erst nach
   Übernahme der Pattern-Bank und Bereitstellung des aktiven Sample-Satzes gemeldet.
   Ungespeicherte Änderungen und wiederholtes MENU dürfen keinen
   zweiten Wechsel auslösen oder unbemerkt verloren gehen.
4. **Aktives Projekt:** Ohne Karte ist der normale Start ohne Projektimport festgelegt.
   Ob bei vorhandener Karte das zuletzt gewählte Projekt wieder geladen wird und wo dessen Name
   liegt, ist noch festzulegen. Ein Flash-Schreiben ist dafür nicht vorgesehen. Eine fehlende
   Projektdatei beim Start braucht einen klaren Rückfall.
5. **Builds und Gerät:** Die gemeinsame Funktion erst für Sampler und Hacktribe im Emulator
   prüfen. Die blaue Firmware hat keinen entsprechenden nativen Sample-Import; aus den
   vorhandenen Pattern-Adressübersetzungen folgt keine Projektunterstützung mit Samples.
   Am Gerät erst nach separater Zustimmung und mit eigenem Kartenbackup prüfen.

Die nächste sinnvolle Arbeit nach Zustimmung ist ein konkreter Umsetzungsplan für den
Container und den gemeinsamen Import, zuerst mit einem belegten Fehler- und Wiederherstellungsablauf.
Dazu gehören künstlich erzeugte Testdaten für beschädigte Bereichsgrenzen, abgebrochene
Sample-Schreibvorgänge, Journal-Wiederherstellung und selektives Lesen ohne Vollimport.
Ein späterer Emulatorfall muss das Lesen und Speichern innerhalb der Containerbereiche prüfen;
die bisherigen Pfadversuche decken das nicht ab. Bis dahin
bleiben Firmware-Patches, Menü und Gerätezugriffe unverändert.

## Festgelegt am 29.10.: RAM während des Projektladens ausleihen

Projektladen und Sample-Swap benutzen den oberen Cachebereich zeitlich
getrennt. Für Projekte wird kein dauerhafter 13-MiB-Bereich vom Swap-Cache
abgezogen. Das begrenzt weder die Sampledatei auf der Karte noch den
bisherigen Cache im normalen Spielbetrieb.

Vor dem ersten Projektzugriff muss der gemeinsame Besitzer alle
Swap-Aufträge anhalten, ihre Generation entwerten und offene Lesehandles
bestätigt schließen. Erst danach darf der Projektlader dort neue Daten
und Sicherungskopien halten. Währenddessen bleiben Spielen, Bearbeiten,
USB-Änderungen und weitere Ladeaufträge ausgeschlossen.
Eine gesperrte Bedienung beweist keinen Stillstand früherer
Hintergrundübertragungen. Auch noch aktive native CPU- oder DMA-Nutzer
müssen vor der tatsächlichen RAM-Übergabe bestätigt beendet sein.

Die aktive Pattern-Bank bleibt im vorhandenen Pattern-Speicher der
Firmware. Der zusätzliche Projektbereich enthält Arbeits- und
Sicherungskopien, keine dauerhaft nötige zweite aktive Bank.

Nach dem geprüften erfolgreichen Laden oder dem vollständig geprüften
Rückweg werden die großen Sicherungskopien freigegeben. Dauerhaft nötig
sind nur kleine Zustandsangaben wie Projektpfad und Status. Der Swap liest
anschließend den gültigen Sample-Index erneut und baut seinen Cache neu
auf. Ein gescheiterter Rückweg darf den Speicher nicht freigeben.

Gemessen im Modell: Die strenge Speicherprüfung verweigert die
Überschneidung weiterhin. Eine gesonderte Planung weist den erforderlichen
exklusiven Besitz von `sample-swap` aus; fremde Besitzer und die
Datei-Arbeitsbereiche bleiben ausgeschlossen. Nach bestätigter
Wiederherstellung hält das Importmodell seine großen Sicherungskopien
nicht mehr. Ein unbestätigter Rückweg behält sie samt Sperre.

Offen: Die Planung erwirbt keinen nativen Besitz. Der Projektlader sowie
seine tatsächliche Übergabe, Rückgabe und anschließende Indexprüfung sind
weiterhin zu bauen. Bestehende Swap-Fehler bei der Übergabe des nativen
Arbeitspuffers werden dadurch nicht als behoben erklärt.
