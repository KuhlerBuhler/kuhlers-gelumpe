# Startbild-Editor im Menü Global: Hintergrund

Stand 2026-10-10, Speicherort geändert am 15.10.

**Stand 16.10.:** der Editor speichert wieder in den Flash (Sektor `0x7F0000`), damit das eigene Bild ab dem ersten Bild beim Start steht. Vom 15. bis 16.10. lag es auf der Karte ([Startbild auf der Karte](../messungen/2026-10-15-startbild-karte.md)); dabei war das Display bis zum Einhängen der Karte weiß. Bilder, die in dieser Zeit auf der Karte gespeichert wurden, liest die Firmware nicht mehr: einmal neu zeichnen und WRITE.

Wie das Startbild im Gerät liegt, wie man es im Menü Global zeichnet, im Flash
speichert und beim Start wieder lädt. Hier steht, was dazu gemessen, gelesen und
hergeleitet wurde und was offen ist (Idee 35 in [ideen.md](../ideen.md)).

**Status:** Der Editor ist gebaut (Patch `data/patches/splash-editor.json`,
erzeugt von `tools/patch/splash_editor.py`) und im Emulator geprüft. Der Bericht
dazu ist [Startbild-Editor: gebaut und im Emulator geprüft](../messungen/2026-10-10-startbild-editor.md).
Am Gerät ist nur der Notschalter (EXIT beim Einschalten) gemessen, der Editor
selbst nicht.

Basis: eine eigene SYSTEM.VSB (Sampler 2.02 mit Hacktribe) und ein eigener
Flash-Dump vom 9.10. Alles lief im Emulator (`tools/emu/machine.py`, Unicorn
2.1.4) oder wurde offline mit Capstone gelesen. Firmware-Funktionen wurden aus
Python aufgerufen: Register setzen, Rücksprung auf eine Falle im `FF`-Bereich,
und zwar an einer festen Stelle im UI-Ablauf (Einsprung des Bildschirm-Ticks
`0xC006F178`) bzw. beim Start an `0xC002ADAC`.

Markierungen: **gemessen** (im Emulator ausgeführt und beobachtet), **offline**
(Code gelesen), **hergeleitet**, **offen**.

Adressen sind RAM-Adressen. Datei-Offset in der VSB = RAM - `0xC0000000` +
`0x100`.

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
  im Emulator 22-mal pro Emulator-Sekunde. Er ruft für jedes Widget im Vektor des
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

Zeitachse (gemessen, Emulator-ms):

| ms | Was |
|---:|---|
| 52,9 bis 65,2 | Startbild gezeichnet (`0xC002AC38` → `0xC003F650`), dauert rund 12 ms, weil jedes Pixel einzeln geht |
| 66,7 | Startbild im Display (Ausgabe über `0xC0015DD0(0xC031BB2C,2,0)` und `(…,3,0)`; danach ruft das Original `0xC0015C78`, das ist der DSP-Boot, keine Anzeige) |
| 68,7 | Flash-Objekt angelegt (`0xC002AD44`); vorher ist `*0xC034028C` = 0 |
| 68,7 bis 74,8 | Panel-Objekt, Version, gehaltene Tasten, Kennung `0x220000` (`0xC00288EC`) |
| 74,8 | Startmodus-Weiche `0xC002AD74`; normaler Weg ab `0xC002ADA8` |
| 74,9 | Globals laden |
| 75,6 | Prüfung Panel-Update-Merker (`0xC002AE40`) |
| 419 | Display gelöscht, ab 465 Hauptbildschirm |

- **Offline:** Beim Zeichnen des Startbilds gibt es noch kein Flash-Objekt und
  keine gehaltenen Tasten. Ein Laden **vor** `0xC002AC38` müsste das Flash-Objekt
  früher anlegen und liefe ohne Notschalter. Außerdem ersetzt der Emulator den
  Treiber-Lesezugriff `0xC001E4AC` durch eine Kopie: Ein zu frühes Lesen sähe im
  Emulator also gut aus, auch wenn der SPI-Treiber noch nicht bereit wäre.
