# 77. Neustart nach dem Update, und Neustart überhaupt

Nach einem Firmware-Update soll das Gerät von selbst neu starten, statt dass man es aus- und wieder einschalten muss. Und
allgemein soll ein Neustart möglich sein, ohne das Gerät auszuschalten.

Status: offen. Ein Neustart über den Watchdog-Timer ist als Stub und im Emulator gebaut, am Gerät nicht probiert
([Neustart über den Watchdog](../messungen/2026-11-16-watchdog-neustart.md)). Zurück zu den [Ideen](../ideen.md).

## Was es schon gibt

- Der Ausschalt-Patch (`tools/patch/power_off.py`) hängt im Ausschalt-Handler `0xC0038A54`. Dort speichert die
  Firmware und lässt danach die Stromhaltung los. Ein Neustart könnte denselben Weg nehmen, nur am Ende neu starten
  statt auszugehen.
- Das Update über USB (`tools/device/usbfile.py`, BLECH FILE BEGIN) schreibt die `SYSTEM.VSB` auf die Karte. Danach muss man heute
  von Hand ausschalten und mit der Update-Tastenkombi wieder einschalten.

## Offen

- Ob das Gerät nach dem Watchdog-Reset wieder hochfährt oder ausgeht (Stromhaltung).
- Ob ein Neustart direkt ins Update führen kann, ohne dass die Tastenkombi gedrückt ist (ein Merker, den der
  Bootloader liest?). Sonst kann der Neustart nach dem Update nur normal starten, und das Update braucht weiter die
  Tastenkombi.
- Dass vorher alles gespeichert wird wie beim Ausschalten: Pattern, Einstellungen, Karte zu.
- Wo der Neustart ausgelöst wird: Menüpunkt unter BLECH, ein SysEx-Befehl für die App (nach dem Update über USB), oder
  beides.
- Rot und blau, mit und ohne Hacktribe.
