# ARM-Befehle und gemeinsame Routinen

Stand 20.10.2026. Ausgang: der in der [Ausgangsmessung](2026-10-20-patch-effizienz-ausgang.md)
festgehaltene Produktstand. Geschwindigkeit hat Vorrang vor Codegröße. Kein Gerätetest,
keine Änderung am Originalcode und keine Änderung der Arbeitsbudgets pro Bild.

## Multiplikation in der Skript-Laufzeit

[script_vm.py](../../tools/patch/script_vm.py) erzeugt für die Skript-Multiplikation
einen nativen MUL-Befehl. Ziel und erste Quelle sind verschieden, wie der vorhandene
ARM-v5-Assembler verlangt. Das niederwertige 32-Bit-Ergebnis entspricht auch für
negative Zahlen und Überlauf dem bisherigen Ergebnis. Die nächste Dispatch-Schleife
überschreibt die Flags durch CMP, bevor sie bedingt verzweigt.

[test_script_vm_optimizations.py](../../tools/patch/test_script_vm_optimizations.py)
prüft 2225 deterministische Zahlenpaare gegen das mathematische Produkt modulo 2^32.
Die Werte umfassen Null, beide Vorzeichen, INT_MIN, INT_MAX, Grenzen um Zweierpotenzen
und Zufallswerte. Derselbe FRAME-Handler wird für jedes Paar ausgeführt. Ein eigener
Befehlszähler zählt vom Eingang in den MUL-Handler bis zum nächsten Dispatch.
Der Test ist in den bestehenden nativen Node-Prüflauf eingebunden.

| Messung | Ausgang | MUL |
|---|---:|---:|
| Vollständiger Testhandler, mittlere ARM-Befehle | 696,03146 | 558 |
| MUL-Handler, maximale ARM-Befehle | 168 | 7 |
| VM-Code, Byte | 11352 | 11328 |
| Zahlenpaare mit gleichem Ergebnis | 2225 | 2225 |

Gemessen: rund **19,83 Prozent weniger Befehle** im vollständigen Testhandler und
24 Byte weniger VM-Code. Der unveränderte Code besteht die Zahlenprüfung, scheitert
jedoch am neuen Handlerbudget von höchstens zehn Befehlen. Der Ersatz besteht beides.
Die bisherigen 16 nativen VM-Prüfungen bestehen ebenfalls.

Das bisherige Planminimum von 20 Prozent wird mit diesem festen Korpus knapp
verfehlt. Die gemessenen 19,83 Prozent wurden ausdrücklich als ausreichend angenommen,
sofern die übrigen Regressionen bestehen. Korpus und ursprüngliches Ziel bleiben
dokumentiert. Der ältere [Prototyp](2026-10-20-patch-performance.md)
benutzte einen anderen Testausschnitt; seine Prozentzahl ersetzt diese Messung nicht.
Eine niedrigere ARM-Befehlszahl ist keine zyklengenaue Messung auf dem Gerät.

Die vollständigen Satzprüfungen bestehen: Hacktribe 432 Checks, Korg rot 457 und
Synth 338. Cache ausgeschaltet, alle vorgesehenen Aufgaben abgeschlossen, Quellen
während der Prüfung unverändert. Der aktuelle Unit-Lauf besteht mit 946 erfolgreichen
Tests und 143 erwarteten Auslassungen; Browser mit 162 erfolgreichen Tests und einer
Auslassung. Die drei gespeicherten Manifeste entsprechen exakt dem Generator.
15 Messwerkzeugtests bestehen ohne Auslassung. Die übrigen Produktumbauten bleiben offen.

## Vergleich vollständiger App-Frames

Die erste Gegenmessung fand beim Synth abweichende App-Zustände. Der Messablauf
zählte den Beginn eines Frames, nicht dessen Abschluss. Bei Life beziehungsweise
Mandelbrot war `FRAME_ACTIVE` am Snapshot noch eins. Außerdem beginnt der Zufall von
Life und Pong mit `korg.millis()`: im Vergleich lag dieser Eingang um eine
Millisekunde auseinander. Es wurden keine identischen Eingaben verglichen.

Messformat 2 wartet bis `frame_return`, nach Rechnen und Bildschirmübertragung.
Es verwendet acht vollständige Aufwärmframes und einen ausdrücklich gesetzten
Zufallsstartwert. Danach misst es fünfzig vollständig beendete Frames. Anfangs- und
Endvariablen sowie Bildpuffer werden gehasht; ein aktiver Frame oder ein Bericht im
alten Format wird abgelehnt. Ein Test mit eigenem ARM-Code zeigt den alten Fehler:
Der Zähler steht schon auf eins, während noch kein Bild fertig gerechnet ist.

