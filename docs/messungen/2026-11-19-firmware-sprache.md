# Firmware in einer anderen Sprache: Texte, Verweise, Schriften, Aufwand

Stand 2026-11-19. Frage: lassen sich die Menüs der Firmware (Sampler 2.02 mit Hacktribe, dazu das BLECH-Menü)
auf Deutsch umstellen, gewählt beim Installieren in App und Patcher? Nur Recherche, keine Firmware gebaut, am Gerät
nichts gemacht. Basis ist die eigene Hacktribe-Datei (`ORIGINAL.BIN`, SHA-256 `163d1d8d…`) und zum Vergleich Korgs rote
2.02. Marker: **gemessen** (im Emulator ausgeführt), **offline** (Code oder Daten gelesen), **hergeleitet**,
**geschätzt**, **offen**. Adressen sind RAM-Adressen, Datei-Offset = RAM - `0xC0000000` + `0x100`. Hier stehen keine
Firmware-Bytes, nur Zahlen und Adressen; die Skripte liefen außerhalb des Repos.

Grundlage für Schriften und Zeichenweg: [Display: Schriften und Symbole](2026-10-14-display-schriften.md).

## Kurz

- Korgs sichtbare Menütexte liegen fast alle in einem Block (`0xC00A3000` bis `0xC00A8000`) und werden über
  Zeigerwörter gefunden, meist in Zeigertabellen. Ein Text lässt sich in unseren Platz verlegen, indem man seine
  Zeigerwörter umbiegt. **gemessen/offline**
- Umlaute zeichnet heute keine Schrift, auch Schrift 2 nicht, obwohl sie Latin-1-Glyphen hat. Ein eigener Glyph mit
  negativem Zeichencode, vorne in eine Kopie des Schriftfelds gelegt, wird ohne jeden Code-Patch gezeichnet. **gemessen**
- Deutsche Texte sind an zehn Beispielen 6 bis 32 % breiter als die englischen, meist rund 25 %; Titel stoßen bei 128 Pixeln schnell an. Der Aufwand
  steckt im Kürzen und Prüfen, nicht im Umbiegen. **gemessen** an Beispielen
- Für 1.4.8 passt höchstens das BLECH-Menü mit Umlauten. Das hilft jemandem ohne Englisch wenig, die meisten Seiten sind Korgs
  Menüs. Empfehlung unten.

## 1. Korgs Texte: wo, wie viele, wie verwiesen

### Bereiche

**Offline**, Ketten ab zwei druckbaren Zeichen mit Null am Ende, Zeigerwörter = jedes ausgerichtete Wort der Datei,
das genau auf den Anfang einer Kette zeigt:

| Bereich | Inhalt (gelesen) | Ketten | Zeichen | mit Zeiger | Zeigerwörter |
|---|---|---:|---:|---:|---:|
| `0xC00A3000` bis `0xC00A8000` | Menütitel, Parameter, Werte, Meldungen, Skalen, Testmodus, Debug-Texte und Pfade gemischt | 781 | 8387 | 677 | 955 |
| `0xC00DA000` bis `0xC00DC000` | Namen der Werks-Samples in festen Datensätzen | 231 | 2358 | 0 | 0 |
| `0xC011F000` bis `0xC0124000` | Effektparameter, feste Datensätze (`Dry:Wet`, `Tap1 Level`, `95.0%`) | 1284 | 10416 | 1 | 15 |

In Korgs roter 2.02 liegen dieselben drei Bereiche an denselben Adressen (781 / 256 / 1284 Ketten, **offline**);
der dritte Bereich ist Korgs Effekttabelle, kein Hacktribe-Code (die Schriften-Messung ordnet ihn Hacktribe zu).
Im ersten Bereich sehen 56 Ketten nach Debug oder Testmodus aus (`.cpp`, `Check`, `%08x`), **offline**, grob gefiltert.

### Was der Bildschirm wirklich zeigt

**Gemessen:** Haken auf die Textfunktion `0xC003F7D0`, alle Bildschirme 0 bis 44 je einmal über `0xC0083D28`
aufgerufen, dann 32 Raststufen am Rad und 32 Mal EDIT nach rechts. Dabei kamen 539 verschiedene Texte an die
Textfunktion (Schrift 0: 285, 1: 233, 3: 184, 2: 77).

