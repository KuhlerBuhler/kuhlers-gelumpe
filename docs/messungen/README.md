# Messungen

Jede Datei hier ist ein Beleg, auf den ein Eintrag der [Gerätekarte](../geraetekarte.md) oder
der Befunde mit `measure:<datum>/<name>` zeigt. Der Kartentest prüft, dass die Datei existiert.
Darum werden Messungen nie umbenannt oder verschoben: `data/` und `test/` zeigen auf ihre Pfade.

Eine Messung beschreibt, was am Gerät getan und was dabei beobachtet wurde, nicht was daraus
folgen soll. Gemessen ist an einer Korg Electribe 2 Sampler mit Firmware 2.02 und Hacktribe,
wenn nicht anders vermerkt. Marker: **gemessen** (am Gerät oder im Emulator), **offline** (Code
oder Dump gelesen), **hergeleitet**, **offen**. Rohdaten von Korg (Firmware, Werks-Patterns,
Samples) liegen hier nie, nur Ergebnisse. Ein Emulatorergebnis ist keine Gerätemessung, der
Titel oder der Kopf einer Datei sagt, was sie belegt.

Die [Speicherkarte und Schutzgrenzen](../speicherbereiche.md) führen die Ergebnisse der
Speicheruntersuchung zusammen. Anleitungen zum Nachvollziehen am eigenen Gerät stehen unter
[Gerätetests](../geraetetests/README.md).

## Funktionen am Gerät

Eingebaute Funktionen der Firmware: Pads, Tasten, Vorschau, Sync Group, Energie.

