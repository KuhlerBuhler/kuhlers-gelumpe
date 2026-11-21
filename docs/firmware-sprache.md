# Firmware-Sprache: Menüs auf Deutsch

Deutsch als zweite Sprache der Menüs (das BLECH-Menü und Korgs Menüs) kommt über den optionalen Patch `lang-de`, eine
Fassung je Build (Hacktribe, Korgs rote 2.02, blaue Electribe). Ohne `lang-de` bleibt alles Englisch. Diese Seite
beschreibt die Daten, die Regeln für die Texte und die Werkzeuge. Stand: das BLECH-Menü und Korgs Hauptmenüs
(GLOBAL PARAMETER, DATA UTILITY, Pattern- und Part-Seiten) sind übersetzt, dazu Dialoge, Meldungen, Skalennamen und die Namen der Effektparameter.

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
| `length` | Länge der alten Kette in Byte, ohne Null |
| `pointers` | die Zeigerwörter auf die Kette, je `at` (Adresse) und `expect` (SHA-256 des alten Worts) |
| `fonts` | Schriften, in denen die Firmware die Kette zeichnet (0 bis 3; Schrift 2 hat keine Umlaute) |
| `buffer` | Größe des Puffers, in den die Firmware die Kette kopiert, mit Null; `"string"`, wenn jeder Leser sie in einen wachsenden C++-String kopiert |
| `space` | optional: Platz der Zeile in Pixeln |
| `inPlace` | `true` bei einem Namensfeld eines Effektparameters: ohne Zeigerwort, der Text steht an Ort und Stelle, mit Null bis zur alten Länge aufgefüllt |

`expect`, `length`, `fonts` und `pointers` schreibt die Werkbank (`--update`), `text`, `keep` und `buffer` kommen von
Hand. Ein deutscher Text länger als `length` braucht ein gemessenes `buffer`, sonst lehnt der Unit-Test ihn ab.
`korg-stock.json` und `korg-synth.json` übernehmen Text, `keep`, `buffer` und `inPlace` aus `korg-hacktribe.json`, wo die
alte Kette gleich ist (gleicher SHA-256): zuerst an derselben Adresse, sonst an der ersten mit gleicher Kette. Ein
`inPlace`-Eintrag geht nur an dieselbe Adresse, denn gleicher Text heißt dort nicht gleiches Feld.

## Kürzungsregel

Gilt für jeden deutschen Text, BLECH und Korg gleich. Die erste Stufe, die passt, gewinnt:

1. **Aufgedruckte und eingeführte Begriffe bleiben Englisch:** alles, was auf dem Gerät steht (PATTERN, PART, MFX, IFX,
   EDIT, WRITE, SHIFT, EXIT, MENU, PLAY, REC, STOP, TAP, KEY, SCALE, TRIGGER, SEQUENCER, MOTION, CHAIN), und Fachwörter,
   die Musiker so sagen (Sample, Loop, Swing, Gate, Pitch, Pan, Cutoff, Resonance, Attack, Decay, Release, Groove,
   Plugin, MIDI, BPM). Die Liste steht in `de-glossar.json` unter `keepEnglish`. So passt die Bedienungsanleitung weiter.
2. **Kürzeres Wort statt Abkürzung:** "Import" statt "Importieren", "Kopie" statt "Kopieren", "Laden" statt "Einlesen".
3. **Abkürzung nur aus der Liste** `de-abk.json`. Eine neue Abkürzung kommt erst in die Liste, dann in den Text. Ein
   Wort mit Punkt, das nicht in der Liste steht, lehnt der Unit-Test ab; ein Punkt am Textende und `...` sind keine
   Abkürzungen. Groß- und Kleinschreibung zählt nicht (`EINST.` in einem Titel ist `Einst.`).
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
Der Startbildschirm zeichnet schon Text, darum sind das Tabellenwort und die Kopie jeder Schrift als `startPhase`
ausgewiesen.

Gemessen im Emulator auf allen drei Builds: jeder Umlaut hat Breite und Pixel, alle ASCII-Zeichen haben dieselbe
Breite wie ohne die Kopie, keine Zusicherung.

## BLECH-Menü

