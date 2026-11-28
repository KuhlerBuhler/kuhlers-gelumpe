# Glossar

Deutsche Version | [English version](glossary.en.md)

Begriffe, die in diesen Docs vorkommen, auch die Namen aus diesem Repo. Jede Seite verlinkt einen Begriff bei der ersten Verwendung. Die Einträge sind alphabetisch sortiert. Die englische Fassung ist [glossary.en.md](glossary.en.md), die Anker (`#hacktribe` und so weiter) sind in beiden Sprachen gleich.

<a id="app"></a>

## App

In den Plugin-Docs ist eine App ein Plugin, das sich mit `korg.app(name, group)` anmeldet und einen eigenen Bildschirm hat. Man öffnet sie im BLECH-Menü unter GAMES oder TOOLS, sie besitzt das Display, solange sie offen ist, und EXIT schließt sie immer.

Siehe: [plugins.md](plugins.md) ("Apps und das Display"), `data/script/contract.mjs` (SCRIPT_APPS)

<a id="arm"></a>

## ARM

Der Hauptprozessor des Electribe (TI AM180x). Er betreibt die Verbindung zum Panel-Controller, Display, Sequencer, Menüs, MIDI, SD-Karte und Flash und schickt zur Laufzeit Befehle und Werte an den DSP.

Siehe: [patcher.md](patcher.md) ("Was in der VSB steckt")

<a id="baukasten"></a>

## Baukasten

Der Bereich im Editor (`BLECHTRIBE -> Baukasten`), in dem Effekte und Modulationen aus DSP-Bausteinen mit echten Einheiten gebaut, auf die Karte exportiert oder live per USB geschickt werden. Hier liegt auch der Effekt-Katalog.

Siehe: [effekt-katalog.md](effekt-katalog.md), `README.md`

<a id="blech"></a>

## BLECH

Name des Patch-Satzes dieses Projekts (Produktname BLECHTRIBE): die Änderungen, die in die Firmware des Electribe 2 eingebaut werden, etwa Menü, Plugin-Laufzeit, Sample-Lader und Pattern-Wechsel. Er läuft direkt auf Korgs Original 2.02 und optional auch auf einer Hacktribe-Datei. Er ist keine Hacktribe-Variante.

Siehe: [patcher.md](patcher.md) (Patch-Satz BLECH), `README.md`

<a id="blechtribe"></a>

## BLECHTRIBE

Die Firmware-Mod dieses Projekts für den Electribe 2. Sie wird als Patch-Satz auf eine VSB angewendet, hat eigene SysEx-Befehle 0x60 bis 0x67 und 0x6F und ein BLECH-Menü am Gerät.

Siehe: `src/protocol.mjs` (BLECH-Befehlstabelle), [emulator.md](emulator.md)

<a id="blechtribe-sysex"></a>

## BLECHTRIBE SysEx

Die zusätzlichen SysEx-Befehle, die der Patch `blech-sysex` einbaut: RAM blockweise lesen und schreiben, Flash lesen, Dateien auf der Karte lesen und schreiben. Sie ersetzen Hacktribes Befehle `0x52` bis `0x57`, die nur mit gehaltenem EXIT beim Einschalten antworten. Auf der blauen Electribe schreiben sie im RAM nur die Effekt-Presets.

Siehe: [patcher.md](patcher.md) (Patch-Tabelle), `data/patches/blech-sysex.json`

<a id="blechy"></a>

## Blechy

Das Maskottchen von BLECHTRIBE. Als App in der Firmware ist es die letzte Seite des EDIT-Rings und winkt beim Ausschalten. Als Seite im Editor (`#rescue`) ist es der Assistent, der durch den Rückweg führt, wenn ein Gerät nicht richtig startet.

Siehe: [patcher.md](patcher.md) (Patches `power-off`, `load-bar`), [rettung.md](rettung.md)

<a id="bootloader"></a>

## Bootloader

Das Startprogramm im Flash `[0, 0x20000)`. Es lädt die Firmware. Der Patcher und der Editor fassen es nie an.

Siehe: [rettung.md](rettung.md) ("Stoppschild"), [patcher.md](patcher.md)

<a id="bsdiff"></a>

## bsdiff

