# BLECH Menü: eigener Bildschirm 0x2D im Edit Ring

Stand 2026-10-15. Alles im Emulator gemessen (Firmware 2.02 mit Hacktribe, virtuelle Karte),
am Gerät nichts geprüft. Markierungen: **gemessen**, **hergeleitet**, **offen**.
Code: `tools/patch/script_menu.s` (Teil des Patches `script-runtime`), Prüfungen:
`tools/emu/menu_cases.py`, `tools/emu/script_cases.py` (`menu-*`, `fremd-*`, `import-*`),
Anwendersicht: `docs/plugins.md`, Abschnitt "Das Menü BLECH am Gerät".

## Wie der Bildschirm eingehängt ist

Alle Bildschirme kommen aus einer Fabriktabelle mit 45 Wörtern bei `0xC00F9CD8`
(`0xC006E664(n, arg)` ruft `tabelle[n](arg)`, einziger Leser ist das Literal bei
`0xC006E68C`). Der Patch legt eine Kopie mit 46 Wörtern bei `0xC01ADE00` an (das Wort 45 ist
unsere Fabrik, die Kopie macht `src/patch.mjs` beim Anwenden aus der eigenen VSB, nichts davon
steht im Patch), setzt das Literal auf sie und die Grenze `cmp r0, #44` auf `#45`.

| Stelle | Vorher | Nachher |
|---|---|---|
| `0xC006E664` | `cmp r0, #44` | `cmp r0, #45` |
| `0xC006E68C` | Literal `0xC00F9CD8` | Literal `0xC01ADE00` |
| `0xC0064D84` | Global, EDIT rechts: `mov r0, #14` | Sprung in `menu_nb_right`: Menü, wenn scharf, sonst 14 |
| `0xC0061880` | Data Util, EDIT links: `mov r0, #8` | Sprung in `menu_nb_left`: Menü auf der letzten Seite, sonst 8 |
| `0xC006E8D8` | `cmp r1, #10` im Bildschirmwechsel | `menu_toplevel`: 0x2D zählt als oberste Ebene, MENU kehrt zurück |
| `0xC006F094` | WRITE zentral, `push {r3, r4, r5, lr}` | `menu_write`: auf 0x2D kein Fenster "Pattern schreiben" |
| `0xC008A83C`, `0xC008A8A8` | Seitenzähler | `menu_counter_new`, `menu_counter_set`: wenn der Zähler `.../29` zeigt, kommt die Seitenzahl dazu (und seit v18 eine weitere für Blechy am Ende), der Ring bleibt lückenlos |
| `0xC0064430` | Event, EDIT rechts: `push {r3, r4, r5, lr}` | Sprung in `menu_event_right`: bei scharfem Menü auf die Seite von Blechy (Ebene 3), sonst der verdrängte Befehl und weiter hinter ihm (v18) |
| `0xC0067754` | Pattern Menü, EDIT links auf der ersten Seite: `mov r0, #10` | Sprung in `menu_pattern_left`: bei scharfem Menü auf die Seite von Blechy, sonst Event (v18) |

Die Klasse ist die des Global Seitenbildschirms (9): der Konstruktor ist `0xC0064C30` mit
eigener Klassentabelle, eigenem Reiter "BLECH" und eigenem Zähler; die Klassentabelle ist eine
Kopie der von Bildschirm 8 (`0xC00E3440`, 18 Wörter, bei `0xC01ADF00`) mit eigenen Plätzen für
Tasten, EDIT links und rechts, MENU (nichts) und das Hauptrad. Die Textfunktionen sind
`0xC00857E4` (Titel), `0xC0085828` (Wert), `0xC0085888` (dritte Zeile), `0xC008A8A8` (Zähler).
Das Menü ist erst scharf, wenn der Haken nach dem Laden der `e2sSample.all` (`0xC0038D68`)
`menu_arm` durchlaufen hat; mit EXIT beim Einschalten oder fehlendem Panel bleibt der Zustand
`0xFFFFFFFF` und alle Haken geben an die Firmware zurück. Zustand: `0xC01D6E00` (512 Byte),
Seiten der Plugins: `0xC01D6C00` (12 mal 40 Byte).

