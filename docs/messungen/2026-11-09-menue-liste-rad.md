# Rad in der Plugin-Liste und schnelles Drehen in SPLASH IMPORT

Stand 9. November 2026. **Gemessen** im Emulator mit Hacktribe 2.02 (eigene Datei), Korgs Original 2.02 rot und blau, jeweils
mit dem BLECH-Satz. Code: `tools/patch/script_menu.s` (`splash_cache`, `splash_cached_text`, `menu_value_list`, Seite STATE
mit Art 52). Fälle: `menu:wheel_*` in `tools/emu/menu_cases.py` (`wheel_cases`), die Plugin-Fälle in `tools/emu/script_cases.py`.
**Am Gerät nicht geprüft.**

## Frage

Beim Gerätetest von 1.4.5 fielen zwei Dinge auf:

1. In BLECH > PLUGINS blättert das Hauptrad nicht durch die Liste, nur EDIT und die Pfeiltasten.
2. In SPLASH IMPORT läuft das Display beim schnellen Drehen weit hinterher.

Woran liegt das, und folgt die Liste nach dem Fix dem Rad so wie der Dateibrowser der Firmware (DATA UTILITY, IMPORT SAMPLE)?
Dabei war AUTO SAVE (BLECH > FEATURES) an. Kostet AUTO SAVE beim Drehen Arbeit?

## Weg

Eine Messung im Emulator, die ein schnelles Drehen nachstellt: 20 Schritte des Rads, 15 ms auseinander, danach läuft das Gerät,
bis sich das Display 0,3 s nicht mehr ändert. Gemessen werden die Zeit vom letzten Schritt bis zur letzten Änderung des Displays
(Nachlauf), die Befehle je Schritt und wo die Auswahl am Ende steht. Je 30 Dateien: `.bmp` in `KORG/blechtribe/` für SPLASH
IMPORT, `.blech` in `KORG/blechtribe/Plugin/` für PLUGINS, `.wav` im Wurzelordner für IMPORT SAMPLE. Beide Richtungen.
Die SD-Karte antwortet im Emulator im Raster von 100 µs, Wartezeiten auf die Karte zählen als Gerätezeit, nicht als Befehle.

## Ursachen

- **PLUGINS**: das Rad blätterte nie. Auf der Ebene der Liste schaltete es das gewählte Plugin an und aus oder lud es (Art 36,
  `menu_value_script`); so stand es auch in [der Messung vom 8.11.](2026-11-08-plugin-liste-browser.md) ("Rad wie vorher").
- **SPLASH IMPORT**: jeder Schritt las den Ordner `KORG/blechtribe` fünfmal ganz durch: einmal für den Namen in der Wertzeile
  (`splash_pick`), einmal für die Zahl der Dateien und dreimal für die drei Zeilen des Browsers. Die Zeit geht fast ganz in das
  Warten auf die Karte, nicht in Befehle.

## Fix

- **PLUGINS**: das Rad blättert durch die Liste und bleibt am ersten und am letzten Plugin stehen, wie in IMPORT SAMPLE. Das
  Schalten liegt auf einer neuen Seite STATE, der zweiten Seite eines Plugins (ENTER, dann EDIT): DESCRIPTION, STATE, die Seiten
  des Plugins, OFF, REMOVE. Dort schaltet das Rad wie vorher in der Liste, WRITE speichert oder erlaubt ein fremdes Plugin.
- **SPLASH IMPORT**: die Namen der ersten 64 `.bmp`-Dateien werden einmal gelesen und in `LIST_TITLES` behalten (15 Zeichen und die
  Länge). Rad und Browser lesen daraus, ohne die Karte. Neu gelesen wird beim Betreten der Seite; für Dateien ab der 65. liest
  SPLASH IMPORT den Namen wie vorher von der Karte.

## Ergebnisse

| Befund | Marker |
|---|---|
| SPLASH IMPORT vorher (Hacktribe): Nachlauf 982,6 ms hoch, 991,6 ms runter; rund 12,1 Mio. Befehle je Schritt | gemessen |
| SPLASH IMPORT nachher (Hacktribe): Nachlauf 60,0 ms hoch, 30,0 ms runter; 1,86 Mio. und 1,87 Mio. Befehle je Schritt; Auswahl 20, dann 0 | gemessen |
| IMPORT SAMPLE der Firmware (Hacktribe, Vergleich): Nachlauf 60,1 ms hoch, 70,1 ms runter; 1,97 Mio. und 2,06 Mio. Befehle je Schritt | gemessen |
| PLUGINS vorher: die Auswahl bleibt beim ersten Plugin, das Rad nach oben versucht Plugins zu laden (5,46 Mio. Befehle je Schritt) | gemessen |
| PLUGINS nachher: 20 Schritte hoch stehen auf dem 21. Plugin (20/30), 20 runter wieder auf dem ersten; Nachlauf 30,0 ms je Richtung, 1,81 Mio. und 1,79 Mio. Befehle je Schritt | gemessen |
| SPLASH IMPORT und PLUGINS folgen dem Rad damit so schnell wie IMPORT SAMPLE | Urteil |
| Ein Schritt in SPLASH IMPORT vorher kostete rund 3,4 Mio. Befehle mehr als Leerlauf; der Rest des Nachlaufs war Warten auf die Karte bei fünf Ordnerdurchläufen | hergeleitet |
| AUTO SAVE an oder aus: dieselben Zahlen; der Haken an SWITCH_SCREEN (`0xC0083D7C`) wird beim Drehen 0-mal angesprungen, vorher und nachher. AUTO SAVE kostet je Schritt nichts | gemessen |
| `menu:wheel_*` mit der alten Firmware (Hacktribe): 5 von 6 Fällen rot (Liste bleibt stehen, Nachlauf 983 und 992 ms), mit dem Fix alle grün | gemessen |
| Grenze in den Fällen: Nachlauf höchstens 150 ms (`WHEEL_LAG_MS`), gut das Doppelte von IMPORT SAMPLE | Urteil |
| SPLASH IMPORT mit 70 Dateien: nach 66 Schritten steht `f66.bmp` in der Wertzeile, ENTER lädt genau diese Datei | gemessen |
| Rot: alle `menu:wheel_*` und `menu:splash_*` grün. Blau: die vier Fälle der Plugin-Liste grün, SPLASH IMPORT gibt es dort nicht | gemessen |

## Grenzen

- Der Speicher der Namen merkt nicht, wenn sich der Ordner ändert, während SPLASH IMPORT offen ist. Beim nächsten Betreten der
  Seite liest er neu. Am Gerät lässt sich die Karte bei offenem Menü kaum wechseln.
- Die Seite STATE ist eine Bedienentscheidung: das Rad schaltet ein Plugin nicht mehr direkt in der Liste.

## Offen

- **Am Gerät**: nicht geprüft, weder das Blättern noch der Nachlauf.
