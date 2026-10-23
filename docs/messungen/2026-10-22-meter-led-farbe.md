# Meter: RAINBOW mit LED-Farbe, und LEDs, die nach einer 1 hängen bleiben (22.10.)

Am Gerät, mit METER STILL auf RAINBOW: die Farbe der LED-Seiten (LED RED, GREEN, BLUE) wirkte nicht mehr, die Bottom-LEDs zeigten
nur noch ein Gelb-Grün.

## Ursache 1: der Vierfarben-Modus übergeht die LED-Farbe (Code gelesen)

Ist auf einer der Seiten METER STILL bis METER LOUD eine Farbe gesetzt, auch RAINBOW, setzt `menu_look_apply` den Meter auf vier
Farben (`M_LED_EFF` 3). Dort nahm eine Zone auf STOCK die Farbe der Firmware (weiß, blau, grün, rot), die LED-Seiten zählten nicht.

Jetzt nimmt eine Zone auf STOCK die Farbe der LED-Seiten, wenn dort eine gesetzt ist, so hell wie der Pegel, genau wie der Meter in
eigener Farbe (`64 + Pegel² · 191`). Mit RAINBOW bei STILL läuft im Stillen der Regenbogen, beim Spielen leuchtet die LED-Farbe.
Ohne LED-Farbe bleibt es bei den Farben der Firmware.

## Ursache 2: die Sendefunktion der Firmware vergleicht das falsche Byte (Emulator, disassembliert)

`0xC00875F4` (LED-Manager, LED, force) schickt eine LED nur, wenn sie sich geändert hat. Dazu vergleicht sie die Kopie des zuletzt
Gesendeten (`Manager + 0x888 + 8 · LED`) mit dem Eintrag (`Manager + 0x48 + 8 · LED`): erst das Halbwort LED/Modus (`+4`), dann aber
den Helligkeitswert der Kopie (`+6`) mit dem Modusbyte des Eintrags (`+5`), das bei den Meter-LEDs immer 1 ist:

```
c008763c  ldrb r0, [r5, #2]     ; Kopie +6: Helligkeit
c0087640  ldrb r2, [ip, #1]     ; Eintrag +5: Modus
c0087644  cmp r0, r2
c0087648  popeq {r3, r4, r5, pc}
```

Ist eine 1 hinausgegangen, schickt die Funktion für diese LED nichts mehr, bis jemand mit `force` sendet. Die Firmware selbst
schreibt nur 0, 192, 255 und 2 × Velocity und trifft das nie. Der Regenbogen läuft durch alle Werte und bleibt im Emulator nach der
ersten 1 auf einem Kanal stehen (Bedienlog: rot und grün auf 1, blau läuft weiter; die Tabelle will 249, 116, 0).

Der Meter schreibt deshalb nie eine 1, sondern 2, in beiden Wegen (eigene Farbe und vier Farben).

## Geschwindigkeit

Der Regenbogen geht drei Schritte je 40-ms-Takt statt einem: einmal rundum in etwa 3,4 s statt 10 s.

## Prüfung (Emulator, Hacktribe und Korg rot, eigenes Flash)

`menu_cases.py`: neuer Fall `led_meter_rainbow_keeps_the_led_colour` (RAINBOW bei STILL, LED-Farbe 15/7/0: laut `249, 116, 0` wie
der Meter in eigener Farbe, still auf dem Farbkreis). Am Gerät noch nicht geprüft.
