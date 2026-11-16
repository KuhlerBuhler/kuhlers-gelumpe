# korg.file.picture: Polarität und Lesezeit

16.11.2026, Hacktribe (`ORIGINAL.BIN`, sha 163d1d8d) mit `data/patches/blech.json`, **gemessen im Emulator**
(`tools/emu`, `Machine.shown()`: gesetztes Bit = dunkler Punkt, nach `0xA7` das Komplement des Display-RAM).
Am Gerät nicht gemessen. Code: `tools/patch/script_media.s` (`media_reversed`), Referenz `src/script/media.mjs`
(`readMediaPicture`, Argument `reversed`).

## Startbild beim Einschalten

Boot mit Karte ohne Einstellungsdatei (DISPLAY INVERT ON ist die Vorgabe), mit Datei ON und mit Datei OFF, alle
10 ms Display-RAM und Controller-Zustand gelesen:

| Fall | Startbild (RAM gleich Bild) | Controller dabei | `0xA7` danach |
|---|---|---|---|
| ohne Datei | 16 Blicke | nicht umgekehrt | ja |
| Datei ON | 16 Blicke | nicht umgekehrt | ja |
| Datei OFF | 16 Blicke | nicht umgekehrt | nein |

Das Startbild steht also immer vor dem `0xA7` auf dem Display: ein gezeichneter Punkt (gesetztes Bit, die schwarze
Farbe der BMP) ist dunkel, egal wie DISPLAY INVERT steht. **gemessen**

## Viewer: korg.file.picture und korg.display.bitmap

Plugin auf der Karte: `korg.file.count(0)`, dann `korg.file.picture(pic, 0, 0, 0)` mit `Media/marker.bmp` (schwarzer
Block 40 x 20 links oben), dann `korg.display.take()` und `korg.display.bitmap(pic, 0, 0, 128)` je Rahmen.
`korg.display.bitmap` schreibt die Bits roh ins Display-RAM.

| Regel | DISPLAY INVERT | Display-RAM | Panel | schwarzer Punkt 0,0 |
|---|---|---|---|---|
| fest "gezeichnet = gesetzt" (Phase 1) | OFF | Bild | Bild | dunkel |
| fest "gezeichnet = gesetzt" (Phase 1) | ON | Bild | Negativ | **hell** |
| umgedreht, wenn das Display umgekehrt ist | OFF | Bild | Bild | dunkel |
| umgedreht, wenn das Display umgekehrt ist | ON | Komplement | Bild | dunkel |

**gemessen.** Mit der festen Regel wäre jedes Bild bei der Vorgabe ON ein Negativ. Darum dreht der Glue alle Bits um,
wenn das BLECH-Menü scharf ist und DISPLAY INVERT ON steht (`MENU_STATE` `M_ON` = 1 und `M_INV` != 0, dieselbe
Bedingung, unter der das Menü `0xA7` schickt). Die Ladeanimation dreht ihre Bits bei OFF selbst um, ihr gezeichneter
Punkt ist also auch immer dunkel; die `.blla`-Bilder folgen derselben Regel (**hergeleitet** aus
`src/loading-anim.mjs`, `pixelsToFrame`, und `tools/patch/load_bar.py`; im Emulator nicht eigens angezeigt).
`tools/patch/test_script_file.py` prüft die Bytes im Feld gegen die Referenz für Menü scharf mit ON, mit OFF und
Menü nicht scharf mit ON.

## Lesezeit (offen)

Jeder Aufruf allein in einem `frame`-Handler, Timer3-Ticks des Handlers (150 MHz):

| Aufruf | Zeit | Folge |
|---|---|---|
| `korg.file.count(0)`, 1 Datei | 3,7 ms | läuft |
| `korg.file.picture` (BMP, 1 KiB) | 9,0 bis 9,3 ms | `TIME`, Plugin abgeschaltet |
| `korg.file.frame` (GIF, 1 KiB, seit API 7) | 7,5 ms | `TIME`, Plugin abgeschaltet |

**gemessen im Emulator.** Das Rahmenbudget ist 5 ms. Auch das ältere `korg.file.frame` reißt es im Emulator; ob das
Gerät die Karte schneller liest, ist nicht gemessen. Für die Polaritätsmessung oben wurde das Plugin nach dem `TIME`
im Emulator wieder scharf geschaltet. Offen für den Viewer (Phase 4) und die Emulator-Fälle (Phase 5).

## Größe

`tools/patch/script_media.s` belegt 2756 Bytes Code samt Pool in MORE3 (Plan: etwa 1,1 KB geschätzt), frei bleiben
35688 Bytes auf Hacktribe und Korg rot, 42568 auf blau (`node tools/patch/script_runtime.mjs --build ...`). RAM 5824
Bytes hinter `GLIDE_END`: Liste 4096, Arbeitspuffer 1024, Lesepuffer 512 und 128, Zustand 64 (`MEDIA_LIST` bis
`MEDIA_END` in `tools/patch/script_hooks.py`). **gemessen**