- [Notenassistent: nach einer Note leuchten die passenden Pads](2026-10-15-note-assistant.md)
- [Patternwechsel erst nach Bestätigung: gebaut und im Emulator geprüft](2026-10-15-patternwechsel.md)
- [Synth-Filter auf Korgs Original: der Patch, im Emulator geprüft](2026-10-15-synth-filter.md)
- [TAP Motion: der Patch, im Emulator geprüft](2026-10-15-tap-motion-patch.md)
- [TAP und Reglerbewegungen: Recherche im Emulator](2026-10-15-tap-motion.md)
- [Pad-LEDs: Helligkeitsstufen](2026-10-16-pad-led-stufen.md)
- [Würfeln am Gerät: SHIFT + PART ERASE würfelt eine Melodie](2026-10-16-wuerfeln.md)
- [Pad-Farben: Part und Auswahl in Rot, Blau oder Pink](2026-10-17-pad-farben.md)
- [Energiesparmodus: LEDs gedimmt](2026-10-18-energiesparen-leds.md)
- [Ruhender Insert-Effekt (2026-10-18)](2026-10-18-ifx-ruht.md)
- [EXIT-Shortcuts: speichern und Part zurücksetzen (19.10.)](2026-10-19-exit-shortcuts.md)
- [Gate-Schweif: gehaltene Noten auf den Step-Pads (19.10.)](2026-10-19-gate-schweif.md)
- [Notenassistent: Helligkeit nach Passung, stehen lassen und ausblenden (19.10.)](2026-10-19-notenassistent-helligkeit.md)
- [Poly-Steps mit mehreren Noten in Pink](2026-10-19-poly-pads-pink.md)
- [Sync Groups: Patterns verketten, Live-Änderungen mitnehmen (19.10.)](2026-10-19-sync-groups.md)
- [Sync Group, MENU-Taste, Menüs und Kalibrierung (22.10.)](2026-10-22-sync-und-menues.md)
- [EXIT-Shortcuts und Akkorde in Pink auf der blauen Electribe (24.10.)](2026-10-24-blau-shortcuts-akkorde.md)
- [Sync Group auf der blauen Electribe (24.10.)](2026-10-24-blau-sync-group.md)
- [Grundlagen für native Bedienmakros (25.10.)](2026-10-25-makro-grundlagen.md)
- [Die Ansicht des nächsten Patterns: Pads und Info-Texte (25.10.)](2026-10-25-pattern-ansicht.md)
- [Stimmen beim Wechsel innerhalb einer Sync-Gruppe](2026-10-25-sync-group-stimmen.md)
- [Sync Group: gestoppt mit ungespeicherten Änderungen ohne Rückfrage (25.10.)](2026-10-25-sync-ungespeichert.md)
- [Eigenes Init-Pattern (Set Init Pattern)](2026-10-28-init-pattern.md)
- [Letztes Pattern beim Einschalten](2026-10-28-letztes-pattern.md)
- [BEAT 8: Steps als Achtel, ein Pattern doppelt so lang](2026-10-29-beat-achtel.md)
- [Schalter LAST PATTERN und Doom ohne Dateien](2026-10-29-letztes-pattern-schalter-doom-ohne-dateien.md)
- [Menü-Anordnung: SYNC GROUP, GLOBAL PARAMETERS, DATA UTILITY](2026-10-29-menue-anordnung.md)
- [Stereo auf einem Pad](2026-10-29-stereo-ein-pad.md)
- [Vorschau: die Pads gehören dem angesehenen Pattern](2026-10-29-vorschau-pads.md)
- [TOUCH SCALE RANGE 0: X spielt nur den Grundton](2026-10-30-touch-scale-null.md)
- [Vorschau: ein gedrückter Part kommt ins laufende Pattern](2026-10-30-vorschau-part-reinholen.md)
- [Vorschau: die Pads der Parts, die im angesehenen Pattern an sind, blinken](2026-11-02-vorschau-pads-blinken.md)
- [KEY PADS fest eingebaut](2026-11-07-key-pads-eingebaut.md)
- [FILTER TOGGLE fest eingebaut](2026-11-08-filter-toggle-eingebaut.md)
- [KEY PADS chromatisch](2026-11-08-key-pads-chromatisch.md)
- [AUTO SAVE: Einstellungen speichern sich beim Verlassen](2026-11-09-auto-save.md)
- [Rad in der Plugin-Liste und schnelles Drehen in SPLASH IMPORT](2026-11-09-menue-liste-rad.md)
- [Vorschau: schnelles Blättern durch die Patterns hält mit der Firmware mit](2026-11-09-pattern-schritte.md)
- [KEY PADS: Pads 13 bis 16 setzen die Oktave (12.11.)](2026-11-12-key-pads-oktave.md)
- [KNOB LEDS: Regler-LEDs ausschalten](2026-11-12-knopf-leds.md)
- [Pegel-LEDs unten: Spitzenpegel des Ausgangs, nicht Velocity](2026-11-12-pegel-leds.md)
- [BPM GLIDE fest eingebaut: GLIDE CHAIN und GLIDE SWITCH](2026-11-15-bpm-glide.md)
- [KEY PADS: Pads 13 bis 16 transponieren um Oktaven (15.11.)](2026-11-15-key-pads-transpose.md)
- [BATTERY %: Ladestand in Prozent neben dem Batteriesymbol](2026-11-16-batterie-prozent.md)
- [Vorschau-BPM: die BPM oben zeigt beim Ansehen das Tempo des angesehenen Patterns](2026-11-19-vorschau-bpm.md)
- [STOP halten: jeden Klang sofort beenden (22.11.)](2026-11-22-stop-halten.md)
- [DATA UTILITY: der Seitenzähler eines Fensters zeigt die Nummer der Funktion (23.11.)](2026-11-23-data-utility-zaehler.md)

## Pattern, Parts und Global

Felder des Pattern-Blocks, der Parts und der Global-Einstellungen, wie sie die Gerätekarte belegt.

