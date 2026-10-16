# Speicherbereiche und Schutzgrenzen

Stand: 15. Oktober 2026. Electribe 2 Sampler, Firmware 2.02 mit dem untersuchten
Hacktribe-Build. Adressen sind versionsgebunden. Dies ist eine Karte der
bekannten Bereiche, keine vollständige Zuordnung jedes Speicherbytes.

**Gemessen am Gerät** bedeutet gelesen, zurückgelesen oder dort beobachtet.
**Gemessen offline** bedeutet Bytevergleich, Disassemblierung oder Ausführung
originaler ARM-Routinen im Emulator. **Vermutet/offen** bezeichnet eine noch
nicht bestätigte Zuordnung. **Schutzvorschlag** ist keine Gerätebeobachtung
und keine bereits implementierte Freigabe.

Alle Intervalle unten sind halb offen: Start einschließlich, Ende ausschließlich.
Die Dokumentation enthält Ergebnisse, keine Firmware-, Pattern- oder Audiodaten.

## Drei getrennte Adressräume

| Raum | Adressierung | Beleg und Grenze |
|---|---|---|
| CPU-RAM | z. B. `0xC0000000` | **Gemessen am Gerät:** Fenster `[0xC0000000, 0xC8000000)` vollständig lesbar; keine Bestätigung von 128 MiB physischem RAM. [RAM-Messung](messungen/2026-10-07-cpu-ram-fenster.md) |
| Flash | Offsets ab `0x000000`, Befehl `0x55` | **Gemessen am Gerät:** Dumps decken `[0, 0x1000000)` ab, zu verschiedenen Zeitpunkten. Eine Anfrage ab `0x1000000` ließ das Gerät hängen. Kein Beleg für die physische Flashgröße. [Flash-Messung](messungen/2026-10-07-werks-sample-flash.md) |
| Logischer DSP-Audiospeicher | Byteoffset aus Metadaten | **Gemessen offline:** ARM-Routinen geben den Offset über Ports an den DSP. Kein direkt mit `read_cpu_ram` lesbarer CPU-Zeiger. [DSP-Pfad](messungen/2026-10-08-dsp-audiopfade.md) |

**Gemessen am Dateiformat:** Für das hier verwendete VSB-Abbild gilt
`Dateioffset = CPU-Adresse - 0xC0000000 + 0x100`. Das gilt für dessen
2-MiB-Nutzlast, nicht für beliebige RAM-Adressen, Flash-Dumps oder DSP-Offsets.

**Gemessen offline:** `0x60000000` ist im untersuchten DSP-Pfad der Datenport,
`0x60000002` der Status-/Steuerport. **Schutzvorschlag:** Keine generischen
RAM-/Flash-Lese- oder Schreibzugriffe auf diese MMIO-Adressen; sie gehören
zu einem Protokoll mit Sperren und Handshakes.

## CPU-RAM: bekannte Bereiche