- **Entwurf: Nachzeichnen nach der Weiche.** Die Aufrufstelle `0xC002ADAC`
  (`bl 0xC002A248`, VSB `0x2AEAC`) liegt nur auf dem normalen Weg (Modus 0), nach
  Panel-Austausch, Tastenabfrage und Kennungsprüfung. Die Startmodi 1 bis 11 und
  die Update-Abfrage (Modus 10) laufen nicht hier vorbei (offline, `0xC002AD80`
  bis `0xC002ADA4`).
- **Gemessen:** An `0xC002ADAC` angehalten (74,9 ms), dann nacheinander aus
  Python aufgerufen: Notschalter und Panel-Update-Merker gelesen
  (`*0xC033E6F8 + 0x18`, `+0x22`), `0xC0029A40`, `0xC0029A74(obj, puffer,
  0x7F0000, 0x40C)`, Prüfung, Deskriptor-Wort `0xC00C5A54` auf Puffer + 8,
  `0xC003F0D4`, `0xC003F650(13,0,0)`, `0xC001531C(0,0,128,64)`, dann dieselbe
  Ausgabe wie nach dem Original-Startbild (`0xC0015DD0` zweimal; `0xC0015C78` ist
  der DSP-Boot und gehört nicht dazu, siehe
  [Startbild-Editor: gebaut und im Emulator geprüft](../messungen/2026-10-10-startbild-editor.md)).
  Ergebnis:

| Fall | gelesen / geprüft | Display 80 bis 400 ms | nach 4 s |
|---|---|---|---|
| Sektor leer (`FF`) | Kennung falsch, kein Tausch | VSB-Bild | Hauptbildschirm, keine Assertion |
| gültiger Satz | Tausch | eigenes Bild ab 80 ms | Hauptbildschirm, keine Assertion |
| ein Bit im Bild gekippt | CRC falsch, kein Tausch | VSB-Bild | Hauptbildschirm |
| halb geschrieben (2 von 5 Seiten) | CRC falsch, kein Tausch | VSB-Bild | Hauptbildschirm |
| gültiger Satz, EXIT gehalten | Maske `0x2000`, übersprungen | VSB-Bild | Hauptbildschirm |

- **Gemessen:** Ohne die Ausgabe-Aufrufe erscheint das eigene Bild erst bei rund
  400 ms und nur kurz, im Puffer stand es trotzdem richtig.
- **Gemessen, Einschränkung:** Die Aufrufe liefen außerhalb der Emulator-Zeit.
  Das Zeichnen über `0xC003F650` kostet beim Start rund 12 ms (gemessen am
  Original), also zeigt das Gerät in diesem Entwurf das VSB-Bild ungefähr von 67
  bis knapp 90 Emulator-ms, dann das eigene. Ein direktes Umsetzen der 1024 Byte
  in den Puffer (Bit 7 oben auf Bit 0 oben drehen) wäre schneller (hergeleitet).
- **Hergeleitet:** Läuft vor den Rettungswegen: nichts. Läuft nach ihnen, aber
  vor dem Hauptbildschirm: Notschalter-Abfrage (3 Befehle), Lesen von 1036 Byte
  über den normalen Lesepfad, CRC-Schleife über 1032 Byte, ein Wort schreiben,
  Zeichnen, Ausgabe. Hängt dieser Code, startet das Gerät normal nicht mehr; EXIT
  beim Einschalten umgeht ihn, Startmodi und Update-Abfrage bleiben erreichbar.
  `0xC002ADAC` gehört trotzdem zur Startphase im Sinne von Regel 2 in
  [patcher.md](../patcher.md) (`tools/emu/bootmap.py`). Das ist eine bewusst
  gewollte Ausnahme.
- **Hergeleitet:** Der Tausch des Deskriptor-Zeigers bleibt stehen. Damit findet
  auch der Editor das aktuelle Bild immer über `*0xC00C5A54`, egal ob VSB oder
  eigenes. Andere Leser von Bild 13 nach dem Start: offen.

## 6. Notschalter

