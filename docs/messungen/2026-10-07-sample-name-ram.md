# Sample-Namen im RAM und Schreibheader

- **Gemessen, 2026-10-07:** Für die 239 Samples aus der aktuellen
  SD-Bank stimmt das 16-Byte-Namensfeld im RAM mit
  `0xC047B08C + Index * 0x20` überein. Index ist nullbasiert.
- **Gemessen:** Sample 653, Index 652, heißt `No!!`; Record-Adresse
  `0xC0480200`, Name bei `0xC048020C`. Nach dem alleinigen Schreibheader
  war der gesamte 32-Byte-Record beim erneuten Lesen unverändert.
- **Gemessen:** Der `0x53`-Schreibheader für Adresse `0xC048020C`,
  Länge 16, Kanal 9, und das folgende `0x54`-Datenpaket werden beide mit
  `F0 42 39 00 01 24 21 F7` beantwortet. Beide Bestätigungen haben
  Funktion `0x21` und den vollständigen gerätespezifischen Kopf.
- **Gemessen:** Nach dem ausdrücklich freigegebenen Schreiben von `Blech`
  mit NUL-Auffüllung in das 16-Byte-Namensfeld enthält das Zurücklesen
  `Blech`. Nur die fünf Adressen `0xC048020C` bis `0xC0480210` haben sich
  geändert; alle übrigen 91 Byte des Prüffensters `0xC04801E0` bis
  `0xC048023F` sind unverändert. Der ursprüngliche Inhalt wurde gesichert.
- **Gemessen, am Display bestätigt:** Nach der Änderung zeigt
  Sample 653 `Blech`. Für diesen Index liefert das Namensfeld der Tabelle
  somit den angezeigten Namen. SD-Datei und Sicherungskopie wurden nicht
  geändert; eine dauerhafte Umbenennung ist durch diesen Test nicht belegt.
- **Vermutet:** Der Bereich ist eine Sample-Beschreibungstabelle mit
  32-Byte-Records und Namen bei `+12`; Audiozeiger sind noch nicht belegt.

Es sind keine Firmware-, Pattern- oder Sample-Audiodaten enthalten.
