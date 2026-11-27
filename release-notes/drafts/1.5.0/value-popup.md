### Entwurf release-notes/1.5.0.md (kommt mit dem Versionssprung)

**Behoben**
- Nach einem Regler gehen Tasten und Hauptrad sofort: MENU, WRITE, SHIFT + Taste, die anderen Tasten und das Hauptrad schließen das Werte-Fenster und tun gleich, was sie sollen, auch im Menü
  - Was: solange nach einem Dreh am Regler der Wert auf dem Display stand, schluckte die Firmware den Tastendruck. MENU und WRITE schlossen nur das Fenster und brauchten einen zweiten Druck, SHIFT + Taste wirkte wie die Taste allein, im Menü ging das Hauptrad ganz verloren. Der Fehler steckt schon in Korgs Firmware. Die Filtertasten lassen das Fenster weiter stehen.

## English

**Fixed**
- Keys and the main dial work right after a knob: MENU, WRITE, SHIFT + key, the other keys and the main dial close the value window and do their job at once, in menus too
  - What: while the value of a turned knob was on the display, the firmware swallowed the key press. MENU and WRITE only closed the window and needed a second press, SHIFT + key acted like the key alone, in a menu the main dial was lost completely. The bug is in Korg's own firmware. The filter keys still keep the window.
