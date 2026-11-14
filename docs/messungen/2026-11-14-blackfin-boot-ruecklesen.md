# Blackfin: Kern und Host-Port als Prüfprototyp

## Gemessen mit erzeugten Programmen

Der zusätzliche Prüfpfad startet einen eigenen Prozess mit dem GNU-Blackfin-
Simulator. Ein selbst erzeugtes Programm setzt Register, erweitert negative
Zahlen mit Vorzeichen und schreibt selbst eine 7 in den DSP-Speicher.
Der ARM-Host-Port liest diese 7 zurück. Anschließende Host-Schreibzugriffe
werden aus demselben DSP-Speicher wieder gelesen. Keine Firmwarebytes oder
Samples sind als Testdaten hinterlegt.

Die erzeugten Gegenproben prüfen ferner begrenzte Ausführung, einen
angeforderten Haltepunkt, ungültige Befehle, nicht vorhandenen Speicher,
fehlerhafte Bootblöcke, fehlende Initialisierungsantworten und kurze
Host-Übertragungen. Ein nicht antwortender Prozess und ein Prozess, der keine
weiteren Eingaben annimmt, werden nach Fristablauf beendet. Fehler liefern
keine Ersatzantwort aus dem bisherigen DSP-Modell.

17 neue Prüfungen und 30 bestehende Modell- und Cacheprüfungen bestehen mit
dem tatsächlich gebauten Simulator. Ohne gesetztes `BFIN_WORKER` werden die
zehn Prüfungen des GNU-Kerns ausdrücklich ausgelassen; die sieben übrigen
Prüfungen benötigen kein SDK.

Die abschließende Projektprüfung besteht mit 1610 Unitprüfungen bei 166
ausgelassenen Prüfungen und 353 Browserprüfungen bei einer ausgelassenen.
Die neun Dokumentationsprüfungen bestehen ebenfalls. Diese grünen Prüfungen
heben die unten dokumentierte fehlgeschlagene DSP-Startdiagnose nicht auf.

## Gemessen beim Simulatorbau

