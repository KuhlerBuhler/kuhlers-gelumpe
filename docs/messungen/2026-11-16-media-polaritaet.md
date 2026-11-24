# korg.file.picture: Polarität und Lesezeit

16.11.2026, [Hacktribe](../glossary.md#hacktribe) (`ORIGINAL.BIN`, sha 163d1d8d) mit `data/patches/blech.json`, **gemessen im [Emulator](../glossary.md#emulator)**
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

## Lesezeit

Jeder Aufruf allein in einem `frame`-Handler, Zeit im Aufruf (Timer3, 150 MHz):

| Aufruf | Zeit im Aufruf |
|---|---|
| `korg.file.count(0)`, 1 Datei | 3,7 ms |
| `korg.file.picture` (BMP, 1 KiB) | 9,0 bis 9,3 ms |
| `korg.file.frame` (GIF, 1 KiB, seit API 7) | 7,5 ms |

**gemessen im Emulator**, am Gerät nicht. Das Rahmenbudget ist 5 ms. Darum zählt die Zeit in den Kartenaufrufen
(`CARD_READS` in `data/script/contract.mjs`: `korg.file.frame`, `read`, `count`, `name`, `picture`) nicht für das
Budget und nicht für die Warnung: `card_timed` in `tools/patch/script_media.s` schiebt den Start des Rahmens und des
Handlers um die Zeit des Aufrufs vor, höchstens 50 ms je Rahmen (`CARD_CLOCK`, am Rahmenanfang 0). Die Kartentreiber
von Korg brechen ein Lesen ohne Antwort selbst ab ("Card Error" nach 8 bis 17 s, [docs/emulator.md](../emulator.md));
die 50 ms sorgen dafür, dass ein Plugin auf so einer Karte mit `TIME` abgeschaltet wird, statt jeden Rahmen anzuhalten.

`tools/emu/plugin_api38_cases.py`, Hacktribe mit `data/patches/blech.json`, ein Plugin liest in jedem Rahmen:

| Fall | ohne Regel | mit Regel |
|---|---|---|
| `korg.file.picture` je Rahmen, 6 s | `TIME` nach dem ersten Lesen, 8,94 ms | an, 137 Lesungen, langsamster Handler 0,09 ms |
| `korg.file.frame` je Rahmen, 6 s | `TIME` nach dem ersten Lesen, 7,53 ms | an, 138 Lesungen |
| zehn `korg.file.picture` in einem Handler | | `TIME`, 41 ms gezählt (90 ms gelesen, 50 ms frei) |

**gemessen im Emulator.**

## Größe

`tools/patch/script_media.s` belegt 2756 Bytes Code samt Pool in MORE3 (Plan: etwa 1,1 KB geschätzt), frei bleiben
35688 Bytes auf Hacktribe und Korg rot, 42568 auf blau (`node tools/patch/script_runtime.mjs --build ...`). RAM 5824
Bytes hinter `GLIDE_END`: Liste 4096, Arbeitspuffer 1024, Lesepuffer 512 und 128, Zustand 64 (`MEDIA_LIST` bis
`MEDIA_END` in `tools/patch/script_hooks.py`). **gemessen**