Binäres Diff-Format (`BSDIFF40`). Der Release enthält `BLECH-for-<hash>.bsdiff`-Dateien, die genau eine bekannte SYSTEM.VSB in die BLECHTRIBE-Version ohne die BLECHTRIBE-App verwandeln. Der Diff-Block besteht dort nur aus Nullen, in der Datei stecken also keine Firmware-Bytes.

Siehe: [patcher.md](patcher.md) ("Patch-Datei und bsdiff"), `tools/patch/bsdiff.mjs`

<a id="build"></a>

## Build

Die Firmware-Ausgabe, für die ein Patch gemacht ist: `hacktribe` (Hacktribe 2.02), `stock` (Korgs rote 2.02) und `synth` (Korgs blaue 2.02). Ein Patch führt sie in `builds` auf, die Basis-Firmware wählt die Variante.

Siehe: [patcher.md](patcher.md) ("Welche Patches passen"), `src/patch.mjs` (`buildsOf`, `selectFor`)

<a id="bytecode"></a>

## Bytecode

Der kompakte Block, in den der Editor ein Plugin übersetzt: Blockformat 2 mit 52 Byte Header, vorzeichenbehafteten 32-Bit-Werten und einer Prüfsumme. Das Gerät lädt diesen Block, nie den Quelltext.

Siehe: `data/script/contract.mjs` (FORMAT_VERSION, HEADER)

<a id="data-utility"></a>

## DATA UTILITY

Die Menüseite des Geräts für Karten- und Sample-Funktionen (IMPORT SAMPLE, EXPORT SAMPLE, EXPORT ALL PATTERN, CARD FORMAT).

Siehe: [emulator.md](emulator.md) (Abschnitt "Virtuelle SD-Karte")

<a id="dev-mode"></a>

## DEV MODE

Seite im BLECH-Menü, mit der BLECH WRITE in das Firmware-Abbild im RAM schreiben darf (außer in gesperrte Bereiche). Nach jedem Einschalten ist sie AUS, sie wird nicht gespeichert und es gibt sie auf dem blauen Electribe nicht.

Siehe: [patcher.md](patcher.md) (Patch `blech-sysex`), `data/dev-closed.mjs`

<a id="doom-loader"></a>

## Doom-Lader

Der Patch `doom-loader`: Bei SHIFT + TAP beim Einschalten liest er `KORG/blechtribe/Doom/doom.bin` von der Karte, prüft Länge und SHA-256 und springt hinein.

Siehe: `tools/patch/doom_loader.py`

<a id="dsp"></a>

## DSP

Der zweite Prozessor (ein Analog Devices Blackfin, genaues Modell offen). Er rechnet den Klang: Samples, Filter, Insert-Effekte, Master-Effekt. Sein Programm steckt in der VSB und wird beim Start vom ARM geladen.

Siehe: [patcher.md](patcher.md) ("Was in der VSB steckt"), [hintergrund/dsp-erster-blick.md](hintergrund/dsp-erster-blick.md)

<a id="e2sallpat"></a>

## e2sallpat

Die Sicherungsdatei aller 250 Patterns (Endung .e2sallpat). Das Gerät erzeugt sie mit EXPORT ALL PATTERN, importieren geht mit IMPORT ALL PATTERN.

Siehe: [emulator.md](emulator.md), `src/map/address.mjs` (PATTERN_FILE)

<a id="e2ssampleall"></a>

## e2sSample.all

Die Sample-Sammeldatei auf der SD-Karte (`Sample/e2sSample.all` im Kartenordner). Die Firmware lädt sie beim Start, die Lader-Patches (`sample-errors`, `sample-swap`, `user-samples`) arbeiten an ihr.

Siehe: [patcher.md](patcher.md) (Patch-Tabelle), [hintergrund/sample-datei.md](hintergrund/sample-datei.md)

<a id="eingangsfilter"></a>

## Eingangsfilter

Der Code, den BLECH vor die Panel-Nachrichten (Touch, Tasten) setzt, damit Plugins oder Patches ändern können, was die Firmware sieht, zum Beispiel das gesperrte Touch-X und -Y.

Siehe: [messungen/2026-11-12-plugin-touch-lock-y.md](messungen/2026-11-12-plugin-touch-lock-y.md), `tools/patch/script_hw.s` (touch_lock_input)

<a id="emulator"></a>

## Emulator

