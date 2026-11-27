BLECHTRIBE 1.5.0 und die App 1.5.0.

**Neu**
- Patterns-Ordner für Export, Import und Sicherung beim Start
  - Was: EXPORT PATTERN und EXPORT ALL PATTERN schreiben nach `KORG/blechtribe/Patterns/`, IMPORT PATTERN und IMPORT ALL PATTERN öffnen dort. Der Ordner entsteht beim ersten Export. Liegt dort die Sicherung `electribe_sampler_allpattern.e2sallpat` (so heißt die Datei von EXPORT ALL PATTERN), vergleicht der Start jedes der 250 Patterns mit seinem Platz und schreibt nur die, die sich unterscheiden. Die Ladeanimation zählt das mit.
  - Gut zu wissen: was du am Gerät mit WRITE speicherst, ohne danach EXPORT ALL PATTERN, ist beim nächsten Start wieder der Stand der Datei. Also nach dem Speichern exportieren, oder die Datei umbenennen. Mit EXIT beim Einschalten lädt der Start nichts. Global-Werte lädt nur IMPORT ALL PATTERN von Hand. Rot und Hacktribe; auf der blauen liegen Exporte weiter direkt in `KORG/blechtribe/`. Nur im Emulator geprüft.

## English

**New**
- Patterns folder for export, import and the backup at start
  - What: EXPORT PATTERN and EXPORT ALL PATTERN write to `KORG/blechtribe/Patterns/`, IMPORT PATTERN and IMPORT ALL PATTERN open there. The folder is created on the first export. If the backup `electribe_sampler_allpattern.e2sallpat` (the name EXPORT ALL PATTERN gives) is in there, the start compares each of the 250 patterns with its slot and writes only the ones that differ. The loading animation counts it.
  - Good to know: what you save on the device with WRITE, without EXPORT ALL PATTERN afterwards, is back to the state of the file at the next start. So export after saving, or rename the file. With EXIT held at power-on the start loads nothing. Global values are loaded only by IMPORT ALL PATTERN by hand. Red and Hacktribe; on the blue, exports stay directly in `KORG/blechtribe/`. Checked in the emulator only.
