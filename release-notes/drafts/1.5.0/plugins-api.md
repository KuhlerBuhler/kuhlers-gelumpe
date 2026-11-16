### Entwurf release-notes/1.5.0.md (kommt mit dem Versionssprung)

**Neu**
- Fünf neue Plugins im Katalog: System Info (Gerät, BLECH-Version, Effekt- und Sample-Grenzen, Netzteil oder Batterie), VU Meter (Ausgangspegel als zwei Balken mit Spitzenwert), MIDI Echo (sendet die Pads als Noten auf einem eigenen MIDI-Kanal) und Motion Clear (löscht die Motion Sequence des gewählten Parts aus dem Menü BLECH).
- Spettro: Spektrum des gewählten Parts als App unter TOOLS, nur Sampler-Firmware. Der Spektrum-Worker dahinter ist jetzt Teil der Firmware. Danke an Luigi (GitHub reflectiveboi, PR #429), der Spettro und den Worker gebaut hat.

**Neu für Entwickler**
- Plugin-API 25 auf 35. Jeder neue Aufruf mit der API-Version, ab der er da ist:
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
- Veraltet seit API 35, fallen in einer späteren Version weg: `korg.read.chainMode()` und `korg.chainMode` (Ersatz `korg.global.chainMode`), `korg.current.*` (Ersatz `korg.pattern.current.*`). Plugins damit laufen weiter.

## English

**New**
- Five new plugins in the catalog: System Info (device, BLECH version, effect and sample limits, adapter or battery), VU Meter (output level as two bars with peak hold), MIDI Echo (sends the pads as notes on a MIDI channel of its own) and Motion Clear (clears the selected part's motion sequence from the BLECH menu).
- Spettro: spectrum of the selected part as an app under TOOLS, Sampler firmware only. The spectrum worker behind it is now part of the firmware. Thanks to Luigi (GitHub reflectiveboi, PR #429), who built Spettro and the worker.

**New for developers**
- Plugin API 25 to 35. Every new call with the API version that brings it:
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
- Deprecated since API 35, removed in a later version: `korg.read.chainMode()` and `korg.chainMode` (use `korg.global.chainMode`), `korg.current.*` (use `korg.pattern.current.*`). Plugins using them keep working.