Jeder Text des BLECH-Menüs, den `blech.json` mit `text` übersetzt, wird in der Laufzeit nicht mehr direkt geladen, sondern
über eine Nummer aus einer Texttabelle, deren Anfang im RAM-Wort `LANG_TEXTS` steht (`tools/patch/lang_texts.py`).
Die Nummern folgen den Labels, ihr SHA-256 ist der Schlüssel der Laufzeit. `lang_arm` läuft in `menu_arm_load`: steht am
Anfang des Sprachbereichs ein Kopf (Tabelle, Anzahl, Schlüssel), der zu dieser Laufzeit passt, zeigt `LANG_TEXTS` auf
die deutsche Tabelle, sonst auf die englische der Laufzeit. Ein `lang-de` aus einem anderen Build der Laufzeit lässt das
Menü also Englisch, statt falsche Texte zu zeigen. Darum baut `tools/patch/ensure-runtime.mjs` `lang-de` zusammen mit
der Laufzeit (`tools/lang/lang_patch.mjs`); beide sind gebaut, nicht committet.

Ein Label ohne Eintrag in `blech.json` bricht den Build ab. Noch direkt geladen und darum Englisch sind die Texte, die
nicht in `script_menu.s` stehen (Startbild-Titel, Fehlertexte der Samples, Pad-Farben, Pattern-Wechsel, `[User]`).

## Korgs Menüs

Jeder Text auf Korgs Seiten ist eine Vorlage im Code (Hacktribe und rot `0xC00A3000` bis `0xC00A8000`, blau
`0xC008E000` bis `0xC0093000`), die die Firmware über ein Zeigerwort lädt und zeichnet oder in ein Widget kopiert.
`lang-de` legt die deutsche Kette in den Sprachbereich und biegt jedes Zeigerwort dorthin (`expect` = SHA-256 des alten
Worts); die englische Vorlage bleibt unverändert.

Gemessen im Emulator (Lese-Haken auf die deutschen Ketten, alle Bildschirme): die Ketten lesen nur die Textfunktion,
`strcpy` der Widget-Setter und das Anhängen an C++-Strings. Verglichen wird nur in SET_VALUE und SET_LINE3 (alter gegen
neuen Wert), nie nach Inhalt. Die Puffer:

| Leser | Puffer |
|---|---|
| Titel `0xC00857E4` (Widget `+0x6c`) | 32 Byte |
| Zeile 3 `0xC0085888` (Widget `+0xac`) | 28 Byte (Heap-Block 0xd0, gemessen am Objekt) |
| Dialogtext `0xC008CB10`, `0xC008CB54` (Objekt `+0x4c`) | 64 Byte |
| `0xC007E2F0` nach `0xC069133C` | 17 Byte (sonst `strncpy` 16 plus Null) |
| Fehlertabelle `0xC00E3280` (35 Ketten, Warnungsdialog um `0xC0063130`) | 64 Byte: derselbe Aufruf `0xC008CCD4` wie die Ersatzkette für unbekannte Fehler, deren Kopie gemessen ist (aus dem Code hergeleitet) |
| `0xC00A2570`, `0xC00A2A78`, `0xC00A26C0`, `0xC00A2B9C` (Zuweisen und Anhängen) | C++-String, wächst (`"string"`) |

Korg löscht eine Dialogzeile vor dem Neuzeichnen mit einem Rechteck, das aus den Glyphen des neuen Texts folgt und eine
Zeile zu kurz ist: die Grundlinie bleibt stehen. Nur ein Leerzeichen oder eine Unterlänge (g, p, q, y) macht das
Rechteck tief genug. Fast jeder englische Text hat eines davon; ein einzelnes deutsches Wort wie "Werkszustand" nach
"Formatieren" ließe deren Grundlinie stehen, darum "Werkseinstellung". Die Layout-Prüfung findet solche Fälle.

Einige Startbildschirme lesen Korg-Zeigerwörter und ihre Ketten schon beim Start (gemessen mit `check.py --quick`:
zwei Wörter auf Hacktribe und rot, eins auf blau). `lang-de` nennt darum alle Korg-Zeigerwörter und den Block der
deutschen Korg-Ketten als Spans der Startphase.

## App