- **Kein einziger** dieser Texte kam direkt aus der Firmware-Datei. Der Zeiger zeigt immer auf einen Puffer im RAM:
  die Firmware kopiert oder formatiert erst (`Pitch:` plus Wert, `ModType: EG+ Fil..`). Ein Text in der Firmware
  ist also eine Vorlage, Formatketten wie `MFX:%s` eingeschlossen. **gemessen**
- Vorlagen, deren Teile (ohne `%`-Platzhalter, ab 3 Zeichen) in den gezeigten Texten vorkommen: 281 Ketten mit
  2374 Zeichen. Davon 191 im ersten Bereich (1963 Zeichen, längste 27 Zeichen) und 76 Effektparameter. **gemessen**
- Die 191 Menüketten haben 247 Zeigerwörter: 217 stehen in Tabellen (ein Nachbarwort zeigt auch auf eine Kette des
  Bereichs), 30 einzeln (Literal hinter Code). 23 Ketten haben mehr als einen Zeiger. Nur eine (`MFX:%s`) hat keinen
  eigenen Zeiger, sie ist das Ende einer längeren Kette. **gemessen/offline**
- Die Effektparameter haben keine Zeiger, sie liegen als Felder in festen Datensätzen und werden über Nummer mal
  Satzlänge gefunden. **offline** Verlegen geht dort nicht über Zeiger, nur in gleicher Länge an Ort und Stelle.

Beispiele der gezeigten Vorlagen: `GLOBAL PARAMETER`, `DATA UTILITY`, `FACTORY RESET`, `COPY PART`, `GATE TIME`,
`EXPORT PATTERN`, `VOICE ASSIGN`, `Pattern Top`, `press  [ Enter ]`, `Working...`, `No File`, `Pitch:`, `Swing:`,
`1: Touch Bottom Left`, `Write All Data`.

**Grenzen der Messung:** nur was die 45 Bildschirme beim Drehen und Blättern zeigen, ohne Dialoge nach WRITE, ohne
Sampling, ohne Fehlerfälle beim Import, ohne Karte voll und ohne Testmodus. Die Zahl der sichtbaren Menüketten liegt
darum über 191; **geschätzt** 300 bis 400 von den 781 (ohne Debug, Pfade und Testmodus).

### Verlegen in unseren Platz

Die Firmware läuft aus dem RAM, Tabellen und Literale sind dort Wörter wie alle anderen. Eine deutsche Kette kann
also in unseren Code-Platz und ihre Zeigerwörter auf sie zeigen. **hergeleitet** aus den Zeigerzahlen oben.

- Je sichtbarer Kette im Mittel 1,3 Zeigerwörter (247 / 191). Für die gemessenen 191 sind das 247 Wörter zu je
  4 Byte, also eine reine Datenänderung mit Prüfsumme der alten Bytes, wie jede rohe Änderung im
  [Patcher](../patcher.md).
- Eine kürzere oder gleich lange Übersetzung kann auch an Ort und Stelle stehen (dann gar kein Zeiger), muss aber
  die Null am Ende innerhalb des alten Platzes behalten. Bei Deutsch ist das die Ausnahme (siehe 2).
- **Offen:** die Puffer, in die die Firmware kopiert oder formatiert, haben feste Größen, die hier nicht gemessen
  sind. Eine längere Vorlage kann so einen Puffer überlaufen lassen. Jeder verlängerte Text braucht einen Emulatorlauf,
  der die Seite zeigt und auf Zusicherungen und RAM-Schreibzugriffe hinter dem Puffer achtet.
- **Offen:** ob irgendwo Code Texte nach Inhalt vergleicht (z. B. `strcmp` gegen `"OFF"`). Dann würde eine
  Übersetzung das Verhalten ändern. Nicht gesucht.
- Für die blaue Electribe (Synth-Build) liegen die Ketten an anderen Adressen; jede Stelle braucht dort einen eigenen
  Eintrag (wie `data/synth-map/`). Nicht gemessen.

## 2. Breite und Schriften

### Umlaute

**Gemessen** mit `0xC003F89C` (Textbreite) und `0xC003F7D0` (zeichnen) in allen vier Schriften:

| Schrift | Breite `A` | Breite `Ä` | Pixel von `Ä` | `MÄDCHEN` gegen `MDCHEN` |
|---:|---:|---:|---:|---|
| 0 | 7 | 0 | 0 | gleich breit (37) |
| 1 | 8 | 0 | 0 | gleich breit (52) |
| 2 | 6 | 0 | 0 | gleich breit (36) |
| 3 | 7 | 0 | 0 | gleich breit (44) |

Ein Umlaut wird übersprungen, auch in Schrift 2, die Glyphen für 160 bis 255 hat. Grund (**offline**): Text,
Textbreite und Kerning lesen jedes Zeichen mit `ldrsb` (vorzeichenbehaftet, `0xC003F7FC`, `0xC003F868`,
`0xC003F8C4`); `Ä` (0xC4) wird zu -60, die binäre Suche in `0xC003F74C` vergleicht vorzeichenbehaftet mit den
Codes im Feld und findet -60 nie. Die Latin-1-Glyphen der Schrift 2 sind über den normalen Textweg nicht erreichbar.

**Weg ohne Code-Patch, gemessen:** im RAM eine Kopie des Kopfs der Schrift 0 mit Anzahl + 1, ein neues Feld mit
einem eigenen Beschreiber vorne (Code -60, Vorschub 6, eigene 5 x 8 Bitmap, nicht von Korg) und dahinter den alten
Zeigern, dann das Wort der Schrift 0 in der Schrifttabelle `0xC00C2818` auf die Kopie. Ergebnis: `Ä` 6 Pixel breit,
18 Pixel gezeichnet, `MÄD` 20 statt 14, `A` unverändert 7, keine Zusicherung. Die Suche bleibt sortiert, weil
negative Codes vor Code 0 und 32 stehen.

Für Deutsch hieße das je Schrift 0, 1 und 3 sieben neue Glyphen (`ÄÖÜäöüß`, Codes -60, -42, -36, -28, -10, -4,
-33), selbst gezeichnet, ein neuer Kopf (16 Byte), ein neues Feld (4 Byte je Zeichen, 98 + 7 bzw. 95 + 7) und vier
Wörter in der Schrifttabelle. **Geschätzt** zusammen unter 1,5 KiB. Schrift 2 (Namenseingabe, Zielwahl) braucht
nichts, dort stehen Namen, die der Nutzer tippt. ae/oe/ue wäre ohne jede Schriftänderung möglich, macht die Texte aber
noch länger (`ZIEL WAEHLEN` 74 Pixel gegen `ZIEL WÄHLEN` 61, Schrift 3, **gemessen**, mit `Ä` als 0 gezählt also
eher 68). Mit diesem Befund sehe ich keinen Grund für ae/oe/ue.

Die Startphase liest Glyphen der Schriften 0, 1 und 3 (siehe Schriften-Messung). Die Kopie lässt die alten
Glyphen in Ruhe, aber das umgebogene Tabellenwort wird beim Start gelesen: der Patch braucht eine
`startPhase`-Ausnahme wie das Startbild. **hergeleitet**

### Breite

Breiten mit der Textbreite der Firmware, **gemessen** (Umlaute zählten hier 0, die echten Texte werden also
4 bis 7 Pixel je Umlaut breiter):

| Schrift | Englisch | Pixel | Deutsch | Pixel |
|---:|---|---:|---|---:|
| 3 | `GLOBAL PARAMETER` | 108 | `GLOBALE EINSTELLUNGEN` | 137 |
| 3 | `SOFTWARE UPDATE` | 102 | `FIRMWARE AKTUALISIEREN` | 135 |
| 3 | `IMPORT PATTERN` | 94 | `PATTERN IMPORTIEREN` | 123 |
| 3 | `COPY PART SOUND` | 102 | `PART-KLANG KOPIEREN` | 127 |
| 3 | `EXPORT ALL PLUGINS` | 113 | `ALLE PLUGINS SICHERN` | 120 |
| 3 | `LOOP START POINT` | 104 | `LOOP-STARTPUNKT` | 110 |
| 0 | `Ptn Change Locked.` | 91 | `Patternwechsel gesperrt.` | 113 |
| 0 | `Decay/Release:127` | 90 | `Abklingen/Ausklingen:127` | 117 |
| 1 | `Enter = remove` | 97 | `Enter = entfernen` | 114 |
| 1 | `file stays on card` | 110 | `Datei bleibt auf Karte` | 138 |