**Eingaben:** Solange `[Bildschirmverwaltung] + 0x2C == 0x2D`, reicht der Eingangsfilter alles
unverändert durch und meldet den Plugins nichts (sonst könnte ein Plugin mit
Tastenabfang das Menü sperren).

## Zwei Ebenen (15.10.)

Gerätebefund zu v12: die Seiten liefen in einer flachen Reihe ("BLECH 38/42"), und auf Seiten mit
längerem Wert lagen zwei Texte übereinander. Der Emulator zeigte dasselbe (die Anzeige ist dort der
Speicher des LCD-Controllers, also genau das, was die Firmware sendet), die Ursache ist **gemessen**:

- Das Widget der Seiten (Titel, Wert, "dritte Zeile") zeichnet die dritte Zeile, die Einheit, immer ab
  **Spalte 28** der Wertzeile, nicht hinter dem Wert. Gemessen mit einem Text allein: "no files" beginnt bei
  Spalte 28, "restart to apply" auch. Der Wert (große Schrift) beginnt bei Spalte 5 und braucht etwa 7,5
  bis 8 Punkt je Zeichen ("ON" endet bei Spalte 22). Jeder Wert ab drei Zeichen läuft damit in die dritte Zeile.
- Das Menü benutzt die dritte Zeile nicht mehr. Was eine Seite sagt, steht im Wert (rund 14 Zeichen).
  Der Titel fasst rund 18 Zeichen ("GROUP > name" mit 20 Zeichen lief über beide Ränder und wurde abgeschnitten,
  darum steht die Gruppe nicht im Titel).
- Das Schild oben links ("BLECH") ist ein Widget, das einen Zeiger auf seinen Text hält (Wort `+0x38` der 60
  Byte). Das Menü hält das Widget fest und zeigt auf einen eigenen Puffer: das Schild nennt auf der obersten
  Ebene BLECH und in einer Gruppe deren Namen (PLUGINS, GAMES, TOOLS, CUSTOM). **gemessen** (`menu:enter_goes_into_the_group`).
- Der Seitenzähler zeigt die Zahl, die man ihm gibt, plus 1 (Seite 0 heißt "1/n"). Die Haken des Zählers der
  Firmware (`n/29`) lassen die Zahlen des Menüs in Ruhe (`M_RAW`), und ein einziger Platz im Ring der Firmware
  gehört dem Menü (`M_COUNT` ist 1): Global 26/30, Data Util 28/30, Event 29/30.
- **EXIT** geht im Menü nicht über einen Haken: die Taste ruft im Tastenverteiler (`0xC0070368`, `blx r3`) den
  Platz 2 der Klassentabelle des Bildschirms, bei uns eine Kopie mit eigenem Platz (`menu_slot_exit`). **gemessen**
  mit Zählern auf allen Plätzen: EXIT ruft die Plätze 0, 1 und 2, MENU auf einer Seite ruft den Platz 6 (der Platz 3,
  den die anderen Tasten nehmen, bekommt von MENU nur das Loslassen). MENU ist darum ENTER im Menü.

**Prüfung (Fall `menu:pages_are_clean`):** für jede Seite aller Gruppen wird der Wert allein und die dritte
Zeile allein gezeichnet (die eigenen Textfunktionen der Firmware, nichts von uns) und verlangt: keine dritte Zeile,
kein gemeinsames Pixel, Titel und Wert erreichen den Rand nicht. Gegen den Stand von v12 schlüge er an.

## Drei Ebenen, Optik von Data Util (v14, 15.10.)

Gerätebefund zu v13: vier Gruppenseiten standen direkt hinter Global, das war unübersichtlich. Jetzt:

