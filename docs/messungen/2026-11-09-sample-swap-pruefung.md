# Sample-Swap: Gesamtprüfung vor weiteren Gerätetests

## Ergebnis

Die vorhandenen Standardprüfungen bestehen. Der Swap ist trotzdem noch nicht
freigabefähig: gezielte Gegenproben zeigen drei offene Schutzlücken. Die
Produktionspatches wurden bei dieser Prüfung nicht geändert. Erzeugte Samples
und Kartenabbilder bleiben die Grundlage der Tests; eigene Firmwaredateien und
vollständige Laufprotokolle liegen außerhalb des Repos.

## Gemessen im Emulator und in den Softwaretests

| Prüfung | Ergebnis |
|---|---|
| `GELUMPE_JOBS=1 npm test` | 1.374 bestanden, 161 übersprungen, kein Fehler |
| `npm run test:e2e` | 285 bestanden, eine übersprungen, kein Fehler |
| Optionaler Browser-Test mit nativer Stock-Firmware, ausdrücklich aktiviert | einer bestanden, keine Auslassung |
| Vollständige native Patchprüfung Stock | 763 Prüfungen bestanden |
| Vollständige native Patchprüfung Hacktribe | 738 Prüfungen bestanden |
| Vollständige native Patchprüfung Synth | 494 Prüfungen bestanden |
| Python-Prüfungen der Patch-Bausteine | 532 Tests, einer übersprungen, kein Fehler |
| Python-Prüfungen der Gerätewerkzeuge | 175 Tests, kein Fehler |
| Python-Prüfungen des Emulators mit eigenen Originalen | 264 Tests, keine übersprungen, kein Fehler |
| Native Sample-Speicherung und Sicherung nach korrigierten Testannahmen | fünf übergeordnete Tests, kein Fehler und keine Auslassung |

Die drei vollständigen nativen Patchprüfungen verwenden `--cases all`. Damit
wird die Freigabedatei `data/patches/verified.json` nicht neu geschrieben. Das
ist keine Release-Verifikation und ersetzt keinen Klangtest. Jede Variante
prüft ihren eigenen enthaltenen Patchsatz; die Synth-Prüfung belegt keinen
Sample-Swap auf einem unveränderten Synth.

Im ersten stark parallelen Lauf liefen drei JavaScript-Tests und zwei
Emulator-Service-Tests in ihre bestehenden Zeitgrenzen. Die isolierten
Wiederholungen bestehen bei unveränderten Grenzen. Die höhere Parallelität
reproduziert somit keinen deterministischen Funktionsfehler; die genaue
Ursache der früheren Zeitüberschreitungen wurde nicht gemessen.

Veraltete Testannahmen wurden an ihrer Quelle korrigiert:

- Der Speicherungsfall liefert inzwischen fünf ausdrücklich benannte Ergebnisse.
- Die native Rücknahme-Sicherung wurde mit einem ungebundenen Swap-Auftrag
  vorbereitet. Der korrigierte Test verwendet den nativen Schreiber im nativen
  Modus, prüft die tatsächlich geschriebenen DSP-Bytes und veröffentlicht erst
  den bestätigten Transfer. Schutzprüfungen werden dabei nicht abgeschaltet.
- Der optionale native Browser-Test erwartete einen inzwischen entfernten
  Beschreibungstext. Er prüft nun die tatsächliche Freigabe des Effekteditors;
  Schreiben, Rücklesen und Undo im nativen Emulator bleiben vollständig erhalten.

Die zusätzlichen Modussitzungen des vollständigen Builds treffen außerdem auf
Pattern Confirm: Drehen während PLAY wählt nur die Vorschau, MENU bestätigt
den Wechsel. Der erste Prüfablauf erwartete dagegen einen unmittelbaren
Wechsel und brach vor den späteren Modi ab. Dieser Abbruch belegt keine
Sample-Swap-Regression und auch keine erfolgreiche Prüfung der unerreichten
Modi.

## Hergeleitet: Aktivierungsgrenze und Startverhalten

Der aktuelle Dateipfad in `sample_swap.py` aktiviert den Swap erst, wenn die
Dateigröße größer als `ss_cap + 0x1000` ist. Der Vorgabewert von `ss_cap`
ist 25 MiB. Verglichen wird die ganze Datei, also auch ihre Record-Header,
nicht nur die Summe ihrer PCM-Daten. Kleinere Dateien verwenden weiterhin
den nativen Gesamtlader. Ein allgemeiner Start mit nur Index und aktivem
Pattern für jede Bibliotheksgröße ist damit noch nicht umgesetzt.

