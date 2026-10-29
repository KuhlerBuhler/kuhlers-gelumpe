# 71. Eigene Ladeanimation von der Karte, Bild je Ladefortschritt

Wunsch (27.10.): eigene animierte Ladebildschirme. Baut auf der Ladeanimation aus Idee 41 auf.

Stand 2026-10-27: **nur untersucht und aufgeschrieben, nichts gebaut, am Gerät nichts.** Marker: **gemessen**,
**hergeleitet**, **ungeprüft**.

## Vorgabe

- Das Startbild bleibt im Flash, wie heute.
- Die Ladeanimation kann von der Karte kommen: wenn sie läuft, ist die Karte schon eingebunden.
- **Ein Bild je Ladefortschritt, kein einfaches GIF.** Welches Bild gezeigt wird, hängt am Prozentwert des Ladens, nicht an
  der Zeit. So sind eigene Animationen möglich, die zum Fortschritt passen (etwa etwas, das sich füllt oder wandert).
- Fehlt die Datei oder ist sie kaputt, läuft Blechy wie heute.

## Befund

- Die heutige Animation ist BLECHs eigene Überlagerung von Korgs "Loading nnn%" (`tools/patch/load_bar.py`). Ihre Bilder
  (`assets/blechy/loading.bin`, 2440 Byte) schreibt der Patch in die Firmware (`0xC01A3D00`), sie werden je Bild
  zusammengesetzt. Höchstens ein neues Bild alle 50 ms. (gemessen, Code gelesen)
- Der Prozentwert kommt schon heute aus dem Loader (Hook `progress`, `0xC00366D4`). (gemessen)
- Im Firmware-Bild ist nur Platz für wenige KB, für eigene Bilder reicht das nicht. (hergeleitet)
- Die Karte ist ab dem Hook `stat` (`0xC002AE60`) eingebunden, das Startbild-Menü liest dort schon Dateien
  (`FS_OPEN 0xC009DB60`, `FS_READ 0xC009DD74`). Der Loader beginnt deutlich später. (hergeleitet)
- RAM für die Bilder: `0xC274F000` bis `0xC4000000` (24,7 MiB) war beim Spielen unbenutzt, während des Ladens nicht geprüft.
  Der Upload-Bereich `0xC1000000` ist nicht sicher (SysEx `0x54` schreibt dort). (gemessen beim Spielen, sonst ungeprüft)
- Lesezeit für rund 66 KB: geschätzt 20 bis 40 ms. (hergeleitet aus der Messung zum SD-Takt)

## Vorschlag zum Format (offen)

- Datei `KORG/blechtribe/loading.e2g` o. ä., 128x64, 1 Bit je Bild, Kopf mit Kennung, Version, Bildanzahl, Prüfsumme.
- Je Bild ein Prozentbereich (oder Bild n gilt ab n/N Prozent), dazu optional eine kleine Schleife innerhalb eines Bereichs,
  damit sich auch bei stehendem Fortschritt etwas bewegt.
- Optional: Prozentzahl und Balken des Patches darüber, abschaltbar in der Datei.
- Obergrenze an Bildern festlegen (etwa 64).
- Die App macht die Datei: Bilder je Bereich hochladen oder aus einem GIF verteilen, Vorschau mit einem Schieber für den
  Fortschritt.

## Plan

1. Nach `stat` die Datei lesen und prüfen, Bilder ins RAM legen.
2. Bild-Hook: Bild nach Prozent aus dem RAM zeigen, sonst der heutige Weg.
3. Emulator-Fälle mit virtueller Karte: gültig, falsche Kennung, zu kurz, keine Datei, EXIT gehalten, keine Karte,
   Startzeit mit und ohne Datei.
4. Seite in der App, Format in `docs/`.
5. Blau: hat die Ladeanimation bisher nicht, eigener Schritt.

## Am Gerät zu testen

- Startzeit mit 64 Bildern gegen heute.
- Langsame Karte, Karte beim Start gezogen, EXIT beim Einschalten.
- Bleibt der RAM-Bereich während des Ladens unberührt?