Der ARM-Emulator in `tools/emu/`, der eine Kopie der Firmware ausführt, damit der Patcher sie vor dem Export prüfen kann. Er spielt keinen Ton und bildet den DSP nur an seiner Schnittstelle nach.

Siehe: [patcher.md](patcher.md) ("Prüfungen vor dem Export"), [emulator.md](emulator.md)

<a id="evidence-markers"></a>

## Evidenz-Marker

Kennzeichen an Fakten in den Docs, die sagen, wie eine Aussage belegt ist: **gemessen** (am Gerät oder im Emulator gemessen), **offline** (Code oder ein Dump gelesen, nichts ausgeführt), **hergeleitet** (aus anderen Fakten abgeleitet) und **offen** (noch nicht geprüft).

Siehe: [messungen/README.md](messungen/README.md)

<a id="execute"></a>

## Execute

Hacktribes SysEx-Befehl 0x57, der das Gerät an eine angegebene Adresse springen lässt. Damit wird ein kleiner Stub aus dem RAM ausgeführt, zum Beispiel um LEDs zu setzen.

Siehe: `src/protocol.mjs` (EXECUTE), [messungen/2026-10-08-led-execute.md](messungen/2026-10-08-led-execute.md)

<a id="execute-stub"></a>

## Execute-Stub

Ein kleines Stück ARM-Code, das per SysEx (0x53/0x54) ins RAM geladen und einmal mit Hacktribes Befehl 0x57 ausgeführt wird. Es muss mit r0 = 1 enden, damit eine Antwort kommt.

Siehe: [hintergrund/virtuelle-sd.md](hintergrund/virtuelle-sd.md) (Abschnitt 6)

<a id="expertenmodus"></a>

## Expertenmodus

Unbekannte Felder lassen sich hinter einem Schalter als rohe Zahlen bearbeiten. Änderungen gehen zuerst den flüchtigsten Weg (RAM oder Pattern-Puffer) und brauchen eine zweite Bestätigung, um dauerhaft zu werden.

Siehe: [geraetekarte.md](geraetekarte.md) (Abschnitt "Expertenmodus")

<a id="fatfs"></a>

## FatFs

Die FAT-Dateisystem-Bibliothek in der Firmware. Sie hat kein Lock, darum benutzen Patches nur ihre Dateifunktionen (`f_open`, `f_read`, `f_write`, `f_close`) und halten die Schreibregel für die Karte ein.

Siehe: [patcher.md](patcher.md) ("Schreibregel für die Karte")

<a id="fingerabdruck"></a>

## Fingerabdruck

Der sha256 über alle Bytes einer VSB außer den `userData`-Bereichen (FX-Tabellen, Groove- und Modulationstabellen, Startbild, Menülängen). `BLECH.patch` prüft ihn für Ein- und Ausgabe statt der ganzen Datei.

Siehe: [patcher.md](patcher.md) ("Patch-Datei und bsdiff")

<a id="firmware"></a>

## Firmware

Die Software auf der ARM-CPU des Electribe 2 (SYSTEM.VSB 2.02: Korgs Original oder Hacktribe), die BLECH patcht.

Siehe: `AGENTS.md`

<a id="frame-hook"></a>

## Frame-Hook

Der Haken bei 0xC00836FC im UiTask, der alle 40 ms (25 Hz) läuft, nachdem die Firmware ihre Widgets gezeichnet hat. Dort leert Plugin-Code den Eingabe-Ring und zeichnet in den Display-Puffer.

Siehe: [hintergrund/skript-laufzeit.md](hintergrund/skript-laufzeit.md) (Abschnitt 1.3)

<a id="fx-katalog"></a>

## FX-Katalog

Die Menge fertiger Effekte (49 Insert- und Master-Effekte, 6 Modulationen) in `data/fx/catalog.mjs`. Der Patch `fx-catalog` hängt sie an die Presets in der Firmware an.

Siehe: [effekt-katalog.md](effekt-katalog.md), `data/fx/catalog.mjs`

<a id="geraetekarte"></a>

## Gerätekarte

Die Gerätekarte: Jedes bearbeitbare Feld des Electribe ist einmal als Daten beschrieben (id, label, wo, Typ, Transport, Quelle, Beleg). UI, Linter und Docs werden daraus erzeugt.

Siehe: [geraetekarte.md](geraetekarte.md), data/map/