- [Part-Felder über Controller zugeordnet](2026-09-16-cc-map.md)
- [Pattern-Block, mit Differenzproben bestätigt](2026-09-16-pattern-diff.md)
- [Cutoff (Part-Byte 13) und Resonanz (Part-Byte 14)](2026-09-17-cutoff-resonance-peak.md)
- [Hüllkurve (Part-Byte 20 Attack, 21 Decay)](2026-09-17-envelope-time.md)
- [Filtertypen (Part-Byte 12)](2026-09-17-filter-types.md)
- [Glide (Part-Byte 37)](2026-09-17-glide-time.md)
- [Modulation: Typ, Speed, Depth (Part-Bytes 16, 17, 18)](2026-09-17-mod-speed-depth.md)
- [Osc Pitch (Part-Byte 36)](2026-09-17-osc-pitch.md)
- [Pattern senden: Glide geht verloren](2026-09-22-pattern-write-glide.md)
- [Menüzustand im RAM: welcher Bildschirm, welche Seite](2026-10-09-menuezustand.md)
- [Pattern-Kette und Pattern-Import von der Karte, im Emulator gemessen](2026-10-10-pattern-kette-import.md)
- [Globals auf Werkseinstellung zurückgefallen: Ursache gesucht](2026-10-13-globals-zurueckgesetzt.md)
- [Global-Menü: welches Byte, welche Werte, welches Label](2026-10-14-global-felder.md)
- [Pattern-Export unter BLECH: wohin, und was in der Datei steht](2026-10-28-pattern-export.md)
- [Live-Schreibwege: Pattern, Parts und Global](2026-11-03-live-schreibwege.md)
- [Plugin API 20: die Globals als Blätter von `korg.global`](2026-11-05-plugin-api20-globals.md)
- [Step-Trigger (Byte 3): wann er zählt, mit Voice Assign, im Emulator](2026-11-06-step-trigger.md)
- [Patterns-Ordner: Export, Import-Browser, Laden beim Start (14.11.)](2026-11-14-patterns-ordner.md)

## Effekte und DSP

Insert- und Master-Effekte, zweite Stufe, Pegel und der DSP selbst.

- [FX-Tabellen im RAM, live beschrieben](2026-09-14-fx-ram-write.md)
- [Modulationstabelle in der Firmware](2026-09-14-modulation-table.md)
- [Zweistufige Insert-Ketten, Handversuche](2026-09-14-stage2-chains.md)
- [level_mod (0x15): Tiefe und Reset](2026-09-21-level-mod.md)
- [Pegel, die Presets unbrauchbar machen](2026-09-21-loudness.md)
- [Ringmodulator mit zweiter Stufe](2026-09-21-ring-mod-chain.md)
- [Stufe 2, automatische Messreihe](2026-09-21-stage2-sweep.md)
- [DSP-Audiopfade und Ausführungsgrenzen, offline](2026-10-08-dsp-audiopfade.md)
- [Was ein Master-Preset an den DSP schickt](2026-10-09-mfx-dsp.md)
- [MFX 2 auf TOUCH SCALE: gebaut und im Emulator geprüft](2026-10-10-mfx-umschalter.md)
- [MFX 2 am Gerät: erster Code-Patch auf der echten Electribe](2026-10-13-mfx-umschalter-geraet.md)
- [FX-Tabellen: Parameterspannen und Wahlnamen aus dem DSP-Strom](2026-10-14-fx-tabellen.md)
- [Offene Fragen: was sich mit Emulator und DSP-Tabellen beantworten lässt](2026-10-14-offene-fragen.md)
- [Effekt-Editor auf Korgs Original: Records live lesen und schreiben](2026-10-15-effekt-editor-original.md)
- [Modulationsarten, Stufe 2: was die übrigen Bytes eines Eintrags tun](2026-10-15-modulation-stufe2.md)
- [Preset-Tabellen: wo Korg sie ablegt, was Hacktribe verschiebt, wer sie liest](2026-10-15-preset-tabellen.md)
- [FX-Katalog: Pegel gegen die Werkspresets](2026-10-29-fx-katalog-pegel.md)
- [Eigene Insert- und Master-Effekte auf der blauen Electribe 2: was es kostet](2026-11-08-blau-eigene-effekte.md)
- [Neue Katalog-Effekte für Bass, Kick, Verzerrung und Mix (11.11.)](2026-11-11-neue-effekte.md)
- [Echter DSP-Code im Simulator: Stand und Grenze](2026-11-12-dsp-im-simulator.md)
- [DSP-Modell im Emulator, für Prüfungen](2026-11-12-dsp-modell.md)
- [Stufe 1 und Stufe 2 im DSP-Simulator: alle Paare](2026-11-13-stufe2-simulation.md)
- [Eigener Speicher für Stufe 2: warum Paare abstürzen und der Patch dagegen](2026-11-13-stufe2-speicher.md)
- [Blackfin: HOSTDP-FIFO und DMA1](2026-11-14-blackfin-host-fifo.md)
- [Blackfin: gemeinsame ARM-/DSP-Modellzeit und GPIO](2026-11-14-blackfin-modellzeit.md)
- [Blackfin: SPORT0 und der native Audiotakt](2026-11-14-blackfin-sport0.md)
- [Effekte und Modulationen vom Gerät lesen](2026-11-14-effekte-vom-geraet.md)
- [FX-Pegel im DSP-Sim (16.11.2026)](2026-11-16-fx-pegel-im-dsp-sim.md)
- [QEMU als DSP-Kern: Hybrid-Worker hinter BFIN9](2026-11-16-qemu-dsp-kern.md)
- [Hacktribes Master-Effekte auf der roten 2.02 (17.11.)](2026-11-17-hacktribe-master-rot.md)
- [Natives Aufnehmen und Abspielen: Master-Abgriff im DSP, Kartenrate, RAM, blau, offline](2026-11-17-native-aufnahme.md)
- [Time Stretch: offline auf dem ARM, live im DSP](2026-11-17-time-stretch.md)
- [DSP-SDRAM: Belegung, Grenzprüfung und geprüfte Kandidaten](2026-11-20-dsp-sdram-freiraum.md)
- [Röhrenkurve statt Soft-Clipper am Ausgang, im QEMU-DSP-Kern und im Emulator](2026-11-20-roehrenkurve.md)
- [DSP-SDRAM am roten Gerät: zwei vollständige Lesevergleiche](2026-11-22-dsp-sdram-am-geraet.md)

