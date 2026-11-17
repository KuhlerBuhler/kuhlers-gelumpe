# Plan: Natives Aufnehmen und Abspielen (1.6)

> Entwurf 17.11.2026, Status: alle Fragen beantwortet (17.11.). Kein Code vor dem Ja; Phase 0 (Messung) darf laufen, Gerät gerade aus.
> Grundlage: docs/messungen/2026-11-17-native-aufnahme.md (Docs-PR gegen develop).

## Ziel

Den laufenden Mix der Electribe ohne PC und Interface als WAV auf die Karte aufnehmen (48 kHz, stereo, 16 Bit, ganze
Sets), und eine WAV von der Karte abspielen, damit ein Track laufen kann, statt live gespielt zu werden. Firmware-nativ
(Menü im Firmware-Look), rot zuerst; blau nur mit Tester.

## Was feststeht (aus der Messung)

- Master nach MFX + Soft-Clipper liegt jedes Sample in DSP `0xFF802888` (L hoch, R tief), Mono in `0xFF80288C` (gelesen).
- Erfassung `0x37` liest ihre Quelle über den Zeiger `0xFF9031DC`; Zeiger auf `0xFF802888` = Master im 100-ms-Ring
  `0x01C722A0` (hergeleitet, Weg A). Teilt Zwischenwort und DMA mit Korgs SAMPLING und Spettro.