Die 24-MB-Modussitzungen liegen unter dieser Schwelle. Auch mit installiertem
vollständigem Patchsatz prüfen sie den nativen Modus und dessen Haken,
nicht die aktive dynamische Auslagerung. Die gezielten Swap-Fälle der
Patchprüfung sind davon getrennte Nachweise.

## Gemessen im Emulator: vollständige native Modussitzungen im Minimalbuild

Stock und Hacktribe bestehen jeweils alle 13 Ergebnisprüfungen einer
Modussitzung mit 40 erzeugten Samples zu je 300.000 Frames, zusammen
24.000.000 PCM-Bytes. Geprüft werden Start, PLAY und Patternwechsel,
Sampling und Resampling in Mono und Stereo, WAV-Import, Sample Edit mit
EXIT und WRITE, Einzel- und Gesamtexport, Import einer Sammeldatei und Löschen.

Die Prüfungen vergleichen die tatsächlichen Metadaten, Sample-Zahlen,
DSP-Freizeiger und erzeugten Dateiinhalte. Beide Sitzungen enden ohne
Assertion und ohne beobachtete CPU-Zugriffe auf `0xC274F000..0xC4000000`
oder den emulierten Alias `0xC674F000..0xC8000000`, jeweils rechte Grenze
exklusiv. Der vollständige Swap ist in diesen
Minimalbuilds nicht enthalten. Die modellierten Aufnahmeenden ersetzen
weiterhin weder Klang noch DMA. Die entsprechenden Sitzungen des
vollständigen Builds werden getrennt bewertet.

## Gemessen im Emulator: dieselben 13 Abläufe im vollständigen Build

Nach zwei gezielten Korrekturen der Teststeuerung bestehen auch Stock und
Hacktribe mit dem vollständigen Patchsatz jeweils alle 13 Ergebnisprüfungen.
Beide Läufe enden ohne Assertion und ohne Zeitüberschreitung. Der Quellstand
bleibt während beider Läufe unverändert. Die Zeitbudgets werden nicht erhöht.

Die Teststeuerung bestätigt den Patternwechsel jetzt mit dem echten MENU.
Für DATA UTILITY verwendet sie die native Liste mit Bildschirmnummer,
Vtable und geprüftem Funktionsindex. Jeder Links-/Rechtsschritt muss den
Index genau zum Ziel bewegen; der Import muss anschließend den echten
Dateibrowser öffnen. Die alten Pixel-Titelhashes werden nicht mehr als
Seitenkennung benutzt. Die vorhandenen Vergleiche von Slots, Metadaten,
Rücknahme und Dateiinhalten bleiben erhalten. 20 gesonderte Modellprüfungen
und der aufrufende JavaScript-Test bestehen nach diesen Korrekturen.
Die zuvor ausgeführte Python-Gesamtsuite mit 264 Tests stammt noch vom
Stand vor diesen zusätzlichen Testfällen.

Auch diese Dateien liegen unter der Aktivierungsschwelle. Der Erfolg
bestätigt nativen Betrieb mit installierten Haken, keine aktive Auslagerung
im `MODE=1` und keine echte Audio- oder DMA-Übertragung.

Anders als die Minimalbuilds erzeugen beide vollständigen Builds jeweils
108 aggregierte Zeilen für Lese- und Schreibzugriffe im oberen RAM. Dazu
gehören die im Patch vorgesehenen Bereiche: Dateipuffer ab `0xC274F000`,
Index ab `0xC2768000`, Cacheverzeichnis ab `0xC2769000`, Schutzdaten ab
`0xC276CE80` und Signaturen ab `0xC3FFF000`. Beispielsweise liest der
Schutzcode bei `0xC019C520` Wörter bei `0xC276CEBC`. Das ist ein konkreter
Besitzer im vollständigen Build. Ein erfolgreiches Modusergebnis gibt
solche Bereiche nicht zur beliebigen Wiederverwendung frei. Für weitere
Besitzer und echte DMA bleibt die Prüfung offen.

## Gemessen im Emulator: breiter RAM-Beobachtungslauf