## SysEx, USB und Transport

Wie das Gerät auf Nachrichten antwortet, Größen, Zeiten und Schutzgrenzen.

- [SysEx: globaler Kanal und Leseobergrenze](2026-09-14-sysex-channel.md)
- [Geräteprotokoll: Suche, RAM lesen und Pattern-Abfrage](2026-10-08-geraeteprotokoll.md)
- [SysEx über die emulierte DIN-MIDI](2026-10-09-din-sysex.md)
- [Hänger im Emulator erkennen](2026-10-10-haenger.md)
- [BLECH SysEx: RAM lesen und schreiben in großen Blöcken](2026-10-15-blech-sysex.md)
- [Update über USB (18.10.)](2026-10-18-update-ueber-usb.md)
- [Tasten vom Rechner (KORG.press und KORG.turn)](2026-10-22-tasten-vom-rechner.md)
- [Hacktribes Flash-Schreibbefehl und die Pattern-Schreibvorgänge (24.10.)](2026-10-24-hacktribe-flash.md)
- [Die Sample-Datei über SysEx, 2026-10-26](2026-10-26-sample-datei-sysex.md)
- [Test-Modus und Fernbedienung aller Bedienelemente](2026-10-29-test-modus-fernsteuerung.md)
- [DEV MODE am Gerät: Schritte und Ergebnisse](2026-11-14-dev-mode-geraet.md)
- [DEV MODE: was im Firmware-Abbild gesperrt bleibt](2026-11-14-dev-mode-sperrbereiche.md)
- [Kartentausch: Hänger, SAVE TO FLASH und Knopf-LEDs (15.11.)](2026-11-15-karte-tausch-haenger.md)
- [Hänger nach EXEC-Tastendrücken (rot)](2026-11-15-remote-exec-haenger.md)

## Speicher, Flash und Samples

Adressräume, Stacks, Flash-Aufbau, Samples und der Zustand im RAM.