| Bereich / Struktur | Status und Bedeutung | Schutzgrenze |
|---|---|---|
| VSB-Zuordnung `[0xC0000000, 0xC0200000)` | **Gemessen am Abbild:** 2 MiB gemischter Programmcode und statischer Daten hinter 0x100 Byte Dateikopf | Keine pauschale Schreibfreigabe für das Abbild |
| `FF`-Block im Abbild `[0xC01A2100, 0xC01FFFF0)` | **Gemessen am Gerät:** im RAM-Dump vollständig `0xFF`, 375 KiB am Stück ([Plugin-Laufzeit](hintergrund/skript-laufzeit.md)). Der Code des MFX-2-Patches ab `0xC01A5000` läuft dort am Gerät ([MFX 2 am Gerät](messungen/2026-10-13-mfx-umschalter-geraet.md)) | Keine Freigabe für Schreibzugriffe des Editors (`allowedRegions()`); Patches des Patchers legen dort ihren Code ab ([Patcher](patcher.md)) |
| Analysefenster `[0xC0000000, 0xC00A3290)` | **Gemessen offline:** Kernel-/ARM-Routinen untersucht, darunter Dateiverarbeitung und DSP-Zugriff; keine lückenlose Trennung von Code, Literalen und Daten | Code/Literale grundsätzlich schützen; Grenze ist eine Analysegrenze, keine bewiesene letzte Codeadresse |
| `[0xC0170540, 0xC0171FEC)` | **Gemessen offline:** untersuchter SysEx-Hook-/eingebetteter Loaderbereich mit Cache-/Startcode | Keine normalen Tabellenedits; keine Freigabe für Execute oder Bootloader |
| IFX `[0xC00A80F0, 0xC00B4DA0)` | **Gemessen am Gerät:** 100 Records à 0x20C Byte | Bestehender FX-Plan plus Inhaltsprüfungen; unbekannte Recordbytes nicht neu erzeugen |
| MFX `[0xC00B4F30, 0xC00C1BE0)` | **Gemessen am Gerät:** 100 Records à 0x20C Byte | Wie IFX; Indexgrenzen und Recordart prüfen |
| Modulationen ab `0xC00D81EC` | **Gemessen am Abbild:** 72 Records à 0x58 Byte, aus Dateioffset 0xD82EC | Live-Schreibwirkung ungeprüft; daraus keine Freigabe ableiten |
| Name `0xC047B080 + i * 0x20` | **Gemessen am Gerät:** Name bei +12, Länge 16; Kategorie +28, Importnummer +30 | Begrenzter Namenstest belegt; keine pauschale Freigabe des ganzen Records oder aller Indizes. Der Editor schreibt nur das Namensfeld (+12, 16 Byte) der Indizes 0 bis 997, alles andere sperrt der Türsteher (Seite Samples) |
| Playback `0xC0362EE8 + i * 0x10` | **Gemessen am Gerät/offline:** Start/Loop/Ende und One-Shot zugeordnet | Zeiger/Längen gemeinsam konsistent halten; keine direkte Editor-Freigabe |
| Metadaten `0xC036AD88 + i * 0x45C` | **Gemessen am Gerät/offline:** Offset, PCM-Länge, Rate, Tune, Slice-Daten zugeordnet | Einzelner Tune-Test belegt; nicht alle Felder damit schreibgeprüft. Der Editor schreibt nur das Tune-Byte (+21) der Indizes 0 bis 997. Index 998 ist ausgelassen: bei 0x45C Byte je Eintrag ragt sein Eintrag 12 Byte in die Namenstabelle (hergeleitet aus den Adressen, die Tabellengröße ist nicht gemessen) |
| Allocatorzustand bei `0xC00F9C80` | **Gemessen offline:** aktueller logischer DSP-Allokationszeiger | Kein roher Parameter; nur geprüfte Reservierungs-/Rollback-Operation |
| Arbeitsplatz `[0xC0D3A940, 0xC273AA40)` | **Gemessen offline:** Puffergeber meldet 27.263.232 Byte; Import/Export nutzen u. a. 65.536-Byte-Blöcke; ganze Lebensdauer offen | Shared Buffer, kein freier Speicher und kein dauerhaftes Audioarchiv |
| Hook-Upload `0xC1000000`, Flash-Lese-Arbeitsbereich `0xC2000000` | **Gemessen offline:** bestehender Hook benutzt diese Adressen | Beide Adressen liegen im gemeldeten Shared Buffer; zeitliche Nutzung ungeklärt. Ab `0xC1000000` ist das erste KiB für Stubs über das Terminal freigegeben (`data/exec.mjs`, am Gerät mit `led_show.py` und `backlight.py` gemessen), immer mit Zurückschreiben der Originalbytes und nur nach einer Probe im Emulator; sonst keine Freigabe für eigene Codeausführung |
| `[0xC0200000, 0xC03167A8)` | **Gemessen offline:** zehn konfigurierte Task-Stacks, originaler Initialisierer emuliert; gespeicherte Zeiger passen | Vollständig gegen beliebige Writes sperren, auch scheinbar ungenutzte Stackbytes |
| `[0xC06A24E4, 0xC06A2624)` | **Gemessen offline:** zehn Task-Kontrollblöcke, Deskriptor- und Stackzeiger | Kernelzustand; kein Parameterbereich |
| `[0xC06A2940, 0xC08A2940)` | **Gemessen offline:** 2-MiB-Heap für untersuchten New-/Delete-Pfad | Pool plus außerhalb liegende Verwaltung sperren; frei heißt nicht fremd nutzbar |
| `[0xC0200000, 0xC08A2940)` | **Gemessen offline:** vollständiger Boot-Löschbereich, Taskfüllungen und Systemdaten | Als Systembereich sperren; gezielte Feld-Ausnahmen separat prüfen |
| `[0xC08A2940, 0xC08B2940)` | **Gemessen offline:** Globals-Basis mit GLST und 64-KiB-Initialisierungsbereich | Nutzerdaten mit geprüftem Feld-/Transportweg |
| `[0xC08B2940, 0xC0C9A940)` | **Gemessen offline:** 250 Patternslots à 0x4000; alle Resolver-Aufrufe und PTST/PTED-Kennungen geprüft | Records nur 0x3C00 Byte; keine pauschale Freigabe ganzer Slots |
| `[0xC0C9A940, 0xC0D3A940)` | **Gemessen offline:** 640-KiB-SIST/SIED-Cache, Sicherung/Wiederherstellung sechs Sample-Info-Tabellen bytegenau geprüft | Cache ist kein PCM und kein freier Uploadspeicher; spätere Rückkopie beachten |
| `[0xC273AA40, 0xC274AA40)` | **Schutzvorschlag:** 64 KiB vor gemessenem Reset-SP 0xC274AA40 reservieren | Startstack wächst hier hinein; maximale Tiefe nicht aus SP allein ableitbar |
| `[0xC274AA40, 0xC274EA3C)` | **Gemessen offline:** Interrupt-/Idle-Stack, Füllbereich und äußere/verschachtelte IRQ-Umschaltung geprüft | Gegen beliebige Writes sperren |
| `[0xFFFF0000, 0xFFFF125C)` | **Gemessen offline:** Loader-Kopie, Dateninitialisierung und sechs CPU-Modus-Stackzeiger | Loadercode, Daten und Stacks sperren; kein Scratchbereich |
| Übriges RAM / mögliche Aliase | **Vermutet/offen:** Tasks, Stacks, Heap, weitere Puffer und Spiegelungen nicht vollständig zugeordnet | Unbekannt bleibt für Schreiben gesperrt |

