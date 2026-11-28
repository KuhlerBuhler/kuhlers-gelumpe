### Entwurf release-notes/1.5.0.md (kommt mit dem Versionssprung)

**Neu**
- Fünf neue Plugins im Katalog: System Info (Gerät, BLECH-Version, Effekt- und Sample-Grenzen, Netzteil oder Batterie), VU Meter (Ausgangspegel als zwei Balken mit Spitzenwert), MIDI Echo (sendet die Pads als Noten auf einem eigenen MIDI-Kanal) und Motion Clear (löscht die Motion Sequence des gewählten Parts aus dem Menü BLECH).
- Spettro: Spektrum des gewählten Parts als App unter TOOLS, nur Sampler-Firmware. Der Spektrum-Worker dahinter ist jetzt Teil der Firmware. Danke an Luigi (GitHub reflectiveboi, PR #429), der Spettro und den Worker gebaut hat.

**Neu für Entwickler**
- Plugin-API 25 auf 41. Jeder neue Aufruf mit der API-Version, ab der er da ist:
  - API 26: `korg.system.device`, `korg.system.version`, `korg.system.limits.*`
  - API 27: `mfx2Type` (Pattern), `korg.touchpad.mode`, Ereignis `touchpadMode`
  - API 28: `korg.motion.lane`, `.destination`, `.value`, `.setValue`, `.clearLane`, `.clearPart`, `.clearMfx`, `.output`, `korg.motion.enabled`
  - API 29: `korg.pads.mode`, `korg.pads.bar`, `korg.screen`, Ereignisse `padMode`, `screen`, `write`, `korg.display.chars`, `korg.read.patternName`
  - API 30: `korg.midi.cc`, `.noteOn`, `.noteOff`, `.program`, `korg.midi.hold`, Ereignis `midiIn`
  - API 31: `korg.audio.level`, `korg.audio.capture`, `korg.audio.spectrum`, `korg.audio.wave` (Spektrum und Wellenform nur Sampler, Worker von Luigi aus #429)
  - API 32: `korg.file.read`, `korg.file.write`
  - API 33: `korg.read.sampleName`, `korg.read.sampleInfo`, `korg.pattern.write`, `korg.part.copy`
  - API 34: `korg.system.power`, `korg.system.battery`, `korg.read.led`
  - API 35: `korg.touchLockY`, Warnungen für veraltete Aufrufe im Editor und beim Kompilieren
  - API 36: der Wert `korg.menu.blech.customizations.led.knobLeds` (KNOB LEDS)
  - API 37: Ereignis `idle` (IDLE SAVE, Stufen des Dimmens)
  - API 38: `korg.file.count`, `korg.file.name`, `korg.file.picture` (Bilder und Ladeanimationen aus `KORG/blechtribe/Media/`)
  - API 39: `korg.file.read` und `korg.file.write` bekommen ein Dateiargument 0 bis 15: jedes Plugin hat einen eigenen Ordner `Plugin/Data/<name>/` mit bis zu 16 Dateien zu je 32 KiB (vorher eine Datei mit 4096 Byte)
  - API 40: `korg.display.popup.begin`, `.timeout`, `.show` (Popup-Zeichnung für Hintergrund-Plugins)
  - API 41: die Werte `korg.menu.blech.features.tube`, `.tubeDrive`, `.tubeAsym` (TUBE, TUBE DRIVE, TUBE ASYM)
- Veraltet seit API 35, fallen in einer späteren Version weg: `korg.read.chainMode()` und `korg.chainMode` (Ersatz `korg.global.chainMode`), `korg.current.*` (Ersatz `korg.pattern.current.*`). Plugins damit laufen weiter.

## English

**New**
- Five new plugins in the catalog: System Info (device, BLECH version, effect and sample limits, adapter or battery), VU Meter (output level as two bars with peak hold), MIDI Echo (sends the pads as notes on a MIDI channel of its own) and Motion Clear (clears the selected part's motion sequence from the BLECH menu).
- Spettro: spectrum of the selected part as an app under TOOLS, Sampler firmware only. The spectrum worker behind it is now part of the firmware. Thanks to Luigi (GitHub reflectiveboi, PR #429), who built Spettro and the worker.

**New for developers**
- Plugin API 25 to 41. Every new call with the API version that brings it:
  - API 26: `korg.system.device`, `korg.system.version`, `korg.system.limits.*`
  - API 27: `mfx2Type` (pattern), `korg.touchpad.mode`, event `touchpadMode`
  - API 28: `korg.motion.lane`, `.destination`, `.value`, `.setValue`, `.clearLane`, `.clearPart`, `.clearMfx`, `.output`, `korg.motion.enabled`
  - API 29: `korg.pads.mode`, `korg.pads.bar`, `korg.screen`, events `padMode`, `screen`, `write`, `korg.display.chars`, `korg.read.patternName`
  - API 30: `korg.midi.cc`, `.noteOn`, `.noteOff`, `.program`, `korg.midi.hold`, event `midiIn`
  - API 31: `korg.audio.level`, `korg.audio.capture`, `korg.audio.spectrum`, `korg.audio.wave` (spectrum and wave on the Sampler only, worker by Luigi from #429)
  - API 32: `korg.file.read`, `korg.file.write`
  - API 33: `korg.read.sampleName`, `korg.read.sampleInfo`, `korg.pattern.write`, `korg.part.copy`
  - API 34: `korg.system.power`, `korg.system.battery`, `korg.read.led`
  - API 35: `korg.touchLockY`, warnings for deprecated calls in the editor and the compiler
  - API 36: the value `korg.menu.blech.customizations.led.knobLeds` (KNOB LEDS)
  - API 37: event `idle` (IDLE SAVE, dimming stages)
  - API 38: `korg.file.count`, `korg.file.name`, `korg.file.picture` (pictures and loading animations from `KORG/blechtribe/Media/`)
  - API 39: `korg.file.read` and `korg.file.write` take a file argument 0 to 15: every plugin has its own folder `Plugin/Data/<name>/` with up to 16 files of 32 KiB each (before: one file of 4096 bytes)
  - API 40: `korg.display.popup.begin`, `.timeout`, `.show` (popup drawing for background plugins)
  - API 41: the values `korg.menu.blech.features.tube`, `.tubeDrive`, `.tubeAsym` (TUBE, TUBE DRIVE, TUBE ASYM)
- Deprecated since API 35, removed in a later version: `korg.read.chainMode()` and `korg.chainMode` (use `korg.global.chainMode`), `korg.current.*` (use `korg.pattern.current.*`). Plugins using them keep working.
