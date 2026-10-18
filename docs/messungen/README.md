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


## Pattern, Parts und Global

Felder des Pattern-Blocks, der Parts und der Global-Einstellungen, wie sie die Gerätekarte belegt.

- [Pattern-Block, mit Differenzproben bestätigt](2026-09-16-pattern-diff.md)
- [Part-Felder über Controller zugeordnet](2026-09-16-cc-map.md)
- [Global-Dump](2026-09-16-global-dump.md)
- [Cutoff (Part-Byte 13) und Resonanz (Part-Byte 14)](2026-09-17-cutoff-resonance-peak.md)
- [Hüllkurve (Part-Byte 20 Attack, 21 Decay)](2026-09-17-envelope-time.md)
- [Filtertypen (Part-Byte 12)](2026-09-17-filter-types.md)
- [Glide (Part-Byte 37)](2026-09-17-glide-time.md)
- [Modulation: Typ, Speed, Depth (Part-Bytes 16, 17, 18)](2026-09-17-mod-speed-depth.md)
- [Osc Pitch (Part-Byte 36)](2026-09-17-osc-pitch.md)
- [Pattern senden: Glide geht verloren](2026-09-22-pattern-write-glide.md)
- [Pattern-Kette und Pattern-Import von der Karte, im Emulator gemessen](2026-10-10-pattern-kette-import.md)
- [Global-Menü: welches Byte, welche Werte, welches Label](2026-10-14-global-felder.md)


## Effekte

Insert- und Master-Effekte, zweite Stufe, Pegel, Parameterspannen.

- [FX-Tabellen im RAM, live beschrieben](2026-09-14-fx-ram-write.md)
- [Modulationstabelle in der Firmware](2026-09-14-modulation-table.md)
- [Zweistufige Insert-Ketten, Handversuche](2026-09-14-stage2-chains.md)
- [Stufe 2, automatische Messreihe](2026-09-21-stage2-sweep.md)
- [Ringmodulator mit zweiter Stufe](2026-09-21-ring-mod-chain.md)
- [level_mod (0x15): Tiefe und Reset](2026-09-21-level-mod.md)
- [Pegel, die Presets unbrauchbar machen](2026-09-21-loudness.md)
- [Was ein Master-Preset an den DSP schickt](2026-10-09-mfx-dsp.md)
- [FX-Einheiten am Display: kein Befund](2026-10-14-fx-einheiten.md)
- [FX-Tabellen: Parameterspannen und Wahlnamen aus dem DSP-Strom](2026-10-14-fx-tabellen.md)
- [Alte offene Fragen, mit Emulator und DSP-Tabellen nachgeprüft](2026-10-14-offene-fragen.md)
- [Modulationsarten, Stufe 2: was die übrigen Bytes eines Eintrags tun, im Emulator gemessen](2026-10-15-modulation-stufe2.md)


## SysEx und Transport

Wie das Gerät auf Nachrichten antwortet, Größen und Zeiten.

- [SysEx: globaler Kanal und Leseobergrenze](2026-09-14-sysex-channel.md)
- [Geräteprotokoll: Suche, RAM lesen und Pattern-Abfrage](2026-10-08-geraeteprotokoll.md)
- [SysEx über die emulierte DIN-MIDI](2026-10-09-din-sysex.md)


## Speicher und Flash

Adressräume, Stacks, Flash-Aufbau, Samples und der Zustand im RAM.

- [Vollständiges CPU-RAM-Adressfenster](2026-10-07-cpu-ram-fenster.md)
- [Sample-Namen im RAM und Schreibheader](2026-10-07-sample-name-ram.md)
- [Sample-Metadaten im RAM, 2026-10-07](2026-10-07-sample-metadaten-ram.md)
- [Werks-Samplebank im Flash: Struktur und vollständige Dekodierung](2026-10-07-werks-sample-flash.md)
- [Startinitialisierung, Interrupt-/Loader-Stacks und Patternbank](2026-10-08-boot-pattern-speicher.md)
- [Task-Stacks, Heap und Arbeitsbuffer, offline gemessen](2026-10-08-systemspeicher-offline.md)
- [DSP-Audiopfade und Ausführungsgrenzen, offline](2026-10-08-dsp-audiopfade.md)
- [USB-Sampleimport ohne SD: Offline-Machbarkeit](2026-10-08-usb-sample-import-offline.md)
- [Ganzer Flash in einem Stand](2026-10-09-flash-dump.md)
- [Menüzustand im RAM: welcher Bildschirm, welche Seite](2026-10-09-menuezustand.md)
- [LED-Zustand im RAM: wo die Firmware merkt, was leuchtet](2026-10-14-led-zustand-ram.md)
- [Globals auf Werkseinstellung zurückgefallen: Ursache gesucht](2026-10-13-globals-zurueckgesetzt.md)


## Firmware, Start und Rückweg

