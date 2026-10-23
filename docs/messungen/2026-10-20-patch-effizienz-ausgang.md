# BLECH: reproduzierbarer Ausgangsstand für die Optimierungen

Stand 20.10.2026. **Phase 0 abgeschlossen.** Die Firmwarepatches selbst
sind unverändert. Grundlage ist der abgeschlossene Produktstand
`0b2aad8de3a91b8a9dab8c67a66f73b5d6ca6a3c`. Die ältere
[Untersuchung aller Patchfamilien](2026-10-20-patch-performance.md) bleibt als frühere Messung
bestehen; ihre Zahlen werden nicht als Messung dieses neueren Stands ausgegeben.

## Originale

| Build | SHA-256 des Eingangs |
|---|---|
| Hacktribe | `7cb4825c184a7e3fa92224304be22a788c96c4b748c277e63a496baa9faae7ee` |
| Korg rot, Sampler 2.02 | `1d0f0689d5a12c8a8bde9f821f2a59adc5f6cd6012ddb201ebb192b72468a646` |
| Synth 2.02 | `41fc5f1c33209ef381d1c9fef21a72380bcd8d3431c9c1350a964f5c619ab8b8` |

Das früher verwendete, bearbeitete Hacktribe-Original war nicht mehr verfügbar. Der neue
Eingang wurde mit dem [offiziellen Hacktribe-Patch](https://github.com/bangcorrupt/hacktribe/tree/94c8e608e6918c432cac90b2c19042b2d65ae626)
auf dem unveränderten Sampler 2.02 erzeugt. Der vollständige Ausgabehash stimmt mit
[der veröffentlichten Ziel-Prüfsumme](https://github.com/bangcorrupt/hacktribe/blob/94c8e608e6918c432cac90b2c19042b2d65ae626/hash/hacked-SYSTEM.VSB.sha)
überein. Kein geänderter Synth-Header. Originale, Patchdownload und erzeugte VSBs liegen nur
im privaten Messpaket, niemals im Repository.

## Prüfen und messen

[check_sets.mjs](../../tools/patch/check_sets.mjs) liest eine private Datei mit allen drei
Originalpfaden und ihren erwarteten Hashes. Der Patcher bestimmt die passende Auswahl mit
`loadBlechSet`, `selectFor` und `applyPatches`. Erst danach schreibt das Werkzeug die Kopien
außerhalb des Repositorys und startet für jeden ganzen Satz `check.py` ohne `--quick`.
Die Ausnahmen stammen ausschließlich aus den angewendeten Manifesten. Die Prüfung läuft
mit ausgeschaltetem Ergebniscache; alle Aufgaben und ihre Gruppen müssen abgeschlossen sein.
Ein fehlender Build, abweichender Hash, Fehler oder unvollständiger Bericht verhindert den Gesamterfolg.

Die Platzbilanz vereinigt Code-/Datenintervalle und RAM-Reservierungen, prüft die freigegebenen
Bereiche am jeweiligen Original auf FF und nennt auch die größte zusammenhängende Lücke.
Unveränderte VSB-Dateigröße ist kein Beleg für unveränderten Platzbedarf.

[patch_performance.py](../../tools/emu/patch_performance.py) erfasst je Original und gepatchter
Fassung drei unabhängige Starts mit identischen selbst erzeugten Pattern- und Plugin-Eingaben.
Die drei Wiederholungen laufen in getrennten Emulatorprozessen parallel; gemessen werden
Gerätezeit und ausgeführte ARM-Blöcke, keine Laufzeit des Rechners.
Netzteilbetrieb ist vorgegeben; Transportzustand, Gerätezeit und Anzahl der App-Bilder werden geprüft.
Einzelszenen: Stillstand, Wiedergabe, KEYBOARD, vierstimmige lange Bindungen in SEQUENCER;
mit BLECH zusätzlich Menü, geschlossene Apps, Mandelbrot, Life, Pong und Hintergrundplugins.
Die Apps werden jeweils über genau 50 Laufzeitbilder gemessen. Der native Plugin-Lader wird
für alle zehn eigenen Presets getrennt von Karten-I/O und eigentlicher App-Ausführung gezählt.

Der Zähler verwirft nach dem Einhängen des Hooks bereits übersetzte Blöcke. Ein eigener
Kontrolltest mit einer vorher ausgeführten ARM-Schleife belegt 66 gezählte Befehle. Ohne
dieses Verwerfen meldete der neue Laderzähler fälschlich 2222929 statt 15148903 Befehlen.
Die korrigierte Messung liefert in drei unabhängigen Läufen jeweils 15148903 für die zehn
Presets. Die fehlerhaften Zwischenwerte werden nicht als Ausgangsprofil verwendet.

Beim ersten Synth-Profil wurde die bereits übersetzte Adresse des Bildschirmwechsels
nochmals durch die Sampler-zu-Synth-Abbildung geschickt. Das Messskript brach beim
Menüaufruf ab. Es verwendet nun die Sampler-Referenz für die abbildende Aufrufhilfe und
liest bereits native Adressen direkt aus dem Emulator. Die Firmware blieb unverändert.
Erfolgreiche einzelne Profile werden zusätzlich privat in `profile-progress.json` gesichert;
nur die anschließend vollständig geprüfte Datei `profile.json` gilt als Ausgangsprofil.

Die Befehlszählung erfolgt an ARM-Blockgrenzen. Es sind keine Hardwarezyklen und keine
DSP-Auslastungswerte. Drei Wiederholungen müssen gleiche Zähler und erfasste App-Zustände
liefern. Vergleiche prüfen Eingangsdateien, Bytecode und Messmethode erneut; fehlende
Phasennachweise werden als Fehler behandelt. MUL- und vollständige Transfermessungen werden
in ihren jeweiligen Optimierungsschritten ergänzt und können vorher nicht als bestanden gelten.

## Wiederholen

Nachtrag: Der spätere [MUL-Vergleich](2026-10-20-arm-optimierungen.md) hat eine Grenze
der ersten App-Messung aufgedeckt: Der Framezähler steigt bereits am Anfang und die
Uhr beeinflusst den Zufallsstart. Messformat 2 verwendet vollständige Frames und
feste Eingaben. Ausgang und Kandidat wurden damit neu erfasst. Die erste
Aufzeichnung bleibt historisch erhalten; das aktuelle Werkzeug lehnt ihr Format
für einen neuen Vergleich ab. Firmware-Prüfungen und Platzbilanz sind davon unberührt.

`BLECH_INPUTS` benennt eine private JSON-Datei mit genau `hacktribe`, `stock` und `synth`.
Jeder Eintrag hat `path` und `sha256`; relative Pfade beziehen sich auf diese Eingangsdatei.
`BLECH_BASELINE_DIR` muss ein neues, leeres Verzeichnis außerhalb des Repositorys sein.
`E2_EMU_PYTHON` benennt Python mit Unicorn. Fehlende Abhängigkeiten werden nicht übersprungen.

```sh
node tools/patch/check_sets.mjs --inputs "$BLECH_INPUTS" --out "$BLECH_BASELINE_DIR"
"$E2_EMU_PYTHON" tools/emu/patch_performance.py --capture "$BLECH_BASELINE_DIR" --out "$BLECH_BASELINE_DIR/profile.json"
"$E2_EMU_PYTHON" tools/emu/patch_performance.py --baseline "$BLECH_BASELINE_DIR" --candidate "$BLECH_BASELINE_DIR" --out "$BLECH_BASELINE_DIR/comparison.json" --phase baseline
```

Die Aufzeichnung beginnt erst nach drei erfolgreichen vollständigen Satzprüfungen. Die letzte
Zeile prüft den unveränderten Ausgangsstand; sie behauptet keinen Optimierungsgewinn. Für einen
späteren Vergleich zeigt `--candidate` auf das getrennt erzeugte und gemessene neue Verzeichnis.
Vorhandene Ausgaben werden nicht als neue vollständige Firmwareprüfung ausgegeben.

## Bereinigte Testannahmen

- Zwei Texttests erwarteten, dass die Menüflags unmittelbar aus r0 gespeichert werden.
  Der bestehende Code bewahrt sie während weiterer Einstellungsabfragen in r10 auf.
  Eine neue native Prüfung führt die eigene Speicherroutine für alle 48 Kombinationen aus
  Laufzeit, MFX, Pattern-Schalter, Notenassistent und TAP-Zustand auf drei Builds aus.
  Sie prüft 144 Kombinationen, gemischte Darstellungswerte und die CRC der Dateidaten vor dem
  Dateiaufruf. Die echten Datei-/Save-Pfade laufen zusätzlich in der vollständigen Firmwareprüfung.
- Die Samplerauswahl enthält den ruhenden IFX am festgehaltenen Produktstand nicht mehr.
  Der Test prüft diese Auswahl und weiterhin die konfliktfreie Zusammensetzung mit dem separaten Patch.
- Browserprüfungen erwarten jetzt die bestehende Seitengruppierung, Reihenfolge und den Titel
  Startbildschirm. Ausgeblendete Gruppenbezeichnungen sind keine zusätzlichen zugänglichen Tabs;
  die Tastatur muss gesperrte Einträge weiterhin überspringen. Die Oberfläche wurde nicht geändert.
- Der Filter-Bildvergleich scheiterte im ersten roten Gesamtlauf. Isoliert bestand der Filterpatch.
  Im ganzen Satz waren DISPLAY INVERT und damit der Bildschirm-Look auf dem normalen Weg an,
  bei EXIT am Start aus. Zudem lag die Probe nach 0,4 s am Ende des Hinweisfensters. Der Vergleich
  verwendet nun dieselbe unveränderte Darstellung auf beiden Wegen und 0,2 s vor dem Ablauf.
  Alle vier Bilder stimmen damit überein, sowohl isoliert als auch im ganzen Satz.
  Die eingeschaltete Gestaltung bleibt Gegenstand der eigenen vollständigen Look-Prüfungen.

## Ausgangswerte

Gemessen im Emulator über die gleichen zwei Sekunden mit vierstimmigen langen Bindungen.
Median und Höchstwert sind jeweils gleich, da alle drei Wiederholungen exakt übereinstimmen.

| Build | Original, ARM-Befehle | BLECH, ARM-Befehle | Mehraufwand |
|---|---:|---:|---:|
| Hacktribe | 71367109 | 88318974 | 23,75 % |
| Korg rot | 71357324 | 88290780 | 23,73 % |
| Synth | 72215639 | 72691789 | 0,66 % |

Der gemeinsame native Plugin-Lader benötigt für alle zehn Presets zusammen 15148903
ARM-Befehle. Auch seine drei Wiederholungen je Build sind identisch. Insgesamt wurden
90 Ladevorgänge und 27 App-Fenster mit zusammen 1350 Bildern geprüft. Die Firmware ist
der unveränderte Ausgangsstand, kein bereits optimiertes Ergebnis.

## Platzbilanz

Gemessen an den bestätigten FF-Bereichen des jeweiligen Originals. Werte in **KiB**,
auf eine Nachkommastelle gerundet. Ein KiB sind 1024 Byte; 1024 KiB sind ein MiB.
Die exakten Bytezahlen bleiben in der Messdatei.

| Build | Code/Daten | Reserviertes RAM | Zusammen belegt | Frei | Größte Lücke |
|---|---:|---:|---:|---:|---:|
| Hacktribe | 84,9 | 441,0 | 525,9 | 33,6 | 3,3 |
| Korg rot | 85,2 | 441,0 | 526,2 | 33,4 | 3,1 |
| Synth | 69,5 | 388,7 | 458,2 | 431,8 | 322,3 |

Alle Einzelwerte, Original- und Ausgabehashes, Setauswahl und Hashes der zehn Plugins stehen
in der [Messdatei](2026-10-20-patch-effizienz-ausgang-zahlen.json). Die freien Gesamtbytes sind
keine zusammenhängende Reserve.

## Was diese Größen bedeuten

Die Tabelle beschreibt unseren bestätigten Platz innerhalb des **2-MiB-Firmware-Abbilds**.
Sie ist keine Messung des insgesamt freien Gerätespeichers. Das Abbild wird beim Start in
RAM geladen. Seine bisher unbenutzten Bereiche können deshalb sowohl eigenen Programmcode
als auch Laufzeitdaten aufnehmen. Ein als RAM reservierter Bereich darf in der VSB weiter
FF enthalten; die laufende Firmware benutzt ihn später als Arbeitsspeicher. Reservierung
ist weder eine zusätzliche Vergrößerung der VSB noch ein Beleg für ständig belegte Daten.

### Wie viel RAM ist belegt?

**Belegt durch die Bootloader-Auswertung:** Der ARM sieht einen 64-MiB-RAM-Bereich, dazu
eine zweite Ansicht desselben Speichers ohne Cache. Die 128 MiB des Emulatorfensters sind
keine 128 MiB unterschiedlicher Speicherzellen. Die bestückte physische Gesamtkapazität
aller Speicherchips einschließlich des getrennten DSP-Speichers ist damit nicht vollständig
bestimmt. Beleg: [MMU und RAM-Alias](2026-10-12-vm-tempo.md#gerätelauf-2026-10-13-execute-ohne-antwort)
und [RAM-Messung](2026-10-07-cpu-ram-fenster.md).

Die 441 KiB unserer Sampler-Reservierungen sind rund **0,43 MiB**, etwa **0,67 %** des
64-MiB-ARM-Bereichs. Trotzdem belegen sie einen großen Teil der hier bestätigten freien
Firmwarefläche: auf den Samplern insgesamt rund 560 KiB. Andere RAM-Bereiche gehören
teilweise Korgs Verwaltung oder sind nicht hinreichend untersucht. Ihre Freigabe folgt
nicht allein daraus, dass eine Messung dort gerade nichts findet.

### Muss alles reserviert bleiben?

Die größten Teile der 441 KiB auf einem Sampler sind:

| Zweck | Reservierung | Nutzung |
|---|---:|---|
| Plugin-Prüfarbeitsbereiche | 160 KiB | Arbeitslisten beim Prüfen neuer Plugins; bleiben für spätere Imports verfügbar |
| Gemeinsamer Speicher für Blechy und Plugins | 128 KiB | Plugin-Bytecode sowie Variablen und Verwaltung; Blechys Bytecode bleibt im Firmware-Abbild |
| SysEx samt Dateiarbeitsbereich | 60 KiB | Kommunikations- und Dateipuffer |
| Datei- und Speicherabbildpuffer | knapp 32 KiB | Plugin-Dateien lesen und Speicherstände bearbeiten |

**Zusätzlich gemessen am nativen Lader mit eigenen Eingaben:** Blechy wird über den
internen Ladeweg `script_load_block_ex` ohne Bytecode-Kopie eingerichtet. Nur sein
Verwaltungseintrag und seine Variablen belegen den gemeinsamen Pool: 15904 Byte,
rund **15,5 KiB**. Mit allen zehn Preset-Plugins zusammen sind es 51964 Byte, rund
**50,7 KiB des 128-KiB-Pools**. Rund 77,3 KiB Poolkapazität bleiben in diesem Beispiel
für weitere Plugins. Die vorherige Angabe von 65,9 KiB stammte aus einem Zusatztest,
der Blechy über den normalen Plugin-Ladeweg kopierte. Dieser Weg entspricht nicht
seiner Einbettung in der Firmware. Das ist kein Nachweis des maximalen Gesamtverbrauchs
aller Laufzeit- und Dateipfade. Die reservierten
160 KiB Prüfarbeitsbereiche werden nicht dauerhaft mit nützlichen Daten gefüllt, müssen
aber bei jedem weiteren Import bereitstehen. Einfaches Überschreiben mit anderem Code
würde diese Lebenszeiten verletzen.

Ein kleinerer SysEx-Puffer kann nach den vollständigen Protokolltests **19 KiB am Stück**
freigeben. Die 160 KiB Prüfarbeitsspeicher sind ein größerer Kandidat für einen anderen
Aufbau oder eine abgesicherte gemeinsame Nutzung. Eine konkrete Einsparung ist dort noch
nicht bewiesen. Ein kleinerer Plugin-Pool würde die Kapazität für weitere Plugins senken.

### Wo liegen Blechys Bilder?

Blechy ist eine fest eingebaute BLECH-Funktion. Er wird nicht von der Karte importiert,
nicht in der Plugin-Liste gezählt und nicht exportiert. Intern verwendet er dieselbe
Skript-Laufzeit für Ereignisse und Anzeige. Der gemeinsame Pool ist deshalb kein
ausschließlich für Nutzerplugins bestimmter Bereich. Ein eigener Bereich für Blechys
Zustand würde den Gesamtbedarf allein durch die andere Zuordnung nicht verkleinern.

Blechy ist einschließlich seiner Bilddaten **in der Firmware eingebaut**. Die PNG-Dateien
werden beim Bauen in kleine Bitmaps umgewandelt. Gleiche Bilder werden wiederverwendet;
verwandte Zustände teilen die gemeinsamen Bildteile. Die PNG-Dateien selbst landen nicht
als einzelne Dateien in der Firmware. Der vollständige kompilierte Blechy-Block, Bilder
und Verhalten zusammen, umfasst **15476 Byte, rund 15,1 KiB**.

Belege: [Bildgenerator](../../tools/blechy-build.mjs),
[Laufzeit-Einbettung](../../tools/patch/script_hooks.py) und
[Bildbeschreibung](../../data/script/blechy-art.mjs).

Das Auslagern des ganzen Blocks auf SD würde höchstens diese rund 15 KiB im Firmwarebereich
freigeben, vor Abzug eines nötigen Ladewegs. Die Bilder brauchen zur Anzeige weiterhin
RAM. Blechy wäre dann von Karte, Datei und erfolgreichem Laden abhängig. Andere Plugins
werden bereits von SD geladen. Das eigene Startbild ist ebenfalls als Datei möglich;
Blechy ist bislang bewusst auch ohne Karte vorhanden.

### Kann die VSB größer werden?

Der unterstützte Aufbau umfasst **2 MiB Nutzabbild plus 256 Byte Dateikopf**. Das beschreibt
auch die [Hacktribe-Dokumentation](https://github.com/bangcorrupt/hacktribe/wiki/Debrick).
Im gemessenen Flash liegen direkt nach dem Firmwarebereich bereits Nutzerdaten. Eine größere
Datei allein schafft weder einen größeren Ladebereich noch eine neue Flash-Aufteilung.
Updater, Bootloader, Prüfsummen, Grenzen und das Layout müssten zusammen geändert und
untersucht werden. Das ist ein eigener Umbau; einen geprüften Erweiterungsweg für die VSB
gibt es bisher nicht. Weitere Daten von SD nachzuladen ist ein anderer Weg und wird bei
Plugins bereits verwendet. [Flash-Karte](../speicherbereiche.md#flash-bekannte-karte-und-dauerhafte-wirkung).

### Kann man die freien Lücken zusammenziehen?

Ja, durch Umordnen **unserer eigenen** Code- und RAM-Blöcke. Dabei müssen Generatoren,
Zeiger, Sprünge, Tabellen, Startreihenfolge und alle Manifeste gemeinsam angepasst werden.
Reines Verschieben vergrößert den gesamten freien Platz nicht: Es macht zum Beispiel einen
zusammenhängenden Block aus mehreren kleinen nutzbar. Die beiden getrennten bestätigten
Sampler-Fenster und der dazwischenliegende Original-/Hacktribe-Code bleiben Grenzen.
Es ist daher noch kein bestimmter größerer Block zugesagt. Reservierungen zu verkleinern
oder anderweitig unterzubringen würde zusätzlich den Gesamtplatz erhöhen. Beides braucht
eine eigene Belegungsplanung und danach die vollständigen drei Firmwareprüfungen.

## Prüfstand

| Prüfung | Ergebnis |
|---|---|
| Neue Satz- und Messwerkzeugtests | 12 bestanden, 0 Fehler |
| Native gemischte Flag-Sicherung | 144 Kombinationen auf drei Builds bestanden |
| `node --test --test-concurrency=2 "test/*.test.mjs"` | 1086 Tests: 943 bestanden, 0 Fehler, 143 vorgesehene Auslassungen |
| `npm run test:e2e` | 163 Tests: 162 bestanden, 0 Fehler, 1 vorgesehene Auslassung |
| Vollständiger Hacktribe-Satz | 432 von 432 bestanden, 104 von 104 Aufgaben |
| Vollständiger Korg-rot-Satz | 457 von 457 bestanden, 111 von 111 Aufgaben |
| Vollständiger Synth-Satz | 338 von 338 bestanden, 76 von 76 Aufgaben |
| Vollständige dreifache Ausgangsprofile | 18 Starts, 126 Szenenfenster; alle Wiederholungen exakt gleich |
| Selbstvergleich des festgehaltenen Ausgangsstands | bestanden; Hashes und vollständige Profile erneut geprüft |

Der erste gleichzeitig gestartete Unit-/Browserlauf enthielt Zeitüberschreitungen.
Ein späterer Gesamtlauf parallel zu den Profilen erreichte das unveränderte 300-s-Limit der
nativen Assemblersuite. Der Aufruf `npm test -- --test-concurrency=2` begrenzte die Parallelität
nicht: Node ignoriert den nach dem Dateimuster angehängten Schalter. Ein eigener Versuch
mit drei selbst erzeugten Testdateien belegt drei gleichzeitige Starts. Vor dem Dateimuster
begrenzt `--test-concurrency=2` dagegen tatsächlich auf zwei. Der abschließende Lauf verwendet
deshalb direkt Node mit denselben vollständigen Testdateien und richtig platziertem Schalter.
Die gezielten Server- und Sample-Wiederholungen bestanden ohne Produktänderung; die anschließenden
vollständigen Läufe nacheinander sind oben ausgewiesen. Kein Timeout wurde verlängert und
kein Test deshalb übersprungen.

Vollständige Logs, Werkzeugeingänge, VSBs und Zwischenläufe bleiben im privaten Messpaket.
Keine reale Electribe wurde angesprochen und keine Firmware installiert. Die vollständige
Ausgangslage ist geprüft und reproduzierbar. Die eigentlichen Optimierungen, die gemeinsame
Codeprüfung und die späteren Gerätetests bleiben Gegenstand der folgenden Schritte.
