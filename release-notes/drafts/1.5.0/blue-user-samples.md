BLECHTRIBE 1.5.0 und die App 1.5.0.

**Neu**
- Eigene Samples auf der blauen Electribe
  - Was: die blaue Electribe lädt beim Einschalten die `Sample/e2sSample.all` von der Karte in freien DSP-Speicher. Die Samples erscheinen als neue Oszillatorgruppe `[User]` hinter Audio In. Bis zu 64 Samples, zusammen etwa 56 Sekunden mono bei 48 kHz. Du legst sie in der App auf der Seite Samples auf die Karte (Schalter auf blau), die App rechnet WAV-Dateien passend um und zeigt, was die blaue lädt. Neue Samples brauchen einen Neustart.
  - Gut zu wissen: ein Sample, das zu groß ist oder ein falsches Format hat, wird übersprungen, die übrigen laden weiter. Im BLECH-Menü zeigt die Zeile USER SAMPLES, was geladen wurde (zum Beispiel `2 OK 1 SKIPPED`). Mit EXIT beim Einschalten wird nichts geladen. Nur im Emulator geprüft, ohne Gerätetest an einer blauen. Danke an das Omnitribe-Projekt von GeorgDub für den Hinweis, dass der blaue DSP freien Speicher für Samples hat; Code und Zahlen sind eigene Messungen.

## English

**New**
- Your own samples on the blue Electribe
  - What: at power-on the blue Electribe loads `Sample/e2sSample.all` from the card into free DSP memory. The samples show up as a new oscillator group `[User]` behind Audio In. Up to 64 samples, about 56 seconds mono at 48 kHz in total. Add them on the Samples page of the app (switch to blue); the app converts WAV files to fit and shows what the blue loads. New samples need a restart.
  - Good to know: a sample that is too big or in a wrong format is skipped and the others still load. In the BLECH menu the line USER SAMPLES shows what was loaded (for example `2 OK 1 SKIPPED`). With EXIT held at power-on nothing is loaded. Checked in the emulator only, no device test on a blue. Thanks to GeorgDub's Omnitribe project for the hint that the blue DSP has spare memory for samples; code and figures are our own measurements.
