# 76. Beim Einschalten das zuletzt angesehene Pattern öffnen

Idee (27.10.): Das Gerät merkt sich das Pattern, das gerade angesehen wird. Beim Einschalten öffnet es dieses Pattern
statt 001. Stand 2026-10-28: **für rot gebaut, im Emulator geprüft, am Gerät offen** ([Messung](../messungen/2026-10-28-letztes-pattern.md)).
Die Nummer liegt in Global-Byte 248, die Firmware speichert sie beim Ausschalten mit; Notschalter EXIT beim Einschalten.

## Was es schon gibt

- BLECH speichert seine Einstellungen auf der Karte, in `KORG/blechtribe/settings.a.bin` und `settings.b.bin`
  (`tools/patch/script_menu.s`). Dort könnte die Pattern-Nummer mit hinein.
- Der Pattern-Umschalter (`tools/patch/pattern_switch.py`) kennt das angezeigte und das bestätigte Pattern (VIEW).

## Offen

- Wo die Firmware beim Start Pattern 001 lädt, und ob sich dort eine andere Nummer einsetzen lässt, bevor die Samples
  geladen werden (sonst lädt sie zweimal).
- Wann gespeichert wird: bei jedem Wechsel auf die Karte, nur wenn die Firmware die Karte gerade nicht braucht, oder
  gesammelt. Ein Ereignis beim Ausschalten gibt es vermutlich nicht.
- Ob es ein Menüpunkt wird (an oder aus), und was passiert, wenn das gemerkte Pattern leer oder kaputt ist.
- Rot und blau.
