# Doom: der Lader startet nach dem Einhängen der Karte

Stand 2026-10-17. Am Gerät gemeldet, im Emulator umgebaut und geprüft. Markierungen: **gemessen**, **hergeleitet**, **offen**.

## Am Gerät

- **Gemessen (Besitzer, 17.10.):** SHIFT + TAP beim Einschalten, mit `doom.bin` und `doom.wad` in `KORG/blechtribe/Doom/` (Prüfsumme
  stimmt): das Startbild bleibt stehen, dann `DOOM ERROR`, `POWER OFF`, `00000101`. Das ist `0x100` plus Fehler 1 von `f_mount`
  (`FR_DISK_ERR`): der Lader hängte die Karte bei `0xC002ADB0` selbst ein, noch bevor die Firmware es tut. Im Emulator ging das, am
  Gerät nicht.

## Umbau

- Der Lader sitzt jetzt bei `0xC002AE64`, der Anweisung (`mov r4, r0`) direkt hinter dem Einhängen der Karte durch die Firmware
  (`0xC002AE60`). Er führt sie selbst aus und kehrt zurück, wenn nicht genau SHIFT + TAP gehalten ist.
- Er hängt nichts mehr selbst ein: er prüft den Eintrag des Volumes der Firmware (`0xC06A010C`, Typ-Byte nicht 0, sonst `0x100`) und
  öffnet `doom.bin` dort, wie die Plugins die Karte lesen. Die Startaufrufe davor (Systemtakt, SD-Task, SD-Dienst) bleiben:
- **Gemessen:** ohne sie hängt `f_open` (Stufe 2, nichts gelesen); mit ihnen liest Doom die WAD.

## Im Emulator

- **Gemessen (`run_runtime.py`, 200 s):** Stufe 5 (spielt) nach 56 s Gerätezeit, 63 Bilder, 22 Spielticks, 2 Tastenereignisse, kein
  Schreiben auf die Karte, Speicherwächter heil, nur die Tasks 1 und 8. Vor dem Lader hat die Firmware ihre Globals und Patterns aus
  dem Flash gelesen und den Bildschirm-Manager angelegt (früher nicht); Samples lädt sie nicht. Die Prüfungen erlauben genau das.
- **Gemessen (`runtime_regression.py`):** alle Startmodi ohne SHIFT + TAP wie BLECH ohne Doom, Update-Abfrage und Panel-Update
  unverändert; keine Karte, fehlende Datei, kurze und kaputte `doom.bin`, fehlende und kaputte WAD melden `DOOM ERROR` und lassen
  sich ausschalten.
- **Offen:** ob der Disk-Fehler am Gerät weg ist und ob Doom dort spielt.

## Ladeanzeige (20.10.)

- **Am Gerät (Besitzer, 20.10.):** mit dem Stand nach dem Einhängen-Umbau blieb nach SHIFT + TAP nur das Startbild stehen,
  gewartet wurde weniger als 56 s. Kein `DOOM ERROR`.
- **Gemessen (`run_runtime.py`, 512-MiB-Karte):** Doom spielt nach 55,6 s Gerätezeit, bis dahin liest die Engine die WAD und
  zeigt nichts. Auf einer 64-MiB-Karte mit 512-Byte-Clustern liest sie etwa neunmal langsamer (nach 110 s 6 MB). Der Look des
  Ladebalken-Patches ändert daran nichts (mit und ohne Seitenhaken nach 30 s je 7,8 MB).
- **Umbau:** `tools/doom/runtime.c` zeichnet, solange die Engine vor ihrem ersten Bild liest, alle 200 ms "DOOM", "LADE WAD n MB"
  und einen Balken aus gelesenen Bytes durch WAD-Größe (`status_display.h`, `doom_status_loading`). Die Engine liest nicht die
  ganze WAD, der Balken steht beim ersten Bild also nicht am Ende.
- **Gemessen:** neue `doom.bin` (`7bfb6282…`, 450972 Byte), bytegleich aus dem neuen Quellarchiv neu gebaut; nach 15 s zeigt das
  Display die Anzeige mit 2 MB; Doom spielt weiter nach 55,6 s, die Anzeige kostet keine messbare Zeit. Der Lader ist auf die
  neue Datei gepinnt (`data/patches/doom-loader.json`), die alte `doom.bin` auf der Karte lehnt er ab.
- **Offen:** die echte Ladezeit am Gerät.
