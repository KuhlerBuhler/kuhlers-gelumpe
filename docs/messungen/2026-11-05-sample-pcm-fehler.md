# Sample-Swap: PCM-Fehler und die nächste RAM-Prüfung

Stand: 06.11.2026. Läufe vom 05./06.11.2026. Gemessen mit erzeugten Daten im ARM-Modell und auf den
beiden roten Originalen im Emulator. Die nachfolgend beschriebenen PCM-Läufe
verwenden kein Gerät. Die spätere lesende Geräteprüfung steht im
[eigenen Bericht](2026-11-06-sample-ram-vorpruefung.md). Ergänzt die
[PCM-Schreibpfade](2026-11-05-sample-pcm-schreibpfade.md) und den
[physischen Schutz](2026-11-05-sample-schutz.md).

## Gemessen: Abbruch wird bis zum Import zurückgegeben

Die Sample-Blockaufrufe bei `0xC00141F8` und `0xC0014284` erhalten nach
initialisiertem Laufzeitstatus auch außerhalb eines Swap-Schritts einen
eigenen begrenzten Kontext. Im untersuchten Parserpfad reichen die
Rückgaben danach bis zum einzelnen WAV-Import durch:

| Fortsetzung | Behandlung |
|---|---|
| `0xC004EF58` | Fehlgeschlagenes Lesen vor einem kleinen Schreibblock beendet den Helfer vor weiteren Datenzugriffen. |
| `0xC0036320` | Fehler des normalen PCM-Schreibens geht zum nativen Parser-Abschluss mit Status 4. |
| `0xC00363E4` | Dasselbe gilt für den letzten Teilblock. |

Die neuen Fälle in `tools/emu/sample_pcm_cases.py` verwenden WAVs mit
1, 16 und 17 Frames. Normale Importe geben 0 zurück. Ein absichtlich nicht
antwortender Lesepfad beim kleinen Block und die beiden Schreibpfade geben
4 zurück. Der eigene Ressourcenbesitz endet, der Kontext wird entfernt,
die Fehlersperre bleibt gesetzt. Nach dem Fehler wird kein weiterer
Portschreibzugriff beobachtet. Die Kartendatei bleibt dabei unverändert.
Die Probe behauptet keine Rücknahme bereits veränderter nativer Tabellen.

Der normale Arbeitspufferwechsel vor dem PCM-Aufruf erhöht bereits den
Cache-Zähler. Die Gegenprobe erfasst deshalb dessen Stand am Beginn des
Transfers und prüft den zusätzlichen Fehlerwechsel getrennt. Ein Vergleich
nur mit dem Stand vor dem ganzen Import wäre falsch.

## Gemessen: laufender Transfer und verriegelter Fehler sind verschieden

Der gemeinsame Transportstatus hat drei Zustände: 0 ist bereit, 1 bezeichnet
einen laufenden Transfer, 2 einen verriegelten Fehler. Ein anderer Besitzer
mit Zustand 1 ist beschäftigt. Er wird nicht allein dadurch zum Fehler.
Ein nach tatsächlich erworbenem Port übrig gebliebener Zustand 1 gilt dagegen
als abgebrochener Vorgang und verriegelt den Transport.

Die Gegenproben setzen einen fremden Fehler während des ersten Wartens,
vor Datenwörtern und am Abschluss. Der fortgesetzte Aufruf darf ihn weder
auf 1 zurücksetzen noch am Ende löschen. Der Übergang vor dem Header und
der Abschluss prüfen den Zustand unter einer kurzen IRQ-Sperre. Vor jedem
Datenwort wird er erneut geprüft. Timer- und Host-Port-Warten geschehen
mit erlaubten Interrupts.

Eine Zeile mit verriegeltem Transportfehler erhält keine neue saubere
Signatur. Auch eine bereits vorbereitete Verdrängung wird dann abgewiesen.
Ein fremder laufender Transfer ist kein solcher Fehler.

## Gemessen: abgebrochene Aufträge schreiben nicht verspätet

Eine native Metadatenänderung beendet den laufenden Swap-Auftrag, ohne
unveränderte andere Cacheeinträge zu verwerfen. Platzsuche, endgültige
Reservierung und Aktivierung verwenden dieselbe Schutzrevision. Eine
Änderung nach der Reservierung oder während der Auftragsvorbereitung darf
den zuvor abgebrochenen Auftrag nicht erneut aktivieren.

Der DSP-Transport prüft seinen Schreibauftrag nach Ressourcenerwerb und
nochmals gemeinsam mit Headerstart und Zustandswechsel. Dabei müssen
Dateileser, Generation, Ziel, Quelle und bereitgestellte Länge noch passen.
Der spezielle Rückgabewert 7 beendet einen veralteten Auftrag, ohne einen
DSP-Protokollfehler vorzutäuschen. Der erworbene Port wird einmal freigegeben.

