# Sample-Swap: native Wartepfade und erneute Ladeaufträge

Stand: 29.10.2026. **Gemessen im Emulator**, mit eigenen erzeugten Samples
und beiden roten Firmwarebasen 2.02. Kein Gerät wurde angesprochen.
Klang und DMA werden nicht nachgebildet. Ergänzung zu
[EXIT und Part-Auswahl](2026-10-29-sample-swap-exit-parts.md).

## Gemessen: native Transfers begrenzen

Die vorhandenen Timeout-Helfer sind im gebauten Swap-Patch enthalten.
35 native Paare aus Ressourcen-Erwerb und Freigabe sowie fünf gemeinsame
Statuslesestellen und sechs GPIO-Aufrufe benutzen sie. Der Zeiger auf den
aktiven Aufruf belegt das vorhandene freie Wort `STATE + 0x1E0`;
es wird kein zusätzlicher Sample-Puffer beansprucht.

Der kalte Bibliothekseinstieg initialisiert den Zeiger atomar. Ein aktiver
Aufruf und ein bereits gesetzter DSP-Fehler bleiben bei erneutem Laden
erhalten. Vor dieser Initialisierung bleibt die ursprüngliche Funktion
erhalten. Gehaltenes EXIT lässt beim Kaltstart den Zeiger auf `0xFFFFFFFF`.
Ohne Sampledatei kann der Bibliothekseinstieg ganz entfallen; dann wird
dieser Schutz noch nicht eingeschaltet.

Gezielt festgehaltene Status- und GPIO-Wartepfade kehren mit gesetztem
DSP-Fehler zurück. Der gültige Stack, die erhaltenen Register und der
ursprüngliche Interruptzustand bleiben erhalten. Eine selbst erworbene
DSP-Ressource wird genau einmal freigegeben. Nach dem Fehler gibt es
keinen weiteren Port-Schreibzugriff. Ein Aufruf aus ungeeignetem,
maskiertem Kontext beginnt keinen Transfer.

Die nativen Prüffälle kontrollieren zuerst sämtliche eingebauten
Hookziele und Codebereiche. Sie benutzen danach diese Implementierung;
sie installieren an ihrer Stelle keine Ersatz-Helfer.

## Hergeleitet: Zeitgrenze und gültige Paketgrößen

Die Grenze beginnt nach dem nativen Erwerb der DSP-Ressource. Timer 3
liefert 150 Millionen Takte pro Sekunde; 15 Millionen Takte ergeben
100 Millisekunden je nativem Aufruf. Ein zusätzlicher Zähler begrenzt
die Wiederholungen auch bei ausgefallenem Timer. Der ursprüngliche
Kernel-Erwerb der Ressource hat dadurch keinen eigenen neuen Timeout.

Die Lese- und Schreibfunktionen `0xC00141F8` und `0xC0014284` speichern
ihre Wortanzahl als 16 Bit. Ein einzelner vermeintlicher 2-MiB-Aufruf
überläuft diesen Parameter auf null und ist kein gültiger Durchsatztest.
Ein korrigierter Versuch schreibt 2 MiB erzeugte PCM in 17 Aufrufen mit
höchstens 65520 Halbworten. Die gesamte PCM stimmt überein; kein Timeout
tritt auf. Die Emulatorzeit von rund 200 Millisekunden ist keine
Übertragungszeit am Gerät.

## Gemessen: Aufnahme und Einzelexport melden Fehler

Vor dem Einbau der zehn zusätzlichen Schutzstellen konnten native
Aufnahmeabschlüsse trotz abgebrochenem Transfer ihre Erfolgsschritte
ausführen. Ebenso konnte ein fehlgeschlagenes DSP-Rücklesen beim
Einzelsample-Export als Erfolg zurückkehren. Beide Fehler sind mit dem
bereits eingebauten nativen Timeout reproduziert.

Mit den Schutzstellen bleibt bei Aufnahmefehlern die bisherige
Sampletabelle erhalten; kein neuer Slot und kein neuer Freizeiger werden
veröffentlicht. Auch erneutes Starten und Abfragen einer Aufnahme wird
bei gespeichertem DSP-Fehler abgewiesen. Ein gesundes Aufnahmeende
funktioniert weiter.

Der Einzelexport gibt bei einem vorhandenen Fehler oder fehlgeschlagenem
Rücklesen einen Fehler zurück. Ein bereits geöffneter Ausgang wird
regulär geschlossen und der Arbeitsbereich freigegeben. Nach dem
DSP-Fehler wird kein PCM mehr in die Datei geschrieben. Bei einem Fehler
während des Lesens kann eine WAV-Datei mit nur 44 Byte Kopf zurückbleiben.
Das ist kein transaktionaler Schutz einer bestehenden Exportdatei und
ersetzt nicht die dauerhafte Slot-Speicherung.