Belege: [FX](messungen/2026-09-14-fx-ram-write.md),
[Modulation](messungen/2026-09-14-modulation-table.md),
[Namen](messungen/2026-10-07-sample-name-ram.md),
[Metadaten/Tune](messungen/2026-10-07-sample-metadaten-ram.md),
[DSP/Export](messungen/2026-10-08-dsp-audiopfade.md),
[Import](messungen/2026-10-08-usb-sample-import-offline.md),
[Stacks/Heap/Puffer](messungen/2026-10-08-systemspeicher-offline.md),
[Boot/IRQ/Loader/Patterns](messungen/2026-10-08-boot-pattern-speicher.md).
`i` ist nullbasiert. Das 1.020-Slot-Dateiformat beweist nicht automatisch die
Lebensdauer oder sichere Schreibbarkeit sämtlicher RAM-Einträge.

### Zusammenhängende Belegung bis zum Interrupt-Stack

Die folgenden Intervalle schließen ohne Lücke aneinander an. **Gemessen
Offline/am Abbild:** Grenzen von Abbild, Boot-Löschbereich, Globals,
Patternbank, Sample-Info-Cache, Dateipuffer und IRQ-Füllbereich.
**Schutzvorschlag:** Die 64 KiB vor dem Reset-SP als Startstack reservieren.
Diese Übersicht ordnet die großen Bereiche zu; sie ist keine Freigabe der
jeweiligen ungenutzten Bytes oder Paddingbereiche.

| Start | Ende exklusiv | Zuordnung |
|---|---|---|
| `0xC0000000` | `0xC0200000` | Firmware-Abbild: Code und statische Daten |
| `0xC0200000` | `0xC08A2940` | Boot-Löschbereich: Task-Stacks, Systemdaten, Heap |
| `0xC08A2940` | `0xC08B2940` | Globals-Initialisierungsbereich |
| `0xC08B2940` | `0xC0C9A940` | 250 Patternslots |
| `0xC0C9A940` | `0xC0D3A940` | Sample-Info-Cache |
| `0xC0D3A940` | `0xC273AA40` | Gemeldeter Datei-/Sample-Arbeitspuffer |
| `0xC273AA40` | `0xC274AA40` | Konservativ reservierter Startstackbereich |
| `0xC274AA40` | `0xC274EA3C` | Interrupt-/Idle-Stack |

