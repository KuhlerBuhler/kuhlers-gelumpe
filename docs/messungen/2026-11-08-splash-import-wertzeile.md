# SPLASH IMPORT: die Wertzeile zeigt nur den Namen

Stand 8. November 2026. **Gemessen** im Emulator mit Hacktribe 2.02 (eigene Datei) und Korgs Original 2.02 rot, jeweils mit
dem BLECH-Satz. Fälle: `tools/emu/menu_cases.py` (`splash_menu_cases`). **Am Gerät nicht geprüft.** Die blaue Electribe hat
keinen Startbild-Editor und damit keine Seite SPLASH IMPORT.

## Befund am Gerät

`Menü -> BLECH -> CUSTOMIZATION -> SPLASH -> SPLASH IMPORT` ohne `.bmp` in `KORG/blechtribe/`: über `no .bmp file` liegt
`press  [ Enter ]`, rechts steht `er ]` über. Gemeldet mit dem Stand von develop.

## Ursache

Die Seite schrieb den Dateinamen (oder `no .bmp file`) in die Wertzeile und dazu `press  [ Enter ]` in die dritte Zeile. Die
Firmware zeichnet die dritte Zeile ab Spalte 28 auf der Zeile des Werts (`page_overlap` in `menu_cases.py` beschreibt das), beide
Texte landen also übereinander. Kein Rest einer alten Zeichnung, sondern zwei Texte im selben Bild. **Gemessen** vor dem Fix:
83 Pixel neben dem Wert ohne Datei, 105 bei `splash.bmp`.

## Fix

SPLASH IMPORT lässt die dritte Zeile leer (`menu_text_splash_pick` in `tools/patch/script_menu.s`). Was ENTER gesagt hat
(`loaded`, `no .bmp file`, `not 128x64 1 bit`) ersetzt den Namen wie bisher. SPLASH DRAW und SPLASH RESET haben keinen Wert und
behalten `press  [ Enter ]`.

Lange Namen: ab 12 Zeichen des breitesten Buchstabens (`m`) schiebt die Firmware die Buchstaben ineinander, gemessen mit
`draw_texts`: 11 mal `m` endet bei Spalte 124, 12 mal füllt die Zeile von 0 bis 127 mit unlesbaren Zeichen. Ein Name mit mehr als
11 Zeichen steht darum ohne `.bmp` und auf 11 Zeichen gekürzt da (`splash (1).bmp` wird `splash (1)`). ENTER liest weiter die Datei
mit dem vollen Namen.

## Ergebnisse

| Fall | Was geprüft wird | Marker |
|---|---|---|
| `splash_no_file_value_clean` | von SPLASH DRAW mit EDIT zurück auf SPLASH IMPORT ohne Datei: Texte `no .bmp file` und leere dritte Zeile, die Pixel der Wertzeile sind genau die von `no .bmp file` allein (0 zu viel, 0 fehlen) | gemessen, vor dem Fix rot |
| `splash_list_value_clean` | zwei Dateien, Name, mit dem Rad der nächste, dann `loaded` nach ENTER: jedes Mal genau die Pixel des Werts allein | gemessen, vor dem Fix rot |
| `splash_import` | Texte vor ENTER `splash.bmp` ohne dritte Zeile | gemessen |
| `splash_long_name_cut` | `a-very-long-name-here.bmp` zeigt `a-very-long`, kein Text am Rand, ENTER speichert genau dieses Bild | gemessen |

## Offen: VERSION

`Menü -> BLECH -> VERSION` hat dasselbe Problem, sobald der Start `e2sFx.all` geladen hat: Wert `HACKTRIBE` und dritte Zeile
`effects loaded` liegen übereinander (`page_overlap`: 35 gemeinsame Pixel, **gemessen**). Ohne Datei ist die dritte Zeile leer
und die Seite sauber. Hier lässt sich nicht einfach eine Zeile weglassen, ohne eine der beiden Angaben zu verlieren. Das bleibt
eine eigene Änderung.
