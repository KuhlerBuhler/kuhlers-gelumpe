BLECHTRIBE 1.5.0 und die App 1.5.0.

**Neu**
- Freier Speicher beim Sampling in MB
  - Was: im Sampling und Resampling zeigt die Zeile Memory (deutsch Speicher) den freien Sample-Speicher in MB statt geschätzter Sekunden, zum Beispiel "24.6 [MB]". Mit aktivem Sample Swap zählen auch die Lücken mit, die der Swap beim Austauschen von Samples frei macht.
  - Gut zu wissen: nur die rote Electribe. Eine Aufnahme kann den Platz hinter dem zuletzt geladenen Sample nutzen; Lücken dazwischen füllt der Swap mit Samples von der Karte. Im Emulator geprüft, am Gerät noch offen.

## English

**New**
- Free memory in MB when sampling
  - What: in sampling and resampling the Memory line shows the free sample memory in MB instead of estimated seconds, for example "24.6 [MB]". With the sample swap active, the gaps the swap frees when it exchanges samples count too.
  - Good to know: red Electribe only. A recording can use the space after the last loaded sample; the swap fills gaps in between with samples from the card. Checked in the emulator, not yet on a device.
