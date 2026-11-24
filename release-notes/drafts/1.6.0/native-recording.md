BLECHTRIBE 1.6.0 und die App 1.6.0.

Entwurf: Geräteabnahme und endgültige Ringwahl stehen noch aus. Noch keine Freigabe für lange Aufnahmen.

**Neu**
- Native Aufnahme auf die SD-Karte für die beiden Sampler-Builds und Korgs blauen Synth: Menü -> BLECH -> FEATURES -> NATIVE RECORDING ON, dann SHIFT+REC, Quelle RECORD und REC zum Starten oder Stoppen. Auf blau öffnet SHIFT+REC direkt RECORD. Die Vorgabe ist OFF; WRITE behält sie.
- Der Mastermix nach MFX und dem vorhandenen Soft-Clipper einschließlich AUDIO IN/THRU landet als Stereo-WAV beim Sampler und Mono-WAV auf blau mit 48 kHz und 16 Bit in `Recordings/REC0001.WAV`. Das Metronom bleibt hörbar, wird aber nicht aufgenommen. PLAY steuert das Pattern unabhängig davon.
- Dateinamen steigen, vorhandene Dateien bleiben erhalten. Kurz vor 4 GiB beginnt die nächste Datei. Anzeige und Dauer gehören zur aktuellen Datei.
- Zwischenstände sichern zuerst Audio und Dateigröße, dann die WAV-Längen. Karte voll, Kartenentnahme und Erfassungslücken enden mit sichtbarem Fehler; Lücken erhalten einen benannten cue-Punkt.
- Plugin-Daten und Einstellungen warten während der Aufnahme. SAMPLING, RESAMPLING und Audioerfassungs-Apps wie Spettro bleiben bis zum Abschluss gesperrt.

Sample-Swap-Integration, Geräteabnahme und der Bericht des blauen Testers bleiben offen. Der spätere Player gehört nicht zu diesem Aufnahmestand.

## English

BLECHTRIBE 1.6.0 and the app 1.6.0.

Draft: device acceptance and the final ring choice are pending. Long recordings are not yet approved.

**New**
- Native SD recording for both sampler builds and the blue synth: enable NATIVE RECORDING in Menü -> BLECH -> FEATURES, then SHIFT+REC, source RECORD and REC to start or stop. On the synth, SHIFT+REC opens RECORD directly. The default is OFF; WRITE keeps it.
- The master mix after MFX and the existing soft clipper, including AUDIO IN/THRU, becomes a stereo WAV on the sampler or a mono WAV on the synth, at 48 kHz and 16 bits in `Recordings/REC0001.WAV`. The metronome stays audible but is excluded. PLAY controls the pattern independently.
- Filenames increase and existing files stay intact. A following file starts just before 4 GiB. The display and duration refer to the current file.
- Checkpoints persist audio and file size before updating WAV lengths. Full cards, card removal and capture gaps produce visible failures; gaps retain a labelled cue.
- Plugin data and settings wait during recording. SAMPLING, RESAMPLING and capture apps such as Spettro remain unavailable until finalization.

Sample Swap integration, device acceptance and the blue tester report remain pending. The later player is outside this recording draft.