Ein zusätzlicher Stock-Lauf mit minimalem SysEx-Build beobachtet die unteren
Arbeitspuffer, Stackfenster sowie den oberen RAM einschließlich des emulierten
Aliasbereichs. Die 40 erzeugten Samples haben jeweils 20.000 Frames,
zusammen 1,6 MB PCM. Der Lauf endet regulär nach 242,25 Sekunden emulierter
Zeit, nach 20 Phasen und ohne Firmware-Assertion.

Erreicht werden Start, Leerlauf, PLAY, Patternwechsel, die vier kurzen
Sampling-/Resampling-Fälle, Sample-Import, Gesamtexport von Samples und
Patterns, Pattern-Import und Ausschalten. Alle vier modellierten
Aufnahmeenden werden durch EXIT verworfen; Sample-Zahl und DSP-Freizeiger
stehen danach jeweils wieder auf dem Ausgangswert. Audiosignal und DMA
werden dabei nicht nachgebildet.

CPU-Schreibzugriffe treffen den Arbeitspuffer ab `0xC0D3A940` und die
Stackregion, in den begrenzten Beobachtungsfenstern bis hinunter zu
`0xC274E92C`. Der zusätzliche Vergleich des Stack-Füllmusters findet nach
dem Sample-Gesamtexport eine Änderung bis `0xC274E924`. Oberhalb
`0xC274F000` werden keine CPU-Schreibzugriffe beobachtet. Ein erster,
deutlich teurerer Versuch mit 24 MB PCM wurde bei der Umstellung seiner
Ausführungssteuerung abgebrochen; er ist ausdrücklich kein bestandener
Beobachtungslauf. Die stärkeren, gesonderten Modustests verwenden 24 MB
und prüfen die tatsächlichen Ergebnisse der Sample-Operationen.

Der breite Lauf beweist die besuchten CPU-Pfade. Das Erreichen einer
Menüseite oder ein fehlerfreier Ablauf allein beweist nicht den Inhalt
eines Exports. Dafür gelten die gesonderten Ergebnisprüfungen. Ebenso
beweist dieser einzelne Stock-Lauf keinen dauerhaften RAM-Besitz für
Hacktribe, den vollständigen Swap oder eine echte DMA-Übertragung.

## Gemessen und hergeleitet: alter Vollspeicherfall passt nicht zum Swap-Modus

Der zusätzliche Test `test/emulator-sample-full.test.mjs` bleibt rot. Vier
andere Tests derselben zusätzlichen Prüfgruppe bestehen. Eine gesonderte
instrumentierte Wiederholung verändert weder den Ablauf noch seine
Erwartungen und bestätigt zwei veraltete Annahmen:

- Die erzeugte Datei enthält 25 MiB PCM und zusätzliche Record-Header.
  Mit 26.833.264 Bytes überschreitet sie die Aktivierungsschwelle von
  26.218.496 Bytes. Der aktuelle Build startet deshalb in `MODE=1`.
  Das Startpattern braucht keine User-Samples: keine aktive User-Zeile,
  DSP-Freizeiger am Werksende `0x365EC0`, keine Sample-Schreibübertragung.
  Der alte Test fordert dagegen 499 vollständig geladene User-Samples.
- Der Test erklärt pauschal alle veränderten Patchbytes als unveränderlich
  und erkennt eigenen Code nur im alten Bereich `0xC0180000..0xC0200000`.
  Die aktuelle VM liegt teilweise bei `0xC0150300..0xC015CDF4`.
  Die Unterschiede des abschließenden Bytevergleichs liegen ausschließlich
  im veränderlichen Timerwort `0xC015CA34` sowie in `FILE_OWNER+4/+8` bei
  `0xC0188718/0xC018871C`. Die ersten 40 als fremd bezeichneten Zugriffe
  kommen aus `menu_arm_zero` bei `0xC0154340` und betreffen den
  Einstellungsbereich ab `0xC01D6E00`.

Der Zugriffsbericht speichert nur die ersten 40 solchen Ereignisse. Deshalb
werden die übrigen als fremd gezählten Zugriffe ausdrücklich nicht pauschal
freigesprochen. Es gibt keinen zusätzlichen Unterschied der Code- oder
Hookbytes im abschließenden Vergleich; das ist kein vollständiger
Besitznachweis aller Zwischenzugriffe.