## Gemessen: verlorene Benachrichtigung und neue Zielwahl

Eine absichtlich verlorene Swap-Benachrichtigung ließ den alten
`POSTED`-Merker dauerhaft stehen. Der Ladeauftrag lief nicht wieder an.
Mit einem Ablaufzähler versucht der Bildschritt nach 50 Aufrufen erneut
zu benachrichtigen. Bei 25 Hz sind das ungefähr zwei Sekunden.
Der native Versuch bestätigt etwa 1,99 Sekunden Emulatorzeit. Bis dahin
bleibt das bisherige Pattern aktiv; erst nach vollständigem Laden
wechselt es. Eine tatsächlich angenommene Nachricht bestätigt weiterhin
erst der Beginn von `ss_step`, nicht ein angenommener Rückgabewert des
nativen Nachrichtenaufrufs.

Ein gescheitertes Ziel blieb außerdem nach einer neuen bestätigten
Patternwahl als alter Auftrag eingetragen. Der zusätzliche Haken bei
`0xC008205C` läuft erst, nachdem der native Wähler die Auswahl angenommen
und seine Auswahlfelder gesetzt hat. Nur im aktiven Swap-Modus löst er
einen vorhandenen alten Auftrag und dessen Fehlermarker. Das Auswählen
des laufenden Patterns verwirft damit das alte Ziel; eine neue Wahl
benutzt wieder den normalen Lade- und Bereitschaftsweg. Cache-Generation
und vorhandene PCM bleiben erhalten. Abgelehnte native Auswahlen und
Karten- beziehungsweise DSP-Fehlermodus benutzen diesen Weg nicht.

Die ARM-Fälle prüfen Register und Interruptzustand. Der native Fehlerfall
beginnt mit einem unlesbaren erzeugten Sample: Das Pattern wartet,
Auswahl des laufenden Patterns löst den Auftrag, danach wird ein neues
gültiges Ziel geladen und gewechselt.

## Prüfstand und offen

Die gezielten ursprünglichen Fehlerfälle und ihre Korrekturen liegen in
[test_sample_swap.py](../../tools/patch/test_sample_swap.py),
[test_native_dsp_scope.py](../../tools/patch/test_native_dsp_scope.py),
[swap_integrity_cases.py](../../tools/emu/swap_integrity_cases.py),
[native_dsp_scope_cases.py](../../tools/emu/native_dsp_scope_cases.py),
[capture_fault_cases.py](../../tools/emu/capture_fault_cases.py) und
[sample_export_fault_cases.py](../../tools/emu/sample_export_fault_cases.py).
Die nativen Fälle gehören zur vollständigen Swap-Prüfung.

Die abschließende Prüfung dieses Gesamtstands besteht: 1360 Unit-Prüfungen
bei 160 übersprungenen Fällen, 285 Browserprüfungen bei einem
übersprungenen Fall sowie sämtliche 740 Patch-Prüfungen für Stock und
715 für Hacktribe. Beide vollständigen Patch-Läufe enden ohne Fehler.
Zusätzlich bestehen 116 ARM-Prüfungen und je 32 gezielte native Fälle.
Der Stereo-Vergleich berücksichtigt
den bereits enthaltenen [Stereo-Ein-Pad-Patch](2026-10-29-stereo-ein-pad.md):
Typ 4 mit zehn DSP-Aufrufen statt des alten Paar-Typs 3 mit elf Aufrufen.
Das veränderte Erwartungsergebnis ist auch vor der Timeout-Einbindung
nachgestellt, kein beseitigter Transferfehler.

Beim Zusammenführen der Fehlerwege ist ein weiterer Widerspruch
reproduziert: Die Pattern-Bereitschaft ließ ein vollständig residentes
Ziel trotz gesetztem DSP-Fehler zu, während Part- und native DSP-Aufrufe
es bereits verweigerten. Im nativen Gegenversuch wechselte die laufende
Nummer von 0 auf 5, obwohl der DSP-Fehler erhalten blieb. Die korrigierte
Bereitschaft verweigert bei diesem Fehler auch residente, leere und nur
mit Werkssamples belegte andere Patterns. Das laufende Pattern bleibt
erhalten. Vorhandene PCM allein belegt nicht, dass die nötigen Stimmen-
und Parameterkommandos des neuen Patterns ausgeführt werden können.
Ein reiner Kartenfehler bleibt davon getrennt.

Die dauerhafte Speicherung aller Sample-Aktionen und die Ablösung des
Gesamtexports sind weiterhin offen. Ebenso fehlen die abschließenden
Geräteprüfungen zu tatsächlichen Stimmen, Klang und DMA-Zugriffen in allen
Sample-Modi. Daraus folgt keine Freigabe für 1.4.
