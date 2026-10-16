# Idee 37: Farbiges Display-Licht

Stand: am Gerät gemessen; als Plugin-Funktion `korg.backlight` im Emulator gebaut, Rest offen. Zurück zu den [Ideen](../ideen.md).

Das Licht hat Rot, Grün und Blau getrennt (GP6P3 bis GP6P5). Am Gerät geschaltet ergibt das acht Zustände ([Startphase](../messungen/2026-10-10-startphase.md), `tools/device/backlight.py`).

## Ideen

- Lichtfarbe als Einstellung im eigenen Menü, gespeichert und beim Start nach den Rettungswegen gesetzt.
- Party-Modus: Farbwechsel alle 300 bis 400 ms, im Takt.
- Farbe als Statusanzeige, zum Beispiel Rot bei REC.

## Weiche Übergänge

Dafür wäre ein schnelles An und Aus der Pins nötig (Software-PWM) aus einem Firmware-Takt, also ein Code-Patch. Über das Kabel ist das zu langsam, und jeder Wechsel blendet kurz „Working...“ ein. Den Takt gibt es schon: die Dimm-Routine `0xC00289F4` läuft auf Batterie alle 0,5 ms. Ein Patch an ihr könnte Farben mischen, Verläufe und den Party-Modus ohne Kabel laufen lassen.

## Plugins

`korg.backlight(rot, gruen, blau)` schaltet die drei Farben an oder aus ([Plugins](../plugins.md)). Auf Batterie mit Power Save „Auto“ überschreibt die Dimm-Routine der Firmware die Farbe laufend.