Der rote Altfall ist damit kein Beleg für ein Überschreiben des BLECH-Codes
beim Befüllen des DSP. Er ist ebenso wenig eine bestandene Prüfung des
aktuellen Swap. Ein sauberer Ersatz braucht getrennte Erwartungen für den
nativen Vollspeicher und den dynamischen aktiven Satz sowie eine aktuelle
Zuordnung unveränderlicher Codebytes und veränderlicher Zustände. In dieser
Prüfung werden weder Swap deaktiviert noch Assertions entfernt, um den alten
Fall grün erscheinen zu lassen.

## Gemessen: reine Audiodatenänderungen bleiben verdrängbar

Der bereits vorhandene Fall in `tools/emu/sample_protection_cases.py` wurde
mit `--pcm-write` gegen die aktuellen vollständigen roten Builds erneut
ausgeführt. Sowohl Stock als auch Hacktribe melden:

| Beobachtung | Ergebnis |
|---|---|
| DSP-Audiodaten geändert | ja |
| ARM-Metadatentabellen unverändert | ja |
| Änderung vor der Signaturprüfung markiert | nein |
| Metadatensignatur gilt als unverändert | ja |
| Verdrängung der physischen Zeile zugelassen | ja |
| Bibliotheksdatei unverändert | ja |

Beide gezielten Prüfungen schlagen deshalb absichtlich fehl. Es handelt sich
um ausgeführten nativen Firmwarecode im Emulator mit erzeugten Audiodaten,
nicht um beobachteten Datenverlust am Gerät. Ursache und betroffene
Schreibpfade stehen in der
[PCM-Untersuchung](2026-11-05-sample-pcm-schreibpfade.md).

## Hergeleitet und isoliert geprüft: Besitzer nach Wartephase

`tools/patch/native_dsp_scope.py` prüft den Modus vor dem Erwerb der nativen
Ressource 1. Nach einer möglicherweise blockierenden Wartephase fehlt die
erneute Prüfung der zuvor gültigen Bibliothek, Generation und Aufrufzuordnung.

Eine isolierte Ausführung des erzeugten ARM-Codes ändert genau an dieser
Grenze Generation 7 auf 8, Modus 1 auf 2 und die Schrittsperre 1 auf 0.
Der native Aufruf setzt trotzdem erfolgreich fort und gibt die Ressource
anschließend einmal frei. Diese gezielte Injektion belegt die fehlende
Nachprüfung, nicht das tatsächliche Auftreten dieses Ablaufs am Gerät.
Der gesonderte Swap-Ladeauftrag prüft seine Identität bereits nach dem
Ressourcenerwerb; das sichert den nativen Pfad noch nicht ab.

## Hergeleitet und isoliert geprüft: neue Aufnahme und Schutzrevision

Die Veröffentlichung einer neuen Aufnahme bei `0xC004F128` macht die zuvor
inaktive physische Zeile 600 aktiv. In der isolierten Gegenprobe ändert sich
dabei die Schutzrevision nicht. Eine davor vorbereitete Verdrängungsprüfung
lässt die Zeile weiter zu; eine neu aufgebaute Prüfung sperrt sie.

Die Gegenprobe ersetzt zwei Abhängigkeiten durch begrenzte Antworten:
den DSP-Endzeiger bei `0xC004E23C` und die native Initialisierung bei
`0xC004DF90`. Sie beweist die fehlende Revisionsänderung dieses
Veröffentlichungspfads. Sie ist weder ein vollständiger Aufnahmeablauf noch
ein Nachweis eines gleichzeitigen Fehlers am Gerät.

## Gemessen am Gerät: Eingabepfad

Das Gerät verwendet weiterhin den minimalen Hacktribe-Messbuild mit der
Korrektur zur Veröffentlichung hochgeladenen Codes. Der vollständige
Sample-Swap und die Erweiterung der Namensanzeige sind dort nicht installiert.
Ein Gerätetest dieses Builds kann deshalb den vollständigen Swap nicht
freigeben.

Ein bestätigter EXEC-Aufruf liest den tatsächlichen Ausführungskontext:
SVC, IRQ freigegeben, FIQ gesperrt, IRQ-Tiefe 0, Task 3 und Eintrittsstack
`0xC0208F60`. Taskzeiger, Deskriptor und Programmeinstieg passen zur
vorherigen nativen Emulatorprüfung. Ein weiterer bestätigter Aufruf reiht
EXIT als Drücken und Loslassen unter derselben Interruptsperre ein.
Beide Nachrichten werden verbraucht. STOP und Hauptseite bleiben erhalten;
der erste KiB des Arbeitsbereichs wird in der ungecachten Sicht vollständig
wiederhergestellt.