Ein nativer Wechseltest fand eine zu enge private 16-KiB-Grenze in dieser
Prüfung. Der Ladepfad verwendet 64-KiB-Blöcke. Die Prüfung verwendet jetzt
dieselbe `CHUNK`-Konstante; ein eigener Modellfall prüft die volle Länge und
einen zu großen Folgeblock. Der native Patternwechsel besteht danach auf
beiden roten Builds.

## Gemessen: tatsächliche Drehregler-Schreibstellen

Zusätzlich zu den direkten Settern sind die inkrementellen Schreibstellen
`0xC007F0EC` für Tune und `0xC007EFE8` für Pegel geschützt. Ihr Zeiger liegt
16 beziehungsweise 8 Byte innerhalb der physischen Metadatenzeile. Die Marke
wird anhand dieser Zeile gesetzt, bevor der neue Wert geschrieben wird.

Die native Probe öffnet Sample Edit, richtet die Auswahl mit erzeugten
Daten ein und bewegt den echten emulierten Drehregler um einen Schritt.
Für die Gegenrichtung ruft sie den nativen inkrementellen Handler auf.
Die zweite Aktion ist kein nachgewiesener negativer Drehreglerimpuls.
Die Rückkehr zum alten Wert entfernt die ungesicherte Änderungsmarke nicht.

## Hergeleitet: Grenzen der Timeout-Aussage

Das bisherige Budget beträgt 100 ms bei gültigem 150-MHz-Timer, zusätzlich
begrenzt eine Pollanzahl den Lauf. Das begrenzt die beobachteten Portschleifen,
belegt aber kein passendes Budget für alle Befehle unter echter Last.
Der ursprüngliche Kernel-Ressourcenerwerb `0xC0000D80` kann weiterhin warten;
diese Wartezeit ist keine nachgewiesene globale Deadline.

PCM-Aufträge benötigen weiterhin eine zum tatsächlichen nativen Aufruf
gehörende Bibliothekskennung nach wartendem Erwerb. Der neue Rückgabepfad
macht deren spätere Ablehnung möglich; er ersetzt diesen Besitznachweis nicht.
Auch eine reine PCM-Änderung ohne geänderte Tabellen erhält noch keine
vollständige Schutzmarke. Die separate PCM-Schreibgegenprobe bleibt deshalb
ein Freigabeblocker.

Die früher am Gerät gemessenen ungefähr 10 bis 11 MiB/s gelten nicht als
Messung dieses neuen Transportstands. IRQ-Prüfungen und Fehlerweitergabe
verändern den Pfad; die reale Geschwindigkeit muss erneut geprüft werden.

## Gemessen im Emulator: Aufnahmefenster und CPU-RAM

`tools/emu/highram_watch.py --capture` ergänzt Sampling und Resampling in
Mono und Stereo. Der Ablauf benutzt Fenster 42, die nativen Einstellungs-
und Start-/STOP-Funktionen und danach den echten EXIT-Pfad. Der geschlossene
Fensterzeiger und der zurückgesetzte Transport werden geprüft. Das Ergebnisfeld
`discarded` bezeichnet diese Fensterprüfung, keinen eigenen Nachweis einer
vollständigen Sample-Löschung.

Die vier ergänzten Fälle bestehen auf dem ursprünglichen Hacktribe-Build
mit erzeugter Karte. In diesen ausgeübten CPU-Pfaden werden keine Zugriffe
oberhalb des Stackbereichs beobachtet. Der DSP-Endzeiger wird ausdrücklich
mit einem 64-Byte-Abschluss modelliert. Es gibt keine echte Aufnahme, kein
Audio und keinen DMA-Nachweis. Der Resampling-Start verwendet `request_play=0`;
der PLAY-startende Zweig ist dadurch nicht abgedeckt.

Der vollständige Lauf mit 40 erzeugten Samples und 24.000.000 Byte PCM
endet nach rund 291 Sekunden emulierter Zeit ohne Assertion und mit
abgeschaltetem Gerät. Boot-Wiederverwendung war abgeschaltet. Er umfasst
PLAY/Pads, Menüs, Patternwechsel, die vier Capturefälle, WAV-Import,
Sample-Gesamtexport, Patternbank-Export und Patternbank-Import.
Die erwarteten DATA-UTILITY-Seiten wurden erkannt. Sample- und
Patternbankdatei entstehen; die exportierte Sampledatei ist 23.553.376 Byte
und die Patternbank 4.161.792 Byte groß. Der Samplegrößenunterschied passt
zu einem durch die 100.000-Byte-WAV ersetzten 600.000-Byte-Sample;
ein vollständiger Slot-Inhaltsvergleich ist damit nicht gemessen.