Das Display hat 128 Pixel, und auf Korgs Seiten teilt sich der Titel die Zeile oft mit Reiter oder Seitenzähler
(Platz je Zeile nicht einzeln gemessen, **offen**). Viele direkte Übersetzungen passen nicht; jede deutsche Zeile muss gekürzt und im Emulator gegen den
echten Platz geprüft werden. Fachwörter, die auf dem Gerät aufgedruckt sind (PATTERN, PART, MFX, IFX, EDIT, WRITE,
SHIFT), bleiben besser englisch, dann passt auch die Bedienungsanleitung noch.

## 3. Das BLECH-Menü

**Offline**, `tools/patch/` auf develop `8f8953d3`:

- Die Texte stehen als `.asciz` im Quelltext, der Assembler (`tools/patch/arm.py`) schreibt sie als Latin-1. Ohne
  Pfade und Dateinamen sind es rund 225 Texte mit rund 2000 Zeichen, davon 146 in `script_menu.s`, 28 in
  `script_migrate.s`, 13 in `script_shortcuts.s`, der Rest verstreut (`sample_errors.py`, `pad_colors.py`,
  `blech_sysex.py`, `script_calibrate.s` und andere). Längster Text 25 Zeichen.
- In `script_menu.s` holen 129 Stellen einen Text mit `ldr rX, =str_…` (Literal), dazu 7 Tabellen `.word str_…`
  (z. B. die Farbnamen der Pad-Farben).
- Platz auf den Seiten (siehe [BLECH Menü](2026-10-14-blech-menue.md)): Titel rund 18 Zeichen in Schrift 3, Wert
  rund 14 Zeichen in Schrift 1. Der Fall `menu:pages_are_clean` prüft schon jetzt jede Seite auf Überlappung und
  Rand. Er würde für eine deutsche Fassung genauso greifen.

Zwei Wege, eine zweite Sprache zu wählen:

1. **Beim Bauen:** der Generator ersetzt die Texte aus einer Datei `data/lang/de.json` (Schlüssel = Label, z. B.
   `str_pdel`), der Assembler baut daraus eine zweite Fassung des Patches. Einfach, aber jede Sprache ist eine eigene
   Patch-Datei je Build (rot, Hacktribe, blau), und weil der Code hinter längeren Texten wandert, unterscheiden sich
   die Fassungen auch im Code. Das verdoppelt `known-releases.json` und die Prüfungen. **hergeleitet**
2. **Zur Laufzeit (empfohlen):** alle Texte bekommen eine Nummer, `ldr rX, =str_…` wird zu einem Aufruf
   `menu_text(n)`, der aus der Tabelle der gewählten Sprache liest. Englisch und Deutsch liegen beide im Patch
   (geschätzt 2 x 2 KiB plus 2 x 225 x 4 Byte Tabellen, also rund 6 KiB), ein Byte in den BLECH-Einstellungen wählt.
   Der Code ist für alle Sprachen gleich, nur die Daten wachsen. Die App setzt das Byte beim Installieren als
   Vorgabe, eine Seite LANGUAGE in CUSTOMIZATION kann es später umstellen. **hergeleitet**, nicht gebaut.

Ob rund 6 KiB plus Schriften in unseren Code-Platz passen, ist nicht gemessen (**offen**); die Reserven stehen in
der [Speicherkarte](../speicherbereiche.md).

Korgs Texte ließen sich auf dieselbe Art zur Laufzeit umschalten: ein Haken nach dem Start schreibt die 247 (oder
mehr) Zeigerwörter auf die deutschen Ketten, wenn das Sprachbyte es sagt. Dann wäre es ein Patch für alle, kein
eigener Build je Sprache. **hergeleitet**, die Startphase bliebe unberührt, weil erst nach dem Laden der
Einstellungen umgebogen wird.

## 4. Wahl beim Installieren und Prüfungen

**Einbau in den Patcher (offline gelesen, hergeleitet):** Vorbild ist das Häkchen Gerätename (`usb-name`) in
Schritt 2 der Seite Patcher: ein optionaler Patch je Build, der zum Set dazukommt. Eine Sprache wäre eine Auswahl
daneben ("Sprache der Menüs: Englisch / Deutsch"). Mit dem Laufzeitweg aus 3 schreibt sie nur das Vorgabebyte,
der Rest des Sets bleibt gleich; so bleibt eine Datei mit BLECHTRIBE über `known-releases.json` aktualisierbar und
eine andere Wahl macht keine zweite Prüfung der ganzen Firmware nötig. Dazu Texte in der App, Notes, Doku
(`docs/patcher.md`, Abschnitt Die Seite Patcher).

