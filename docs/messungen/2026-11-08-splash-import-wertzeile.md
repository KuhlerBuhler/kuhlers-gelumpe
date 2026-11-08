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

## VERSION

`Menü -> BLECH -> VERSION` hatte dasselbe Problem, sobald der Start `e2sFx.all` gefunden hatte: Wert `HACKTRIBE` und dritte Zeile
`effects loaded` lagen übereinander (`page_overlap`: 35 gemeinsame Pixel, **gemessen**). Ohne Datei war die dritte Zeile leer und
die Seite sauber.

Der Effektstatus steht jetzt als kurzes Kürzel hinter der Firmware in der Wertzeile (`menu_text_version`, Texte in
`tools/patch/script_menu.s`), die dritte Zeile bleibt leer. Breiten mit `draw_texts` **gemessen**, Rand bei Spalte 125:

| Status | Wert | letzte Spalte HACKTRIBE / KORG RED |
|---|---|---|
| keine Datei | `HACKTRIBE` | unverändert |
| geladen | `HACKTRIBE FX` | 94 / 89 |
| beim Start übersprungen | `HACKTRIBE FX off` | 118 / 113 |
| Datei für eine andere Firmware | `HACKTRIBE FX fw?` | 120 / 115 |
| Datei kaputt | `HACKTRIBE FX bad` | 122 / 117 |

Die ausgeschriebenen Texte passen nicht: `HACKTRIBE FX skipped` und `HACKTRIBE FX wrong fw` laufen über die ganze Zeile. Die blaue
Electribe hat keine Effektdatei, dort steht nur `KORG BLUE`.

Fälle `fxcard:version_none`, `version_loaded`, `version_build`, `version_checksum` (`tools/emu/fx_card_cases.py`): Wert wie in
der Tabelle, dritte Zeile leer, kein `page_overlap`, die Pixel der Wertzeile genau die des Werts allein. **Gemessen** auf Hacktribe
und Korg rot, vor dem Fix rot (91 bis 139 Pixel neben dem Wert). `FX off` ist nur in der Breite gemessen, der Fall braucht die
Sperrtasten beim Start.