- **Gemessen:** Mit `held = 0x2000` steht an `*(*0xC033E6F8 + 0x18)` schon am
  Haken `0xC002ADAC` (74,9 ms) `0x2000`, oberes Wort 0. Nach rund 21 s mit
  Menübedienung und mehreren EXIT-Drücken steht dort immer noch `0x2000` (Bit 13
  gesetzt), ohne gehaltene Taste 0. Beim Zeichnen des Startbilds (52,9 ms) ist
  das Panel-Objekt noch nicht angelegt (`*0xC033E6F8` = 0), die Maske also dort
  nicht lesbar.
- EXIT als Bit 13 war zunächst hergeleitet (siehe
  [Startphase](../messungen/2026-10-10-startphase.md)). Inzwischen ist es am
  Gerät gemessen: Beim Start gehalten `0x2000`, Startmodus 0
  ([Rückweg geübt](../messungen/2026-10-10-rueckweg-geuebt.md), Punkt 6).

## Entwurf und Umsetzung

Alles im `FF`-Bereich ab `0xC01A2100`, eigene Bytes nur dort plus wenige Stellen
im Original. Der Entwurf ist gebaut, so wie der Bericht
[Startbild-Editor: gebaut und im Emulator geprüft](../messungen/2026-10-10-startbild-editor.md)
ihn beschreibt. Abweichungen zum Entwurf stehen jeweils dabei.

1. **Zeiger** `0xC0064D3C` (Literal der vtable von Bildschirm 9, VSB `0x64E3C`):
   `0xC00E33F8` → Kopie der vtable (18 Wörter) im `FF`-Bereich. Entworfen waren
   die Slots 3 (Tasten roh), 4 (Edit ◄), 5 (Edit ►), 6 (MENU), 10 (VALUE) und 2
   (EXIT); gebaut sind die Slots 0, 1, 2, 3, 4, 5, 6, 10. Jeder Ersatz fragt
   zuerst den Notschalter-Merker und springt sonst ins Original.
2. **Seite 20** „SPLASH SCREEN“: eigener Zähler statt `0xC0691328`. Edit ► auf
   Seite 19 setzt unseren Zähler auf 20, setzt den Titel über die vorhandenen
   Text-Widgets (`0xC0085888` leeren, `0xC00857E4` Titel aus eigenem String,
   `0xC0085828` „press  [ Enter ]“ aus `0xC00A5A23`). Edit ► auf 20 geht auf Seite
   0 über das Original. Die Seitenanzeige stand im Entwurf offen („/20“ lassen
   oder über `0xC008A8A8(widget, 20, 21)` neu setzen); gebaut zeigt sie „/21“ (zwei
   Literale der Firmware).
3. **Editor-Modus** (MENU auf Seite 20): Puffer aus `*0xC00C5A54` füllen, Display
   löschen und Bild zeichnen (wie in Abschnitt 3 gemessen), eigenes Widget an den
   Vektor des Bildschirms hängen (Slot 2: alle 6 bis 8 Takte Pixel am Cursor mit
   `0xC0015824` umschalten, gebaut: alle sechs Takte; Slots 1 und 4 leer).
   VALUE: Cursor ± Delta, Index `y * 128 + x` modulo 8192, also Zeilenumbruch von
   selbst. MENU: Bit im Puffer kippen und Pixel neu setzen. EXIT: Modus
   verlassen, Seite 20 neu aufbauen. Edit ◄/► im Modus ignorieren.
4. **WRITE** im Modus: Slot 3 sieht `(0x0E, 1)` vor dem zentralen Speichern. Dort
   Datensatz bauen (Kennung, Version, Länge, Bild, CRC-32) und
   `0xC0029AB8(0xC0029A40(), 0x7F0000, 1036, satz)` aufrufen, danach
   `*0xC00C5A54` auf den Puffer zeigen. Die Firmware speichert danach wie immer
   die (unveränderten) Globals und zeigt „Working...“, das passt als
   Rückmeldung.
5. **Start**: `0xC002ADAC` `bl 0xC002A248` → `bl` auf eigene Funktion, die zuerst
   `0xC002A248` ruft, dann: EXIT gehalten oder `+0x22` gesetzt → zurück, sonst
   lesen, prüfen (Kennung, Version, Länge, CRC, CRC nicht `FFFFFFFF`), bei Erfolg
   `*0xC00C5A54` tauschen, Puffer löschen, zeichnen, Ausgabe wie nach dem
   Original-Startbild. Bei jedem Fehler nichts tun: Das VSB-Bild bleibt.
