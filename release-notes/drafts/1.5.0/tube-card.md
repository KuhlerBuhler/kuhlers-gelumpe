BLECHTRIBE 1.5.0 und die App 1.5.0.

**Geändert**
- TUBE in der App und für Plugins
  - Was: die Seite Features der App hat jetzt eine Karte für den Röhrenklang am Ausgang (BLECH > FEATURES > TUBE, TUBE DRIVE, TUBE ASYM) mit Bild und Erklärung in allen Sprachen der App. Plugins lesen und setzen die drei Seiten über `korg.menu.blech.features.tube`, `.tubeDrive` und `.tubeAsym` (ab Plugin-API 41).
  - Gut zu wissen: ein Plugin wirkt wie ein Dreh auf der Seite, auch auf den Klang; WRITE behält es. Ohne die Röhrenkurve im Satz liest TUBE 0 und Schreiben tut nichts.

## English

**Changed**
- TUBE in the app and for plugins
  - What: the app's Features page now has a card for the tube sound on the output (BLECH > FEATURES > TUBE, TUBE DRIVE, TUBE ASYM) with a picture and an explanation in every language of the app. Plugins read and set the three pages with `korg.menu.blech.features.tube`, `.tubeDrive` and `.tubeAsym` (from plugin API 41).
  - Good to know: a plugin acts like a turn on the page, on the sound too; WRITE keeps it. Without the tube curve in the set, TUBE reads 0 and a write does nothing.