Ein konkreter CPU-Befund widerlegt dauerhaft freien unteren Cache-RAM:
Beim Patternbank-Import beschreibt `0xC0018178` den Arbeitspuffer bis
`0xC1122840`, `0xC009BB2C` bis `0xC1122940` (jeweils exklusive Grenze).
Das reicht über den vorgesehenen Cachebeginn `0xC1010000` hinaus.
Der gesamte beobachtete Importpuffer umfasst 4.096.000 Byte ab
`0xC0D3A940`. Die untere Fläche darf daher nur mit ausdrücklicher,
abbrechbarer Besitzübergabe benutzt werden.

Im vollständigen Lauf gibt es keine aufgezeichneten CPU-Zugriffe ab
`0xC274F000`; der beobachtete Stack liegt weiterhin darunter. Das gilt
nur für diese ausgeübten Pfade. Ein erfolgreicher Skriptausgang allein
beweist keinen vollständigen Import-/Exportinhalt. USB, lange Aufnahmen,
der PLAY-startende Resamplingzweig und sämtliche Bearbeitungswege bleiben
eigene Nachweise. DMA und zukünftige Leser werden dadurch nicht ausgeschlossen.

## Vorbereitete Geräteprobe

`tools/device/sample_ram_canary.py` benutzt nur `0xC274F000` bis
`0xC4000000`. Der native Arbeitspuffer und beide Stackbereiche bleiben
außerhalb des Füllbereichs. Die bisherigen rund 47 MiB sind damit nicht
als zusammenhängender Cache freigegeben.

Die Probe benötigt einen frisch gestarteten Ausgangsbuild ohne Sample-Swap
und ohne andere Verbraucher des oberen RAMs. Dafür sind getrennte Kopien der
eigenen Originale mit ausschließlich dem vorhandenen BLECH-SysEx-Patch
vorbereitet. Je 20 Start-/Abbildprüfungen dieser minimalen Kopien bestehen;
sie wurden nicht installiert. Eine erzeugte Testbibliothek und
eine WAV liegen getrennt davon außerhalb des Repositorys bereit.
Die Vorprüfung vergleicht sieben Codebereiche einschließlich Variantenliteral,
Doom-Lader, Plugin-Laufzeit und Versionsbereich mit dem eigenen Original.
Eine Abweichung beendet die Probe vor dem Füllen. Diese Stichproben ersetzen
nicht die Voraussetzung eines frisch gestarteten bekannten Messbuilds.
Die Probe liest außerdem das CPU-Steuer-
register: Mit eingeschalteter MMU oder Daten-Cache beginnt keine Messung.
Code, Ergebnis und Tabelle teilen ausschließlich das bereits erlaubte erste
KiB bei `0xC1000000` bis `0xC1000400`. Eine Teilprüfung umfasst höchstens
224 Seiten, damit ihre Tabelle in die verbleibenden 224 Byte passt. Große
Bereiche werden in mehreren solchen Portionen ausgelesen. Die vorhandene
Schutz-Tabelle wird dafür nicht erweitert.

Eine zusätzliche Prüfung über die echte BLECH-SysEx-Schnittstelle im Emulator
benutzt auf beiden minimalen Builds jeweils 225 Seiten. Zwei Portionen
liefern zunächst keine Änderung. Ein absichtlich geändertes Wort in der
letzten Seite erscheint danach genau dort. Upload, EXEC und die per CRC
geprüfte Scratch-Wiederherstellung funktionieren. Der erste Entwurf mit
einer Tabelle außerhalb des erlaubten Fensters scheiterte dagegen bereits
bei WRITE BEGIN während der Wiederherstellung; dieser Entwurf wird nicht
für das Gerät verwendet.

Die Scratch-Routinen liegen vorübergehend im nativen Arbeitspuffer und dürfen
keine Modusaktion überleben. Deshalb gibt es ausschließlich Einzelaufrufe
bei bestätigtem STOP auf der Hauptseite ohne Fenster. Firmwarezustand und
Zeiger werden vor Upload, EXEC und Wiederherstellung geprüft; der ARM-Code
prüft den Kontext nochmals vor dem ersten Zugriff auf den oberen Bereich.

Der Ablauf am Gerät ist:

1. Gesicherte Testkarte und passenden frisch gestarteten Ausgangsbuild prüfen, STOP und Hauptseite,
   freier MIDI-Port. Während jedes Aufrufs keine Bedienung oder weitere Sitzung.
