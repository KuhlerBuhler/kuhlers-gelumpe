# Media-Ordner: Startbild und Ladeanimation von der Karte, 2026-11-14

Stand 2026-11-14. Im Emulator mit Hacktribe 2.02 und Korgs Original 2.02 (rot) sowie der blauen 2.02, jeweils mit dem BLECH-Satz.
**Am Gerät ist nichts gemessen.** Markierungen wie in [Doom über USB](2026-11-11-doom-usb.md).

Frage: Können Startbild und Ladeanimation aus `SD:KORG/blechtribe/Media` kommen statt aus dem Patcher?

## Befund

- **offline:** Die Ladeanimation liegt als `Media/loading.blla` auf der Karte. `media_load` (`MEDIA_CODE` `0xC01AD000` + 0) liest sie
  beim Start in den RAM ab `0xC01A6000`, nur wenn ein Ladevorgang erwartet wird. Ohne Datei spielt Blechy. Der Patcher schreibt den
  Platz nicht mehr. `media_get` (+4) und `media_set` (+8) lesen und schreiben Byte 14 der Datei (`f_open`, `f_lseek` auf 14,
  `f_write` von 1 Byte), ohne die Datei neu zu schreiben (die FatFs der 2.02 hat kein `f_truncate`).
- **offline:** Byte 14 im BLLA-Kopf: Bit 0 keine Schleife, Bit 1 aus, Bit 2 Blechy statt Datei. Byte 15 ist 0, Byte 12 die Größe (u16).
- **offline:** `splash_sync` (`0xC01A250C`, neben IMPORT/DRAW/RESET) vergleicht `Media/splash.bmp` nach dem Start mit dem Bild im
  Flash. Weicht es ab, speichert `splash_tick` es in den Flash. SPLASH IMPORT und DRAW WRITE schreiben `Media/splash.bmp` mit
  (`media_write`, 62 Byte Kopf, fehlende Ordner mit `f_mkdir`). IMPORT listet zuerst `Media/`, dann das Wurzelverzeichnis.
- **offline:** BLECH-Menü, CUSTOMIZATION -> SPLASH: LOADING ANIM (CARD/BLECHY/OFF, ohne Datei NO FILE) und ANIM LOOP.
- **gemessen:** `loadbar_cases` auf Hacktribe und rot: 46 von 46. `menu_media` in `menu_cases` auf rot: grün.
- **gemessen:** `splash_menu_cases` auf Hacktribe, rot und blau: alle Fälle grün (13, 13, 12).
- **gemessen:** `splash_cases` auf allen drei: alle IMPORT- und Media-Schritte grün. `Media/splash.bmp` wird geschrieben oder nicht
  wie erwartet, ein anderes Bild landet im Flash und steht nach einem Neustart ohne Karte im Display, ein gleiches lässt den Flash
  unverändert. 67 Schritte "page index N equals stock" und die XY-CALIBRATION-Navigation schlagen fehl; ein Lauf mit dem Stand vor
  dieser Änderung zeigt dieselben 67 plus die neuen Media-Schritte. Ursache ist der Vergleich gegen die Basis ohne BLECH-Satz,
  nicht diese Änderung.

## Offen

- Am Gerät: Start mit und ohne `Media/loading.blla`, Byte 14 aus dem Menü und aus der App, `Media/splash.bmp` mit anderem Bild.
- Die 67 "equals stock"-Schritte in `splash_cases` brauchen eine Basis mit BLECH-Satz.
