# Patterns-Ordner: Export, Import-Browser, Laden beim Start (14.11.)

Zu `tools/patch/script_patterns.s` und `tools/patch/load_bar.py` (Release 1.5, rot und Hacktribe). Alles hier ist
**gemessen im Emulator** (eigene Dateien Hacktribe und Korg rot 2.02), nicht am Gerät, wo nicht anders gesagt.

## Datei

| Teil | Offset | Größe |
|---|---|---|
| Kopf, `KORG` an 0 | 0 | 0x100 |
| Globals (`GLST` bis `GLED`, dann Füllung) | 0x100 | 0x10000 |
| 250 Patterns, je `PTST` an 0 und `PTED` an 15356 | 0x10100 | je 0x4000 |

Ganze Datei 0x3F8100 Byte (4 161 792). Eine `.e2spat` ist 0x4100 Byte, Kopf und ein Pattern, ohne Globals.

## Start

- Die Firmware liest alle 250 Patterns bei etwa 80 ms aus dem Flash in den RAM (`0xC08B2940`, je 0x4000).
- Der Card-Haken läuft nach dem Sample-Lader und vor der ersten Patternwahl (Card-Haken 576 ms, Patternwahl 597 ms ohne
  Datei). Das Pattern, das das Gerät öffnet, ist also das der Datei.
- Jedes Pattern der Datei wird mit seinem Platz im RAM verglichen, nur ein anderes geht durch Korgs Pattern-Schreiben
  `0xC004C28C` (Platz im RAM und 16 KiB im Flash). Gleiche Datei noch einmal: kein Schreiben.
- Die Benutzeroberfläche zeichnet weiter, während der Card-Haken schreibt; der Hauptbildschirm kommt erst danach.
- Dauer im Emulator: 4 MiB lesen rund 9 s Emulatorzeit, je geändertes Pattern etwa 0,4 s dazu. Der Emulator-Flash hat
  keine Busy-Zeiten, die Dauer am Gerät ist **offen** (Datenblatt-Schätzung 30 bis 90 s für 250 geänderte Patterns).

## Globals

Korgs IMPORT ALL PATTERN übernimmt die Globals der Datei: im Emulator nahmen der Globals-Bereich (`0xC08A2940`) und die
laufenden Globals (Zeiger `0xC0691324`, Block um 4 verschoben) die 5 geänderten Bytes, dazu wechselte das laufende Byte
`+0xF8` von 1 auf 0. Geschrieben wird nur einmal, `0xC002A0C4` mit der Pattern-Bank. Der Gegenlauf ohne Import änderte
nichts. Entschieden 14.11.: der Start lädt die Globals nicht, nur die Patterns.

## Datei bleibt, jeder Start vergleicht

Ein Merker "schon geladen" auf der Karte ginge nur über das Archiv-Bit: Anlegen und Überschreiben setzen es auf Linux,
macOS und Windows, Kopieren ist **nicht geprüft** (Windows CopyFile/Explorer, macOS copyfile). Die FatFs der Firmware hat
kein `f_chmod`, kein `f_truncate`, kein `f_rename`. Deshalb vergleicht jeder Start die ganze Datei.

## Import-Browser

- Korgs Datei-Browser ist ein Objekt (`[0xC03405CC]`, vtable `0xC00A7F30`), sein Ordner ein `std::string` an `+0x18`, der
  von Import zu Import bleibt. Der Browser-Schritt `0xC00313B8` öffnet den Ordner (`0xC003D978`, darin `f_opendir`
  `0xC009E660`) beim Start des Imports und nach jedem MENU auf einem Ordner oder Upper Folder.
- `pat_browse_hook` sitzt auf `ldr r0, [r6]` bei `0xC0031400` davor: ist der Ordner noch der des letzten Öffnens (gleicher
  String, gleiche Länge, gemerkt in `KNOB_HOLD+4`/`+8`), beginnt ein neuer Import und der Ordner wird
  `SD:/KORG/blechtribe/Patterns`.
- Fehlt der Ordner, gibt `f_opendir` `FR_NO_PATH` und Korgs Browser geht von selbst nach `SD:`.
- Upper Folder geht von `Patterns` nach `SD:`, nicht eine Ebene hoch: Korgs Browser zählt seine Ebenen selbst mit.
- IMPORT SAMPLE (Erzeuger `0xC0061104`) teilt das Objekt, nicht den Schritt: nach dessen Browser öffnet der Import dort.

## Ladeanimation

`lb_stat` fragt nach `e2sSample.all` auch nach der Sicherung (`f_stat`, die Karte ist dann gemountet). Liegt sie da, zählt
der Fortschritt die Bytes beider Dateien: Samples zuerst, dann die Sicherung (`S_PAT`, `S_PPOS`, `S_PSIZE` in STATE+40
bis +48). Ohne `e2sSample.all` startet `pat_boot_load` das Overlay über `lb_patterns` (bei `0xC0181000` hinter dem Wort
`PABL`). Gemessen: mit 20 Samples steigt die Anzeige über die Samples bis rund 10 % und dann mit der Sicherung, ohne
Samples von 0 bis 100; beide enden mit dem Hauptbildschirm.

## Datum

Gerätedateien tragen immer den 01.01.2014, die Electribe hat keine Uhr ([Pattern-Export](2026-10-28-pattern-export.md)).