<a id="globals"></a>

## Globals

Der 256 Byte große Block der Geräteeinstellungen hinter GLOBAL PARAMETERS (MIDI-Kanal, Clock-Modus, Kontrast, Batterietyp und mehr). Er liegt im Flash bei 0x230000, beginnt mit `GLST`, endet mit `GLED` und wird beim Ausschalten und bei WRITE gespeichert.

Siehe: `data/map/global.mjs`, [messungen/2026-10-13-globals-zurueckgesetzt.md](messungen/2026-10-13-globals-zurueckgesetzt.md)

<a id="gscr"></a>

## GSCR

Die vier Byte lange Kennung am Anfang eines übersetzten Plugin-Blocks (Format 2, mit eigener Größe und CRC-32). Eine Plugin-Datei `e2sPlugin.all` besteht aus einem Header (`GSAL`) und solchen Blöcken.

Siehe: `data/script/contract.mjs`

<a id="hacktribe"></a>

## Hacktribe

Open-Source-Firmware-Mod eines Dritten für den Electribe 2 Sampler. Sie wird aus Korgs 2.02 mit Hacktribes `hacktribe-2.patch` gebaut (nicht in diesem Repo) und liest ihren eigenen Kartenordner `KORG/hacktribe/`. BLECHTRIBE läuft direkt auf Korgs Original 2.02 und braucht Hacktribe nicht. Optional lässt es sich auch auf eine Hacktribe-Datei setzen.

Siehe: [patcher.md](patcher.md) ("Original Korg 2.02 zu Hacktribe")

<a id="haken"></a>

## Haken

Eine Stelle, an der ein Patch die Firmware umlenkt (ein Funktionsanfang, eine Aufrufstelle oder ein Tabellenzeiger). Sie steht mit Kette, Position und Swallow-Flag in der `hooks`-Liste des Patches.

Siehe: [patcher.md](patcher.md) ("Einhaken", "Haken-Register"), `src/hooks.mjs`

<a id="host-port"></a>

## Host-Port

Der Speicher-Port, über den der ARM-Prozessor den Speicher des DSP liest und schreibt, zum Beispiel um Sample-Audio in den DSP zu laden oder zurückzulesen. Im Emulator ist er als Mailbox mit Steuerwörtern wie 0xA9 und 0xAB nachgebildet.

Siehe: [ideen/52-ton-im-emulator.md](ideen/52-ton-im-emulator.md), [ideen/59-sample-editor.md](ideen/59-sample-editor.md), [hintergrund/dsp-erster-blick.md](hintergrund/dsp-erster-blick.md)

<a id="jtag"></a>

## JTAG

Hardware-Debug-Schnittstelle. Hängt die Firmware, bevor ihre Rettungswege greifen, oder ist das Startprogramm beschädigt, kann nur eine JTAG-Sonde das Gerät noch retten.

Siehe: [patcher.md](patcher.md) ("Startablauf", "Was kaputtgehen kann"), [rettung.md](rettung.md)

<a id="kurzpruefung"></a>

## Kurzprüfung

Die Standard-Emulatorprüfung der Patcher-Seite: nur Start- und Rettungswege (`check.py --quick`), nicht die Fälle der einzelnen Patches. "Voller Test" prüft auch die, "Kein Test" überspringt die Prüfung.

Siehe: [patcher.md](patcher.md) ("Prüfumfang"), `tools/emu/check.py`

<a id="lang-de"></a>

## lang-de

Optionaler, erzeugter Patch, der das BLECH-Menü und Korgs Hauptmenüs auf Deutsch zeigt. Standardmäßig aus, nur über die App verfügbar.

Siehe: [firmware-sprache.md](firmware-sprache.md), `src/patcher.mjs` (`LANG_DE_URLS`)

<a id="linter"></a>

## Linter

Der Regelsatz (src/rules.mjs, data/findings.mjs), der Effekt-Presets und andere Felder gegen alles prüft, was früher schiefgegangen ist. Schweregrade: fatal, silent, error, warn, note.

Siehe: [linter.md](linter.md)

<a id="loading-animation"></a>

## Ladeanimation

Die Datei KORG/blechtribe/Media/loading.blla (Format BLLA), die die Firmware beim Laden der Samples abspielt. Ohne gültige Datei spielt Blechy.