Bei der ersten reinen Vorprüfung wich ein Wort des IRQ-Bereichs vom rohen
Firmwareabbild ab. Sie brach vor WRITE und EXEC ab. Die Untersuchung des
nativen Starts erklärt die Abweichung: der IRQ-Vektor wird regulär von
`0xC000007C` auf `0xC0001560` gesetzt. Der anschließende Abgleich verlangt
exakt diesen Startzustand und die unveränderten übrigen Bytes. Es wird kein
beliebig abweichender Bereich ausgeblendet und kein IRQ-Vektor verändert.

## Gemessen am Gerät: automatische Bearbeitung, Rücknahme unbestätigt

Der anschließende eng begrenzte Bedienablauf verwendet intern Slot 540,
angezeigt als 541, mit dem erzeugten Sample `import` und 100.000 PCM-Bytes.
Vor der Bearbeitung passen Name, logischer und physischer Index, die
vollständige native Metadatensicherung und die relativen Playback-Werte zum
aktuellen Ziel. Der DSP-Bereich ist 27.563.200 bis 27.663.200.

Bestätigte Aufrufe öffnen Sample Edit, gehen zur Startpunktseite und ändern
den relativen Startpunkt von 0 auf 1. Ein erster vollständiger EXIT-Tastendruck
verlässt die Feinbearbeitung und kehrt zur Startpunktseite zurück. Nach jedem
dieser sechs Aufrufe ist die Eingabewarteschlange leer und der erste KiB des
Arbeitsbereichs in der ungecachten Sicht wiederhergestellt.

Beim zweiten EXIT-Aufruf, der die eigentliche native Rücknahme auslösen soll,
fehlt die bestätigte EXEC-Rückkehr. Der Ablauf beendet daraufhin sämtliche
Gerätekommunikation. Es folgen keine zusätzlichen Lese-, Schreib-, EXEC-
oder Aufräumversuche. WRITE wurde nicht betätigt. Ein vollständiger
Nachhervergleich aller Sample-Metadaten, Playback-Werte, des Patterns und
des erhaltenen RAM-Musters ist deshalb ausdrücklich **nicht** vorhanden.
Auch die Wiederherstellung des zuletzt hochgeladenen Arbeitsbereichs ist
nicht bestätigt.

Die Ursache der fehlenden Rückkehr ist offen. Weder ein DSP-Hänger noch ein
bloß verspätetes Transportpaket ist damit bewiesen. Der neue automatische
Rücknahmeversuch gilt als unvollständig. Der früher separat beobachtete
[manuelle EXIT-Test](2026-11-08-sample-ram-bearbeiten.md) bleibt ein eigener
Nachweis. Vor weiterer Gerätekommunikation ist ein bestätigter Neustart nötig;
damit verliert auch das bisher erhaltene RAM-Prüfmuster seine Gültigkeit.

## Offen

- Reine PCM-Änderungen müssen vor einer Verdrängung mit ihrer tatsächlichen
  physischen Version geschützt werden.
- Native DSP-Aufträge brauchen eine erneute Besitzerprüfung nach dem Warten.
- Die native Ressourcenvergabe kann weiterhin unbegrenzt warten. Zusätzlich
  zu einzelnen DSP-Abfragen braucht der gesamte Vorgang ein begrenztes Zeitbudget.
- Neue Aufnahmen müssen vorbereitete Schutzentscheidungen ungültig machen.
- Der gesamte obere RAM ist durch unveränderte Muster einzelner Sitzungen
  noch nicht für jeden Besitzer und jede DMA-Lebensdauer freigegeben.
- Der vollständige Swap-Build braucht weiterhin seinen eigenen Gerätetest:
  dynamisches Startpattern, Namen ungeladener Samples, Slotwechsel,
  fortdauernde Stimmen und Fehler bei Karten- oder DSP-Zugriffen.
- Dauerhaftes Speichern nativer Sample-Änderungen ist gesondert zu verbinden.
  Das bisherige Gesamtexport-Menü darf eine große Bibliothek nicht auf den
  momentan geladenen DSP-Ausschnitt verkürzen.
- Das spätere Ordnerformat ist ein eigener Umbau. Für die aktuelle Prüfung
  bleibt `e2sSample.all` unverändert das Bibliotheksformat.
