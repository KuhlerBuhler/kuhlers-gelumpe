# Sample-Datei: gemeinsamer Schreibzugriff und erneutes Indexlesen

Stand: 31.10.2026. **Gemessen im Emulator** mit erzeugten Samples und
eigenen Originalen von Stock 2.02 und Hacktribe. Kein Gerät, Klang oder
Aufnahme-DMA. Ergänzung zum [dauerhaften Speicherweg](../plans/2026-10-27-sample-store.md)
und zum [Snapshot eines einzelnen Samples](2026-10-30-sample-snapshot.md).

## Gebaut und hergeleitet

Der Laufzeitpatch enthält `catalogue_begin` und `catalogue_end` als
gemeinsame Grenze für einen Kartenschreiber. Sie verwenden die bestehende
Dateisperre und die bisherigen Puffer. Es gibt keine zusätzliche
RAM-Reservierung und keinen neuen Flash-Zugriff.

`catalogue_begin` verweigert einen nicht initialisierten oder über EXIT
umgangenen Laufzeitstand, einen DSP-Fehler und einen konkurrierenden
Dateibesitzer. Nach erfolgreichem Erwerb einer Wiederherstellungs-Sperre:

1. Patternwechsel sperren und die Cache-Generation erhöhen.
2. Alte Ladeaufträge, vorbereitete Blöcke und Cache-Einträge ungültig machen.
3. Den gemeinsamen Leser vollständig schließen.
4. Das Journal auflösen und den tatsächlichen Dateikopf lesen und prüfen.

Der Schreiber behält die Sperre bis `catalogue_end`. Auch bei einem
gemeldeten Schreibfehler wird dort zuerst erneut geschlossen, das Journal
geprüft und der tatsächliche Index gelesen. Erst dieser geprüfte Stand
erlaubt die Freigabe des Katalogs. Ein vorheriger Operationsfehler bleibt
ein Fehler, selbst wenn der Index wieder lesbar ist.

Schließ-, Wiederherstellungs- und Lesefehler halten den Katalog ungeklärt
und den Swap gesperrt. Ein inzwischen gesetzter DSP-Fehler bleibt erhalten
und verhindert ebenfalls die Freigabe zum Wechseln. Eine kleine Datei
kehrt zum bisherigen Ladebetrieb zurück; eine große Datei zum Swap.

Der Aufrufer muss aus einem Task mit erlaubten Interrupts kommen. Die
zusätzliche Prüfung `owner_check_recovery` verlangt vor Dateizugriffen den
aktuellen Wiederherstellungs-Token, Task-Kontext und eine gestartete
Firmware ohne laufenden Interrupt. Ein ungültiger Abschluss lässt den
bestehenden Besitzer unverändert, damit der zuständige Task aufräumen kann.

## Gemessen: Fehler und Unterbrechungsgrenzen

Die ARM-Modellfälle führen den erzeugten Code aus. Sie prüfen ungültige
und fremde Token, konkurrierende Leser, Journalfehler, kurze und fehlerhafte
Indexlesezugriffe, ungültige Offsets, Schließfehler und DSP-Fehler. Sämtliche
Dateioperationen finden bei erlaubten Interrupts statt.

Zwei Gegenproben schlugen vor der Korrektur fehl:

- Ein Abschluss mit gültigem Token führte bei gesperrten Interrupts bereits
  Dateizugriffe aus. Erst danach verweigerten die alten Sperrfunktionen die
  Freigabe. Der Abschluss prüft jetzt den Ausführungskontext vor dem ersten
  Dateizugriff.
- Ein UI-Frame konnte die Generation zwischen Vorprüfung und Sperrerwerb
  auf `0xFFFFFFFF` erhöhen. Das anschließende Erhöhen wurde null. Nach
  Aktivierung der Wechselsperre wird die Grenze erneut geprüft; ein solcher
  Auftrag endet ohne Dateizugriff und ohne Überlauf.

Die nativen Snapshot-Fälle benutzen diese gemeinsame Grenze mit echtem
FatFs, nativem Deskriptor und begrenztem DSP-Transport. Geprüft werden
Mono und Stereo, ursprüngliche und verschobene DSP-Zuordnung, erneutes
Speichern ohne Dateischreiben sowie vollständiger Neustart. Unterschiedliche
alte und neue PCM verhindern, dass ein überschriebenes altes Sample
versehentlich als erhalten gilt. Der Index im CPU-RAM entspricht nach dem
Speichern dem erneut gelesenen Kartenindex.

## Prüfung dieses Stands

| Prüfung | Ergebnis |
|---|---|
| Neue ARM-Fälle für die Schreibgrenze | 13 bestanden |
| ARM-Fälle für den Dateibesitzer | 15 bestanden |
| Native Snapshot-Fälle, Stock und Hacktribe | jeweils 8 bestanden |
| Nativer Dateileser samt Schließfehlern und konkurrierendem Besitzer | jeweils 5 bestanden |
| `tools/emu/check.py --quick`, Start und Schutzgrenzen | jeweils 21 bestanden |
| `npm test` | 1365 bestanden, 161 ausgelassen, kein Fehler |
| `npm run test:e2e` | 285 bestanden, 1 ausgelassen, kein Fehler |

Die beiden roten Originale erzeugen denselben geschützten Swap-Patch.
Die ausgelassenen lokalen Prüfungen ersetzen keine Geräteprüfung. Der
gesonderte Snapshot-Aufbau und die Tests des Dateilesers liefen mit
eigenen Originaldateien auf beiden roten Builds.

## Offen

Die normalen Import-, WRITE-, Lösch- und Aufnahmebestätigungen sind noch
nicht an diese Grenze angeschlossen. Der Snapshotadapter wird in diesen
Fällen gesondert im Emulator installiert. Die Prüfung belegt deshalb noch
keine dauerhafte Speicherung über die normalen Bedienelemente.

Vor dem ersten Import ohne vorhandene Sammlung fehlt die frühe
Initialisierung von Standardpfad und Laufzeitstand. Ein fehlgeschlagenes
Schließen des Import-Quellhandles muss beim späteren Anschluss ebenfalls
als unklarer Dateizustand erhalten bleiben. Die physischen Versionsmarken
und die Belegung einer neuen DSP-Zeile sind noch nicht veröffentlicht.

Gesamtexport, echte Aufnahme mit DMA, Stimmenausklang, die physische
DSP-Grenze und der 25-MHz-Test auf einer Ersatzkarte bleiben offen.
Die vorherige vollständige Prüfung mit 742 beziehungsweise 717 Fällen
ist kein vollständiger Prüflauf des hier erweiterten Laufzeitpatches.
Die Freigabe für 1.4 bleibt ausstehend.