Siehe: [hintergrund/ladeanimation.md](hintergrund/ladeanimation.md)

<a id="mailbox"></a>

## Mailbox

Der Befehlskanal vom ARM zum DSP: Rahmen aus 64 Wörtern, die abwechselnd an zwei Mailbox-Adressen gehen (0xFF900018, 0xFF900098). Der ARM wartet, bis der DSP Bit 31 löscht, bevor der nächste Rahmen kommt.

Siehe: [hintergrund/patternwechsel.md](hintergrund/patternwechsel.md) (Abschnitt 2.4)

<a id="mfx"></a>

## MFX

Master-Effekt: der eine Effekt auf dem ganzen Mix, pro Pattern gewählt (Seite MFX TYPE). Der Patch MFX 2 macht aus TOUCH SCALE eine zweite MASTER-FX-Taste mit einem zweiten Effekttyp pro Pattern-Slot.

Siehe: `tools/patch/mfx_switch.py`, [messungen/2026-10-10-mfx-umschalter.md](messungen/2026-10-10-mfx-umschalter.md)

<a id="motion-sequence"></a>

## Motion Sequence

Die aufgezeichnete Reglerbewegung des Electribe pro Part. Der Modus eines Parts ist aus (0), glatt (1) oder Trigger halten (2), eingestellt auf der Seite MOTION SEQ im Part-Menü oder mit `korg.parts[i].motionMode`.

Siehe: `data/script/contract.mjs` (PATTERN_MOTION, PART_FIELDS motionMode)

<a id="notschalter"></a>

## Notschalter

Hält man beim Einschalten EXIT, überspringt jeder eingehakte Patch seinen Code, das Gerät läuft dann nur für diesen Start wie die ungepatchte Firmware. Es wird nichts gespeichert.

Siehe: [patcher.md](patcher.md) ("Notschalter")

<a id="panel-controller"></a>

## Panel-Controller

Der eigene Mikrocontroller (ARM Cortex-M3, FM3-Familie) hinter Tasten, Reglern, Pads und LEDs. Er spricht über UART0 in 5-Byte-Nachrichten mit dem Haupt-ARM, seine Firmware steckt in jeder VSB.

Siehe: [hintergrund/panel-controller.md](hintergrund/panel-controller.md)

<a id="patch"></a>

## Patch

Eine Menge von Byte-Änderungen an der eigenen SYSTEM.VSB des Nutzers (JSON unter data/patches/, gebaut von tools/patch/). Code-Patches haken sich in Firmware-Funktionen ein, Daten-Patches ersetzen nur Bytes.

Siehe: [hintergrund/blech-theme.md](hintergrund/blech-theme.md), data/patches/

<a id="patcher"></a>

## Patcher

Das Werkzeug, das aus Patch-Dateien (ARM-Code und Haken) eine geänderte SYSTEM.VSB baut. Es steckt in der App und ist als tools/patch/apply.mjs verfügbar.

Siehe: [development.md](development.md) (Abschnitt "Patcher"), `tools/patch/apply.mjs`

<a id="pattern-confirm"></a>

## Pattern confirm

BLECH-Funktion (Menü BLECH > FEATURES > PATTERN CONFIRM, Patch pattern-switch): Dreht man beim Spielen das Rad, wird nur geblättert (VIEW:), MENU bestätigt (NEXT:) und der Wechsel passiert am Ende der Sequenz.

Siehe: [hintergrund/patternwechsel.md](hintergrund/patternwechsel.md)

<a id="plugin"></a>

## Plugin

Ein kleines Programm in der eigenen Skriptsprache dieses Repos, das auf dem Electribe in der BLECHTRIBE-Laufzeit läuft (Apps, Spiele, Werkzeuge, Helfer). Man schreibt es im Editor auf der Plugins-Seite und testet es in einem Simulator, bevor man es schickt.

Siehe: [plugins.md](plugins.md)

<a id="plugin-laufzeit"></a>

## Plugin-Laufzeit

Die Laufzeit (Patch `script-runtime`, erzeugt, nicht im Repo), die Plugins von der Karte ausführt und das BLECH-Menü und die eingebaute App Blechy auf das Gerät bringt.

Siehe: [patcher.md](patcher.md), [plugins.md](plugins.md)

<a id="pool"></a>

## Pool