- [Vollständiges CPU-RAM-Adressfenster](2026-10-07-cpu-ram-fenster.md)
- [Sample-Metadaten im RAM, 2026-10-07](2026-10-07-sample-metadaten-ram.md)
- [Sample-Namen im RAM und Schreibheader](2026-10-07-sample-name-ram.md)
- [Werks-Samplebank im Flash: Struktur und vollständige Dekodierung](2026-10-07-werks-sample-flash.md)
- [Startinitialisierung, Interrupt-/Loader-Stacks und Patternbank](2026-10-08-boot-pattern-speicher.md)
- [Task-Stacks, Heap und Arbeitsbuffer, offline gemessen](2026-10-08-systemspeicher-offline.md)
- [USB-Sampleimport ohne SD: Offline-Machbarkeit](2026-10-08-usb-sample-import-offline.md)
- [Ganzer Flash in einem Stand](2026-10-09-flash-dump.md)
- [LED-Zustand im RAM: wo die Firmware merkt, was leuchtet](2026-10-14-led-zustand-ram.md)
- [Voller Samplespeicher: schreibt die Firmware in BLECHs RAM?](2026-10-14-sample-speicher-voll.md)
- [Plugin Speicher: korg.store über die Karte](2026-10-14-skript-speicher.md)
- [Sample-Fehler: ein Sample überspringen und sagen, welches](2026-10-15-sample-fehler.md)
- [Die PCM-Bank der blauen Electribe 2 aus WAV-Dateien nachgebaut](2026-10-15-synth-pcm-flash.md)
- [Samples auf der blauen Electribe 2: PCM-Wellen und Oszillator-Tabelle](2026-10-15-synth-samples.md)
- [Freier RAM oberhalb von 0xC1010000 (22.10.)](2026-10-22-ram-frei.md)
- [Der Stack bei 0xC274E000 und wer den RAM darüber nutzt (24.10.)](2026-10-24-ram-task-stack.md)
- [Sample-Swap: RAM-Besitz und ein begrenzter DSP-Transfer](2026-10-25-sample-swap-timeout.md)
- [Sample-Swap: der Bau](2026-10-26-sample-swap-bau.md)
- [Sample-Sammlung: einen Slot dauerhaft speichern](2026-10-27-sample-store.md)
- [Sample-Swap: Schutz der Daten im DSP und auf der Karte](2026-10-30-sample-swap-schutz.md)
- [Hacktribe und die Samples: was die Quellen sagen, was gemessen ist](2026-11-06-hacktribe-samples.md)
- [Sample-RAM: CPU-Register und Speicherabbildung](2026-11-06-sample-ram-mmu.md)
- [Updatepfad der laufenden BLECH-Firmware: KORG/blechtribe/System/SYSTEM.VSB](2026-11-06-sample-ram-vorpruefung.md)
- [Hacktribe-Oszillatoren auf den freien Plätzen](2026-11-08-ht-osc-freie-plaetze.md)
- [ORIG im BLECH-Menü und die später eingesteckte Karte (11.11.)](2026-11-11-orig-und-karte-spaeter.md)
- [Plugin API 33: Samples lesen, Pattern speichern, Part kopieren](2026-11-11-plugin-api33-samples.md)
- [Eigene Samples auf der blauen Electribe 2: wo im DSP-Speicher Platz ist](2026-11-12-blau-sample-import.md)
- [Kartentausch bringt die ganze Einstellungsdatei mit (12.11.)](2026-11-12-karte-spaeter-einstellungen.md)
- [BLECH-Einstellungen ohne Karte im Flash (13.11.)](2026-11-13-einstellungen-flash.md)
- [IMPORT SAMPLE auf Werks-Slots](2026-11-16-import-werks-slots.md)
- [Platz für weitere ARM- und DSP-Funktionen](2026-11-20-firmware-speicherbudget.md)
- [Sample-Kategorie in SAMPLE EDIT](2026-11-21-sample-kategorie.md)

## Firmware, Start und Rückweg

Startphase, Notschalter, Firmware als Datei, Update und der Weg zurück.