Startphase, Startmodi, Notschalter, Firmware als Datei und der Weg zurück.

- [Startphase, Startmodi und Notschalter-Taste](2026-10-10-startphase.md)
- [Firmware-Rückweg: geprüfte Quellen und getrennte Verfahren](2026-10-08-firmware-rueckweg.md)
- [Geänderte Firmware als Datei, im Emulator gebootet](2026-10-09-firmware-export.md)
- [Rückweg geübt: eigene Firmware hin, Original zurück](2026-10-10-rueckweg-geuebt.md)


## Emulator

Boot, Bedienfeld, LEDs, Takt und Tempo des Emulators.

- [Firmware im Emulator booten](2026-10-08-emulator-boot.md)
- [Bedienfeld: Nummern der Tasten, Regler, Pads und LEDs](2026-10-08-panel-bedienung.md)
- [LEDs selbst setzen: Execute, Caches, RGB](2026-10-08-led-execute.md)
- [Hänger im Emulator erkennen](2026-10-10-haenger.md)
- [Emulator-Takt: 1000 Timer-Interrupts je Sekunde](2026-10-12-emulator-takt.md)
- [Display-Helligkeit: die Firmware schaltet nur an und aus](2026-10-12-lcd-helligkeit.md)
- [Emulator-Tempo: Zeit je Gerätesekunde](2026-10-13-emulator-tempo.md)
- [LED-Inventur am eigenen Gerät](2026-10-13-led-inventur.md)
- [Korgs Original-Firmware 2.02 im Emulator](2026-10-14-stock-emulator.md)
- [Voller Samplespeicher: schreibt die Firmware in BLECHs RAM?](2026-10-14-sample-speicher-voll.md)
- [BLECH auf Korgs Original 2.02: Ordner, Startbild, Ladezeit, Prüfung](2026-10-14-stock-blech.md)
- [Preset-Tabellen: wo Korg sie ablegt, was Hacktribe verschiebt, der Patch für 128 Plätze](2026-10-15-preset-tabellen.md)
- [Die blaue Electribe 2 (Synth) im Emulator: Hauptbild, Stellen, Flash-Kennung](2026-10-15-blaue-electribe.md)
- [Samples auf der blauen Electribe 2: PCM-Wellen, Oszillator-Tabelle, Entwurf für BLECH](2026-10-15-synth-samples.md)
- [Die PCM-Bank der blauen Electribe 2 aus WAV-Dateien nachgebaut und im Emulator geprüft](2026-10-15-synth-pcm-flash.md)


## Patches

Startbild-Editor, zweiter Master-Effekt (MFX 2), Patternwechsel mit Bestätigung, Ladebalken, das BLECH-Menü und seine Anpassung.

- [Startbild-Editor im Menü Global (Idee 35): gebaut und im Emulator geprüft](2026-10-10-startbild-editor.md)
- [MFX 2 auf TOUCH SCALE (Idee 44): gebaut und im Emulator geprüft](2026-10-10-mfx-umschalter.md)
- [MFX 2 am Gerät: erster Code-Patch auf der echten Electribe](2026-10-13-mfx-umschalter-geraet.md)
- [Patternwechsel erst nach Bestätigung (Idee 46): gebaut und im Emulator geprüft](2026-10-15-patternwechsel.md)
- [Ladebalken im Startbild (Idee 41): gebaut und im Emulator geprüft](2026-10-15-ladebalken.md)
- [Sample-Fehler: ein Sample überspringen und sagen, welches (und die Werksbank des leeren Flash)](2026-10-15-sample-fehler.md)
- [Startbild auf der Karte statt im Flash (Idee 35)](2026-10-15-startbild-karte.md)
- [BLECH Menü: eigener Bildschirm 0x2D im Edit Ring](2026-10-14-blech-menue.md)
- [BLECH Anpassung: untere LEDs und Display-Licht, Software-PWM](2026-10-14-blech-anpassung.md)
- [Aussehen früh im Start: Zeitlinie und der früheste Punkt](2026-10-16-blech-look-frueh.md)
- [Pad-LEDs: nur an oder aus, am Gerät gemessen](2026-10-16-pad-led-stufen.md) (am 18.10. widerlegt: Pulsieren pulsiert flüssig)
- [Display: Schriften und Symbole der Firmware](2026-10-14-display-schriften.md)


## Plugins

Die Laufzeit für Plugins: VM, Haken, Anzeige, LEDs, Speicher, Karte.