6. **Pflichtprüfungen** im Emulator (wie in Abschnitt 5 gemessen, als Tests in
   `check.py`): leer, gültig, gekippt, halb geschrieben, EXIT gehalten, dazu
   Startmodi, Update-Abfrage und Panel-Update unverändert.

**Entscheidung zum Laden:** Nicht neu zeichnen, sondern bis nach den Rettungswegen
gar kein Startbild. Der Aufruf `0xC002AC38` (Bild 13) fällt weg, der Hook nach den
Rettungswegen zeichnet einmal das gespeicherte Bild oder das der VSB. Das Display
bleibt in der Zwischenzeit hell und leer: Das Licht (GP6P3 bis GP6P5, rot, grün,
blau) schaltet die Firmware bei 52,5 ms unabhängig vom Startbild ein
([Startphase](../messungen/2026-10-10-startphase.md)). Vor den Rettungswegen läuft
damit kein neuer Code, es fällt nur ein Aufruf weg. Die Prüfung vor dem Export
braucht dafür eine ausdrückliche Ausnahme (gebaut, siehe Regel 1 in
[patcher.md](../patcher.md)).

## Risiken

- **Startcode:** Der Hook läuft auf jedem normalen Start. Ein Fehler darin
  verhindert den Hauptbildschirm. Rettung ist EXIT beim Einschalten; dass EXIT am
  Gerät Bit 13 ist, ist gemessen (Abschnitt 6). Vor dem ersten Flashen am Gerät
  lesend prüfen (`tools/device/screen_check.py --held`).
- **Kurzes VSB-Bild:** Im Entwurf mit Nachzeichnen steht das Original-Startbild 20
  bis 25 Emulator-ms, bevor das eigene kommt. Die gebaute Fassung zeichnet das
  Bild stattdessen erst nach den Rettungswegen (siehe Entscheidung oben). Die
  echte Dauer am Gerät ist nicht gemessen.
- **Flash-Ort:** `0x7F0000` hat keinen bekannten Schreiber, das ist aus den
  direkten Aufrufen hergeleitet. Indirekte Aufrufe über Funktionszeiger und ein
  Löschen ganzer Blöcke durch den Bootloader oder Korgs Update sind nicht
  ausgeschlossen. Dann greift der Rückfall.
- **Löschdauer:** Während Sektor-Löschen und Programmieren hält `0xC0000D80(2)`
  eine Sperre. Audio- und MIDI-Aussetzer am Gerät sind möglich (die Firmware macht
  dasselbe beim Speichern der Globals).
- **Tabellen mit Index 20:** Wird `0xC0691328` je 20 oder ruft unser Code für
  Seite 20 die Originale `0xC0064948`/`0xC007B094`, liest die Firmware hinter ihre
  Tabellen, im Fall `+0x448` ein Aufruf über Müll.
- **Batterie-Symbol:** übermalt 14 Byte oben im Editor. Im gebauten Editorlauf im
  Emulator zeigte das Display nach MENU das Startbild Byte für Byte, ob das Symbol
  am Gerät das Bild oben stört, ist offen.
- **Hacktribe-Stand:** Alle Adressen gelten nur für diese VSB.

## Offen

- Was `+0x3A8` im Parameter-Objekt tut.
- Ob die zweite Zeichenebene (Statusleiste) im Editor angehalten werden darf.
- Andere Leser von Bild 13 nach dem Start (Versionsseite, Ausschalten).
- Löschdauer und Flash-Typ am Gerät.
- Ob Korgs Update oder ein „alle Daten laden“ von SD den Block `0x7F` anfasst
  (Längen der Wege über `0xC0029CBC` nicht ausgewertet).
- Ob der SPI-Treiber am Gerät an `0xC002ADAC` schon bereit ist (die Firmware liest
  dort selbst schon die Kennung und die Globals über denselben Weg, hergeleitet).

Erledigt seit der Forschung: Bildschirm-Tick und Cursor-Widget sind als Code
gebaut und im Emulator gemessen (Blinken über Zeit, Abbau beim Verlassen von
Bildschirm 9), die Seitenanzeige zeigt „/21“.