Beide Stände wurden mit diesem Verfahren neu gemessen. Der Ausgang verwendet eine
unveränderte Quellkopie des festgehaltenen Produktstands und das neue Messwerkzeug.
Die erzeugten Laufzeitabschnitte müssen vollständig zum jeweils geprüften Abbild
passen. Es werden keine Firmwarefunktionen ersetzt, um den Vergleich passend zu machen.

Je Stand: 18 unabhängige Starts, 126 Szenenfenster, 27 App-Fenster mit zusammen
1350 vollständigen Frames. Alle Wiederholungen stimmen überein. Zwischen Ausgang und
MUL stimmen Bilder, Rechenfortschritt und der gesamte App-Variablenspeicher überein.
Keine Assertion und kein App-Fehler. Die erneute Abnahme besteht auf allen drei Basen.

| Build | Mandelbrot, weniger Laufzeitbefehle | Life | Pong |
|---|---:|---:|---:|
| Hacktribe | 1,1140 % | 0,1240 % | 0,0294 % |
| Korg rot | 1,1106 % | 0,1240 % | 0,0298 % |
| Synth | 1,1128 % | 0,1252 % | 0,0316 % |

Diese Prozente betreffen den Laufzeitbereich des Patches. Auf alle ARM-Befehle im
App-Fenster bezogen spart Mandelbrot rund 0,26 bis 0,31 Prozent. Das Bild wird durch
diesen Eingriff nicht früher fertig: das Arbeitsbudget pro Frame bleibt unverändert.
Die alte, unvollständig abgegrenzte Aufzeichnung bleibt als Diagnose erhalten.

## Ganze Originale durchsuchen

Gemessen: alle drei hashgeprüften Original-Payloads mit je 2 MiB wurden an sämtlichen
524288 ausgerichteten ARM-Wortpositionen nach Schleifen und begrenzten exakten
Funktionsduplikaten durchsucht. Insgesamt sind das 1572864 Positionen. Thumb und der
separate DSP sind kein Bestandteil dieses ARM-Scans. Die Originale, Disassemblierungen
und ausführlichen Kandidatenlisten bleiben ausschließlich außerhalb des Repositorys.

Der direkt verfolgte Graph ab Reset und fünf auf gleichen Code geprüften
FatFs-Einstiegen umfasst je 5667 Befehlspositionen. Dort verwendet das Original
bereits MUL, MLA und SMULL. Die restlichen Suchbereiche sind dadurch noch nicht als
ausführbarer Code bestätigt. Indirekte Aufrufe und Sprungtabellen begrenzen die
Abdeckung; ein linearer Scan ist keine vollständige Kontrollflussanalyse.

Die enger gefilterte klassische Schleife aus Bit-1-Test, bedingter Addition sowie
Links-/Rechtsverschieben hat keinen weiteren Treffer. Andere Formen der
Softwaremultiplikation sind damit nicht ausgeschlossen. Die breiteren Treffer
enthalten auch Umwandlung und Normalisierung, die keine einfache MUL-Ersetzung sind.

| Original | Kandidatengruppen mit exakten begrenzten Funktionsbytes |
|---|---:|
| Hacktribe | 49 |
| Korg rot | 46 |
| Synth | 41 |

Die Zahlen sind keine Anzahl sicher entfernbarer Funktionen. Die größten drei Gruppen
je Build wurden zusätzlich auf Literalwerte und externe Sprungziele geprüft. Gleiche
Befehle können an unterschiedlichen Adressen andere Werte oder Funktionen erreichen.

Ein 112-Byte-Paar ist auf allen drei Basen besonders plausibel: keine unterschiedlichen
sichtbaren Literalwerte oder externen direkten Sprungziele, ein beziehungsweise vier
direkte Aufrufmuster und keine gefundenen äußeren Referenzen ins Funktionsinnere.
Je Build stimmen 64 synthetische Vergleiche von Ergebnis, Speicher, erhaltenen Registern
und Befehlszahl überein. Die indirekt aufgerufenen Methoden werden dabei durch eigene
Testfunktionen vertreten. Die vollständige Analyse der echten Aufrufer bleibt offen.
Es wurde keine Originalroutine entfernt.

## Speicher leeren

Die bisherige [VM-Routine](../../tools/patch/script_vm.s) schreibt ein Byte pro
Schleife. Das Original enthält bereits einen ausrichtungsabhängigen Helfer mit
Wortzugriffen und größeren Schleifenschritten. Die Zuordnung zum Synth wurde mit
[fwmap.py](../../tools/patch/fwmap.py) samt 16-Wort-Vergleich geprüft.

