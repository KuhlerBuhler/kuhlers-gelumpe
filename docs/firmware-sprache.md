# Firmware-Sprache: Menüs auf Deutsch

Deutsch als zweite Sprache der Menüs (das BLECH-Menü und Korgs Menüs) kommt über den optionalen Patch `lang-de`, eine
Fassung je Build (Hacktribe, Korgs rote 2.02, blaue Electribe). Ohne `lang-de` bleibt alles Englisch. Diese Seite
beschreibt die Daten, die Regeln für die Texte und die Werkzeuge. Stand: Speicher, Datenformat, Regeln, Umlaute und
Werkbank stehen, der Patch `lang-de` und die Auswahl in der App sind noch nicht gebaut.

## Was nicht ins Repository kommt

Korgs englische Texte und Hacktribes Bytes stehen nirgends im Repository. Die Sprachdateien tragen nur Adressen,
Prüfsummen der alten Bytes und die deutschen Texte. Wo `lang-de` Firmware-Bytes braucht (Schriftkopf, Glyphenfeld),
kopiert ihn eine `copy`-Änderung beim Anwenden aus der Datei des Nutzers ([Patcher](patcher.md)). Ein Unit-Test lehnt
jeden Schlüssel `en` oder `english` in `data/lang/` ab.

## Speicher

`lang-de` schreibt seine Texte, Tabellen und Glyphen in den Sprachbereich `[0xC016C000, 0xC0170000)`, die oberen 16 KiB
der Code-Fläche MORE3. Der Bereich ist in allen drei Builds `0xFF`; der Code der Laufzeit endet davor
(`tools/patch/script_hooks.py:LANG`, [Speicherbereiche](speicherbereiche.md)). Die Glyphen belegen davon 1824 Byte
(gemessen mit `tools/lang/glyphs.mjs` auf allen drei Builds).

## Dateien

| Datei | Inhalt |
|---|---|
| `data/lang/de/blech.json` | BLECH-Menü: Schlüssel ist das Label des Texts im Quelltext (z. B. `str_pdel`) |
| `data/lang/de/korg-<build>.json` | Korgs Menüs je Build: Schlüssel ist die Adresse der Vorlage |
| `data/lang/de-abk.json` | erlaubte Abkürzungen: Kurzform, Langform, Beispiel |
| `data/lang/de-glossar.json` | Begriffe mit genau einer deutschen Fassung, dazu die Wörter, die Englisch bleiben |
| `data/lang/glyphs/font<n>.json` | `ÄÖÜäöüß` für die Schriften 0, 1 und 3 als Pixelbild (`#` Tinte, `.` leer, oberste Zeile zuerst) |

Ein Eintrag hat entweder `text` (Deutsch) oder `keep` (Grund, warum die Zeile Englisch bleibt). Optional nennt
`glossar` die Begriffe aus dem Glossar, die der Text enthält. Ein Eintrag in `korg-<build>.json` hat dazu:

| Feld | Inhalt |
|---|---|
| `expect` | SHA-256 der alten Kette samt Null |
| `pointers` | die Zeigerwörter auf die Kette, je `at` (Adresse) und `expect` (SHA-256 des alten Worts) |
| `font` | Schrift der Zeile: 0, 1 oder 3 |
| `space` | Platz der Zeile in Pixeln, gemessen im Emulator |
| `buffer` | Größe des Puffers, in den die Firmware die Vorlage kopiert oder formatiert, oder `null` |

## Kürzungsregel

Gilt für jeden deutschen Text, BLECH und Korg gleich. Die erste Stufe, die passt, gewinnt:

1. **Aufgedruckte und eingeführte Begriffe bleiben Englisch:** alles, was auf dem Gerät steht (PATTERN, PART, MFX, IFX,
   EDIT, WRITE, SHIFT, EXIT, MENU, PLAY, REC, STOP, TAP, KEY, SCALE, TRIGGER, SEQUENCER, MOTION, CHAIN), und Fachwörter,
   die Musiker so sagen (Sample, Loop, Swing, Gate, Pitch, Pan, Cutoff, Resonance, Attack, Decay, Release, Groove,
   Plugin, MIDI, BPM). Die Liste steht in `de-glossar.json` unter `keepEnglish`. So passt die Bedienungsanleitung weiter.