- [Firmware-Rückweg: geprüfte Quellen und getrennte Verfahren](2026-10-08-firmware-rueckweg.md)
- [Geänderte Firmware als Datei, im Emulator gebootet](2026-10-09-firmware-export.md)
- [Rückweg geübt: eigene Firmware hin, Original zurück](2026-10-10-rueckweg-geuebt.md)
- [Startbild-Editor im Menü Global: gebaut und im Emulator geprüft](2026-10-10-startbild-editor.md)
- [Startphase, Startmodi und Notschalter-Taste](2026-10-10-startphase.md)
- [Ladebalken im Startbild: gebaut und im Emulator geprüft](2026-10-15-ladebalken.md)
- [Aussehen früh im Start: Zeitlinie und der früheste Punkt](2026-10-16-blech-look-frueh.md)
- [Ladebalken: Streuung der Ladezeit im Emulator](2026-10-18-ladebalken-streuung.md)
- [Alten Kartenordner beim ersten Start übernehmen (19.10.)](2026-10-19-ordner-uebernehmen.md)
- [Alten Kartenordner beim ersten Start übernehmen, blaue Electribe](2026-10-29-blau-ordner-uebernehmen.md)
- [Farbe des Hintergrundlichts schon beim Einschalten](2026-10-29-hintergrundlicht-beim-start.md)
- [Rettung: dieselbe SYSTEM.VSB in allen drei Ordnern](2026-11-08-rettung-alle-ordner.md)
- [Ordner KORG/blechtribe beim ersten Start, Frage der blauen nach der Pattern-Sicherung](2026-11-09-blechtribe-ordner.md)
- [Fehlende Unterordner in KORG/blechtribe, rote fragt auch nach der Pattern-Sicherung (9.11.)](2026-11-09-unterordner-rote-sicherung.md)
- [Startbild-Editor auf der blauen, im Emulator](2026-11-13-startbild-editor-blau.md)
- [SOFTWARE UPDATE prüft die Dateigröße, im Emulator](2026-11-13-update-schutz.md)
- [Neustart über den Watchdog (rot, 16.11.)](2026-11-16-watchdog-neustart.md)
- [Firmware in einer anderen Sprache: Texte, Verweise, Schriften, Aufwand](2026-11-19-firmware-sprache.md)

## SD-Karte

Kartentakt, Karte ziehen und stecken, Kartenfehler beim Start.

- [Plugin-Datei von der Karte: Lader und Dateiformat](2026-10-14-skript-karte.md)
- [Karte gezogen, TAP blinkt](2026-10-18-karte-gezogen-tap-blinkt.md)
- [Presets und Modulationen von der Karte (e2sFx.all)](2026-10-22-sammeldatei-karte.md)
- [SD-Karte mit 25 statt 12,5 MHz (25.10.)](2026-10-25-sd-takt.md)
- [MANAGE PLUGINS: 64 Dateien, REMOVE löscht die Datei, OFF behält sie](2026-10-30-plugin-liste-64-entfernen.md)
- [Tote Karte beim Start (10.11.)](2026-11-10-tote-karte-beim-start.md)
- [Karte steckt, aber "No Card.": die Init-Sperre in Korgs SD-Treiber (14.11.)](2026-11-14-karte-init-sperre.md)
- [Karte im Betrieb getauscht: neue Karte wird mit 12,5 MHz identifiziert (14.11.)](2026-11-14-karte-tausch-takt.md)
- [Karte im Betrieb wieder gesteckt: Lesen, solange die Karte noch rutscht (15.11.)](2026-11-15-karte-stecken-prellen.md)
- [Karte vom Mac zurück, Start hängt oder "No Card.": CMD8 geht verloren (22.11.)](2026-11-22-karte-cmd8-verloren.md)

## Emulator

Boot, Bedienfeld, LEDs, Takt und Tempo des Emulators, Korgs Original und die blaue Electribe im Emulator.