- Karte lesen 3,1/5,1 MiB/s am Gerät; Schreiben schätzt Pascal auf rund 3 MB/s (geschätzt, nicht gemessen). Bedarf 0,19 MB/s.
- WAV ohne `f_truncate`: anhängen, Kopf am Ende per `f_lseek` überschreiben. Kein `f_sync` gefunden.
- Sample Swap (#166) belegt `0xC274F000..0xC4000000`.
- Blau: `0x37` da, kein Stereo-Wort, kein `0x3B`.

## Arbeitsregeln

- Gerät: READ ohne Rückfrage; WRITE, EXEC, Kartenschreiben am Gerät nur mit Pascals OK. Nie EXEC `0xC0029AB8`.
- Firmware-PRs seriell, gegen develop. `node tools/load-gate.mjs` vor Tests.
- Neue RAM-Bereiche in der RAM-Liste der Patches anmelden; der RAM-Kollisionstest muss grün bleiben.
- DSP-Verhalten im QEMU-DSP-Kern prüfen (Plan 2026-11-16-qemu-dsp-kern), sobald umgeschaltet; bis dahin GNU-Sim.

## Phase 0: Belege am Gerät und Weg entscheiden (Spike, 1 bis 2 Tage)

Ziel: Weg A, B oder C für den DSP-Ring festlegen, mit Zahlen.

- [ ] 0.1 Nur lesend: während RESAMPLING die Zustandswörter `0xFF9031F8..0xFF90320C` lesen (Quelle = Master-Wort?), Ringzeiger `0xFF9031D8` bei laufendem Spettro lesen
- [ ] 0.2 Im DSP-Sim: Erfassung starten, Quellzeiger umbiegen, Ring gegen das gepackte Master-Wort vergleichen (bit-gleich); Stufe ab `0xFFA0189A` und `[P4+0x6C]/[P4+0x70]` benennen
- [ ] 0.2b Wo AUDIO IN und Metronom in den Master kommen: liegt AUDIO IN schon im Master-Wort (sonst dazumischen)? Gibt es einen Abgriffpunkt nach AUDIO IN, aber vor dem Metronom (Pascal: Metronom nicht auf der Aufnahme, aber weiter hörbar)? Wenn nicht: Metronom mit drauf, Pascal fragen
- [ ] 0.3 OK da (Pascal 17.11., Gerät gerade aus): Kartenschreibtest am Gerät (64-KiB-Blöcke, 60 s, 12,5 und 25 MHz): Rate, längste Schreibpause, Pausen beim Clusterwechsel; Testdatei danach löschen
- [ ] 0.4 OK da (Pascal 17.11.): Laufabstand eines Lesers messen (CommandTask vs. eigene Task) während Pattern-Wechsel, WRITE (Flash-Löschen) und Sample-Swap-Laden; Ergebnis längste Lücke in ms
- [ ] 0.5 Entscheidung A/B/C in die Messung schreiben: A, wenn die längste Leserlücke unter 80 ms bleibt; sonst C (DSP-Ring im Sample-Speicher) oder B

Akzeptanz: Messdatei hat Zahlen zu 0.1 bis 0.4 und die Entscheidung.

## Phase 1: Master auf die Karte, ein Knopf (2 bis 3 Tage)

Vertikaler Schnitt: Start/Stopp an der Bedienung, Leser, ARM-Ring, Schreiber, WAV auf der Karte.

- [ ] 1.1 Aufnahmedienst: Erfassung mit Master-Quelle starten (gewählter Weg), Sperre gegen SAMPLING (Status belegt); Spettro zeigt während der Aufnahme den Master, und wenn das stört, lässt es sich während der Aufnahme gar nicht erst wählen (Pascal 17.11.), Leser leert den DSP-Ring in einen ARM-Ring und dreht R/L zu L/R
- [ ] 1.2 Schreiber in einer Task, die die Karte darf: WAV-Kopf 512 Byte (JUNK), Daten in 64-KiB-Blöcken anhängen, beim Stopp Längen setzen und schließen; Dateiname fortlaufend `Recordings/REC0001.WAV` (Pascal 17.11.)
- [ ] 1.3 Bedienung: SHIFT + REC zeigt heute RESAMPLING und AUDIO IN, dazu eine dritte Wahl RECORD (Pascal 17.11.); Korgs Auswahl dafür im Code finden und erweitern; Start nur über RECORD, nicht an PLAY gekoppelt (Pascal 17.11.); Anzeige: läuft, Zeit, Karte voll; Gerät schläft während der Aufnahme nicht
- [ ] 1.4 Emulator: DSP-Modell/QEMU liefert ein bekanntes Signal im Master-Wort; Fall prüft die WAV auf der virtuellen Karte (Kopf gültig, Frames bit-gleich, Länge stimmt), Fall-Modul im Verify-Scope angemeldet
- [ ] 1.5 Patcher-Tabelle, Messung, Schalter unter FEATURES (aus = kein Verhalten)

Akzeptanz: Fall grün auf Hacktribe und rot; WAV öffnet in einem Audioprogramm; Gerätetest (Liste im PR) mit Pascal.

## Phase 2: Lange Sets ohne Lücke (1 bis 2 Tage)

- [ ] 2.1 Lückenzähler: Leser erkennt überholten DSP-Ring und ARM-Ring-Überlauf; Anzeige und Marker (cue-Chunk oder Logdatei), nie stilles Verschlucken
- [ ] 2.2 Ring dynamisch (Pascal 17.11.): nur während der Aufnahme belegen, Größe nach Phase 0 (bis 2 MiB), mit dem Speicherplan von Sample Swap (#166) abstimmen
- [ ] 2.3 Andere Kartenschreiber (Einstellungen, Patterns, Plugins, Sample Swap) während der Aufnahme: warten lassen oder seriell, mit Fall
- [ ] 2.4 Stromausfall: Längen regelmäßig nachtragen oder Reparatur beim Start (Länge aus Dateigröße), mit Fall
- [ ] 2.5 Karte voll, Karte gezogen, 4-GiB-Grenze: sauber beenden, ab 4 GiB neue Datei

Akzeptanz: Emulatorfälle für Überlauf, Karte voll, Reparatur grün; Gerät: 60 min Set mit Pattern-Wechseln, 0 Lücken.

## Phase 3: Plugin-API Master-Quelle (0,5 Tag, optional)

- [ ] 3.1 `korg.audio.capture` bekommt die Quelle Master (neue Nummer am Listenende, API-Sprung), Spettro zeigt den Mix
- [ ] 3.2 Aufnahme-Status lesbar für Plugins (läuft, Zeit, Lücken), nur wenn Pascal will

Akzeptanz: Plugin-API-Fall grün; Doku DE/EN.

## Phase 4: WAV abspielen (später, 3 bis 5 Tage)

Pascal 17.11.: erst Aufnahme, der Player ist ein späterer Schritt und baut auf Sample Swap (#166) auf. Startet erst, wenn #166 in develop ist. Weg: P2 (DSP-Patch, Ring in den Mix), Pascal 17.11.; Player weniger wichtig als Aufnahme.

- [ ] 4.1 DSP-Patch: Leseweg aus einem Ring im DSP-Speicher, addiert nach MFX und nach der Röhrenkurve (Plan 2026-11-17-roehrenkurve-1.5.x), also nach dem Clipper bei 0xFFA0135C (Pascal 17.11.); die Aufnahme nimmt alles auf, was rausgeht, also auch die Wiedergabe (Pascal 17.11.): der Patch schreibt die Summe nach dem Player in ein eigenes Wort, und die Erfassung `0x37` zeigt dann darauf statt auf `0xFF802888`; Metronom bleibt die Ausnahme (0.2b), eigenes Zwischenwort, damit Aufnahme und Wiedergabe gleichzeitig laufen; im QEMU-Kern bit-genau geprüft
- [ ] 4.2 ARM: WAV wählen (Dateibrowser im Firmware-Look), Format prüfen (48 kHz, 16 Bit, mono/stereo, Rest ablehnen), Ring per Host-Port füllen, Start/Stopp, Pegel
- [ ] 4.3 Start mit PLAY koppeln (optional), Anzeige Zeit/Rest
- [ ] 4.4 Emulatorfall: WAV auf der Karte, Ausgang am DSP-Modell gleich der Datei

Akzeptanz: Fall grün; Gerät: Track 10 min ohne Aussetzer, gleichzeitig Pattern spielen.

## Phase 5: Blau (nur mit Tester)

- [ ] 5.1 Start über eigenen ARM-Code (Postfach `0x37` auf blau), mono über `0xFF802818`
- [ ] 5.2 Stereo auf blau entfällt, mono reicht (Pascal 17.11.); Wiedergabe über denselben P2-Patch fürs blaue Programm
- [ ] 5.3 Fälle auf blau, Gerätetest durch Tester

Akzeptanz: Fälle grün auf blau; Testerbericht.

## Phase 6: Doku und Release

- [ ] 6.1 Patcher-Doku, Plugin-Doku DE/EN (falls Phase 3), README-Zeile, 1.6-Notes DE/EN/FR

Akzeptanz: Docs-Test grün.

## Fragen an Pascal

1. Bedienung: ~~Menü oder Tastenkombi~~ SHIFT + REC mit dritter Wahl RECORD neben RESAMPLING und AUDIO IN (Pascal 17.11.), nicht an PLAY gekoppelt
2. ~~Ordner~~: `Recordings/REC0001.WAV` (Pascal 17.11.)
3. ~~Was soll drauf~~: Master mit AUDIO IN; Metronom nicht, wenn es geht, aber nur wenn man es weiter hört (Pascal 17.11.), siehe 0.2b
4. ~~RAM~~: dynamisch, mit Sample Swap abstimmen (Pascal 17.11.)
5. Player: P2 per DSP-Patch, weniger wichtig, gemischt nach MFX und nach der Röhrenkurve (Pascal 17.11.)
6. ~~Gerät~~: OK für Kartenschreiben und EXEC in 0.3/0.4 (Pascal 17.11.), Gerät gerade aus
7. ~~Spettro~~: zeigt den Master; wenn es in die Quere kommt, während der Aufnahme nicht wählbar (Pascal 17.11.)
8. ~~Blau~~: mono reicht (Pascal 17.11.)

## Blind Spots & Open Unknowns

> Unbekanntes, das niemand gesagt hat: ungeprüfte Annahmen, ungefragte Fragen, unbesessene Teile.

- Schreibrate (Pascal schätzt rund 3 MB/s) und längste Schreibpause der Karte am Gerät: nicht gemessen, Phase 0.3.
- Laufabstand eines Lesers während WRITE (Flash-Löschen) und Pattern-Laden: offen, Phase 0.4.
- Ob ein Host-Port-Schreiben in `0xFF9031DC` während der laufenden Erfassung sicher ist (DSP liest das Wort je Sample): hergeleitet, Phase 0.2.
- Bedeutung der Stufe ab `0xFFA0189A` (vermutlich Metronom/THRU) und von `[P4+0x6C]/[P4+0x70]`: offen, Phase 0.2.
- Kein `f_sync`: Stromausfall-Verhalten, Phase 2.4.
- FatFs-Reentranz mit anderen Kartenschreibern der Firmware: offen, Phase 2.3.
- CPU-Kosten des Kartentreibers bei 0,19 MB/s Dauerschreiben: offen, LOAD METER am Gerät.
- Sample Swap ist nicht gemergt (#166); Ringbereich und Weg C/P1 hängen an seinem Speicherplan.
- Idle Power Save und Auto Power Off während der Aufnahme: ungefragt, in 1.3 klären.
- Blau: Tester nötig, Pascal hat nur rot.

## Implementation Log

> Findings, deviations, and decisions made during implementation that weren't
> anticipated in the original plan. This section is populated by the implementing
> agent, leave it empty when creating the plan.

## References

- docs/messungen/2026-11-17-native-aufnahme.md
- docs/messungen/2026-11-12-plugin-api31-spektrum.md, docs/messungen/2026-11-07-spettro.md
- docs/messungen/2026-10-25-sd-takt.md, docs/messungen/2026-10-22-ram-frei.md
- thoughts/shared/plans/2026-11-16-qemu-dsp-kern.md
- Zweig feature/sample-swap-native-dsp: docs/messungen/2026-11-06-sample-ram-aufnahme.md
