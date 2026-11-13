# Sample Edit: Sicherung und tatsächliches Bearbeitungsziel

## Gemessen am Gerät: Ausgangszustand

Rote Electribe 2 Sampler mit Korg 2.02, Hacktribe und minimalem
BLECH-SysEx-Messbuild. Seit dem [einzelnen WAV-Import](2026-11-08-sample-ram-import.md)
gab es keinen weiteren Neustart und keinen Kartenwechsel.

Vor der Bedienung bestätigt ein weiterer RAM-Vergleich alle 396 Blöcke
des erhaltenen Musters `Adresse XOR 0x36E2B951` in
`0xC274F000..0xC4000000`, rechte Grenze exklusiv. Spiegel, gecachte Sicht
und Sichtvergleich sind ohne abweichende Seite. Der erste KiB des
EXEC-Arbeitsbereichs ist anschließend wiederhergestellt.

Es sind 41 physische Sample-Zeilen aktiv. Slot 541, intern 540, heißt
`import`, hat 100.000 PCM-Bytes und den relativen Startpunkt 0.

## Gemessen am Gerät: erste Beobachtung abgebrochen

Die neue Bedienbeobachtung sendet nur INFO und READ. Beim Eintritt in
Sample Edit bleibt eine Leseantwort länger als sechs Sekunden aus. Die
Beobachtung bricht ab; sie enthält keinen EXEC-Aufruf. Die Ursache der
fehlenden Leseantwort ist nicht bestimmt. Der Fehler wird nicht durch
eine erhöhte Frist oder einen automatischen Wiederholungsversuch verdeckt.

Nach bestätigter manueller Änderung antworten zwei gesonderte reine
Lese-Prüfungen wieder. Die Bearbeitungsseite ist Bildschirm 38, der
Transport steht auf STOP. Die Prüfungen finden:

| Gegenstand | Ergebnis |
|---|---|
| Zielslot | intern 540, Name `import` |
| Physische Zielzeile | 540 |
| Relativer Startpunkt des Ziels | 67 statt vorher 0 |
| Sicherung gültig, Byte `0xC0345A20` | 1 |
| Index am Anfang des Sicherungsdeskriptors `0xC0345A2C` | 500 |
| Name im Sicherungsdeskriptor | `t501` |
| Zuordnungsschlüssel im Sicherungsdeskriptor | 500 |
| Name und Zuordnungsschlüssel der Zielzeile | `import`, 540 |

Die Sicherung gehört damit zu einem anderen Sample. Es handelt sich
nicht nur um zwei unterschiedliche Nummerierungen desselben Eintrags.
Die Beobachtung verlangt eine zum Bearbeitungsziel passende Sicherung
und wertet diesen Versuch deshalb nicht als bestandenen EXIT-Test.

Die anschließende manuelle Bereinigung setzt den Startpunkt von
Slot 541 auf 0 zurück, danach folgt EXIT ohne WRITE. Eine neue reine
Lese-Prüfung bestätigt Startpunkt und Playback-Werte, alle 41
Metadaten-Prüfsummen und den DSP-Freizeiger 27.663.200 im Ausgangszustand.
Die Sicherung ist freigegeben. Ein weiterer RAM-Vergleich bestätigt alle
396 Blöcke ohne Abweichung in beiden Sichten; der Arbeitsbereich ist
wiederhergestellt. Dies ist eine manuelle Bereinigung und noch kein
bestandener Test der nativen Rücknahme des geänderten Samples.

## Gemessen am Gerät: Wiederholung mit passender Sicherung

Vor jeder weiteren Änderung wird der tatsächliche Zustand getrennt
gelesen. Die Bearbeitungsseite ist bereits aktiv. Der Sample-Manager
wählt intern Slot 540; gültiger Sicherungsindex, gesicherter Name und
Zuordnungsschlüssel lauten jetzt ebenfalls 540, `import`, 540. Der
relative Startpunkt ist noch 0. Ein weiteres ENTER ist nicht nötig.

Danach wird nur der Startpunkt geändert. Die nächste reine Lese-Prüfung
findet den Wert 18, weiterhin bei derselben Auswahl und derselben
passenden Sicherung. Es folgt EXIT auf die Hauptseite, ohne WRITE und
ohne vorheriges manuelles Zurückdrehen des Startpunkts.

| Nachherbeobachtung | Ergebnis |
|---|---|
| Bedienseite und Transport | Hauptseite, kein Modalfenster, STOP |
| Sicherung gültig | 0, freigegeben |
| Zielslot und physische Zeile | weiterhin 540 |
| Name und PCM-Länge | weiterhin `import`, 100.000 Bytes |
| Relativer Startpunkt | 0, durch EXIT von 18 zurückgesetzt |
| Playback-Werte des Ziels | wie vor der Änderung |
| Metadaten aller 41 aktiven Zeilen | alle Prüfsummen wie vorher |
| Nächster freier DSP-Platz | unverändert 27.663.200 |

Die Auswertung der tatsächlichen Vorher-, Änderungs- und Nachherzustände
bestätigt damit die Rücknahme. Es sind ausdrücklich getrennte reine
Lese-Prüfungen; eine durchgehende Beobachtung jedes Bedien- oder
Speicherzugriffs wird nicht behauptet.