- [Firmware im Emulator booten](2026-10-08-emulator-boot.md)
- [LEDs selbst setzen: Execute, Caches, RGB](2026-10-08-led-execute.md)
- [Bedienfeld: Nummern der Tasten, Regler, Pads und LEDs](2026-10-08-panel-bedienung.md)
- [Emulator-Takt: 1000 Timer-Interrupts je Sekunde](2026-10-12-emulator-takt.md)
- [Display-Helligkeit: die Firmware schaltet nur an und aus](2026-10-12-lcd-helligkeit.md)
- [Tempo der Plugin-VM: Messskript, Emulatorwerte und Gerätewerte](2026-10-12-vm-tempo.md)
- [LED-Inventur am eigenen Gerät](2026-10-13-led-inventur.md)
- [Display: Schriften und Symbole der Firmware](2026-10-14-display-schriften.md)
- [BLECH auf Korgs Original 2.02](2026-10-14-stock-blech.md)
- [Korgs Original-Firmware 2.02 im Emulator](2026-10-14-stock-emulator.md)
- [Die blaue Electribe 2 (Synth) im Emulator](2026-10-15-blaue-electribe.md)
- [Emulator-Zeit gegen Gerätezeit: vier kleine Schleifen](2026-10-16-emulator-timing.md)
- [Windows: der Emulator stirbt beim ersten Firmware-Befehl](2026-10-17-windows-cfg.md)
- [CPU-Last und Laden der Samples](2026-10-18-cpu-last-und-laden.md)
- [Emulator-LEDs: nur was die Firmware schickt](2026-10-31-emulator-leds.md)
- [CPU-Last mit BLECH: was es am Gerät zu sehen gibt und was BLECH kostet](2026-11-08-cpu-last-blech.md)
- [Die rote Electribe als blaue: Korgs Synth-Firmware auf dem Sampler und zurück, im Emulator](2026-11-08-rot-als-blau.md)
- [Gerätetakt im Emulator: Cache und Multiply in der laufenden Zeit](2026-11-10-emulator-geraetetakt.md)
- [Energie und Last: Befunde vor der Umsetzung](2026-11-14-energie-befunde.md)
- [Plugin API 37: Energiesparmodus und IDLE SAVE lesen, das Ereignis idle, die Schalter in Byte 7](2026-11-15-plugin-api37-energie.md)

## BLECH-Menü und Funktionen

Das BLECH-Menü und die eingebauten Funktionen der Firmware.

- [BLECH Anpassung: untere LEDs und Display-Licht](2026-10-14-blech-anpassung.md)
- [BLECH Menü: eigener Bildschirm 0x2D im Edit Ring](2026-10-14-blech-menue.md)
- [Blechy beim Ausschalten: Bild statt "Power Off"](2026-10-15-blechy-power-off.md)
- [Blechy in BLECH eingebaut: die letzte Seite des Rings](2026-10-15-blechy.md)
- [Doom als Patch des BLECH-Satzes](2026-10-15-doom-im-patcher.md)
- [Doom: Quellen und Lizenzbefund](2026-10-15-doom-lizenzen.md)
- [Nativer Doom-SD-Lader](2026-10-15-doom-sd-lader.md)
- [Doom im Firmwareemulator geprüft](2026-10-15-doom-v21.md)
- [BLECH auf der blauen Electribe 2, Firmware 2.02](2026-10-16-blech-synth.md)
- [Plugin bleibt aus (18.10.)](2026-10-18-plugin-bleibt-aus.md)
- [ARM-Befehle und gemeinsame Routinen](2026-10-20-arm-optimierungen.md)
- [Gebundene Noten auf den Pads schneller auswerten](2026-10-20-pad-geometrie.md)
- [BLECH: neue Vergleichsbasis nach dem Abgleich mit develop](2026-10-21-patch-effizienz-basis.md)
- [BLECH mit Hacktribe auf der blauen Electribe 2, im Emulator](2026-10-26-blech-hacktribe-blau.md)

## Plugins

Die Plugin-Laufzeit: VM, Haken, Anzeige, LEDs, Speicher, Karte und die Schritte der API.