- **Ring:** eine Seite BLECH ("BLECH 28/30", Global 27/30, Data Util 29/30), Ebene 0, in der Optik der Seite
  DATA UTILITY: Titel, leerer Wert, dritte Zeile `press  [ Enter ]`. Das Widget zeichnet diese Zeile ab Spalte 28
  der Wertzeile, mit leerem Wert stört nichts (`menu:pages_are_clean` lässt die Zeile nur unter leerem Wert zu).
- **Liste der Gruppen** (Ebene 1): PLUGINS, GAMES, TOOLS, MFX 2, CUSTOMIZATION (ABOUT bis v17, seit v18 entfernt), jede mit `press  [ Enter ]`,
  Schild BLECH, Zähler "1/5" bis "5/5". ENTER geht in die Gruppe, EXIT zurück in den Ring.
- **Seiten einer Gruppe** (Ebene 2): Schild mit dem Namen der Gruppe (Plugins, Games, Tools, Custom, MFX 2),
  EXIT zurück auf die Liste an der Stelle der Gruppe. EXPORT ALL und IMPORT PLUGIN sehen aus wie IMPORT SAMPLE
  ("press  [ Enter ]"). Bei IMPORT PLUGIN öffnet ENTER die Dateiliste ohne Ordnerwahl ("Upper Folder" gibt es nicht):
  das Hauptrad blättert Datei für Datei (je Schritt eine, auch bei schnellem Drehen), ENTER lädt die gezeigte Datei.
- **Versteckte Dateien:** die Dateiliste der Firmware überspringt jeden Namen, der mit einem Punkt beginnt, und
  Dateien mit Attribut versteckt oder System. Grund: macOS legt auf FAT Karten zu jeder Datei eine `._Name` an
  (AppleDouble). Gemessen mit `._a.blech` und `._b.BLECH` auf der Testkarte (`import-versteckte-dateien-fehlen`).
- **Schilder passen:** das Schild ist weiß auf dem schwarzen Balken, rechts davon steht der Zähler. `menu:pages_are_clean`
  und `menu:tab_labels_fit` messen für jede Seite und jedes Schild mit dem breitesten Zähler (39/40), ob nach dem Schild
  noch ein weiterer schmaler Buchstabe vor dem Zähler Platz hätte. "CUSTOM" in Großbuchstaben (der abgeschnittene Befund
  vom Gerät: "CUSTOM 1/7" zeigte das M halb) fällt damit durch, die Schilder in Groß- und Kleinschreibung der Firmware
  ("Custom") bestehen. Das Schild heißt darum "Custom".
- **ABOUT** zählte die geladenen Plugins ("2 plugins" mit zwei Plugins auf der Karte, "0 plugins" ohne Karte oder ohne
  Plugins). Die Gruppe ist seit v18 weg (sie verwirrte); die Fälle `menu-about-zaehlt-skripte` und `menu:about_counts_no_plugins` auch.

Bilder der Seiten (Emulator, Anzeige aus dem LCD Speicher): `docs/images/blech-menue-v14/`, Sammelbild `00-all.png`.

## Blechy am Ende des Rings (v18, 15.10.)

Der Ring der Firmware hat 29 Seiten, Event ist die
letzte (Zähler 29/29), und EDIT rechts auf Event führt auf die erste Seite des Pattern Menüs (**gemessen**: `0xC0064430` setzt die gemerkte Seite des
Pattern Menüs zurück und schaltet auf 3), EDIT links auf der ersten Pattern Seite führt auf Event (`0xC0067754`). Dazwischen steht
seit v18 eine Seite: Blechy, der in BLECH eingebaut ist ([Messung](2026-10-15-blechy.md)).

- **Ebene 3** des BLECH Bildschirms (`M_LEVEL_BLECHY`), derselbe Bildschirm 0x2D, kein eigener: seine Texte sind leer, den ganzen Bildschirm
  füllt der Rahmenhaken mit Blechys Bild. Der Zähler zeigt 31/31 (unsichtbar). Die Ringseite BLECH bleibt 28/31, Data Util 29/31, Event 30/31:
  `menu_counter_new` und `menu_counter_set` addieren eine Seite zum Gesamtwert (`MENU_RING_TAIL`), verschieben aber die Seitenzahlen nicht
  weiter, `menu_counter_args` setzt für Ebene 3 den letzten Platz.
