# Rad in der Plugin-Liste und schnelles Drehen in SPLASH IMPORT

**Gemessen** im [Emulator](../glossary.md#emulator) mit [Hacktribe](../glossary.md#hacktribe) 2.02 (eigene Datei), Korgs Original 2.02 rot und blau, jeweils
mit dem [BLECH](../glossary.md#blech)-Satz. Code: `tools/patch/script_menu.s` (`splash_cache`, `splash_cached_text`, `menu_value_list`, Seite STATE
mit Art 52). Fälle: `menu:wheel_*` in `tools/emu/menu_cases.py` (`wheel_cases`), die Plugin-Fälle in `tools/emu/script_cases.py`.
**Am Gerät nicht geprüft.**

## Frage

Folgt die Plugin-Liste (BLECH > PLUGINS) und SPLASH IMPORT dem Hauptrad so wie der Dateibrowser der Firmware (DATA UTILITY, IMPORT SAMPLE),
auch beim schnellen Drehen? Kostet AUTO SAVE (BLECH > FEATURES) beim Drehen Arbeit?

## Weg

Eine Messung im Emulator, die ein schnelles Drehen nachstellt: 20 Schritte des Rads, 15 ms auseinander, danach läuft das Gerät,
bis sich das Display 0,3 s nicht mehr ändert. Gemessen werden die Zeit vom letzten Schritt bis zur letzten Änderung des Displays
(Nachlauf), die Befehle je Schritt und wo die Auswahl am Ende steht. Je 30 Dateien: `.bmp` in `KORG/blechtribe/` für SPLASH
IMPORT, `.blech` in `KORG/blechtribe/Plugin/` für PLUGINS, `.wav` im Wurzelordner für IMPORT SAMPLE. Beide Richtungen.
Die SD-Karte antwortet im Emulator im Raster von 100 µs, Wartezeiten auf die Karte zählen als Gerätezeit, nicht als Befehle.

## Verhalten

- **PLUGINS**: das Rad blättert durch die Liste und bleibt am ersten und am letzten Plugin stehen, wie in IMPORT SAMPLE. Das
  Schalten liegt auf der Seite STATE, der zweiten Seite eines Plugins (ENTER, dann EDIT): DESCRIPTION, STATE, die Seiten
  des Plugins, OFF, REMOVE. Dort schaltet das Rad das Plugin an und aus, WRITE speichert oder erlaubt ein fremdes Plugin.
- **SPLASH IMPORT**: die Namen der ersten 64 `.bmp`-Dateien werden einmal gelesen und in `LIST_TITLES` behalten (15 Zeichen und die
  Länge). Rad und Browser lesen daraus, ohne die Karte. Neu gelesen wird beim Betreten der Seite; für Dateien ab der 65. liest
  SPLASH IMPORT den Namen von der Karte. Ohne diesen Speicher läse jeder Schritt den Ordner `KORG/blechtribe` fünfmal ganz durch
  (Wertzeile, Zahl der Dateien, drei Zeilen des Browsers), und die Zeit ginge in das Warten auf die Karte.

## Ergebnisse

| Befund | Marker |
|---|---|
| SPLASH IMPORT (Hacktribe): Nachlauf 60,0 ms hoch, 30,0 ms runter; 1,86 Mio. und 1,87 Mio. Befehle je Schritt; Auswahl 20, dann 0 | gemessen |
| IMPORT SAMPLE der Firmware (Hacktribe, Vergleich): Nachlauf 60,1 ms hoch, 70,1 ms runter; 1,97 Mio. und 2,06 Mio. Befehle je Schritt | gemessen |
| PLUGINS: 20 Schritte hoch stehen auf dem 21. Plugin (20/30), 20 runter wieder auf dem ersten; Nachlauf 30,0 ms je Richtung, 1,81 Mio. und 1,79 Mio. Befehle je Schritt | gemessen |
| SPLASH IMPORT und PLUGINS folgen dem Rad damit so schnell wie IMPORT SAMPLE | Urteil |
| AUTO SAVE an oder aus: dieselben Zahlen; der Haken an SWITCH_SCREEN (`0xC0083D7C`) wird beim Drehen 0-mal angesprungen. AUTO SAVE kostet je Schritt nichts | gemessen |
| Alle sechs `menu:wheel_*` grün (Hacktribe) | gemessen |
| Grenze in den Fällen: Nachlauf höchstens 150 ms (`WHEEL_LAG_MS`), gut das Doppelte von IMPORT SAMPLE | Urteil |
| SPLASH IMPORT mit 70 Dateien: nach 66 Schritten steht `f66.bmp` in der Wertzeile, ENTER lädt genau diese Datei | gemessen |
| Rot: alle `menu:wheel_*` und `menu:splash_*` grün. Blau: die vier Fälle der Plugin-Liste grün, SPLASH IMPORT gibt es dort nicht | gemessen |

## Grenzen

- Der Speicher der Namen merkt nicht, wenn sich der Ordner ändert, während SPLASH IMPORT offen ist. Beim nächsten Betreten der
  Seite liest er neu. Am Gerät lässt sich die Karte bei offenem Menü kaum wechseln.
- Die Seite STATE ist eine Bedienentscheidung: das Rad schaltet ein Plugin nicht mehr direkt in der Liste.

## Offen

- **Am Gerät**: nicht geprüft, weder das Blättern noch der Nachlauf.