Gemessen: 256 Vektoren je Firmware, insgesamt 768 Vergleiche. Längen 0 bis 160 KiB,
vier Ausrichtungen und vier Füllwerte liefern gleiche Inhalte und unveränderte
Wächterbereiche. Für 160 KiB ausgerichteten Speicher mit Null benötigt der eigene
Helfer 491523 ARM-Befehle, das Original 81948. Das sind rund 83,33 Prozent weniger
Befehle im isolierten Löschaufruf. Rückgabewerte und Scratch-Register sind noch kein
freigegebener Austauschvertrag. Es gibt noch keinen Produktumbau dieser Routine.

Das ist kein Nachweis einer Beschleunigung von Sample-Import oder Export. Diese
Pfade benötigen eigene Profile. Der vorhandene Sample-Test nennt ausdrücklich die
langsame Verarbeitung mit dem DSP-Ersatz im Emulator. ARM-Arbeit, Dateisystem,
SD-Wartezeit und DSP-Wartezeit müssen getrennt bewertet werden.

Eine zusätzliche Aufzeichnung zählt die Helferaufrufe beim Hacktribe-Start mit
eigener leerer Sample-Datei sowie einem synthetischen Sample mit 1 oder 64 KiB Audio.
Alle drei Starts erreichen die Hauptseite ohne Assertion; das Sample ist jeweils
wie erwartet vorhanden oder abwesend. Bei zehn Sekunden Gerätezeit ergibt sich:

| Audio in der eigenen Datei | Vom VM-Helfer geleerte Byte | Vom Originalhelfer geleerte Byte | Von FatFs angeforderte Byte |
|---|---:|---:|---:|
| 0 | 1542640 | 129433 | 4096 |
| 1024 | 1542640 | 130605 | 6360 |
| 65536 | 1542640 | 130605 | 70872 |

Der eigene Löschaufwand wächst in diesen Starts nicht mit der Audiolänge. Die
Dateianfragen tun es. Diese Messung begründet eine Verbesserung des festen
Initialisierungsaufwands, aber keine Zusage für schnelleres Übertragen von Audio.
Menü-Import, Export und echte SD-Latenz sind damit noch nicht profiliert.

## Gemeinsame CRC, MLA und Grenzen

Die frühere isolierte CRC-Messung liefert zwölf gleiche Prüfsummen und rund
69 Prozent weniger Befehle für die vorhandene SysEx-Variante. Die schnellere
Einzelfunktion ist größer. Ein weiterer Prototyp vereinigt Splash, SysEx und Card:
260 Byte bisherige Helfer gegen 156 Byte einschließlich gemeinsamer Tabelle und
Streaming-Adapter. Das spart 104 Byte innerhalb dieser isolierten Helfergruppe.
18 Vergleiche fertiger CRCs sowie 36 Streaming-Vergleiche mit unterschiedlichen
Anfangszuständen und leeren Zwischenstücken stimmen mit zlib überein. Der
Streaming-Adapter erhält außerdem die bisherigen Endzeiger.

Bei 32 KiB brauchen Splash, SysEx und der gemeinsame Prototyp 1277958, 393222 und
360455 ARM-Befehle. Bei leerer Eingabe braucht der Prototyp sieben statt sechs
Befehle; bei einem Byte stimmen die Befehlszahlen überein. Vor einer Übernahme sind
die tatsächlich häufigen Aufruflängen zu prüfen. Ein anderer untersuchter Aufbau
brauchte mehr Code und mehr Aufrufarbeit.

Das ist noch keine Nettobilanz des vollständigen Patch-Satzes. Besitzer,
Aufrufstellen, Verschiebungen, Ausrichtung und alle Fehlerpfade müssen im Produkt
geprüft werden. Card führt einen laufenden CRC-Zustand, andere Helfer liefern fertige
Prüfsummen. Der Prototyp ist noch keine Änderung an diesen Produktpfaden.

Für MLA gibt es einen konkreten gemessenen Kandidaten in
[tap_motion.py](../../tools/patch/tap_motion.py): Im Abschnitt `tk_part` multipliziert
der Code die Partnummer mit dem Datensatzabstand und addiert den Patternzeiger.
MUL und ADD lassen sich dort durch einen MLA ersetzen. 2225 deterministische
Vergleiche einschließlich der 16 gültigen Partnummern und 32-Bit-Überläufen liefern
gleiche Register und Flags. Der isolierte Abschnitt mit Vorbereitung und Rückkehr
braucht vier statt fünf ARM-Befehle und 16 statt 20 Byte. Der vollständige Patch
wurde noch nicht geändert; sein Nettogewinn und seine Regression bleiben offen.

Andere Treffer müssen ebenfalls gleiche Register, Flags, Vorzeichen, Überläufe und
Rundung ergeben. Getrennte Bereichs- und Budgetprüfungen dürfen nicht zu einem nur
ähnlich aussehenden Ausdruck verschmolzen werden. Thumb bleibt zurückgestellt.

Messwerte: [arm-optimierungen-zahlen.json](2026-10-20-arm-optimierungen-zahlen.json).