- **Tasten:** EDIT links geht auf Event (10), EDIT rechts auf das Pattern Menü über die verdrängte Anweisung (`menu_next_pattern`), EXIT ist die
  der Firmware (Hauptbildschirm), MENU und WRITE tun nichts (`menu_slot_keys`, Art 19). Das Hauptrad ändert nichts, was auch auf Data Util,
  Event, Global und Pattern **gemessen** so ist (Hauptrad drehen: Bildschirm und Zähler bleiben).
- **Eingaben für Plugins:** der Eingangsfilter reichte bisher auf 0x2D alles unverändert durch und meldete den Plugins nichts. Auf Ebene 3
  meldet er das Touchpad (Taste 34 und Lage) und reicht alles durch, ohne dass ein Plugin Tasten abfangen kann (`r8` im Filter).
- **Öffnen:** der Rahmenhaken (`blechy_follow`) öffnet Blechy, sobald 0x2D mit Ebene 3 gezeigt wird, und schließt ihn bei jedem anderen
  Bildschirm. Das Kopieren des Bildes (`script_display_blit`) gilt für den Hauptbildschirm und diese Seite.
- **Mit EXIT beim Einschalten:** `M_ON` ist nicht 1, beide Haken geben sofort die Firmware zurück: Event rechts geht ins Pattern Menü, Pattern
  links nach Event, die Zähler sind `/29`.

## DATA UTILITY (offen)

Die Funktionsliste von DATA UTILITY ist der **Bildschirm 15** (Zähler "n/14", MENU öffnet sie vom Bildschirm 14). Sie hat
dieselben Widgets wie unsere Seiten (Titel, "press [ Enter ]" als dritte Zeile). Alles andere ist eine Zustandsmaschine:
`0xC0061A24` springt nach einem Zustand im Objekt (`+0x20`, 40 Zustände) und setzt Titel und Texte jeder Funktion aus
Literalen. IMPORT SAMPLE ist dort ein Zustandsstrang mit Dateiauswahl. Nicht gebaut: IMPORT PLUGIN und EXPORT ALL stehen
in der Gruppe PLUGINS des Menüs BLECH, nur in der Optik von IMPORT SAMPLE.

## Seiten der Anpassung

Die Gruppe CUSTOMIZATION hat neun Seiten (BOTTOM LEDS, LED RED, GREEN, BLUE, BACKLIGHT RED, GREEN, BLUE, DISPLAY INVERT, PATTERN CONFIRM). Haken, Zustand, Datei
(Version 2) und Messungen: [Anpassung](2026-10-14-blech-anpassung.md). Der Zustand dafür liegt bei
`MENU_STATE + 0xA0` bis `0xE0`.

## Gemessen (14.10., Emulator)

- **Ring** (`menu:ring_forward`, `ring_backward`, `neighbour_counters`, `global_counter`,
  `event_counter`): von Global (26/30) durch die vier Einträge der obersten Ebene nach Data Util (28/30) und zurück,
  der Zähler des Menüs zählt nur diese Einträge, Event ist die letzte Zahl (29/30).
- **WRITE, EXIT, MENU** (`write_opens_nothing`, `enter_goes_into_the_group`, `exit_goes_one_level_up`,
  `exit_returns_to_the_groups_row`, `exit_to_main`, `menu_key_returns`): WRITE öffnet kein Fenster, ENTER geht in die Gruppe,
  EXIT eine Ebene zurück und auf der obersten zum Hauptbildschirm, MENU zurück auf 0x2D.
- **48 Tasten** (`all_keys_run`): jede der Tasten 0 bis 0x2F auf dem Bildschirm, keine Assertion.
- **EXIT beim Einschalten** (`exit_held_is_stock`, `exit_held_left_is_stock`): der Ring ist der der
  Firmware (Global, Data Util 28/29), das Menü bleibt unscharf.