### Parameter mitten im Code

**Gemessen offline:** Bei `0xC003EFE4` steht `mov r0, #50`, danach die
Rückkehr. Die dokumentierte MFX-Menülänge ist das Immediate-Byte einer
ARM-Instruktion. Eine Sperre für sämtlichen Code würde auch diese derzeit
gezielt erlaubte Änderung sperren. Die IFX-Zähler haben mehrere gekoppelte
Patchstellen; [die Messung](messungen/2026-09-14-fx-ram-write.md) listet sie.

**Schutzvorschlag:** Code ist gesperrt. Ausnahmen benötigen einen exakten
Firmwarebezug, das erwartete ursprüngliche Instruktionswort, eine erlaubte
Byte-/Bitmaske und enge Wertebereiche. Nur diese Bytes dürfen verändert
werden; alle gekoppelten Stellen müssen gemeinsam gesichert und geprüft
werden.

**Gemessen im Repository:** Für die MFX-Menülänge ist die Instruktionsprüfung
gebaut. Die Gerätekarte (`data/map/firmware.mjs`, `instruction`) nennt das
erwartete Wort `0xE3A000nn` und die Maske, `src/plan.mjs` liest das ganze Wort
vor dem Schreiben, `src/guards.mjs` vergleicht es, danach wird es ganz
zurückgelesen. Für die gekoppelten IFX-Stellen prüft der Plan nur das
Zurücklesen der einzelnen Bytes; ein gemeinsamer Wortvergleich über alle Stellen
ist Vorschlag.

## Flash: bekannte Karte und dauerhafte Wirkung

| Offset / Bereich | Erkenntnis | Schutzvorschlag |
|---|---|---|
| `[0x000000, 0x005E74)` | **Gemessen offline:** TIPA/AIS-Startimage, drei Section Loads und abschließender Jump geparst | Start-/Firmwaredaten sperren |
| `[0x020000, 0x220000)` | **Gemessen offline:** vollständiges 2-MiB-VSB-Nutzabbild zugeordnet; Unterschiede zur bearbeiteten Referenz ausschließlich FX/Menüs | Firmware-Umschlag einschließlich Padding konservativ `[0x000000, 0x220000)` sperren |
| alte Markierung `0x1D0000` | **Gemessen offline:** liegt innerhalb des zugeordneten 2-MiB-Firmwareabbilds | Durch Schutz-Umschlag bis 0x220000 ersetzen; keine Freigabe darüber ableiten |
| `0x220000` / `0x230000` | **Gemessen am alten Dump:** Nutzerdatenkennung / Nutzer-Globals | Kein direkter Flash-Schreibweg freigegeben |
| `[0x240000, 0x628000)` | **Gemessen am alten Dump:** Nutzer-Patternbank, 250 × 0x4000 Byte | Wiederherstellbare Daten, aber keine Erlaubnis für beliebige Flash-Schreibbefehle |
| `0x630000` | **Gemessen am alten Dump:** Werks-Globals | Gegen Schreiben sperren |
| `[0x640000, 0x660017)` | **Gemessen offline:** SQEZ/LH5-Werks-Patternbank, 0x20017 Byte | Gegen Schreiben sperren |
| `[0x660017, 0x6B0000)`, `[0x7C0002, 0x7DFFFE)`, `[0xE5F013, 0x1000000)` | **Gemessen am Dump (2026-10-09):** nur `FF`, in allen verglichenen Ständen gleich. Dass die Firmware sie nie beschreibt, ist nicht gemessen ([Flash-Dump](messungen/2026-10-09-flash-dump.md)) | Nicht als freier Speicher behandeln; keine Freigabe |
| alte PCM-Markierung `0x6B0000` | **Vermutet/offen:** als PCM-Start nicht belegt | Nicht als Audio-Freigabe verwenden |
| `0x800000` | **Gemessen:** KORGelec2PCM-Werksbank, Tabellen und dekodiertes Audio | Gegen Schreiben sperren; kein sicherer Werksbank-Schreibweg nachgewiesen |
| `[0x807500, 0xE5F013)` | **Gemessen offline:** vollständiger SMPL-Blockstrom dieses Dumps | Bekannte Kodierung bedeutet keine sichere Schreibbarkeit |
| ab `0x1000000` | **Gemessen am Gerät:** erste fehlende Flash-Antwort / Hänger | Nicht erneut abtasten; bei erster fehlender Antwort stoppen |

