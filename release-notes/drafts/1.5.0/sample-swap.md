BLECHTRIBE 1.5.0 und die App 1.5.0.

**Neu**
- Sample Swap: sehr große Sample-Sammlungen auf der roten Electribe
  - Was: ist die `e2sSample.all` größer als 25 MiB, lädt der Start nur die Samples des ersten Patterns. Die Samples weiterer Patterns kommen von der Karte oder aus einem Zwischenspeicher im RAM, wenn ein Pattern sie braucht. Ein Patternwechsel wartet, bis seine Samples da sind. Kleinere Dateien lädt die Firmware wie immer ganz. Bei gestopptem Gerät hängt der WAV-Import ein neues Sample hinten an die Datei auf der Karte.
  - Gut zu wissen: nur die rote Electribe (Korgs Original und Hacktribe). Im Emulator geprüft, am Gerät erst teilweise: der ganze Swap-Build am echten Gerät ist offen. Mit aktivem Swap bleibt EXPORT ALL SAMPLE gesperrt.

## English

**New**
- Sample swap: very large sample libraries on the red Electribe
  - What: if `e2sSample.all` is larger than 25 MiB, the start loads only the samples of the first pattern. The samples of other patterns come from the card or from a cache in RAM when a pattern needs them. A pattern switch waits until its samples are there. Smaller files load completely as always. With the device stopped, WAV import appends a new sample to the file on the card.
  - Good to know: red Electribe only (Korg's original and Hacktribe). Checked in the emulator, on a real device only in part: the whole swap build on a device is still open. With swap active, EXPORT ALL SAMPLE stays locked.