**Was CI und Emulator prüfen müssten:**

- Je Sprache jede BLECH-Seite: `menu:pages_are_clean` mit gesetztem Sprachbyte (Überlappung, Rand).
- Je übersetzter Korg-Kette: die Breite mit `0xC003F89C` in ihrer Schrift gegen den Platz ihrer Zeile, und die Seite
  einmal zeichnen lassen ohne Zusicherung; dazu ein RAM-Wächter hinter den Formatpuffern (Überlauf, siehe 1).
- Jeder Text der Sprachdatei nur aus Zeichen, die die Schriften haben (ASCII plus die sieben neuen Glyphen),
  ein Unit-Test ohne Emulator.
- Glyphen: jeder neue Glyph wird gezeichnet (Breite > 0) und `A` bis `z` bleiben byte-gleich in Breite und Pixeln.
- Die vielen bestehenden Fälle, die englische Texte vergleichen (in `menu_cases.py` allein 148 Stellen mit Titel
  oder Wert), laufen weiter mit Englisch; die deutsche Fassung bekommt nur die Breiten- und Zeichenfälle, keine
  Kopie aller Fälle.
- Startphase: die Ausnahme für das Wort in der Schrifttabelle, sonst nichts in der Startphase.

## 5. Aufwand

Alles **geschätzt**, in Arbeitstagen, ohne Gerätetest, Deutsch als erste Sprache, nur rote Builds (blau: je Teil
etwa ein Drittel dazu für die Adressen).

| Teil | Inhalt | Aufwand |
|---|---|---|
| (a) BLECH-Menü | Texte nummerieren und Laufzeittabelle (225 Texte, 129 Literale, 7 Tabellen), Sprachbyte und Seite LANGUAGE, Umlaut-Glyphen in Schrift 0/1/3 mit Generator, deutsche Texte kürzen bis `pages_are_clean` grün ist, App-Auswahl, Tests | 4 bis 6 |
| (b) Korgs Hauptmenüs | dazu: alle sichtbaren Vorlagen finden (Dialoge, Fehler, WRITE, Sampling, die gemessenen 191 sind nur ein Teil), übersetzen und kürzen, Zeigerwörter umbiegen (Haken nach dem Start), Puffergrößen prüfen, Breitenfall je Kette | 6 bis 10 mehr |
| (c) alles | dazu: Effektparameter in festen Datensätzen (nur gleich lang an Ort und Stelle), Skalen- und Akkordnamen, Testmodus, Hacktribe-eigene Texte, blauer Build voll | 6 bis 10 mehr |

Für (b) ist das Umbiegen der kleine Teil; das Meiste ist Übersetzen in 128 Pixel und das Prüfen jeder Seite. Am Gerät
braucht es danach einen Durchgang durch alle Menüs.

## 6. Empfehlung für 1.4.8

1.4.8 ist ein Fix-Release. Firmware-Sprache gehört nicht hinein:

- (a) allein passt vom Umfang, hilft ohne Englisch aber kaum, weil GLOBAL PARAMETER, DATA UTILITY und die Pattern-
  und Part-Seiten Korgs Texte sind.
- (b) ist ein eigenes Feature, sinnvoll als 1.5.x oder 1.6 nach einer Entscheidung, und zwar gleich mit (a)
  zusammen, weil beide dieselbe Sprachwahl und dieselben Glyphen brauchen.

Was in 1.4.8 passt und sofort hilft (**Urteil**): eine deutsche Begriffsliste der Menüs (Englisch auf
dem Display, Deutsch daneben, nach Seite geordnet), als Seite in der App oder Doku. Kein Firmware-Risiko, die Liste
lässt sich später direkt als Sprachdatei weiterverwenden.

## Offen

- Welche Sprachen, ob Korgs Menüs dazugehören (zu entscheiden).
- Sichtbare Korg-Vorlagen außerhalb der gemessenen Wege (Dialoge, Fehler, Sampling, Testmodus).
- Größe der Formatpuffer, Textvergleiche im Code.
- Freier Code-Platz für Texte und Schriften.
- Blau (Synth-Build) gar nicht gemessen.
- Am Gerät nichts geprüft.