- [Apps und Display der Plugins](2026-10-14-plugin-apps.md)
- [Plugin ARM-VM](2026-10-14-skript-arm-vm.md)
- [Plugin Display: native Zeichenfunktionen und Fehlermeldung](2026-10-14-skript-display.md)
- [Plugin-Haken: Eingangsfilter und Rahmenhaken](2026-10-14-skript-haken.md)
- [Plugin Hardware: Uhr, Lesen, Handeln, Ereignisse](2026-10-14-skript-hardware.md)
- [Plugin LED-Ausgabe](2026-10-14-skript-led.md)
- [Snake als Plugin in der Firmware im Emulator](2026-10-14-skript-snake.md)
- [Mandelbrot: offene Rechtecke in einer Arbeitsliste](2026-10-19-mandelbrot-arbeitsliste.md)
- [IMPORT PLUGIN als Liste mit Namen und Beschreibung (19.10.)](2026-10-19-plugin-import-liste.md)
- [Pong: kurzer Ballschweif, Life: schneller zeichnen](2026-10-19-pong-life.md)
- [Plugins schreiben Steps: korg.seq](2026-10-26-plugin-steps.md)
- [Uhr und Timer der Plugin-Laufzeit](2026-10-29-plugin-timer.md)
- [Plugin API 15: Pattern-Setter, Touchpad-X und Tastendruck](2026-11-03-plugin-api15.md)
- [Plugin API 21: Pattern und Parts schreibbar](2026-11-06-plugin-api21-pattern-parts.md)
- [Plugin API 22: Steps lesen](2026-11-06-plugin-api22-step-getters.md)
- [Plugin API 23: IFX ON, IFX TYPE, Sample und AMP EG schreibbar](2026-11-07-plugin-api23-part-writes.md)
- [Native DSP-Erfassung der Firmware (Grundlage von API 31 Spektrum)](2026-11-07-spettro.md)
- [Plugin API 24: Schreibwege wie Regler, Tasten und Menüseiten, MIDI-CC, Fensterschalter](2026-11-08-plugin-api24-part-cc.md)
- [Plugin API 25: Tasten, Pads, Encoder und Touchpad wie ein Finger](2026-11-08-plugin-api25-panel-calls.md)
- [Plugin-Liste und SPLASH IMPORT als Dateibrowser](2026-11-08-plugin-liste-browser.md)
- [Part-Werte aus Plugins: was an die Klangerzeugung geht](2026-11-09-plugin-part-dsp.md)
- [Plugin API 26: Gerät, Version und Grenzen lesen](2026-11-11-plugin-api26-device-info.md)
- [Plugin API 27: MFX-2-Typ und Touchpad-Modus](2026-11-11-plugin-api27-mfx2-touchpad.md)
- [Plugin API 28: Motion-Spuren und Motion an/aus](2026-11-11-plugin-api28-motion.md)
- [Plugin API 29: Zustand lesen und Events für Sequencer-Plugins](2026-11-11-plugin-api29-state-events.md)
- [Plugin API 30: MIDI senden, empfangen und halten](2026-11-11-plugin-api30-midi.md)
- [Plugin API 31: Ausgangspegel wie die Pegelanzeige](2026-11-11-plugin-api31-audio-level.md)
- [Plugin API 32: eine Datendatei pro Plugin auf der Karte](2026-11-11-plugin-api32-data-file.md)
- [Plugin API 34: Netzteil oder Batterie, Ladestand, LEDs lesen](2026-11-11-plugin-api34-system.md)
- [Plugin API 31: Spektrum und Wellenform, im Emulator](2026-11-12-plugin-api31-spektrum.md)
- [Plugin API 35: Touchpad-Y halten, im Emulator](2026-11-12-plugin-touch-lock-y.md)
- [Image Viewer: Zeiten auf Hacktribe, Korg rot und blau](2026-11-16-image-viewer-timing.md)
- [korg.file.picture: Polarität und Lesezeit](2026-11-16-media-polaritaet.md)
- [Plugin API 39: ein Ordner mit 16 Datendateien je Plugin, 32 KiB je Datei](2026-11-17-plugin-daten-heap.md)
