# Plan: Natives Aufnehmen und Abspielen (1.6)

> Stand 17.11.2026: Umsetzung freigegeben, Phase 0 und Phase 1 in Arbeit. Gerätemessungen bleiben beim Besitzer; diese Ausführung greift nicht auf das Gerät zu.
> Grundlage: docs/messungen/2026-11-17-native-aufnahme.md (Docs-PR gegen develop).

## Ziel

Den laufenden Mix der Electribe ohne PC und Interface als WAV auf die Karte aufnehmen (48 kHz, stereo, 16 Bit, ganze
Sets), und eine WAV von der Karte abspielen, damit ein Track laufen kann, statt live gespielt zu werden. Firmware-nativ
(Menü im Firmware-Look), rot zuerst; blau nur mit Tester.

## Was feststeht (aus der Messung)

- Master nach MFX + Soft-Clipper liegt jedes Sample in DSP `0xFF802888` (L hoch, R tief), Mono in `0xFF80288C` (gelesen).
- Erfassung `0x37` liest ihre Quelle über den Zeiger `0xFF9031DC`; Zeiger auf `0xFF802888` = Master im 100-ms-Ring
  `0x01C722A0` (hergeleitet, Weg A). Teilt Zwischenwort und DMA mit Korgs SAMPLING und Spettro.