Schritt 2 des Patchers zeigt "Gerätemenüs auf Deutsch" neben dem Gerätenamen. Die App legt die Fassung für das Build der Datei dazu, auch auf eine mitgebrachte `BLECH.patch`. Passt `lang-de` nicht
(fremde Datei), sagt die Planzeile, dass es nur auf BLECHs eigene Dateien passt. Beim Update erkennt die App `lang-de`
an den Wörtern der Schrifttabelle (`data/known-releases.json`, `tools/known-releases.mjs`) und legt es wieder dazu: eine
englische Datei bleibt Englisch, eine deutsche Deutsch.

## Werkzeuge

```bash
node tools/lang/glyphs.mjs --check
node tools/lang/glyphs.mjs --facts hacktribe=HT.VSB stock=RED.VSB synth=BLUE.VSB
node tools/patch/ensure-runtime.mjs --force
tools/emu/.venv/bin/python tools/emu/lang_cases.py cases --patched NEW.VSB
tools/emu/.venv/bin/python tools/lang/workbench.py --vsb ORIGINAL.BIN
```

`workbench.py --update` schreibt die Fakten jeder gefundenen Vorlage in `korg-<build>.json`.

`glyphs.mjs --check` prüft das Pixelbild allein (alle sieben Buchstaben, Höhe in der Schrift, keine zwei gleich),
`--facts` misst Schriftköpfe und Grundbuchstaben der eigenen Dateien nach `data/lang/fonts.json` (nur Adressen und
Prüfsummen). `ensure-runtime.mjs` baut Laufzeit und `lang-de` für alle drei Builds. `lang_cases.py` prüft eine
gepatchte Datei im Emulator: mit `lang-de` sind alle BLECH-Seiten auf Deutsch sauber (nichts über dem Rand, keine
Überlappung), die Umlaute zeichnen sich, und drei Seiten zeigen Deutsch; ohne `lang-de` zeigen sie Englisch. Auf Korgs
Bildschirmen 0 bis 44 (32 Raststufen, 32 Mal EDIT) zeigt jedes Zeigerwort einer übersetzten Kette auf ihre deutsche
Kopie, keine englische Vorlage einer übersetzten Kette wird gezeichnet, kein deutscher Text läuft über den Rand oder
über einen anderen Text (Besitz je Pixel über die Haken auf Text- und Pixelfunktion; eine Überlappung, die die
englische Fassung derselben Datei genauso zeigt, ist Korgs eigene und zählt nicht), und keine Kopie ist länger als ihr
Puffer. Die Texte, die diese Bildschirme nicht erreichen (Dialoge, Meldungen, Fehler: Einträge ohne `fonts`), passen
in Schrift 0 und 1 auf die 128 Pixel oder sind nicht breiter als die englische Kette, und ein Dialogtext (Puffer 64)
behält ein Leerzeichen oder eine Unterlänge, wo die englische Kette eine hat; die Namensfelder der Effektparameter (`inPlace`) stehen deutsch und gleich lang im Datensatz. Ohne `lang-de` ist
jedes Zeigerwort und jedes Namensfeld das alte. Die Texte ohne `fonts` prüft erst der Gerätedurchgang am Bildschirm. `check.py` führt die Fälle für jede Datei mit BLECH-Menü aus.

Die Werkbank liest die eigene Firmware, zeigt im Emulator alle Bildschirme 0 bis 44, dreht auf jedem 32 Raststufen und
blättert 32 Mal mit EDIT und notiert dabei jeden gezeichneten Text mit Schrift. Daraus sucht sie Korgs Vorlagen (Ketten,
deren Teile ohne Platzhalter in gezeichneten Texten vorkommen), ihre Zeigerwörter und Breiten, und legt sie neben die
deutschen Einträge aus `korg-<build>.json`. Sie meldet Vorlagen ohne Eintrag und Texte, die breiter sind als ihr Platz;
für die Breite zählt ein Umlaut vorläufig wie sein Grundbuchstabe. Auf Hacktribe findet sie 191 Menüvorlagen mit 247
Zeigerwörtern und 71 Effektparameter (gemessen, rund eine Minute). Die blaue Electribe hat ihre Texte an anderen
Adressen (Abschnitt Korgs Menüs). Die Ausgabe liegt in `.lang-work/` und enthält Korgs Text: der Ordner ist von
Git ausgenommen und wird nie committet.