- **Einstellungen** (`settings_*`): Voreinstellungen ohne Datei; Ändern und WRITE schreibt
  `settings.b.bin` mit Generation 1, das zweite WRITE `settings.a.bin` mit 2; der nächste Start liest
  beide und nimmt die neuere gültige; eine beschädigte neuere, eine abgeschnittene, eine zu
  lange Zählung, 17 Prüfsummen und Müll werden ignoriert; ohne Karte "no card", mit
  geschützter Karte "card protected" (die Firmware hat im Emulator keinen Schreibschutz, die Prüfung
  lässt `f_open` im Schreibmodus `10` liefern) und die Karte bleibt unverändert, ohne Ordner
  "folder missing"; MFX 2 aus in der Datei: der Touchpad Start ist wie im Original.
- **Plugin-Seiten** (`menu-*`): Zählung, Texte, Pausieren und Fortsetzen, ein Fehler-Plugin zeigt
  `DIV_ZERO line 3` und lässt sich nicht einschalten, Eingaben erreichen die Plugins nur außerhalb
  des Menüs.
- **EXPORT ALL**: die Datei ist Byte für Byte gleich der des Browser Bauers und wird beim nächsten Start
  wieder geladen; ohne Plugins "no plugins loaded", die Karte bleibt unverändert.
- **Fremde Plugins** (`fremd-*`): ohne PROBED Bit wartet das Plugin (ASK), das Hauptrad ändert
  nichts, WRITE erlaubt, startet den Rumpf, gibt `ready` und speichert die Prüfsumme; der nächste
  Start fragt nicht wieder; sind 16 Prüfsummen voll, fliegt die älteste raus.
- **IMPORT PLUGIN** (`import-*`): listet nur `*.blech` (Groß und Kleinschreibung egal, Unterordner und
  andere Dateien nicht), lädt und startet, lehnt doppelte Namen, kurze Dateien und Müll ab, legt die Laufzeit
  an, wenn noch keine Karte geladen wurde, und tut bei ausgeschalteten Plugins nichts.
- **korg.menu.add** (`menu-add-*`): zwei Seiten (Zahlen mit Vorzeichen), Hauptrad ändert, klemmt an den
  Grenzen, das Plugin sieht `menu`; derselbe Name ist dieselbe Seite; 12 Seiten, die 13. liefert -1;
  `min` über `max` beendet das Plugin mit `API_ARG`.

## Grenzen und offene Punkte

- **Startbild:** kein Schalter, weil es rund 290 ms vor dem Kartenzugriff gezeichnet wird
  (Emulator: Haken `0xC002ADAC` bei 59 ms, Kartenhaken bei 350 ms). Ein Schalter bräuchte ein Kennzeichen
  im Flash (zum Beispiel im Sektor des Startbild Editors) und damit einen Gerätetest des Flash Schreibens.
- **Wirkung der Schalter:** PLUGINS und MFX 2 gelten ab dem nächsten Start. MFX 2 liest den wirksamen
  Wert bei jedem Haken (`0xC01D6E1C`), er wird beim Start gesetzt.
- **Pausierte Plugins** bleiben nur bis zum Ausschalten pausiert, die Datei merkt es sich nicht.
- **Am Gerät nichts davon geprüft:** FatFs Zugriffe (`f_opendir` `0xC009E660`, `f_readdir`
  `0xC009E740`, `f_closedir` `0xC009E728`, `f_open`, `f_read`, `f_write`, `f_close`), die Darstellung langer Namen
  (was der Titel nicht fasst, wird abgeschnitten), die Zeit der Dateiliste bei
  vielen Dateien (höchstens 8 Namen werden gemerkt), die Menütasten in der Praxis.
- **Hergeleitet:** der Kartenordner `Plugin/` und die Dateien müssen vom Nutzer angelegt sein
  (keine Anlage von Ordnern), das Menü meldet es.
