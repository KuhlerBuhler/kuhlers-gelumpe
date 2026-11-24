# Startbild-Editor: Hintergrund

Wie das Startbild im Gerät liegt, wie der Editor es zeichnet, im Flash speichert und beim Start wieder lädt. Der Editor
ist der Patch `data/patches/splash-editor.json` (erzeugt von `tools/patch/splash_editor.py`), er gehört zu allen drei
Builds (Hacktribe, Korgs rote 2.02, blaue Electribe, jeweils mit eigener Fassung). Bedient wird er im BLECH-Menü unter
CUSTOMIZATION: SPLASH IMPORT, SPLASH DRAW und SPLASH RESET. Der Bericht zum Bau: [Startbild-Editor: gebaut und im Emulator
geprüft](../messungen/2026-10-10-startbild-editor.md). Am Gerät ist von den Messungen nur der
[Notschalter](../glossary.md#notschalter) (EXIT beim Einschalten) bestätigt, der Editor selbst nicht.

## Überblick

- Das Bild (128 x 64 Pixel, 1 Bit je Pixel, 1024 Byte) liegt in einem eigenen Flash-Sektor `0x7F0000` und steht beim
  Start ab dem ersten Bild. Das Startbild der VSB bleibt der Rückfall.
- Der Editor ist eine zusätzliche Seite 20 "SPLASH SCREEN" im Bildschirm Global. EDIT erreicht sie nicht,
  nur SPLASH DRAW im BLECH-Menü öffnet sie samt Editor. Der Patch kopiert die vtable von Global und tauscht ein
  Zeigerwort (Abschnitt 1).
- Die Karte spiegelt das Bild: `KORG/blechtribe/Media/splash.bmp` wird beim Start (`splash_sync`, Eintrag `0xC01A250C`,
  aus den Start-Haken der Script-Laufzeit) mit dem gezeigten Bild verglichen. Weicht es ab, schreibt der UI-Tick es in
  den Flash (`save_image`), zu sehen ist es ab dem Start danach. SPLASH IMPORT liest ein BMP (128 x 64, 1 Bit,
  unkomprimiert), WRITE im Editor schreibt auch die Karte.
- Im Editor bewegt das Hauptrad einen blinkenden Cursor, MENU kippt das Pixel darunter, WRITE speichert, EXIT verlässt.
  Mit SHIFT gehalten springt das Rad zeilenweise, mit MENU gehalten malt es (Abschnitt 7).

Basis der Messungen: eine eigene `SYSTEM.VSB` (Sampler 2.02) und ein eigener Flash-Dump, im Emulator
(`tools/emu/machine.py`) oder offline mit Capstone gelesen. Markierungen: **gemessen**, **offline** (Code gelesen),
**hergeleitet**, **offen**. Adressen sind RAM-Adressen, Datei-Offset in der VSB = RAM - `0xC0000000` + `0x100`.

## 1. Menü Global: Aufbau

- **Gemessen:** Global hat zwei Bildschirme. Nummer 8 (Klasse `0xC00E3440`) ist
  die Kopfseite „GLOBAL PARAMETER / press [Enter]“ in der Edit-►-Reihe (nach
  Sample 37, vor Data Util 14). MENU dort öffnet Nummer 9 (Klasse
  `0xC00E33F8`), die eigentlichen Parameterseiten. EXIT auf 9 führt zurück auf 8.
- **Offline:** Slots von `0xC00E3440`: [4] Edit ◄ ruft `0xC0083D28(0x25,0)`
  (Bildschirm wechseln), [5] Edit ► `(0x0E,0)`, [6] MENU `(9,0)`.
- **Gemessen:** Auf Nummer 9 zählt Edit ► die Seite an Objekt `+0x2C` von 0 bis
  19 und dann wieder 0, Edit ◄ rückwärts. 20 Seiten.
- **Offline:** Es gibt **keine Eintragstabelle**. Der Titel jeder Seite kommt aus
  einem `switch` in `0xC0064948` (Sprungtabelle direkt hinter `0xC0064990`,
  `cmp r3,#0x13`), jede Seite lädt einen eigenen String-Zeiger aus dem
  Literal-Pool `0xC0064B00` bis `0xC0064B54`. Die Texte stehen lückenlos ab
  `0xC00A5E8A` („TRIGGER MODE“ bis „XY CALIBRATION“, dahinter „???“, „Global“,
  „GLOBAL PARAMETER“). Seite 19 (XY CALIBRATION) zeigt zusätzlich
  „press  [ Enter ]“ (`0xC00A5A23`), MENU dort (`0xC0064888`) wechselt auf
  Bildschirm `0x20`.
- **Offline:** Die Seitenzahl 20 steht fest im Code, an fünf Stellen:
  `0xC0064980` (`mov r2,#0x14`, Seitenanzeige), `0xC006498C` (`cmp r3,#0x13`,
  switch), `0xC0064BF0` (`movmi r4,#0x13`, Umlauf nach unten), `0xC0064BF8`
  (`cmp r4,#0x14`, Umlauf nach oben), `0xC0064D04` (`mov r2,#0x14`,
  Seitenanzeige im Konstruktor `0xC0064C30`).
- **Offline:** Die zuletzt gewählte Seite steht zusätzlich im Byte `0xC0691328`
  (Setter `0xC007B084`, Getter `0xC007B074`). Der Konstruktor übernimmt sie,
  Nummer 9 öffnet also auf der zuletzt offenen Seite.
- **Gemessen + offline:** Die Werte der Seiten hängen an einem Parameter-Objekt
  `*0xC0691240` (hier `0xC06B6B00`) mit drei Tabellen von Member-Funktionszeigern
  zu je 20 Einträgen à 8 Byte: `+0x308` (Wert zeichnen, über `0xC007B1A0`),
  `+0x3A8` (offen), `+0x448` (Wert ändern um Delta, über `0xC007B094`). Die
  Tabellen werden zur Laufzeit gefüllt (Heap), sie liegen direkt hintereinander,
  Eintrag 19 ist jeweils 0. Ein Index 20 läse den ersten Eintrag der nächsten
  Tabelle. In `+0x448` stünde an Index 20 `0xC06B6FF0` mit ungeradem Versatz
  `0x11`, also ein virtueller Aufruf über Müll. Aufgerufen werden die Tabellen
  nur bei Ereignissen (VALUE, Seitenwechsel), nicht im Leerlauf (gemessen).
- **Gemessen:** WRITE auf Nummer 8 oder 9 speichert die Globals sofort, ohne
  Rückfrage: Fenster „Working...“ (Klasse `0xC00E3E08`, Art 25) für rund 1 s,
  `0xC004C1B4` → `0xC002A128` → Flash-Schreiben `0x230000`, Länge `0x100`, ein
  Sektor-Löschen. Ausgelöst zentral in `0xC006F094` (Bildschirmnummer 8 oder 9 →
  `0xC002D5D8(0xB,0,0)`, offline).

**Am wenigsten invasiv (hergeleitet):** Eine Tabelle zu verlängern geht nicht,
es gibt keine. Stattdessen eine eigene Klasse als Kopie der vtable `0xC00E33F8`
(18 Wörter) im `FF`-Bereich, darin nur einzelne Slots ersetzt, und **ein
Zeigertausch**: Der Konstruktor von Bildschirm 9 (`0xC0064C30`) lädt seine vtable
aus dem Literal `0xC0064D3C` (VSB `0x64E3C`). Offline geprüft: Nur dieser eine
Befehl liest das Literal. Dieses eine Wort auf die Kopie zu zeigen genügt, damit
jedes neue Objekt von Nummer 9 unsere Slots hat (der Destruktor `0xC006490C`
setzt die Original-vtable selbst zurück, das stört nicht). Unsere Slots
behandeln Seite 20 selbst und rufen für 0 bis 19 die Originale. Die fünf
Konstanten bleiben unverändert, und das Byte `0xC0691328` wird nie 20, damit die
drei Tabellen nie mit Index 20 gelesen werden. Seite 20 merkt sich unser Code in
einem eigenen Byte.

**Platz (gemessen am Abbild):** `FF`-Läufe ab 16 KiB: `0xC0148880` bis
`0xC0150000` (29 KiB), `0xC015027C` bis `0xC0170000` (127 KiB), `0xC01720B0` bis
`0xC01A0000` (183 KiB), `0xC01A2100` bis `0xC01FFFF0` (375 KiB am Stück).
Hacktribe-Code liegt bei `0xC0150000` und `0xC0170000` direkt davor, wird also
dort ausgeführt. `0xC01A2100` als Anfang für unseren Code und Puffer ist
plausibel (hergeleitet: kein Zeiger darauf, laut [patcher.md](../patcher.md) im
Betrieb unverändert).

## 2. Eingabeweg

- **Offline:** Der Tasten-Verteiler ab `0xC0070140` holt den aktuellen
  Bildschirm (oder ein offenes Fenster) über `0xC006EA4C`/`0xC006EA54` und ruft
  dessen vtable.
- **Gemessen** (Hooks auf alle Slots von `0xC00E33F8`, Bildschirm 9):

| Eingabe | Slot (Byte-Offset) | Argumente | Aufrufer |
|---|---|---|---|
| EXIT (0x0D) | 2 (`+0x08`) | this, 0x0D, 1 | `0xC0070368` |
| Edit ◄ (0x08) | 4 (`+0x10`) | this, 0x08, 1 | `0xC0070368` |
| Edit ► (0x0C) | 5 (`+0x14`) | this, 0x0C, 1 | `0xC0070368` |
| MENU (0x09) | 6 (`+0x18`) | this, 0x09, 1 | `0xC0070368` |
| jede Taste, gedrückt und losgelassen, auch WRITE, SHIFT, STOP | 3 (`+0x0C`) | this, Taste, 1 oder 0 | `0xC0070578` |
| VALUE ±1 | 10 (`+0x28`) | this, Delta (+1 / 0xFFFFFFFF) | `0xC006EBEC` |
| PLAY (Meldung) | 12 (`+0x30`) | this, 0x0B, ... | `0xC006F3E8` |

- **Gemessen:** Nach den Slots 2, 4, 5, 6 kommt Slot 3 noch einmal mit
  „losgelassen“. Bei WRITE kommt zuerst Slot 3 (`0x0E`, 1) am Bildschirm, danach
  erscheint das „Working...“-Fenster und bekommt die weiteren Ereignisse. Ein
  eigener Slot 3 sieht WRITE also vor dem Speichern der Globals.
- **Offline:** Der Handler `0xC006B980` gehört zu einer anderen Klasse, für
  Global ist er nicht im Spiel.

## 3. Zeichnen und Anzeige

- **Offline:** `0xC003F650(&nr, &x, &y)` zeichnet Bild `nr` aus der Bildtabelle
  `0xC00C1C2C` (19 Einträge, Zeiger auf Deskriptoren). Deskriptor: `+0` Breite,
  `+4` Höhe, `+8` Zeiger auf die Daten. Datenformat: 1 Bit je Pixel, Byte
  `(y/8) * Breite + x`, Bit `7 - y%8`. Es werden nur gesetzte Pixel gemalt (pro
  Pixel `0xC003F12C`), gelöschte bleiben, wie sie sind.
- **Offline:** Bild 13 ist das Startbild: Deskriptor `0xC00C5A4C` = {128, 64,
  `0xC00F9854`}, also 128 x 64 Pixel, 1024 Byte. Das Datenzeiger-Wort liegt bei
  `0xC00C5A54` (VSB `0xC5B54`), es ist der einzige Verweis auf die Daten. Die
  Tabelle wird nur von `0xC003F650` gelesen.
- **Offline:** Pixel: `0xC0015824(&x, &y, &farbe)` setzt oder löscht ein Pixel im
  Puffer `0xC031B310` (Byte `(y/8)*128 + x`, Bit `y%8`) und meldet das Rechteck
  als geändert (`0xC001531C(x0,y0,x1,y1)`, Liste bei `0xC031BB10`).
  `0xC0015804` löscht den ganzen Puffer (ohne Änderungsmeldung), `0xC003F0D4`
  setzt den Zeichenzustand (`0xC03487CC`: Farbe 1, Fenster 128 x 64) und löscht
  den Puffer. `0xC0015988(seite, spalte, anzahl, an)` füllt Bytes einer Seite.
- **Gemessen:** Auf Bildschirm 9 Puffer gelöscht, Deskriptor 13 auf einen
  RAM-Puffer mit Testbild gezeigt, `0xC003F650` aufgerufen, dann
  `0xC001531C(0,0,128,64)`: Der Puffer gleicht dem Testbild Byte für Byte, nach
  0,3 s auch das Display. Ein Deskriptor darf also auf RAM zeigen.
- **Gemessen:** Danach weichen genau 14 Byte ab, Seite 0, Spalten 84 bis 97: das
  Batterie-Symbol der Statusleiste malt sich regelmäßig neu. Sonst bleibt das
  Bild auch nach 1,8 s stehen. VALUE ruft auf Seite 0 den Original-Handler und
  malt die Seite neu (642 Byte anders).
- **Gemessen:** `0xC0015824` mit Farbe 1 an (5,3): Das Pixel ist danach im
  Display gesetzt. Damit geht Umschalten unter dem Cursor.
- **Offline + gemessen:** Takt: `0xC006F178` (aufgerufen von `0xC00836F8`) läuft
  alle 40 ms (25 Hz). Er ruft für jedes Widget im Vektor des
  aktuellen Bildschirms (Objekt `+0x10` Anfang, `+0x14` Ende, `+0x18` Kapazität;
  anhängen mit `0xC00614FC`) dessen vtable-Slot 2 (Zeichnen), danach dasselbe für
  eine zweite Ebene (Statusleiste). Die Bildschirm-Klasse selbst bekommt keinen
  Takt (gemessen: kein Slot läuft im Leerlauf). Für einen blinkenden Cursor
  braucht es also ein eigenes kleines Widget im Vektor, dessen Slot 2 den Cursor
  alle paar Takte umschaltet (hergeleitet). Der Basis-Destruktor `0xC0060F10`
  ruft beim Abbau für jedes Widget Slot 4 und Slot 1 (löschen), ein statisches
  Widget braucht dort leere Funktionen.
- **Offen:** ob `+0x18`/`+0x19` am Takt-Objekt die zweite Ebene (Batterie-Symbol)
  während des Editors anhalten darf, oder ob der Editor die 14 Byte selbst
  übermalt.

## 4. Speichern

- **Offline:** Flash-Objekt: `0xC0029A40()` (Singleton `*0xC034028C`, im Betrieb
  `0xC06C1AD0`, wird beim Start in `0xC002AD44` angelegt). Lesen:
  `0xC0029A74(obj, ziel, adresse, länge)` (Sperre `0xC0000D80(2)`, Treiber
  `0xC001E4AC`). Schreiben: `0xC0029AB8(obj, adresse, länge, quelle)`: liest
  jeden betroffenen 4-KiB-Sektor in den Puffer `0xC033F28C`, setzt die neuen
  Bytes ein und schreibt den Sektor über `0xC001E57C` (löschen `0xC001E7BC`,
  Befehl `0x20`, dann 16 Seiten zu 256 Byte über `0xC001E6B0`). Die Sektorgröße
  ist 4 KiB, Schreiben ist Lesen-Ändern-Schreiben, der Rest des Sektors bleibt
  erhalten.
- **Offline:** Globals: Laden `0xC004BEE0` → `0xC002A0F8` (Block `0x23`, `0x100`
  Byte), prüfen mit `0xC004718C`, bei Fehler Vorgabe aus `0xC00CFE58` kopieren.
  Speichern `0xC004C1B4` → `0xC002A128(obj, quelle, 0x100)` →
  `0xC0029AB8(obj, 0x230000, 0x100, quelle)`. Dasselbe Muster (prüfen, sonst
  Vorgabe) braucht das Startbild.
- **Offline:** Alle Schreiber (alle `bl`/`b` auf `0xC0029AB8` und auf die
  allgemeine Funktion `0xC0029CBC`): Globals `0x230000`, Patterns
  `0x240000 + n * 0x4000`, Block `0x6B0000`, Panel-Kennung `0x7EF000`, `0x7FF000`
  (8 Byte, vier Halbwörter aus `0xC002A2F0`, vermutlich die XY-Kalibrierung),
  Update-Wege über `0xC0029CBC` mit Block 0, 2, `0x22`, `0x75`, `0x80`
  (Bootloader, Firmware, Nutzerdaten ab `0x220000`, Bereich `0x750000` bis
  `0x7E0000` laut `0xC0029C94`, Werks-Samples ab `0x800000`). Hacktribe ruft
  Lesen und Schreiben zusätzlich aus `0xC0170710`/`0xC017073C` auf (SysEx-Weg,
  Puffer `0xC1000000`/`0xC2000000`).
- **Hergeleitet:** Die freien Bereiche aus dem
  [Flash-Dump-Bericht](../messungen/2026-10-09-flash-dump.md) sind nicht gleich
  sicher: `0x7C0002` bis `0x7DFFFE` liegt im Bereich, den der Update-Weg `0x75`
  beschreibt, `0xE5F013` bis Ende im Samplebereich (Update-Weg `0x80`),
  `0x660017` bis `0x6B0000` im Nutzerdaten-Bereich `0x220000` bis `0x6B0000`
  (Weg `0x22`). Kein bekannter Schreiber berührt dagegen `0x7E0000` bis
  `0x7EEFFF` und `0x7F0000` bis `0x7FEFFF`, beide sind im Dump `FF` (gemessen).
  Die belegten Sektoren `0x7EF000` und `0x7FF000` werden nur als eigener
  4-KiB-Sektor neu geschrieben. Gewählt: Sektor `0x7F0000`.
- **Gemessen** (Hauptbildschirm, Aufruf am Takt): `0xC0029AB8(obj, 0x7F0000,
  1036, puffer)` gibt 1 zurück. Flash-Befehle dabei: 1 Lesen, 1 Löschen 4 KiB
  (`0x20`), 16 Seiten-Programmieren (`0x02`), je 17 Mal WREN/WRDI, 68 Status.
  Geändert ist nur der Sektor `0x7F0000`, Inhalt gleich dem Datensatz, Rest des
  Sektors `FF`. Lesen mit `0xC0029A74` gibt denselben Datensatz zurück. Ein
  zweites Schreiben über den alten Inhalt klappt ebenso (Löschen vorher). Die
  Firmware läuft danach normal weiter, keine Assertion.
- **Geschätzt:** Am Gerät dauert ein 4-KiB-Löschen typisch zig bis einige hundert
  ms (Größenordnung aus Datenblättern, Flash-Typ nicht gemessen).

Datensatz (1036 Byte): 4 Byte Kennung, 2 Byte Version, 2 Byte Länge 1024, 1024
Byte Bild im Format von Bild 13, 4 Byte CRC-32 über alles davor. Die Firmware hat
keine CRC-32-Funktion (keine Tabelle gefunden, nur zwei CRC-16-Tabellen bei
`0xC00D7F98` und `0xC00A7750`, ohne handliche Funktion), die bitweise Schleife
ist eigener Code von rund 15 Befehlen. Weil die Seiten der Reihe nach programmiert
werden, kommt die CRC zuletzt. Ein halb geschriebener Satz endet in `FF` und fällt
durch (hergeleitet, durch den Fall „halb“ in Abschnitt 5 gemessen).

## 5. Laden beim Start

Zeitachse des Starts (gemessen, Emulator-ms): Startbild der VSB gezeichnet bei 52,9 bis 65,2 (`0xC002AC38` ruft
`0xC003F650`, jedes Pixel einzeln, rund 12 ms), im Display bei 66,7; Flash-Objekt angelegt bei 68,7; Startmodus-Weiche
`0xC002AD74` bei 74,8; Globals laden 74,9; Panel-Update-Merker bei 75,6; Display gelöscht bei 419, Hauptbildschirm ab 465.

- **Offline:** Beim Zeichnen des Startbilds gibt es noch kein Flash-Objekt und keine gehaltenen Tasten. Ein Laden davor
  liefe ohne Notschalter.
- **Der Aufruf `0xC002AC38` (Bild 13) fällt weg.** Stattdessen zeichnet ein Haken an der Aufrufstelle `0xC002ADAC`
  (`bl 0xC002A248`, nur auf dem normalen Weg, nach Panel-Austausch, Tastenabfrage und Kennungsprüfung) einmal das
  gespeicherte Bild oder das der VSB. Die Startmodi 1 bis 11 und die Update-Abfrage laufen nicht dort vorbei. Das Display
  bleibt in der Zwischenzeit hell und leer: das Licht schaltet die Firmware bei 52,5 ms unabhängig vom Startbild ein
  ([Startphase](../messungen/2026-10-10-startphase.md)). Vor den Rettungswegen läuft kein neuer Code. Die Prüfung vor
  dem Export braucht dafür eine ausdrückliche Ausnahme ([Patcher](../patcher.md), Regel 1).
- **Ablauf des Hakens:** `0xC002A248` aufrufen, dann: EXIT gehalten oder Panel-Update-Merker (`+0x22`) gesetzt: zurück.
  Sonst lesen (`0xC0029A74(obj, puffer, 0x7F0000, 0x40C)`), prüfen (Kennung, Version, Länge, CRC, CRC nicht
  `FFFFFFFF`), bei Erfolg den Deskriptor-Zeiger `*0xC00C5A54` auf den Puffer tauschen, Puffer löschen, zeichnen und
  ausgeben wie nach dem Original-Startbild (`0xC0015DD0` zweimal). Bei jedem Fehler nichts tun: das VSB-Bild bleibt.
- **Gemessen** (Emulator, vier Fälle plus Notschalter): leerer Sektor, gekipptes Bit und halb geschriebener Satz zeigen
  das VSB-Bild, ein gültiger Satz das eigene Bild ab 80 ms, bei gehaltenem EXIT bleibt das VSB-Bild. In allen Fällen
  folgt der Hauptbildschirm ohne Assertion.
- **Hergeleitet:** Der Tausch des Deskriptor-Zeigers bleibt stehen, der Editor findet das aktuelle Bild also immer über
  `*0xC00C5A54`. Hängt der Haken-Code, startet das Gerät nicht mehr normal; EXIT beim Einschalten umgeht ihn,
  Startmodi und Update-Abfrage bleiben erreichbar. `0xC002ADAC` gehört damit zur Startphase im Sinne von Regel 2 in
  [patcher.md](../patcher.md) (`tools/emu/bootmap.py`), eine gewollte Ausnahme.
- **Offen:** andere Leser von Bild 13 nach dem Start; ob der SPI-Treiber am Gerät an `0xC002ADAC` schon bereit ist (die
  Firmware liest dort selbst schon die Kennung und die Globals über denselben Weg, hergeleitet).

## 6. Notschalter

- **Gemessen:** Mit `held = 0x2000` steht an `*(*0xC033E6F8 + 0x18)` schon am
  Haken `0xC002ADAC` (74,9 ms) `0x2000`, oberes Wort 0. Nach rund 21 s mit
  Menübedienung und mehreren EXIT-Drücken steht dort immer noch `0x2000` (Bit 13
  gesetzt), ohne gehaltene Taste 0. Beim Zeichnen des Startbilds (52,9 ms) ist
  das Panel-Objekt noch nicht angelegt (`*0xC033E6F8` = 0), die Maske also dort
  nicht lesbar.
- EXIT ist Bit 13: beim Start gehalten `0x2000`, Startmodus 0, am Gerät gemessen
  ([Rückweg geübt](../messungen/2026-10-10-rueckweg-geuebt.md), Punkt 6).

## 7. Bedienung im Editor: SHIFT, Malen, Rad

Alles **gemessen im Emulator** (`tools/emu/splash_cases.py run`, BLECH auf einer eigenen Hacktribe-Datei mit dem
Flash-Abbild vom 09.10.), am Gerät nicht geprüft, außer wo es dabeisteht.

- **SHIFT gehalten:** ein Schritt des Rads ist eine ganze Zeile (128 Pixel), mit Umlauf über die 8192 Pixel. Erkannt
  über das Tastenwort von SHIFT (Taste `0x0A`, Wort `0xC06BCA70 + 8 * 0x0A` nicht 0). Gemessen: zwei Schritte von
  Pixel 3 nach 259, drei zurück nach 8067 (Umlauf), einer vor nach 3, das Bild bleibt unverändert.
- **MENU gehalten malt:** MENU kippt das Pixel und merkt sich die neue Farbe (`S_PAINT`, `STATE + 0x30`). Solange MENU
  (Taste `0x09`) gehalten ist, geht der Cursor Schritt für Schritt, und jedes Pixel, auf dem er landet, bekommt diese
  Farbe. Ein schneller Dreh mit mehreren Schritten in einer Nachricht lässt also keine Lücke. Gemessen: vier Schritte
  in einer Nachricht, die Bytes 3 bis 7 tragen die Farbe des Kippens, Byte 8 bleibt.
- **Das Bild bleibt beim Drehen stehen:** nach VALUE setzt die Firmware am Bildschirm-Manager das Flag "alles neu
  zeichnen" (`+0x5C`, gesetzt bei `0xC006F00C`, im nächsten Takt gelöscht bei `0xC006F1B8`). Der Takt malt dann die
  Widgets der Seite über das Bild. Ein Neuzeichnen des Bilds erst im nächsten Takt reicht nicht: am Gerät blitzte die
  Menüseite kurz auf (Rückmeldung vom Gerät 17.10.), das Display überträgt schon dazwischen. Darum gilt: solange der
  Editor offen ist, sieht der Takt nur das Widget des Editors. Der Widget-Vektor der Seite wird gegen einen mit nur
  diesem Widget getauscht und beim Verlassen und beim Abbau zurückgegeben, und der Takt-Haken löscht den Wunsch, alles
  neu zu zeichnen. Gemessen: Schreibzugriffe in den Displaypuffer nach einem Rad-Klick 3 (nur der Cursor) statt 1606
  zum Leeren plus 8061 Pixel.
- **Offen:** ob die Firmware SHIFT mit dem Rad auf der Global-Seite selbst noch anders nutzt. Im Emulator kam der
  Schritt unverändert im Slot an.

Quelle: Messung 2026-10-18/startbild-malen, Messung 2026-10-17/startbild-import

## Aufbau des Patches

Alles im `FF`-Bereich ab `0xC01A2100`, eigene Bytes nur dort plus wenige Stellen im Original (Belegung in
`tools/patch/splash_editor.py`).

1. **Zeiger** `0xC0064D3C` (Literal der vtable von Bildschirm 9, VSB `0x64E3C`) zeigt auf eine Kopie der vtable
   (18 Wörter) mit den Slots 0, 1, 2, 3, 4, 5, 6, 10. Jeder Ersatz fragt zuerst den Notschalter-Merker und springt sonst ins
   Original.
2. **Seite 20** "SPLASH SCREEN": eigener Zähler statt `0xC0691328`. Titel über die vorhandenen Text-Widgets
   (`0xC0085888` leeren, `0xC00857E4` Titel, `0xC0085828` "press  [ Enter ]" aus `0xC00A5A23`). Die Seitenanzeige zeigt "/21"
   (zwei Literale der Firmware).
3. **Editor-Modus:** Puffer aus `*0xC00C5A54` füllen, Display löschen und Bild zeichnen, ein eigenes Widget in den Vektor des
   Bildschirms hängen (Slot 2 schaltet alle sechs Takte das Pixel am Cursor um; Slots 1 und 4 leer). VALUE bewegt den
   Cursor, Index `y * 128 + x` modulo 8192. MENU kippt das Bit und setzt das Pixel neu. EXIT verlässt den Modus.
4. **WRITE** im Modus: Slot 3 sieht `(0x0E, 1)` vor dem zentralen Speichern. Dort Datensatz bauen und
   `0xC0029AB8(0xC0029A40(), 0x7F0000, 1036, satz)` aufrufen, danach `*0xC00C5A54` auf den Puffer zeigen. Die Firmware
   speichert danach wie immer die (unveränderten) Globals und zeigt "Working...", das dient als Rückmeldung.
5. **Start:** Haken an `0xC002ADAC` (Abschnitt 5).

## Risiken

- **Startcode:** Der Haken läuft auf jedem normalen Start. Ein Fehler darin verhindert den Hauptbildschirm. Rettung ist EXIT
  beim Einschalten. Vor dem ersten Flashen am Gerät lesend prüfen (`tools/device/screen_check.py --held`).
- **Flash-Ort:** `0x7F0000` hat keinen bekannten Schreiber (aus den direkten Aufrufen hergeleitet). Indirekte Aufrufe über
  Funktionszeiger und ein Löschen ganzer Blöcke durch den Bootloader oder Korgs Update sind nicht ausgeschlossen. Dann
  greift der Rückfall auf das VSB-Bild.
- **Löschdauer:** Beim Sektor-Löschen und Programmieren hält `0xC0000D80(2)` eine Sperre, Audio- und MIDI-Aussetzer am
  Gerät sind möglich (die Firmware macht dasselbe beim Speichern der Globals).
- **Tabellen mit Index 20:** Würde `0xC0691328` je 20 oder riefe der Code für Seite 20 die Originale `0xC0064948` und
  `0xC007B094`, läse die Firmware hinter ihre Tabellen (bei `+0x448` ein Aufruf über Müll). Der Patch hält das Byte unter 20.
- **Batterie-Symbol:** es übermalt 14 Byte oben im Editor. Ob es am Gerät das Bild stört, ist offen.
- **Firmware-Stand:** Alle Adressen gelten nur für diese VSB.

## Offen

- Was `+0x3A8` im Parameter-Objekt tut.
- Ob die zweite Zeichenebene (Statusleiste) im Editor angehalten werden darf.
- Löschdauer und Flash-Typ am Gerät; ob Korgs Update oder "alle Daten laden" von SD den Block `0x7F` anfasst.