Der gemeinsame 128 KiB große Speicherbereich (0xC01D7000 bis 0xC01F7000), in dem die Plugin-Blöcke, ihre Variablen und ihre Plugin-Einträge liegen. Ein Block, der nicht passt, wird mit POOL_BUDGET abgelehnt.

Siehe: `tools/patch/script_hooks.py` (POOL), `data/script/contract.mjs` (SCRIPT_POOL_BYTES, ERROR_LIST)

<a id="probelauf"></a>

## Probelauf

Das simulierte Gerät bekommt genau den Byte-Strom, der zum Gerät gehen würde, und spielt ihn auf einer Kopie durch. Das fängt falschen Kanal, fehlende Adressnachrichten und Kodierungsfehler.

Siehe: [architektur.md](architektur.md)

<a id="rahmenhaken"></a>

## Rahmenhaken

Die Routine, die in den UI-Task der Firmware eingehakt ist und einmal pro Frame läuft (alle 40 ms, 25 mal pro Sekunde). Sie vergleicht den Zustand der Firmware, um Sequencer-Ereignisse zu erzeugen, liefert Ereignisring, Timer und Frame-Ereignisse an die Plugins, schickt LED-Pakete und kopiert das Plugin-Display.

Siehe: `tools/patch/script_hooks.s`, [plugins.md](plugins.md) ("Ereignisse")

<a id="sample-swap"></a>

## Sample-Swap

Der Patch `sample-swap`: Bei einer großen `e2sSample.all` lädt der Start nur die Samples des ersten Patterns. Weitere Samples kommen von der Karte oder aus dem RAM-Cache, wenn ein Pattern sie braucht. Nur roter Sampler.

Siehe: [patcher.md](patcher.md) (Patch-Tabelle), `data/patches/sample-swap.json`

<a id="seqtask"></a>

## SeqTask

Der Firmware-Task (Priorität 2), der den Sequencer betreibt. Er wird alle 2 ms geweckt und macht aus den Timer-Ticks Sequencer-Schritte, Noten und MIDI.

Siehe: [hintergrund/sequencer-timing.md](hintergrund/sequencer-timing.md), [hintergrund/skript-laufzeit.md](hintergrund/skript-laufzeit.md) (Abschnitt 1.1)

<a id="sidecar"></a>

## Sidecar

Der eingefrorene (PyInstaller) Emulator-Dienst, den die Desktop-App neben der Seite startet.

Siehe: [development.md](development.md) (Abschnitt "Die App"), `tools/emu/build-sidecar.mjs`

<a id="splash-screen"></a>

## Startbild

Das Startbild mit 128 x 64 Pixeln. BLECH legt ein Nutzerbild im Flash-Sektor 0x7F0000 ab und spiegelt es als KORG/blechtribe/Media/splash.bmp.

Siehe: [hintergrund/startbild-editor.md](hintergrund/startbild-editor.md)

<a id="sprachbereich"></a>

## Sprachbereich

Die 16 KiB von `0xC016C000` bis `0xC0170000` (oberes Ende des Code-Bereichs MORE3), in die `lang-de` seine Texte, Tabellen und Glyphen schreibt.

Siehe: [firmware-sprache.md](firmware-sprache.md), `tools/patch/script_hooks.py` (`LANG`)

<a id="startphase"></a>

## Startphase

Der Startablauf der Firmware vor dem Hauptbildschirm: Startprogramm, Panel-Austausch, Tastenabfrage beim Start, Update-Abfrage. Patches dürfen Code, der dort läuft, nicht ändern, weil dort die Rettungswege liegen. Aufgeführte Ausnahmen stehen in `startPhase` des Patches.

Siehe: [patcher.md](patcher.md) ("Regeln", "Prüfungen vor dem Export")

<a id="swap-file"></a>

## Swap-Datei

Die temporäre Datei e2sSample.tmp auf der Karte, mit der e2sSample.all verkleinert wird, weil das FatFs der Firmware weder kürzen noch umbenennen kann.

Siehe: [hintergrund/sample-datei.md](hintergrund/sample-datei.md)

<a id="sync-group"></a>

## Sync Group

Eine Einstellung pro Pattern (OFF oder 1 bis 999), die BLECHTRIBE hinzufügt. Patterns derselben Gruppe wechseln am Ende der Sequenz ohne MENU-Bestätigung, und Live-Änderungen (Tonhöhe, Modulation) gehen im RAM ins nächste Pattern mit, es gibt also keinen Sprung.