- [Tempo der Plugin-VM: Messskript, Emulatorwerte und Gerätewerte](2026-10-12-vm-tempo.md)
- [Plugin ARM-VM](2026-10-14-skript-arm-vm.md)
- [Plugin-Haken: Eingangsfilter und Rahmenhaken](2026-10-14-skript-haken.md)
- [Plugin Hardware: Uhr, Lesen, Handeln, Ereignisse](2026-10-14-skript-hardware.md)
- [Plugin Display: native Zeichenfunktionen und Fehlermeldung](2026-10-14-skript-display.md)
- [Plugin LED-Ausgabe](2026-10-14-skript-led.md)
- [Plugin Speicher: korg.store über die Karte](2026-10-14-skript-speicher.md)
- [Plugin-Datei von der Karte: Lader und Dateiformat](2026-10-14-skript-karte.md)
- [Snake als Plugin in der Firmware im Emulator](2026-10-14-skript-snake.md)
- [Apps und Display der Plugins](2026-10-14-plugin-apps.md)
- [Blechy in BLECH eingebaut: die letzte Seite des Rings](2026-10-15-blechy.md)
- [Blechy beim Ausschalten: Bild statt "Power Off"](2026-10-15-blechy-power-off.md)
- [TAP und Reglerbewegungen: Regler, Touchpad, Motion Sequence, Takt und TAP im Emulator](2026-10-15-tap-motion.md)
- [TAP Motion: der Patch, TAP schaltet die aufgenommene Bewegung, Master-FX-Schalter gefunden](2026-10-15-tap-motion-patch.md)
- [Notenassistent: im KEYBOARD-Modus leuchten nach einer Note die passenden Pads rosa, Pad-Layout, Helligkeit der Pad-LEDs, im Emulator geprüft](2026-10-15-note-assistant.md)
- [Synth-Filter auf Korgs Original: Tastenauswahl und Setter, Reihenfolge von Hacktribe, Muster mit Synth-Typ](2026-10-15-synth-filter.md)
- [Würfeln am Gerät: SHIFT + PART ERASE würfelt eine Melodie für den gewählten Part, Step-Records im RAM, LAST STEP, Tonleitertabelle der Firmware, im Emulator geprüft](2026-10-16-wuerfeln.md)

- [2026-10-15-doom-engine-build](2026-10-15-doom-engine-build.md)

- [2026-10-15-doom-geraetetest](2026-10-15-doom-geraetetest.md)

- [2026-10-15-doom-integration](2026-10-15-doom-integration.md)

- [2026-10-15-doom-lizenzen](2026-10-15-doom-lizenzen.md)

- [2026-10-15-doom-machbarkeit](2026-10-15-doom-machbarkeit.md)

- [2026-10-15-doom-native-runtime](2026-10-15-doom-native-runtime.md)

- [2026-10-15-doom-planung](2026-10-15-doom-planung.md)

- [2026-10-15-doom-sd-lader](2026-10-15-doom-sd-lader.md)
- [BLECH SysEx: RAM lesen und schreiben in großen Blöcken, mit CRC, FLASH READ, auch auf Korgs Original und der blauen Electribe 2](2026-10-15-blech-sysex.md)
- [Effekt-Editor auf Korgs Original: Records über die Zeigerfelder live lesen, schreiben und zurücknehmen, Schutztabelle je Build](2026-10-15-effekt-editor-original.md)

- [Doom auf BLECH v21](2026-10-15-doom-v21.md)
- [Doom als Patch des BLECH-Satzes, auf Hacktribe und Korgs Original](2026-10-15-doom-im-patcher.md)
- [Emulator-Zeit gegen Gerätezeit: vier kleine Schleifen, Rechnen 1,0, Speicher-Durchlauf rund 4](2026-10-16-emulator-timing.md)

- [Blaue Electribe: Ladebalken, Kartenordner und Sample-Fehler](2026-10-16-blau-ladebalken-ordner.md)
- [BLECH-Satz für die blaue Electribe 2](2026-10-16-blech-synth.md)
- [Eigener Start-Haken für BLECH auf dem Synth](2026-10-16-synth-start-haken.md)
- [TAP Motion: einmal abspielen, TOUCH SCALE wie MASTER FX](2026-10-17-tap-motion-einmal.md)
- [Startbild: Rad im Editor, Bild von der Karte](2026-10-17-startbild-import.md)
- [Windows: der Emulator stirbt beim ersten Firmware-Befehl, Control Flow Guard im gepackten Dienst](2026-10-17-windows-cfg.md)
- [Doom: der Lader startet nach dem Einhängen der Karte](2026-10-17-doom-nach-dem-einhaengen.md)
- [Pad-Farben: Part und Auswahl in Rot, Blau oder Pink](2026-10-17-pad-farben.md)
- [Karte gezogen: Funktionen bleiben an; TAP blinkt bei laufender Master-FX-Bewegung](2026-10-18-karte-gezogen-tap-blinkt.md)
- [Plugin bleibt aus über einen Neustart](2026-10-18-plugin-bleibt-aus.md)
- [Startbild-Editor: malen mit gehaltenem MENU, SHIFT hoch und runter](2026-10-18-startbild-malen.md)
- [CPU-Last und Laden der Samples im Emulator](2026-10-18-cpu-last-und-laden.md)