**Gemessen im Editor-Code:** Die alte Konstante `src/layout.mjs:FLASH.pcm`
trägt weiterhin `0x6B0000`. Dieser Wert ist keine aktuelle PCM-Zuordnung.
Diese Doku korrigiert die Wissenslage, ändert aber keine Konstanten oder
Geräteoperationen. Auch `FLASH.codeEnd` ist keine vollständige
Schutzkarte. [Belege und Prüfsummen](messungen/2026-10-07-werks-sample-flash.md).

## Was der Editor bereits prüft

**Gemessen im Repository:** `data/map/` ist die maßgebliche Gerätekarte.
`src/plan.mjs:allowedRegions()` gibt vermessene RAM-Tabellen und ausgewählte
Menüzähler frei. `src/gate.mjs:regionCheck()` verlangt, dass jeder einzelne
Schreibheader vollständig in einen freigegebenen Bereich passt und keinen
Eintrag der [Sperrliste](#die-sperrliste-als-maschinenregel) berührt.
`src/gate.mjs:executeCheck()` erlaubt Ausführen nur im Stub-Puffer und für die
Leerung des Befehls-Caches, und einen Stub nur, wenn er vorher zurückgelesen
wurde. Der Linter prüft zusätzlich bekannte Absturz-/Stummfälle und
Record-Strukturen.

**Gemessen im Repo:** `SimDevice` prüft Kanal, Nachrichten, Abbildgrenzen,
Schreibablauf und Antworten. Es führt keinen ARM- oder DSP-Code aus; Execute
ist dort ein Fehler, es sei denn, ein Test gibt eine Ersatzfunktion mit
(`src/device.mjs`). Es kann daher weder Task-Rennen noch Cachefehler oder
unbekannte Audiofehler vorhersagen. Ein ACK oder erfolgreiche Simulation
beweist keine semantische Sicherheit jedes Feldwerts.

**Schutzvorschlag:** Bestehende Freigaben nicht aus einer bloßen Lesemessung
erweitern. Ergänzungen gehören als Feldwissen in `data/map/` und als
Verhaltensbefunde in `data/findings.mjs`, mit Prüfungen im vorhandenen Gate.
Diese Doku erzeugt keine zweite maschinenlesbare Gerätekarte.

## Bekanntes in der RAM-Suche ausblenden

**Gemessen im Repository:** Die Suche im Terminal (`KORG.ram.snapshot`, `diff`, `search`,
[Idee 36](ideen/36-terminal.md#ram-erforschen-idee-11)) blendet aus, was diese Karte erklärt. Dafür
liest sie keine zweite Karte, sondern drei Stellen: die Gerätekarte bis zum einzelnen Feld, die
Sperrliste und `data/known-ram.mjs`, wo jeder RAM-Eintrag der Sperrliste eingeordnet ist (erklärt oder
nur als Bereich bekannt) und die Bereiche stehen, die Karte und Sperrliste nicht tragen. Ein Test
schlägt fehl, wenn ein neuer RAM-Eintrag der Sperrliste dort fehlt. Erklärt heißt: der Inhalt ist
verstanden (Code, Stacks, Felder). Heap, Arbeitspuffer, Sample-Info-Cache und die Systemdaten
zwischen den Stacks bleiben sichtbar.

## Die Sperrliste als Maschinenregel

**Gemessen im Repository:** Die Bereiche, die der Editor nie beschreibt, stehen in
`data/protected.mjs`, jeder mit Intervall, Beleg und Status (`measured` oder
`proposal`, also Schutzvorschlag). `src/protect.mjs` wendet die Liste auf jeden
einzelnen Zugriff an. Zwei Stellen lesen sie, damit kein Weg daran vorbeiführt:
`regionCheck()` im Gate prüft vor der Simulation, und der Sender prüft als
letzte Stelle vor dem Senden. Das Terminal erreicht das Gerät über beide, ein
Skript bekommt also dieselbe Antwort wie der Effekt-Editor
(`test/protect.test.mjs`).

Die Liste liegt über der Freigabeliste (`allowedRegions()`), sie ersetzt sie
nicht: Ein Schreibzugriff muss in einen erklärten Bereich passen und darf keinen
Eintrag der Sperrliste berühren. Ausnahmen sind namentlich festgelegt (`except`)
und ein Test hält, dass jeder erklärte Bereich, der in einem geschützten liegt,
dort als Ausnahme steht und nirgends sonst. Schreiben ist überall gesperrt, wo
unten ein Eintrag steht. Lesen ist nur dort gesperrt, wo schon der Zugriff
selbst ein Risiko ist: die DSP-Ports, der Loader, alles hinter dem Flash und
alles außerhalb des vermessenen RAM-Fensters. Code, Stacks und Heap lassen sich
weiter lesen, Sicherung und Prüfung brauchen das.

| Id | Raum | Intervall | Ausnahme | Status |
|---|---|---|---|---|
| `firmware-image` | RAM | `[0xC0000000, 0xC0200000)` | FX-Tabellen, Menüzähler | gemessen |
| `sysex-hook` | RAM | `[0xC0170540, 0xC0171FEC)` | keine | gemessen |
| `task-stacks` | RAM | `[0xC0200000, 0xC03167A8)` | keine | gemessen |
| `task-control-blocks` | RAM | `[0xC06A24E4, 0xC06A2624)` | keine | gemessen |
| `heap` | RAM | `[0xC06A2940, 0xC08A2940)` | keine | gemessen |
| `boot-clear` | RAM | `[0xC0200000, 0xC08A2940)` | Display-Puffer | gemessen |
| `sample-info-cache` | RAM | `[0xC0C9A940, 0xC0D3A940)` | keine | gemessen |
| `work-buffer` | RAM | `[0xC0D3A940, 0xC273AA40)` | Stub-Puffer (erstes KiB) | gemessen |
| `start-stack` | RAM | `[0xC273AA40, 0xC274AA40)` | keine | Schutzvorschlag |
| `irq-stack` | RAM | `[0xC274AA40, 0xC274EA3C)` | keine | gemessen |
| `loader` | RAM, auch Lesen | `[0xFFFF0000, 0xFFFF125C)` | keine | gemessen |
| `dsp-ports` | RAM, auch Lesen | `[0x60000000, 0x60000004)` | keine | Schutzvorschlag |
| `flash-bootloader` | Flash | `[0x000000, 0x020000)` | keine | gemessen |
| `flash-firmware` | Flash | `[0x020000, 0x220000)` | keine | gemessen |
| `flash-user-data` | Flash | `[0x220000, 0x640000)` | keine | gemessen |
| `flash-factory-patterns` | Flash | `[0x640000, 0x660017)` | keine | gemessen |
| `flash-unassigned` | Flash | `[0x660017, 0x800000)` | keine | gemessen |
| `flash-factory-samples` | Flash | `[0x800000, 0xE5F013)` | keine | gemessen |
| `flash-tail` | Flash | `[0xE5F013, 0x1000000)` | keine | gemessen |
| `flash-beyond` | Flash, auch Lesen | ab `0x1000000` | keine | gemessen |

Die Flash-Einträge zerlegen `[0, 0x1000000)` ohne Lücke, ein Flash-Schreibweg ist
nirgends freigegeben. Der Editor kennt auch keinen Befehl, der Flash beschreibt;
ein Befehl, den er nicht kennt, wird als möglicher Flash-Schreibzugriff
gesperrt (`unknown-command`). Der Bootloader liegt nach dem
[Hintergrund zur virtuellen Karte](hintergrund/virtuelle-sd.md) in `[0, 0x20000)`
(offline gelesen); sein Eintrag ist die Grenze, hinter der nur noch JTAG hilft ([Rettung](rettung.md)).

**Außerhalb des Fensters:** Nichts außerhalb von `[0xC0000000, 0xC8000000)` ist
vermessen. Zugriffe dort sind gesperrt (`outside-window`), auch Lesen.

**Vermutete Spiegelung:** Die obere Hälfte des Fensters gleicht der unteren fast
Byte für Byte (4074 von 4096 Blockpaaren, [RAM-Messung](messungen/2026-10-07-cpu-ram-fenster.md)).
Bewiesen ist keine Spiegelung, darum wird ein Zugriff gegen die geschützten
Bereiche beider Hälften geprüft. Die Meldung sagt dann, dass die Adresse im
vermuteten Spiegel liegt.

**Die Meldung** nennt den Bereich, sein Intervall und was dort beobachtet wurde,
und bei einem Schutzvorschlag, dass er am Gerät nicht beobachtet wurde. Eine neue
Sperre gehört in `data/protected.mjs` mit Beleg, und eine Freigabe, die in einen
geschützten Bereich fällt, braucht dort ihre Ausnahme.

## Bedingungen für neue Schreibfreigaben

**Schutzvorschlag:** Vor einer Freigabe müssen Geräte-/Firmwarebezug, Besitzer,
Feldgrenzen, erlaubte Werte und Abhängigkeiten bekannt sein. CPU, Flash und
DSP müssen getrennt bleiben; Spiegeladressen dürfen keine Sperre umgehen.
Die Operation braucht Originaldaten-Sicherung, exakte Antwortprüfung und
Zurücklesen. Bei mehrteiligen Änderungen ist Rücksetzung für Teilfehler nötig.

**Schutzvorschlag:** Generische Pointer-, Längen-, Heap-, Stack-, MMIO- und
Execute-Zugriffe bleiben gesperrt. Eine Zustandsänderung im RAM ist flüchtig,
kann aber laufenden Code beschädigen oder einen Absturz auslösen. Dauerhafte
Schäden werden nicht dadurch ausgeschlossen, dass nur ein bekannter Code-
Bereich geschützt ist: Auch ein aufgerufener Speicher-/Flash-Treiber kann
persistente Daten verändern.

**Vermutet/offen:** Ein künftiges `electribe.ram.MFX_Presets[0].parameter.level`
kann auf der Gerätekarte und dem bestehenden Plan/Gate aufbauen (Idee 8 in
[ideen.md](ideen.md)). Explizites
Anwenden beziehungsweise eine Transaktion ermöglicht gemeinsame Validierung,
Sicherung und Rücksetzung. `flash` sollte keine live ins RAM schreibende API
bezeichnen. Diese Objekt-API und die zusätzlichen Schutzregeln sind Vorschläge.

## Offen

- **Vermutet/offen:** exakte Grenzen aller ARM-/DSP-Programme, zusätzlicher
  Stack-Hochwasserstände, weiterer dynamischer Puffer/Allocatoren und physischer
  Speicher. Boot-Löschbereich, zehn Task-Stacks, IRQ-/Idle-Stack, sechs
  Loader-Modus-Stackzeiger und der untersuchte 2-MiB-Heap sind zugeordnet;
- **Vermutet/offen:** echte DSP-Antworten und der passende Task-Kontext für
  ausgeführten RAM-Code;
- **Teils gemessen:** kleine Stubs (LEDs, Hintergrundlicht) laufen am Gerät über
  Execute im Stub-Puffer; warum sie trotz Daten-Cache laufen, ist nicht geklärt
  ([LEDs selbst setzen](messungen/2026-10-08-led-execute.md), Hintergrundlicht in
  [Startphase](messungen/2026-10-10-startphase.md)). Sichere Ausführung
  eines beliebigen hochgeladenen RAM-Helfers bleibt offen;
- **Vermutet/offen:** USB-Sampleimport ohne SD auf dem echten Gerät,
  vollständiger Fehler-Rollback und Persistenz;
- **Vermutet/offen:** Lesen der SD-Dateien über USB mit vorhandenen
  Dateiroutinen; noch kein geprüfter Host-Dateizugriff;
- **Vermutet/offen:** RAM nach Leeren/Neuladen: freigegebene Samplebytes
  können liegen bleiben. Ein Differenzdump allein beweist keine Schreibbarkeit.

Diese Grenzen bleiben offen, bis neue Messungen sie klären.
