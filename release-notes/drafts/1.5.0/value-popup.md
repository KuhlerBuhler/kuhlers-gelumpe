### Entwurf release-notes/1.5.0.md (kommt mit dem Versionssprung)

**Behoben**
- Nach einem Regler gehen Tasten sofort: MENU, WRITE, SHIFT + Taste und die anderen Tasten schließen das Werte-Fenster und tun gleich, was sie sollen
  - Was: solange nach einem Dreh am Regler der Wert auf dem Display stand, schluckte die Firmware den Tastendruck. MENU und WRITE schlossen nur das Fenster und brauchten einen zweiten Druck, SHIFT + Taste wirkte wie die Taste allein. Der Fehler steckt schon in Korgs Firmware. Die Filtertasten lassen das Fenster weiter stehen.

## English

**Fixed**
- Keys work right after a knob: MENU, WRITE, SHIFT + key and the other keys close the value window and do their job at once
  - What: while the value of a turned knob was on the display, the firmware swallowed the key press. MENU and WRITE only closed the window and needed a second press, SHIFT + key acted like the key alone. The bug is in Korg's own firmware. The filter keys still keep the window.
