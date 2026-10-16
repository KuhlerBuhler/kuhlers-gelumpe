# Idee 47: Übergänge automatisieren

Stand: Generator gebaut und im Editor bedienbar (Seite Pattern-Werkzeuge), am Gerät ungehört. Zurück zu den [Ideen](../ideen.md).

Übergangs-Patterns aus zwei Patterns bauen, im Stil der eigenen Ketten ([Übergänge](../set/uebergaenge.md)). Der Generator liegt in `src/transition.mjs` (die Befehlszeile in `tools/set/transition.mjs`), die Seite beschreibt [Pattern-Werkzeuge](../set/pattern-werkzeuge.md), das Aufspielen [Pattern aufspielen](../set/pattern-aufspielen.md).

Gebaut:

- A und B aus einer Sicherung, einer Einzeldatei oder dem Puffer des Geräts oder Emulators,
- die Optionen des Generators, eine Vorschau mit Part-Tabelle und Beschreibung,
- Ausgabe als `.e2spat`, als Kopie der Sicherung mit den Plätzen und Chain To, oder einzeln in den Puffer des Geräts, mit Linter, Türsteher und Bestätigung,
- Patterns benennen statt "Init Pattern": ein Namensfeld je Übergang, 16 Zeichen, druckbares ASCII.

Offen:

- am Gerät anhören,
- die Optionen `--mfx`, `--keep`, `--drop`, `--leave-max` und `--clip` sind nur in der Befehlszeile,
- ob das Gerät beliebige ASCII-Namen aus Datei oder Dump anzeigt, ist nicht geprüft (das Feld ist 16 Zeichen lang, gemessen).