2. Genau einen `fill`-Aufruf vollständig beenden lassen. Scratch-RAM muss
   wiederhergestellt sein, bevor eine Modusaktion beginnt.
3. Sampling, Resampling, Import, Export und USB jeweils am Gerät ausführen,
   vollständig beenden und zu STOP/Hauptseite zurückkehren.
4. Dazwischen jeweils einen getrennten `check`-Aufruf vollständig abschließen.
   Erst nach dessen Prozessende weiterbedienen.
5. Nach der Sitzung neu starten. Ein unbestätigter EXEC beendet die Verbindung
   ohne Wiederholung oder weitere Wiederherstellung; dann direkt neu starten.

Ohne `--execute` wird nur der Offline-Plan ausgegeben. Ein konkreter Aufruf
nach Gerätefreigabe sieht beispielsweise so aus:

```bash
python3 tools/device/sample_ram_canary.py --execute --operation fill \
  --ram-overwrite-confirmed --port-idle-confirmed --stopped-main-confirmed \
  --vsb "$E2_HACKTRIBE_VSB" --json "$RAM_FILL_REPORT"
```

Für spätere Einzelprüfungen wird `--operation check` mit jeweils einer neuen
Berichtsdatei verwendet. Die obere Testfläche selbst wird nicht mit alten
Daten zurückgeschrieben; wiederhergestellt wird nur der kurz belegte Scratch-
Bereich. Die 13 synthetischen Gegenproben prüfen Grenzverletzungen,
Cache-/Kontextverweigerung und den Abbruch nach unbestätigtem EXEC.

Geänderte Canaries belegen eine Schreibnutzung. Unveränderte Werte beweisen
keinen fehlenden Besitzer, keinen zukünftigen Leser und keine sichere DMA-
Lebensdauer. Der Controller- und Besitznachweis bleibt zusätzlich erforderlich.
Es wurde noch kein neuer Gerätewert gemessen und kein neuer Cache installiert.

## Gemessen: abschließende lokale Prüfungen

| Prüfung | Ergebnis |
|---|---|
| ARM-Modelle für Swap, Schutz, Transport, Scope, Capture, Export, Store und RAM-Probe | 239 bestanden |
| `GELUMPE_JOBS=1 npm test` | 1368 bestanden, 161 ausgelassen, kein Fehler |
| `npm run test:e2e` | 285 bestanden, 1 ausgelassen, kein Fehler |
| Patcher-Browserfälle mit der letzten Patchdatei erneut geprüft | 19 bestanden |
| Gezielte native Fälle je rotem Build | 25 bestanden |
| Startprüfungen des gesamten Patchsets je rotem Build | 21 bestanden |
| Dokumentprüfung | 9 bestanden |

Der breite Browserlauf begann vor der letzten Korrektur der Chunkgrenze;
die betroffenen Patcher-Seiten wurden deshalb danach gesondert wiederholt.
Die letzten Laufzeitquellen und Testquellen sind per Prüfsummen festgehalten.

Die ersten überladenen Gesamtprüfungen liefen in Prozess-Zeitlimits. Die
Modelle assemblieren ihre unveränderliche Codevorlage jetzt einmal pro
Testprozess und verwenden weiterhin getrennte RAM-Inhalte. Die äußere
Testparallelität ist in den Unit-, CI- und lokalen Testbefehlen auf eine
Datei begrenzt. Die bisherigen Zeitlimits und Assertions bleiben bestehen.
Der abschließende Gesamtaufruf ist damit grün.

Die separate PCM-only-Gegenprobe scheitert dagegen auf beiden letzten
roten Builds weiterhin wie erwartet: DSP-Daten ändern sich, Tabellen und
Signatur bleiben gleich, die fehlende Marke lässt Verdrängung zu. Diese
Gegenprobe wird nicht als bestandener Featuretest gezählt. Die enge
Codeprüfung des neuen Transport- und Geräteprüfpfads ist abgeschlossen;
das Gesamtfeature bleibt gesperrt.

## Entscheidung und offene Arbeit

Weiterbau des Swap-Schutzes ist lokal vorbereitet. Vor einer Installation
oder einem Hörtest muss der tatsächliche RAM-/DMA-Besitz geklärt werden.
Der aktuelle Stand ist kein fertiges Sample-Swap-Feature und keine Freigabe
für 1.4. PCM-Versionen, vollständige native Änderungen, Journal-I/O-Fehler,
dauerhaftes Speichern über die Menüs und die abschließende große Bibliothek
bleiben zusätzlich offen. `verified.json` wurde nicht erneuert.