## Gemessen am Gerät: RAM nach dem passenden EXIT-Ablauf

Das erhaltene Muster wird nach der Rücknahme erneut ohne Füllen geprüft.
Alle 396 Blöcke und 6321 Seiten des oberen Bereichs werden bestätigt:
keine Seite weicht im Spiegel oder in der gecachten Sicht vom Muster ab,
beide Sichten melden keine unterschiedlichen Werte. Der Durchgang endet
ohne Timeout und mit wiederhergestelltem ersten KiB des EXEC-Arbeitsbereichs.

Der passende Startpunkt-/EXIT-Ablauf und sein RAM-Nachhervergleich sind
damit für diesen einzelnen erzeugten Mono-Sample geprüft. Er ersetzt
keine Freigabe aller Bearbeitungsarten oder der gesamten oberen Fläche.

## Gemessen im Emulator: richtige und abweichende Auswahl

Die Auswertung besteht 17 Gegenproben mit selbst erzeugten Tabellen.
Sie folgen der gesamten Zuordnung vom logischen Slot bis zur physischen
Zeile. Eine zusätzliche Probe verwendet absichtlich eine physische Zeile,
die von der logischen Slotnummer abweicht. Mono- und Stereo-Startpunkte
werden in Frames ausgewertet.

Im nativen Stock-Emulator mit erzeugten Samples liefert der geprüfte
Startpunkt dieselben Werte wie der native Getter `0xC004E63C`:

- Sample 500 vor Eintritt auswählen und seine Sicherung erzeugen.
- Startpunkt 0 auf 1 ändern.
- EXIT setzt den Startpunkt auf 0 zurück. Metadaten und DSP-Freizeiger
  entsprechen dem Vorherzustand; es gibt keine Emulator-Assertion.

Eine separate native Gegenprobe wechselt erst nach der Sicherung von
Sample 500 über `0xC007EC74` zu Sample 501 und ändert dessen Startpunkt.
Der Sicherungsindex bleibt 500. Nach EXIT steht der Startpunkt von
Sample 501 weiterhin auf 1. Auch dieser Ablauf meldet keine Assertion.
Er reproduziert die Wirkung einer nachträglich abweichenden Auswahl;
er belegt keine identische Folge physischer Tastendrücke am Gerät.

## Hergeleitet aus dem Stock-Original

Der Sicherungspfad `0xC0039514` liest den ausgewählten Eintrag aus dem
Sample-Manager und ruft `0xC004EBD4` auf. Diese Funktion schreibt ihren
Eingabeindex an den Anfang des Sicherungsdeskriptors und kopiert die
zugehörige Namenzeile hinein. Der EXIT-Pfad `0xC0039420` gibt diesen
Deskriptor an die native Wiederherstellung `0xC004EFF4` weiter.

Ein geschlossener Bearbeitungsbildschirm allein beweist daher nicht,
dass die Änderung am gewünschten Sample zurückgenommen wurde. Vor der
Änderung müssen ausgewähltes Sample, Sicherungsindex und gesicherter Name
zusammenpassen. Danach muss der tatsächliche Startpunkt zurückkehren.

## Vorbereitung im Emulator: WRITE und anschließendes EXIT

Eine zusätzliche native Stock-Probe mit erzeugten Samples ändert den
Startpunkt von 0 auf 1 und drückt auf der Bearbeitungsseite WRITE.
Der Wert bleibt nach WRITE und anschließendem EXIT auf 1. Die
Metadaten-Prüfsummen und der DSP-Freizeiger sind unverändert. Nach WRITE
ist die Sicherung noch gültig; eine sofort freigegebene Sicherung wäre
für diesen Ablauf deshalb kein passendes Prüfkriterium.

Die emulierten Flash- und Karteninhalte sind vor und nach dem Ablauf
bytegleich. Es gibt keinen zusätzlichen NOR-Programmier- oder
Löschbefehl und keine Assertion. Das ist eine Vorbereitung der nächsten
Geräteprobe, keine bereits gemessene WRITE-Bedienung am Gerät und kein
Nachweis dauerhaften Speicherns in der `.all`.

## Offen

Die Ursache der einmal ausgebliebenen Leseantwort bleibt offen. WRITE,
Löschen, Export und weitere Sample-Edit-Parameter sind mit dieser
Geräteprobe nicht geprüft. Die DSP-Audiodaten wurden nicht zurückgelesen
oder verglichen; gleiche Metadaten sind kein separater Klangnachweis.
Kurzzeitige oder zurückgenommene Änderungen sowie unbekannte
DMA-Eigentümer bleiben durch einen RAM-Nachhervergleich allein offen.

Es wurde keine neue Firmware installiert und kein neuer Karten- oder
Flash-Schreibpfad ausgeführt. Das obere Prüfmuster bleibt erhalten; vor
normaler Nutzung ist die Messsitzung mit einem Neustart zu beenden.
Ein neuer Swap-Cache ist weiterhin nicht freigegeben.
