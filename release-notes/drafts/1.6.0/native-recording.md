BLECHTRIBE 1.6.0 und die App 1.6.0.

Entwurf: Geräteabnahme und endgültige Ringwahl stehen noch aus. Noch keine Freigabe für lange Aufnahmen.

**Neu**
- Native Aufnahme auf die SD-Karte für die beiden Sampler-Builds: Menü -> BLECH -> FEATURES -> NATIVE RECORDING ON, dann SHIFT+REC, Quelle RECORD und REC zum Starten oder Stoppen. Die Vorgabe ist OFF; WRITE behält sie.
- Der Mastermix nach MFX und Röhrenkurve einschließlich AUDIO IN/THRU landet als Stereo-WAV mit 48 kHz und 16 Bit in `Recordings/REC0001.WAV`. Das Metronom bleibt hörbar, wird aber nicht aufgenommen. PLAY steuert das Pattern unabhängig davon.
- Dateinamen steigen, vorhandene Dateien bleiben erhalten. Kurz vor 4 GiB beginnt die nächste Datei. Anzeige und Dauer gehören zur aktuellen Datei.
- Zwischenstände sichern zuerst Audio und Dateigröße, dann die WAV-Längen. Karte voll, Kartenentnahme und Erfassungslücken enden mit sichtbarem Fehler; Lücken erhalten einen benannten cue-Punkt.
- Plugin-Daten und Einstellungen warten während der Aufnahme. SAMPLING, RESAMPLING und Audioerfassungs-Apps wie Spettro bleiben bis zum Abschluss gesperrt.

Blau, Sample-Swap-Integration und Geräteabnahme bleiben offen. Die blauen Mono- und späteren Player-Schritte sind hier nicht freigegeben.

## English

BLECHTRIBE 1.6.0 and the app 1.6.0.

Draft: device acceptance and the final ring choice are pending. Long recordings are not yet approved.

**New**
- Native SD recording for both sampler builds: enable NATIVE RECORDING in Menü -> BLECH -> FEATURES, then SHIFT+REC, source RECORD and REC to start or stop. The default is OFF; WRITE keeps it.
- The master mix after MFX and the tube curve, including AUDIO IN/THRU, becomes a stereo 48 kHz, 16-bit WAV in `Recordings/REC0001.WAV`. The metronome stays audible but is excluded. PLAY controls the pattern independently.
- Filenames increase and existing files stay intact. A following file starts just before 4 GiB. The display and duration refer to the current file.
- Checkpoints persist audio and file size before updating WAV lengths. Full cards, card removal and capture gaps produce visible failures; gaps retain a labelled cue.
- Plugin data and settings wait during recording. SAMPLING, RESAMPLING and capture apps such as Spettro remain unavailable until finalization.

Blue support, Sample Swap integration and device acceptance remain pending. Blue mono recording and the later player are not approved in this draft.