Siehe: [messungen/2026-10-19-sync-groups.md](messungen/2026-10-19-sync-groups.md)

<a id="sysex"></a>

## SysEx

System Exclusive, der MIDI-Nachrichtentyp, mit dem über USB mit dem Gerät gesprochen wird (Speicher und Dateien lesen und schreiben, Fernsteuerung).

Siehe: [test-modus.md](test-modus.md), [patcher.md](patcher.md)

<a id="test-modus"></a>

## Test-Modus

Zustand, in dem das Gerät wie ausgeschaltet aussieht (Display, Licht und LEDs dunkel, Auto Power Off gehalten), aber weiterläuft. Nur über USB, nur im RAM. Auf einem echten Gerät ist er gesperrt, seit er eines eingefroren hat.

Siehe: [test-modus.md](test-modus.md)

<a id="timer3"></a>

## Timer3

Der Hardware-Timer, der mit 150 MHz zählt und den die Firmware mit einer Periode von einer Sekunde betreibt. Die Plugin-Uhr (`korg.millis`) und die Timer bauen darauf auf.

Siehe: `data/script/contract.mjs` (TIMER3)

<a id="touch-scale"></a>

## Touch Scale

Einer der drei Touchpad-Modi (Touch Scale allein, Gate Arp + Touch Scale, Gate Arp allein), gewählt mit den Tasten TOUCH SCALE, GATE ARP und MASTER FX. X auf dem Pad spielt die Note der Skala.

Siehe: [tastenkombinationen.md](tastenkombinationen.md), [ideen/102-gate-arp-y-rhythmus.md](ideen/102-gate-arp-y-rhythmus.md)

<a id="tuersteher"></a>

## Türsteher

Der Türsteher: Jede Änderung läuft durch den Linter und einen Probelauf im simulierten Gerät, bevor sie zum Gerät geht. Fehler blockieren das Senden, Warnungen brauchen eine Bestätigung.

Siehe: [architektur.md](architektur.md) (Abschnitt "Der Türsteher"), `src/gate.mjs`

<a id="uitask"></a>

## UiTask

Der Firmware-Task, der Tasten verteilt, alle 40 ms die Bildschirme zeichnet und der einzige Kontext ist, in dem Plugin-Handler laufen.

Siehe: [hintergrund/skript-laufzeit.md](hintergrund/skript-laufzeit.md) (Abschnitt 1.1)

<a id="unicorn"></a>

## Unicorn

Die CPU-Emulationsbibliothek, mit der die Emulator-Werkzeuge ARM-Code ausführen, auch einzelne Routinen ohne die ganze Firmware (zum Beispiel um die Befehle eines Display-Aufrufs zu zählen).

Siehe: [plugins.md](plugins.md) ("Im Emulator"), `tools/patch/test_script_display.py`

<a id="vm"></a>

## VM

Die Bytecode-Maschine der Plugin-Laufzeit (tools/patch/script_vm.s): eine Stapelmaschine mit bereichsgeprüften Variablen, einem Treibstoff-Zähler, der Endlosschleifen stoppt, und einer festen API-Tabelle statt Firmware-Adressen.

Siehe: [hintergrund/skript-laufzeit.md](hintergrund/skript-laufzeit.md) (Abschnitte 2.2, 2.3)

<a id="vsb"></a>

## VSB

Die Firmware-Datei `SYSTEM.VSB` des Electribe 2: 0x200100 Bytes, ein 256 Byte großer Header plus das 2-MiB-Abbild des ARM-Prozessors (Code, Daten und das eingebettete DSP-Programm). Sie ist nicht verschlüsselt. Das Gerät installiert sie von der SD-Karte über DATA UTILITY, SOFTWARE UPDATE.

Siehe: [patcher.md](patcher.md) ("Was in der VSB steckt")

<a id="wfi"></a>

## WFI

Der ARM-Befehl "wait for interrupt". Eine ruhige Firmware wartet darin etwa 3000 mal pro Sekunde, eine, die in einer Schleife hängt, nie. Der Emulator unterscheidet so Leerlauf von Hänger.

Siehe: `tools/emu/machine.py` (idle_waits), `tools/emu/server.py` (alive)