Der Quellstand ist GNU GDB 15.2. Die veröffentlichte SHA-256 des Archivs
lautet `83350ccd35b5b5a0cba6b334c41294ea968158c573940904f00b92f76345314d`.
Der Builder prüft sie vor dem Entpacken. Quelle:
[GNU-Veröffentlichung](https://sourceware.org/pipermail/gdb-announce/2024/000141.html).
Der Build bleibt außerhalb des Repositorys.

Neben der bereits beschriebenen 32-Bit-Korrektur von `SIGNEXTEND` war eine
zweite Buildkorrektur nötig. Die Erzeugung von `sim_modules_detected` benutzt
eine `sed`-Anweisung ohne abschließendes Semikolon vor der schließenden
Klammer. Das macOS-`sed` weist diese Anweisung ab. Wegen der nachfolgenden
Sortierung meldet die Pipeline trotzdem Erfolg, und die Modulliste bleibt
leer. Beim Aufbau der Blackfin-Geräte folgt ein Absturz in `sim_hw_parse`.
Mit der portablen Schreibweise enthält die Liste unter anderem
`sim_install_hw`, und der Hardware-Modus startet.

Der Builder verwendet die System-zlib; die mitgelieferte alte zlib baute mit
dem verwendeten macOS-SDK nicht. Beide Quellkorrekturen und die Prüfsummen
des gebauten Programms werden im SDK-Verzeichnis protokolliert.

## Gemessen mit der privaten roten Originalfirmware

Der Bootstrom wird aus der eigenen Firmware gelesen. Die Adressumrechnung
bleibt `file = ram - 0xC0000000 + 0x100`. Boot-ROM-Initialisierungsblöcke
werden bei diesem direkten Speicherladen nicht ausgeführt; dies ist kein
nachgebildeter SPI-Boot-ROM-Lader.

Sechs Initialisierungsfunktionen laufen in der aus dem Scratchpad bekannten
Reihenfolge bis zu ihrem echten Rücksprung. Zusammen benötigen sie im
Einzelschrittverfahren 7732 Schritte. Danach steht an `0xFF9031D8` der vom
DSP-Code geschriebene Zeiger `0x01C722A0`; vorher stand dort null.
Das ist ein Nachweis ausgeführter Initialisierungsfunktionen, kein
vollständiger Reset- oder RTOS-Start.

Der direkte Start bei `0xFFA00000` bleibt im virtuellen Modus bei
`0xFFA00090`, einer Interrupt-Rückkehr, ohne Bereitschaftsantwort.
Im Hardware-Modus läuft er weiter, gerät aber in eine Ausnahme:
`SEQSTAT = 0x2A`, also nicht ausgerichteter Instruktionszugriff.
Der zugehörige Aufruf liegt bei `0xFFA0BE6C`. Die gezielte Beobachtung vor
diesem Aufruf sieht `P0 = 0` und das ungerade Ziel `P1 = 0xFFA0E149`.
Warum die vorherige Initialisierung dieses Ziel liefert, ist offen.
Es wurden weder das Ziel korrigiert noch die Ausnahme unterdrückt.

Nach einer Million Schritten ohne erzeugte Bereitschaftsantwort bricht der
ausdrückliche Bereitschaftstest ab. Der erste Anschluss wartete an dieser
Stelle auch innerhalb des ARM-Upload-Aufrufs. Diese zusätzliche Wartebedingung
war falsch und wurde entfernt.

Die native ARM-Funktion bei `0xC0011AB8` bestätigt den Abschluss ihrer
SPI-Übertragung. Sie prüft dabei nicht den späteren Zeiger bei `0xFF9031D8`.
Programmübertragung und DSP-Initialisierung sind deshalb getrennte Zustände:
Ein korrekt geladener Strom darf den Upload abschließen, ohne bereits einen
initialisierten DSP zu behaupten. Fehlerhafte Ströme oder Workerfehler dürfen
dagegen keinen Upload-Erfolg veröffentlichen. Der Bereitschaftstest bleibt
eine getrennte, begrenzte Diagnose.

Mit dieser Trennung wurde der gekoppelte ARM/DSP-Lauf erneut gestartet.
Er erreichte innerhalb der gesetzten Wandzeitgrenze von 45 Sekunden keinen
Bootabschluss. Auch dieser Lauf ist keine bestandene Bootprüfung.

## Hergeleitet

`Machine(..., dsp_backend=...)` wählt den neuen Pfad ausdrücklich. Ohne
dieses Argument bleibt das bisherige Verhalten erhalten. Ein zusätzlich
angeschlossenes Host-Port-Modell wird abgewiesen, damit es keine echte
Rückleseantwort überschreibt. Snapshots und Wiederherstellung sind mit
einem laufenden Backend nicht erlaubt; der Startcache wird umgangen.

Die Host-Port-Statusantwort `0x85` beschreibt im Prototyp nur die
Transportbereitschaft des Endpunkts. Sie ist noch kein vom laufenden DSP
kalibrierter BUSY-Zustand. Der Kern bekommt nach einer vollständigen
Host-Schreibung eine begrenzte Ausführungsscheibe. Eine gemeinsame ARM- und
DSP-Zeitbasis sowie SPORT-Ereignisse sind noch nicht angeschlossen.
Auch Statusabfragen und der Beginn einer Leseübertragung geben dem Kern
eine begrenzte Ausführungsscheibe. Die Wörter einer Leseübertragung stammen
aus dessen Speicherbild zu Beginn dieses Transfers.

Die wiedergefundenen Replay- und DMA-Erweiterungen bleiben Referenz für
diesen Ausbau. Der reproduzierbare Grundkern dieses Prototyps verwendet
den geprüften GNU-Quellstand mit den beiden genannten Korrekturen. Er
übernimmt keine Firmware oder Speicherauszüge aus dem Scratchpad.

## Wiederholen

```sh
python3 tools/dsp/build_blackfin.py "$BFIN_SDK"
export BFIN_WORKER="$BFIN_SDK/blackfin-worker"
PYTHONPATH=tools/emu tools/emu/.venv/bin/python -m unittest test_blackfin_backend test_blackfin_stream test_dsp_model test_bootcache
python3 tools/dsp/blackfin_probe.py --worker "$BFIN_WORKER" --vsb "$E2_STOCK_VSB" --functional-init
python3 tools/dsp/blackfin_probe.py --worker "$BFIN_WORKER" --vsb "$E2_STOCK_VSB" --operating
```

`BFIN_SDK` muss außerhalb des Repositorys liegen. Der letzte Befehl schlägt
beim hier gemessenen Stand erwartungsgemäß fehl; er ist keine grüne
Bootprüfung. Die Funktionsinitialisierung ist ausdrücklich davon getrennt.

## Offen

- Der vollständige DSP-Start und die Ursache des ungültigen Aufrufziels.
- Echte Briefkastenverarbeitung im laufenden DSP, SPORT, DMA und gemeinsame
  Gerätezeit.
- Die Auswahl des Sample-Abspielpfads und natürliche Stimmenenden.
- Hardwaregenaue BUSY-Zeiten und der Vergleich mit dem Gerät.
- Hacktribe und blaue Firmware in diesem neuen Ausführungspfad.

Der Prototyp ist daher noch kein Ersatz für das schnelle DSP-Modell oder
eine Freigabe für Sample Swap. Es gab keinen Gerätezugriff und keine
Firmwareänderung.