- Karte lesen 3,1/5,1 MiB/s am Gerät; Schreiben schätzt Besitzer auf rund 3 MB/s (geschätzt, nicht gemessen). Bedarf 0,19 MB/s.
- WAV ohne `f_truncate`: anhängen, Kopf am Ende per `f_lseek` überschreiben. `f_sync` wurde am 18.11. im ARM-Emulator bestätigt.
- Sample Swap (#166) belegt `0xC274F000..0xC4000000`.
- Blau: `0x37` da, kein Stereo-Wort, kein `0x3B`.

## Arbeitsregeln

- Gerät: READ ohne Rückfrage; WRITE, EXEC, Kartenschreiben am Gerät nur mit des Besitzers OK. Nie EXEC `0xC0029AB8`.
- Firmware-PRs seriell, gegen develop. `node tools/load-gate.mjs` vor Tests.
- Neue RAM-Bereiche in der RAM-Liste der Patches anmelden; der RAM-Kollisionstest muss grün bleiben.
- DSP-Verhalten im QEMU-DSP-Kern prüfen (Plan 2026-11-16-qemu-dsp-kern), sobald umgeschaltet; bis dahin GNU-Sim.

## Phase 0: Belege am Gerät und Weg entscheiden (Spike, 1 bis 2 Tage)

Ziel: Weg A, B oder C für den DSP-Ring festlegen, mit Zahlen.

- [ ] 0.1 Nur lesend: während RESAMPLING die Zustandswörter `0xFF9031F8..0xFF90320C` lesen (Quelle = Master-Wort?), Ringzeiger `0xFF9031D8` bei laufendem Spettro lesen
- [x] 0.2 Im DSP-Sim: Erfassung starten, Quellzeiger umbiegen, Ring gegen das gepackte Master-Wort vergleichen (bit-gleich); Stufe ab `0xFFA0189A` und `[P4+0x6C]/[P4+0x70]` benennen
- [x] 0.2b Wo AUDIO IN und Metronom in den Master kommen: liegt AUDIO IN schon im Master-Wort (sonst dazumischen)? Gibt es einen Abgriffpunkt nach AUDIO IN, aber vor dem Metronom (Besitzer: Metronom nicht auf der Aufnahme, aber weiter hörbar)? Wenn nicht: Metronom mit drauf, den Besitzer fragen
- [ ] 0.3 OK da (Besitzer 17.11., Gerät gerade aus): Kartenschreibtest am Gerät (64-KiB-Blöcke, 60 s, 12,5 und 25 MHz): Rate, längste Schreibpause, Pausen beim Clusterwechsel; Testdatei danach löschen
- [ ] 0.4 OK da (Besitzer 17.11.): Laufabstand eines Lesers messen (CommandTask vs. eigene Task) während Pattern-Wechsel, WRITE (Flash-Löschen) und Sample-Swap-Laden; Ergebnis längste Lücke in ms
- [ ] 0.5 Entscheidung A/B/C in die Messung schreiben: A, wenn die längste Leserlücke unter 80 ms bleibt; sonst C (DSP-Ring im Sample-Speicher) oder B

Akzeptanz: Messdatei hat Zahlen zu 0.1 bis 0.4 und die Entscheidung.

## Phase 1: Master auf die Karte, ein Knopf (2 bis 3 Tage)

Vertikaler Schnitt: Start/Stopp an der Bedienung, Leser, ARM-Ring, Schreiber, WAV auf der Karte.

- [x] 1.1 Aufnahmedienst: Erfassung mit Master-Quelle starten (gewählter Weg), Sperre gegen SAMPLING (Status belegt); Spettro zeigt während der Aufnahme den Master, und wenn das stört, lässt es sich während der Aufnahme gar nicht erst wählen (Besitzer 17.11.), Leser leert den DSP-Ring in einen ARM-Ring und dreht R/L zu L/R
- [x] 1.1a DSP-Abgriff mit THRU und Ausgangsverstärkung, ohne Metronom; Ausgang bitgleich prüfen
- [x] 1.1b Nativer Ring-Leser mit Besitzprüfung, R/L-Konvertierung und sichtbaren Lückenfehlern
- [x] 1.2 Schreiber in einer Task, die die Karte darf: WAV-Kopf 512 Byte (JUNK), Daten in 64-KiB-Blöcken anhängen, beim Stopp Längen setzen und schließen; Dateiname fortlaufend `Recordings/REC0001.WAV` (Besitzer 17.11.)
- [x] 1.2a Nativer WAV-Schreiber mit eigenem FIL-Kontext, exklusiven Dateinamen, Sektorkopf und Fehlerabschluss
- [x] 1.2b Schreiber im Aufnahmedienst an die kartenzugriffsberechtigte Task anbinden
- [x] 1.3 Bedienung: SHIFT + REC zeigt heute RESAMPLING und AUDIO IN, dazu eine dritte Wahl RECORD (Besitzer 17.11.); Korgs Auswahl dafür im Code finden und erweitern; Start nur über RECORD, nicht an PLAY gekoppelt (Besitzer 17.11.); Anzeige: läuft, Zeit, Karte voll; Gerät schläft während der Aufnahme nicht
- [x] 1.4 Emulator: DSP-Modell/QEMU liefert ein bekanntes Signal im Master-Wort; Fall prüft die WAV auf der virtuellen Karte (Kopf gültig, Frames bit-gleich, Länge stimmt), Fall-Modul im Verify-Scope angemeldet
- [x] 1.5 Patcher-Tabelle, Messung, Schalter unter FEATURES (aus = kein Verhalten)

Akzeptanz: Fall grün auf Hacktribe und rot; WAV öffnet in einem Audioprogramm; Gerätetest (Liste im PR) mit dem Besitzer.

## Phase 2: Lange Sets ohne Lücke (1 bis 2 Tage)

- [x] 2.1 Lückenzähler: Leser erkennt überholten DSP-Ring und ARM-Ring-Überlauf; Anzeige und Marker (cue-Chunk oder Logdatei), nie stilles Verschlucken
- [x] 2.2 Ring dynamisch (Besitzer 17.11.): nur während der Aufnahme belegen, Größe nach Phase 0 (bis 2 MiB), mit dem Speicherplan von Sample Swap (#166) abstimmen
- [ ] 2.3 Andere Kartenschreiber (Einstellungen, Patterns, Plugins, Sample Swap) während der Aufnahme: warten lassen oder seriell, mit Fall
- [x] 2.3a UI-Kartenzugriffe sperren, gepufferte Änderungen nachholen und Start an UI-Grenze freigeben
- [x] 2.3b Native Pattern-Schreiber und Aufnahme in derselben CommandTask nachweisen
- [ ] 2.3c Sample-Swap-Kartenzugriffe nach Integration von #166 prüfen
- [x] 2.4 Stromausfall: Längen regelmäßig nachtragen oder Reparatur beim Start (Länge aus Dateigröße), mit Fall
- [x] 2.5 Karte voll, Karte gezogen, 4-GiB-Grenze: sauber beenden, ab 4 GiB neue Datei

Akzeptanz: Emulatorfälle für Überlauf, Karte voll, Reparatur grün; Gerät: 60 min Set mit Pattern-Wechseln, 0 Lücken.

## Phase 3: Plugin-API Master-Quelle (0,5 Tag, optional)

- [ ] 3.1 `korg.audio.capture` bekommt die Quelle Master (neue Nummer am Listenende, API-Sprung), Spettro zeigt den Mix
- [ ] 3.2 Aufnahme-Status lesbar für Plugins (läuft, Zeit, Lücken), nur wenn Besitzer will

Akzeptanz: Plugin-API-Fall grün; Doku DE/EN.

## Phase 4: WAV abspielen (später, 3 bis 5 Tage)

Besitzer 17.11.: erst Aufnahme, der Player ist ein späterer Schritt und baut auf Sample Swap (#166) auf. Startet erst, wenn #166 in develop ist. Weg: P2 (DSP-Patch, Ring in den Mix), Besitzer 17.11.; Player weniger wichtig als Aufnahme.

- [ ] 4.1 DSP-Patch: Leseweg aus einem Ring im DSP-Speicher, addiert nach MFX und nach der Röhrenkurve (Plan 2026-11-17-roehrenkurve-1.5.x), also nach dem Clipper bei 0xFFA0135C (Besitzer 17.11.); die Aufnahme nimmt alles auf, was rausgeht, also auch die Wiedergabe (Besitzer 17.11.): der Patch schreibt die Summe nach dem Player in ein eigenes Wort, und die Erfassung `0x37` zeigt dann darauf statt auf `0xFF802888`; Metronom bleibt die Ausnahme (0.2b), eigenes Zwischenwort, damit Aufnahme und Wiedergabe gleichzeitig laufen; im QEMU-Kern bit-genau geprüft
- [ ] 4.2 ARM: WAV wählen (Dateibrowser im Firmware-Look), Format prüfen (48 kHz, 16 Bit, mono/stereo, Rest ablehnen), Ring per Host-Port füllen, Start/Stopp, Pegel
- [ ] 4.3 Start mit PLAY koppeln (optional), Anzeige Zeit/Rest
- [ ] 4.4 Emulatorfall: WAV auf der Karte, Ausgang am DSP-Modell gleich der Datei

Akzeptanz: Fall grün; Gerät: Track 10 min ohne Aussetzer, gleichzeitig Pattern spielen.

## Phase 5: Blau (nur mit Tester)

- [x] 5.1 Start über eigenen ARM-Code (Postfach `0x37` auf blau), Mono-Summe im eigenen DSP-Wort
- [ ] 5.2 Stereo auf blau entfällt, mono reicht (Besitzer 17.11.); Wiedergabe über denselben P2-Patch fürs blaue Programm
- [ ] 5.3 Fälle auf blau, Gerätetest durch Tester

Akzeptanz: Fälle grün auf blau; Testerbericht.

## Phase 6: Doku und Release

- [x] 6.1 Patcher-Doku, Plugin-Doku DE/EN (falls Phase 3), README-Zeile, 1.6-Notes DE/EN/FR

Akzeptanz: Docs-Test grün.

## Fragen an den Besitzer

1. Bedienung: ~~Menü oder Tastenkombi~~ SHIFT + REC mit dritter Wahl RECORD neben RESAMPLING und AUDIO IN (Besitzer 17.11.), nicht an PLAY gekoppelt
2. ~~Ordner~~: `Recordings/REC0001.WAV` (Besitzer 17.11.)
3. ~~Was soll drauf~~: Master mit AUDIO IN; Metronom nicht, wenn es geht, aber nur wenn man es weiter hört (Besitzer 17.11.), siehe 0.2b
4. ~~RAM~~: dynamisch, mit Sample Swap abstimmen (Besitzer 17.11.)
5. Player: P2 per DSP-Patch, weniger wichtig, gemischt nach MFX und nach der Röhrenkurve (Besitzer 17.11.)
6. ~~Gerät~~: OK für Kartenschreiben und EXEC in 0.3/0.4 (Besitzer 17.11.), Gerät gerade aus
7. ~~Spettro~~: zeigt den Master; wenn es in die Quere kommt, während der Aufnahme nicht wählbar (Besitzer 17.11.)
8. ~~Blau~~: mono reicht (Besitzer 17.11.)

## Blind Spots & Open Unknowns

> Unbekanntes, das niemand gesagt hat: ungeprüfte Annahmen, ungefragte Fragen, unbesessene Teile.

- Schreibrate (der Besitzer schätzt rund 3 MB/s) und längste Schreibpause der Karte am Gerät: nicht gemessen, Phase 0.3.
- Laufabstand eines Lesers während WRITE (Flash-Löschen) und Pattern-Laden: offen, Phase 0.4.
- Ob ein Host-Port-Schreiben in `0xFF9031DC` während der laufenden Erfassung sicher ist (DSP liest das Wort je Sample): hergeleitet, Phase 0.2.
- Bedeutung der Stufe ab `0xFFA0189A` (vermutlich Metronom/THRU) und von `[P4+0x6C]/[P4+0x70]`: offen, Phase 0.2.
- Kein `f_sync`: Stromausfall-Verhalten, Phase 2.4.
- FatFs-Reentranz mit anderen Kartenschreibern der Firmware: offen, Phase 2.3.
- CPU-Kosten des Kartentreibers bei 0,19 MB/s Dauerschreiben: offen, LOAD METER am Gerät.
- Sample Swap ist nicht gemergt (#166); Ringbereich und Weg C/P1 hängen an seinem Speicherplan.
- Idle Power Save und Auto Power Off während der Aufnahme: ungefragt, in 1.3 klären.
- Blau: Tester nötig, der Besitzer hat nur rot.

## Implementation Log

> Findings, deviations, and decisions made during implementation that weren't
> anticipated in the original plan. This section is populated by the implementing
> agent, leave it empty when creating the plan.

- **Phase 0, Arbeitsstand:** Der bestehende Zweig liegt im separaten Worktree. Keine Geräteverbindung wurde geöffnet. 0.1, 0.3 und 0.4 bleiben Gerätemessungen durch den Besitzer; die frühere Freigabe für EXEC und Kartenschreiben gilt für diese Ausführung nicht.
- **Phase 0.2, Simulator:** Ein reproduzierbares Prüfprogramm liegt unter `tools/dsp/native_recording_probe.py`. Es führt die originalen Blackfin-Abschnitte mit synthetischen Eingaben aus. Rücksprünge begrenzen die geprüften Abschnitte. Extrahierte Daten und ELF bleiben außerhalb des Repos. 4803 Frames prüfen Quellwechsel, Zwischenwort, DMA-Adressen und Ringumlauf. Der virtuelle GNU-Simulator bildet hier keine echte MDMA ab; Ringdaten werden aus den geprüften Deskriptoren nachgebildet. Kein Beleg für Gerätezeiten.
- **Phase 0.2b, Abweichung im Signalweg:** AUDIO IN THRU kommt erst bei `0xFFA018B8..0xFFA018DC` zum Mix, hinter dem bisherigen Capture-Abgriff. Das Mono-Signal danach ist das Metronom: Der Sequencer fragt die Metronomeinstellung ab und ruft über `0xC003FC60` den Auslöser `0xC0014198` auf. Dieser schreibt DSP-Parameter `0x4C55` und `0x4C56`. Die Ausgangsstufe verarbeitet diese bei `0xFFA018E0..0xFFA01906`. Ein neues Aufnahme-Wort muss den Eingangsanteil enthalten, den Klick auslassen und die nachfolgende Ausgangsverstärkung berücksichtigen. Ein bloßes Umstellen auf `0xFF802888` würde AUDIO IN THRU verlieren.
- **Phase 0.2b, Folgerung für Phase 1:** Das eigene DSP-Wort aus 4.1 wird schon für die Aufnahme benötigt; der Player ergänzt später seine Summe an dieser Stelle. THRU wird nach der Röhrenkurve ergänzt. Der klickfreie Zweig braucht dieselbe Ausgangsverstärkung. Der Capture-Abschnitt läuft in der bestehenden Schleife früher; die neue Reihenfolge oder ein definierter Frame-Abstand samt Initialisierung muss im DSP-Fall geprüft werden. Den fertigen Klick nachträglich abzuziehen wäre bei Sättigung nicht korrekt.
- **Phase 0.5, offen:** Ohne die längste Leserlücke und die längste Kartenpause ist A/B/C nicht belastbar wählbar. Die erste Sperre vor Phase 1 wurde später ausdrücklich aufgehoben (siehe Fortsetzung unten); ein Aufnahmedienst ist noch nicht angebunden. Die optionalen Plugin-Erweiterungen, der spätere Player und der Test auf blau bleiben in ihrer vorgesehenen Reihenfolge.

- **Phase 0, Prüfstand:** Der abschließende GNU-Lauf ist grün: vier Stereo/Mono-Paare, Capture-Start und 4803 Frames mit wechselnder Quelle, Ringumlauf sowie je sechs Differenzfälle vor und nach dem Klick. Der Docs-Test besteht 8 von 9 Prüfungen; nur die schon vorhandenen Personennamen in dieser temporären Plan-Datei verletzen die Veröffentlichungsregel. Die Datei bleibt bis zur weiteren Umsetzung erhalten und wird vor dem Merge entfernt.

- **Phase 1, Freigabe vor den Gerätemessungen:** Die Umsetzung wird auf ausdrücklichen Wunsch fortgesetzt; gemessen wird später am selben Tag. Aus dem missverstandenen Wert „0,3“ wird kein neuer Zahlenwert abgeleitet. Rund 3 MB/s bleibt die bisherige Schätzung, nicht eine gemessene Garantie. 0.1, 0.3, 0.4 und die endgültige Ringentscheidung bleiben offen.
- **Phase 1.2, Aufteilung:** Der native Dateischreiber wird zuerst unabhängig vom DSP-Ring umgesetzt (1.2a); danach folgt die Anbindung an den Aufnahmedienst und dessen Task (1.2b). Ein eigener Dateikontext verhindert die gemeinsame Nutzung des Plugin-Lader-FIL. Das FIL braucht laut SD-Recherche rund `0x224` Byte; reserviert werden `0x240`, dazu der Sektorkopf und ein eigener Pfad.

- **Phase 1.2a, geprüft:** Elf native ARM-Fälle sind grün, einschließlich Sektor-Kopf, exakter PCM-Daten, Dateinamenskollisionen, Mono für alle drei Adressprofile, Teilwrites, I/O-Fehlern, Abschlussfehlern und FAT32-Grenze. Der Dateikontext bleibt nach einem fehlgeschlagenen Schließen im Besitz des Schreibers und wird beim nächsten Abschluss nur erneut geschlossen. Der Baustein ist noch nicht im Aufnahmedienst angebunden.

- **Phase 1.1, vorläufiger Weg A:** Der bestehende 100-ms-Ring dient als Arbeitsgrundlage. Die 80-ms-Grenze aus dem Plan wird konservativ geprüft, einschließlich der Übertragungszeit; sie ist kein Messwert. Eine Überschreitung beendet den gültigen Datenstrom mit sichtbarem Fehler. Die endgültige Entscheidung A/B/C und die Gerätefreigabe bleiben offen.
- **Phase 1.1a, DSP:** Zwei Umleitungen speichern den Mix nach THRU und wenden dieselbe geglättete Ausgangsverstärkung auf den klickfreien Zweig an. Der normale Ausgang bleibt in acht GNU-Fällen bitgleich. Der eigene Boot-Block lädt nach `0x01F12000`, außerhalb der vier gelesenen DSP-Heaps und der vorhandenen Ladeblöcke. Die Verlängerung bleibt vor dem Preset-Reservat bei `0xC013C200`. Ein eigenes Kennwort verhindert den Start ohne diesen DSP-Code.
- **Phase 1.1b, Zeitprüfung korrigiert:** Die unabhängige Prüfung fand einen Fehler beim Zeitstempel: Die Abschlusszeit eines langsamen Transfers verdeckte das Alter seines früheren Ring-Snapshots. Zwei zunächst fehlschlagende Fälle belegen das beim Start und beim laufenden Lesen. Der Zeitstempel gehört jetzt zum Beginn des Snapshots; zwölf Leser-Fälle sind grün.

- **Phase 1.2b, Worker:** Die Command-Anforderung macht nur Speicherzugriffe. Der Worker prüft die Capture-Belegung vor dem Anlegen der Datei, braucht mindestens zwei 64-KiB-Blöcke und friert die Erfassung vor dem Leeren des Restpuffers ein. Teilwrites, Stop während des Öffnens, lange Kartenpausen und fehlgeschlagene Abschlussversuche sind mit Fällen geprüft. Der dauerhafte Laufzeithook und die Heap-Verwaltung fehlen noch.
- **Phase 1.2b, Anforderungsrennen korrigiert:** Eine unabhängige Prüfung reproduzierte einen Stop, der zwischen Lesen und Löschen einer Start-Anforderung verlorenging. Command-Veröffentlichung und Start-Übernahme einschließlich STARTING sind jetzt kurze atomare Speicherabschnitte. Vor DSP- und Dateiaufrufen ist der vorherige Interruptzustand wiederhergestellt; der Unterbrechungsfall ist grün.
- **Phase 1.4, native Karte:** `tools/emu/recording_cases.py` führt den Worker aus eigenem Emulator-Arbeitsraum im CommandTask-Kontext aus. Auf rot und Hacktribe bestehen jeweils drei Prüfungen: lesbare 48-kHz-Stereo-WAV mit bitgleichen eigenen PCM-Frames, unveränderter Benutzer-Flash und keine Assertions. Die realen FatFs-, Karten- und Host-Port-Routinen laufen dabei als ARM-Code. Der DSP liefert ein synthetisches Signal. Das ist noch keine Prüfung des Menüeintrags.
- **Phase 1.1b, Host-Port-Vertrag korrigiert:** Die native Routine `0xC0014284` ignoriert Transfers unter 16 Wörtern. Das war im ersten Firmware-Integrationstest sichtbar. Kurze Transfers verwenden nun `0xC00146B4` mit exakter Länge, über den nativen Port aus `0xC0015C98`, unter derselben DSP-Sperre 1 (`0xC0000D80`/`0xC0000CA8`). Benachbarte Zustandswörter werden nicht mitgeschrieben.
- **Phase 1.1a, Belegung:** Unveränderliche ARM-Bootdaten sind durch die Schreibbereiche der Patch-Datei belegt, nicht als zusätzliches Laufzeit-RAM. Der eigene DSP-Bereich steht getrennt unter `dspMemory`; der Builder prüft vorhandene Ladeblöcke und die Heap-Tabelle auf Überschneidung. Der RAM-Kollisionstest mit beiden Sampler-Patchsets ist grün.

- **Task und Besitz:** CommandTask führt den Dienst unabhängig von PLAY aus. Eingaben veröffentlichen nur Wünsche;
  die Anzeige liest keinen privaten Heap-Kontext. Dateikontext und Ring bleiben bei fehlgeschlagenem Schließen erhalten.
  Der öffentliche Belegt-Zustand endet erst nach der Speicherfreigabe, zusammen mit Zeiger und Wunsch unter IRQ-Sperre.
  Der Fehler an dieser Grenze wurde erst rot, danach grün geprüft.
- **Dynamischer Speicher:** Im vollständigen Startlauf kann der originale Allocator keine 2 MiB bereitstellen. Es wird
  die größte verfügbare Zweierpotenz von 128 KiB bis 2 MiB versucht und die tatsächliche Größe veröffentlicht. Beide
  Sampler-Läufe erhalten 1 MiB. Das ist ein Emulatorbefund, keine Zusage für das Gerät und keine endgültige Ringwahl.
- **Native Ansicht:** RECORD ist die dritte Quelle in SHIFT+REC; der native Quellwert bleibt 0/1. Konstruktor und
  Destruktor melden die Lebensdauer ohne behaltenen Ansichtszeiger. PLAY schließt die Ansicht und startet keine Aufnahme.
  Normales REC außerhalb der Ansicht bleibt Transport-REC. Quelle und Stop-Bedienung bleiben bis zur Freigabe erreichbar.
  Die Anzeige nennt Datei, Dauer aus PCM-Bytes und Fehler; Öffnungszeit und Abschlussversuche zählen nicht als WAV-Dauer.
- **Erfassungssperre:** Apps mit Erfassung werden anhand gültiger Bytecode-Befehle erkannt, nicht anhand des Namens.
  Während der Aufnahme sind sie nicht wählbar; eine offene Erfassungs-App schließt der UI-Rahmen. CommandTask schließt
  seine eigene Spektrumerfassung vor dem Aufnahmestart. Native SAMPLING bleibt bis zum Abschluss gesperrt, auch wenn
  der Aufnahmeschalter schon ausgeschaltet ist.
- **Zeitgrenze:** Ein voller 64-KiB-Write im aktuellen Karten-/CPU-Modell überschreitet die vorläufige 80-ms-Frist und
  erzeugt sichtbaren Lückenstatus 20. Die WAV enthält einen exakten, zusammenhängenden PCM-Anfang und einen gültigen
  Abschlusskopf. Das belegt den Fehlerabschluss, keinen erfolgreichen langen Take und keine gemessene SD-Rate.
  Kurze native Takes und der Fristabbruch werden getrennt geprüft. 0.3/0.4 entscheiden weiter über Weg A.
- **Softwarestand Phase 1:** 64 gezielte native und strukturelle Tests sind grün. Das vollständige Patch-Set besteht je
  15 Aufnahmeprüfungen auf Hacktribe und rot, acht Scope-Prüfungen und zwei gezielte RAM-/Patcher-Prüfungen. Der statische
  DSP-Prüfer kontrolliert beide Umleitungen, eigenen Ladeblock, Start-Header und Ladelänge, auch zusammen mit
  stage2-memory. Alle drei Laufzeitdateien wurden neu gebaut und bleiben nach dem aktuellen Repository-Verfahren
  erzeugte, ignorierte Dateien. Geräteabnahme und endgültige Ringwahl sind offen.

- **Phase 2.1:** Ein terminaler Erfassungsfehler erhält einen benannten cue-Marker am Ende des gültigen PCM-Anfangs.
  cue und LIST/adtl/labl ersetzen einen Teil des reservierten JUNK-Bereichs im Sektorkopf. PCM bleibt ab Byte 512;
  es gibt keinen zusätzlichen Schreibzugriff während der Erfassung. Die Anzeige zeigt den Lückenzähler, auch nach
  Abschluss; erst eine neue Aufnahme setzt ihn zurück. Die unbekannte Zahl verlorener Frames wird nicht erfunden.
  Beide vollständigen Sampler-Patchsets bestehen jetzt je 17 Aufnahmeprüfungen einschließlich dauerhaftem WAV-Marker.
- **Phase 2.2:** Der private Ring wird ausschließlich im allgemeinen Heap angefordert und nach Freigabe von Datei und
  DSP-Erfassung gelöscht. Er verwendet keinen festen Bereich aus der Sample-Swap-Reservierung. Die vorläufige
  Ringwahl und Gerätezeiten bleiben von 0.3/0.4 abhängig.

- **Phase 2.4, Vorbefund:** Der native Abschluss bei `0xC009E3DC` ruft vor dem Invalidieren des FIL-Kontexts
  `0xC009E2C8` auf. Diese Routine prüft den Kontext und schreibt geänderte Puffer und Verzeichniseinträge zurück.
  Sie ist ein Kandidat für das bisher nicht benannte f_sync und wird vor einer Verwendung im Emulator geprüft.
  Es gab keinen Aufruf dieser Routine am Gerät.
- **READ am Gerät:** Am 18.11. wurde über den Linux-Rechner der USB-SOUND-Port auf MIDI-Kanal 10 erreicht.
  Gesendet wurde ausschließlich BLECH READ 0x61. Die Ausgangswerte stehen in Abschnitt 10 der Messdatei;
  der DSP-Leser mit EXEC bleibt unbenutzt. Spettro muss für seinen bestehenden ARM-Zustand manuell geöffnet werden.


- **Phase 2.3, Zwischenstand:** Gepufferte Plugin-Daten und SD-Einstellungen warten im RAM bis zum Aufnahmeabschluss.
  Import, Export und Plugin-Verwaltung prüfen den Aufnahmezustand vor Dateizugriffen und Änderungen. Sieben gezielte
  Sperrfälle bestehen. Ein vollständiger Hacktribe-Lauf bedient WRITE während der Aufnahme: der Wunsch wartet,
  nach REC-Stopp entsteht eine gültige SD-Einstellungsdatei, die WAV bleibt PCM-genau und ohne Lücke. Die Reihenfolge
  zwischen Eingabetask und UI-Kartenzugriffen wird vor Abschluss der Aufgabe gesondert geprüft.
- **Gerät vertagt:** Spettro ist auf dem Gerät nicht installiert. Eine geprüfte Katalogdatei liegt außerhalb des
  Repositorys bereit. Installation und weitere Gerätemessungen wurden auf später verschoben; die Verbindung bleibt
  auf READ beschränkt.


- **Phase 2.3, Task-Grenze:** Eingaben laufen in CsTask, der UI-Rahmen und native Tastenhandler in UiTask. Eine reine
  Belegt-Prüfung reichte deshalb nicht. RECORD sperrt neue UI-Kartenzugriffe sofort; CommandTask wartet vor dem Start
  auf die nächste UI-Rahmengrenze. Ein gezielter Fall unterbricht einen laufenden Plugin-Dateizugriff genau bei f_open:
  die Aufnahme wartet, der gespeicherte Wert bleibt exakt. Stop kann die Wartephase ohne Datei oder Erfassung abbrechen.
  Nachgeholtes SD-Speichern und Wachhalten hängen nicht vom scharfgeschalteten Plugin-Lauf ab. Der öffentliche Bereich
  umfasst dafür 72 Byte und ist in allen drei Laufzeiten neu angemeldet.
- **Phase 2.3, Patterns:** Einzel- und Gesamtexport bestehen im Emulator. 253 originale f_write-Aufrufe laufen ausschließlich
  in derselben Task wie der Aufnahme-CommandTask-Haken, die UI-Rahmen getrennt davon. Sample Swap #166 ist weiter offen;
  dessen Integration bleibt Teilaufgabe 2.3c. Es wurde kein Firmware-Zweig parallel verändert.
- **Phase 2.4, f_sync bestätigt:** Der isolierte native Aufruf bei `0xC009E2C8` persistiert eine noch offene WAV samt
  Verzeichnisgröße und 32 KiB exakten PCM-Daten im Emulator. Der Kopf trägt dabei weiterhin die alte Länge. Für einen
  konsistenten Zwischenstand müssen zuerst PCM und Verzeichnis, dann der vergrößerte WAV-Kopf gesichert werden.


- **Phase 2.4:** Der Schreiber sichert den leeren Anfangskopf und danach ungefähr jede Sekunde neu geschriebener PCM-Daten.
  Zuerst werden PCM und Verzeichnisgröße synchronisiert, dann der größere WAV-Kopf geschrieben und synchronisiert.
  Die Dateiposition kehrt zum PCM-Ende zurück. Der Fehlerabschluss folgt derselben Reihenfolge; ein fehlgeschlagener
  erster Sync darf keinen Kopf veröffentlichen, der über die gesicherte Dateigröße hinausgeht. Ein solcher Zwischenfehler
  wurde in der Prüfung gefunden und mit einem nativen Fehlerfall abgesichert. 38 gezielte Kerntests und je 31 vollständige Aufnahmeprüfungen beider Sampler bestehen.
  Native SD-Abbilder an den Aufrufgrenzen bleiben gültige PCM-Anfänge. Physische Sektorabbrüche sind damit nicht geprüft.
- **Blaue f_sync-Übersetzung:** Die ursprüngliche blaue Firmware liegt für den lokalen Vergleich vor. Der erste Aufruf
  ihres bereits zugeordneten f_close führt zu `0xC008AE20`; 69 Befehle entsprechen dem Sampler nach Maskieren der
  Sprungabstände. Nur Adresse und Herleitung wurden in der Übersetzungskarte ergänzt, keine Firmware-Bytes.


- **Phase 2.5, Speicherfehler:** Ein ungültiges privates Dateiobjekt oder eine nachweislich entfernte Karte beendet den
  Besitz am FIL-Kontext mit erhaltenem Fehler. Solange die Karte vorhanden und das Objekt gültig ist, bleiben
  Abschlussfehler wiederholbar. Im nativen Entnahmefall endet die Erfassung, der Heap wird frei und die Ansicht zeigt
  Card error. Eine eingesetzte Ersatzkarte nimmt nach erneutem REC wieder PCM-genau auf.
- **Phase 2.5, Dateigrenze:** Der Worker kürzt einen Block an der maximalen WAV-Datenlänge auf ganze Frames und legt
  bei verbleibenden Daten die nächste exklusive REC-Datei an. Ein exaktes Ende erzeugt keine leere Folgedatei.
  Die echte 32-Bit-Arithmetik wird ohne 4-GiB-Speicherbelegung geprüft; der native FatFs-Fall verwendet eine 8-KiB-Grenze
  und vergleicht die zusammengefügten Dateien PCM-genau. Die Anzeige zählt die Dauer der aktuellen Datei.
- **Vollkartenfall:** Das isolierte Kartenabbild muss seine üblichen BLECH-Ordner bereits besitzen. Ohne sie arbeitete
  die Startmigration noch in UiTask, während der isolierte Worker außerhalb der produktiven Startfreigabe begann.
  Mit vollständig vorbereiteten Ordnern und weiterhin acht freien Clustern endet der native Lauf mit Card full,
  896 exakten Frames und freigegebenen Ressourcen. Die produktive Aufnahme wartet bereits auf die UI-Rahmengrenze.


- **Phase 2.5, Abschluss im Emulator:** 61 gezielte Laufzeit-, Schreiber-, Leseranbindungs- und Kartensperrfälle sowie
  je 38 vollständige Aufnahmeprüfungen auf rot und Hacktribe bestehen. Die Ersatzkarte erhält 2750 exakte Frames;
  der Vollkartenfall 896 Frames. Eine echte 4-GiB-Datei wurde nicht erzeugt. Die Folgedatei ist mit nativer FatFs und
  verkleinerter Segmentgrenze geprüft, die reale Grenzarithmetik getrennt. Gerätewerte und Langzeitabnahme bleiben offen.


- **PLAY während der Aufnahme:** Beide Sampler lassen die Erfassung nach PLAY und geschlossener Ansicht weiterlaufen.
  SHIFT+REC öffnet die Ansicht wieder, REC stoppt. Die zusätzliche native Prüfung erhält eine PCM-genaue WAV ohne
  Lücke. PLAY ohne REC-Start legt weiterhin keine Datei an.
- **Weitere Reihenfolge:** Phase 3 bleibt ohne angeforderte API-Erweiterung offen. Phase 4 wartet wie entschieden auf
  Sample Swap in develop. Für Phase 5 ist die Verfügbarkeit eines blauen Testgeräts angefragt; davon abhängiger Code
  beginnt noch nicht. Die Bedienungsdoku und mehrsprachigen Notizen aus 6.1 werden als Entwurf für den geprüften
  Sampler-Stand vorbereitet. Es gibt keinen Versionssprung und keine Release-Freigabe.


- **Doku für den Sampler-Stand:** Bedienung, Fehlermeldungen, Dateifortsetzung und offene Geräteabnahme stehen dauerhaft
  in der Aufnahmeanleitung und Messdatei. Patcher-Doku und README verlinken sie; die 1.6-Notizen liegen als deutscher,
  englischer und französischer Entwurf vor. Die Prüfung der Release-Notizen und die gezielten Dokumentationsprüfungen
  bestehen. Die Plandateien bleiben für die noch offenen Aufgaben erhalten und müssen vor dem Merge entfernt werden.


- **Phase 5, 19.11.:** Ein blauer Tester ist vorhanden; die Offline-Umsetzung ist damit freigegeben. Eigener ARM-Code
  verwendet den nachgewiesenen nativen Halbwortsender für Start und Stop von `0x37`. Der ursprüngliche Ring besteht
  aus 32-Bit-Worten; ARM verdichtet die oberen 16 Bit in Mono-PCM. Der geplante feste Abgriff `0xFF802818` entfällt
  zugunsten des eigenen DSP-Summenworts nach THRU und Ausgangspegel. Zehn GNU-Differenzfälle erhalten den hörbaren
  Ausgang bitgenau, einschließlich rechts gepannter Signale in der Mono-Aufnahme.
- **Blaue Bedienung:** Ohne ursprüngliche Sampling-Ansicht öffnet SHIFT+REC eine eigene RECORD-Ansicht im BLECH-Menü.
  CsTask stellt nur Anfragen; UiTask prüft bei REC den aktuellen Bildschirm. Ein im Review gefundener verspäteter
  REC-Druck nach EXIT löst damit keine Aufnahme mehr außerhalb der Ansicht aus. Der native vollständige blaue Build
  schreibt PCM-exakte Mono-WAVs, hält PLAY unabhängig und zeigt nach Abschluss Saved. Beide Sampler bestehen nach
  Aufteilung der gemeinsamen Anzeige und des Lesers weiterhin je 46 Aufnahmefälle. Gerätebericht, Messwerte und
  lange Sets bleiben offen; der Player aus Phase 4 wird nicht vorgezogen.

- **Startphasenprüfung:** Der vollständige blaue Prüflauf fand zwei fehlende genaue Deklarationen: den beim Boot
  gelesenen DSP-Längenwert und den leeren Audio-Dienst aus CommandTask. Beide Spannen sind jetzt im jeweiligen
  Patch begründet, mit vier Byte je Bereich. Die Laufzeit, der Signalweg und die Startbedingungen wurden dafür
  nicht gelockert. Die Übersetzungskarte für den Browser wurde aus den vorhandenen Quelldaten neu erzeugt.

- **Vollständige Offline-Abnahme dieses Stands:** Die eigenen Originale bestehen `check.py --cases recording_cases`:
  blau 52 Prüfungen mit 27 Aufnahmefällen, beide Sampler je 73 Prüfungen mit 48 Aufnahmefällen, einschließlich Start
  und DSP-Schnittstelle. 103 gezielte Python-Fälle, vier RAM-/Haken-/Patcher-Fälle und 17 Doku-/Scope-Fälle bestehen.
  Die volle Suite bleibt in CI. Sample Swap #166 ist weiterhin offen; dessen Karteneinbindung und der spätere Player
  werden deshalb noch nicht umgesetzt. Es gab in diesem Schritt keine Geräteverbindung.

- **App-Abnahme, 19.11.:** Der Import beider BSDIFF-Dateien über `readAnyPatch` und `applyAnyPatch` erzeugt
  zwar die richtigen Firmwarekopien, prüft aber noch nicht den installierten Emulator-Dienst. Die installierte
  Desktop-App vom 14.11. lehnt den blauen Aufnahme-Abgriff mit `dsp_stream` ab; der Fehler ist über ihren
  HTTP-Prüfaufruf reproduziert. Die Testverteilung braucht daher auch einen aktuellen gebündelten Prüfer.
  Ein separater App-Teststand mit eigener Versionskennung verhindert die Wiederverwendung des alten Dienstes.
  Es wird keine DSP-Prüfung abgeschaltet und keine Firmwareänderung vor diesem Fehler versteckt.

- **Gebündelter App-Teststand:** Die separate Mac-App `1.6.0-rec.1` wird mit eigener Kennung gebaut. Der
  tatsächlich enthaltene, signierte Emulator besteht die HTTP-Kurzprüfung des blauen und roten Testpatches mit
  jeweils 23 Prüfungen. Ein absichtlich beschädigter DSP-Abgriff wird weiterhin abgelehnt. Die App-ZIP wurde wieder entpackt; Signatur, Hauptprogramm und Emulator stimmen.
  Die Firmware-Patchdateien bleiben bytegleich. Die Testverteilung nennt nun ausdrücklich den erforderlichen
  neuen App-Prüfer; die zuvor installierte App wurde nicht überschrieben. Die neue Röhrenkurve ist nicht gebaut,
  der aktuelle Aufnahme-Abgriff liegt hinter dem vorhandenen Soft-Clipper.

## References

- docs/messungen/2026-11-17-native-aufnahme.md
- docs/messungen/2026-11-12-plugin-api31-spektrum.md, docs/messungen/2026-11-07-spettro.md
- docs/messungen/2026-10-25-sd-takt.md, docs/messungen/2026-10-22-ram-frei.md
- DSP-Kern-Plan vom 16.11.2026 (separater Arbeitsplan)
- Zweig feature/sample-swap-native-dsp: docs/messungen/2026-11-06-sample-ram-aufnahme.md
