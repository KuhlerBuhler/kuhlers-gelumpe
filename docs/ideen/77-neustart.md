# 77. Neustart nach dem Update, und Neustart überhaupt

Idee (27.10.): Nach einem Firmware-Update startet das Gerät von selbst neu, statt dass man es aus- und wieder
einschalten muss. Und allgemein soll ein Neustart möglich sein, ohne das Gerät auszuschalten.
Stand 2026-10-27: **aufgeschrieben, nicht untersucht, nichts gebaut.**

## Was es schon gibt

- Der Ausschalt-Patch (`tools/patch/power_off.py`) hängt im Ausschalt-Handler `0xC0038A54`. Dort speichert die
  Firmware und lässt danach die Stromhaltung los. Ein Neustart könnte denselben Weg nehmen, nur am Ende neu starten
  statt auszugehen.
- Das Update über USB (`usbfile.py`, BLECH FILE BEGIN) schreibt die `SYSTEM.VSB` auf die Karte. Danach muss man heute
  von Hand ausschalten und mit der Update-Tastenkombi wieder einschalten.

## Offen

- Wie der Chip neu startet: Watchdog-Timer, Sprung auf den Reset-Vektor, oder das Reset-Register des SoC. Ob dabei die
  Stromhaltung bestehen bleibt.
- Ob ein Neustart direkt ins Update führen kann, ohne dass die Tastenkombi gedrückt ist (ein Merker, den der
  Bootloader liest?). Sonst kann der Neustart nach dem Update nur normal starten, und das Update braucht weiter die
  Tastenkombi.
- Dass vorher alles gespeichert wird wie beim Ausschalten: Pattern, Einstellungen, Karte zu.
- Wo der Neustart ausgelöst wird: Menüpunkt unter BLECH, ein SysEx-Befehl für die App (nach dem Update über USB), oder
  beides.
- Rot und blau, mit und ohne Hacktribe.