2. **Kürzeres Wort statt Abkürzung:** "Import" statt "Importieren", "Kopie" statt "Kopieren", "Laden" statt "Einlesen".
3. **Abkürzung nur aus der Liste** `de-abk.json`. Eine neue Abkürzung kommt erst in die Liste, dann in den Text. Ein
   Wort mit Punkt, das nicht in der Liste steht, lehnt der Unit-Test ab; ein Punkt am Textende und `...` sind keine
   Abkürzungen.
4. **Gleich überall:** ein Begriff hat genau eine deutsche Fassung (`de-glossar.json`). Nennt ein Eintrag den Begriff
   in `glossar`, muss der Text diese Fassung oder ihre gelistete Abkürzung enthalten.
5. **Letzter Ausweg: Englisch lassen,** als `keep` mit Grund. Kein Text wird abgeschnitten.

"Passt" heißt: die Breite mit der Textbreite der Firmware (`0xC003F89C`) in der Schrift der Zeile ist höchstens der
Platz der Zeile, und die gezeichnete Seite hat keine Überlappung und nichts über den Rand. Maß ist der Platz, nicht
die englische Länge. Platzhalter wie `%d` und `%s` bleiben in Zahl und Reihenfolge gleich.

## Umlaute

Die Textfunktion liest Zeichen mit `ldrsb`, ein Latin-1-Umlaut kommt also als negative Zahl an (`Ä` = -60), und die
Glyphensuche vergleicht vorzeichenbehaftet. `lang-de` gibt den Schriften 0, 1 und 3 eine Kopie ihres Kopfs mit sieben
Glyphen mehr und ein neues Feld, in dem die Umlaute mit ihren negativen Codes vorne stehen und die alten Zeiger
dahinter; das Wort der Schrift in der Schrifttabelle (`0xC00C2818`, blau über `data/synth-map/`) zeigt auf die Kopie.
Korgs Glyphen bleiben unverändert. Abstand und Grundlinie nimmt ein Umlaut von seinem Grundbuchstaben (`ß` von `b`).
Das Tabellenwort wird beim Start gelesen und ist darum als `startPhase` ausgewiesen.

Gemessen im Emulator auf allen drei Builds: jeder Umlaut hat Breite und Pixel, alle ASCII-Zeichen haben dieselbe
Breite wie ohne die Kopie, keine Zusicherung.

## Werkzeuge

```bash
node tools/lang/glyphs.mjs --check
node tools/lang/glyphs.mjs --vsb SYSTEM.VSB
tools/emu/.venv/bin/python tools/lang/workbench.py --vsb ORIGINAL.BIN
```

`glyphs.mjs --check` prüft das Pixelbild allein (alle sieben Buchstaben, Höhe in der Schrift, keine zwei gleich),
`--vsb` baut die Änderungen für eine Datei und nennt ihre Größe.

Die Werkbank liest die eigene Firmware, zeigt im Emulator alle Bildschirme 0 bis 44, dreht auf jedem 32 Raststufen und
blättert 32 Mal mit EDIT und notiert dabei jeden gezeichneten Text mit Schrift. Daraus sucht sie Korgs Vorlagen (Ketten,
deren Teile ohne Platzhalter in gezeichneten Texten vorkommen), ihre Zeigerwörter und Breiten, und legt sie neben die
deutschen Einträge aus `korg-<build>.json`. Sie meldet Vorlagen ohne Eintrag und Texte, die breiter sind als ihr Platz;
für die Breite zählt ein Umlaut vorläufig wie sein Grundbuchstabe. Auf Hacktribe findet sie 191 Menüvorlagen mit 247
Zeigerwörtern und 71 Effektparameter (gemessen, rund eine Minute). Die blaue Electribe hat ihre Texte an anderen
Adressen und ist noch nicht vermessen. Die Ausgabe liegt in `.lang-work/` und enthält Korgs Text: der Ordner ist von
Git ausgenommen und wird nie committet.
