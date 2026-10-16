# Idee 16: Firmware ändern und gefahrlos prüfen

Stand: teilweise. Eigene Menüseiten laufen im Emulator, MFX 2 am Gerät. Zurück zu den [Ideen](../ideen.md).

Eigene Funktionen, neue Effektbausteine, LED-Mods, Optimierungen. Jede Änderung geht drei Stufen. Der Emulator senkt das Risiko, beweist aber nichts: die Hardware-Modelle sind unsere, Timing und DSP fehlen.

1. **Im Emulator:** startet die Firmware, stimmt das Display, reagieren die Tasten.
2. **Am Gerät nur im RAM.** Der Execute-Befehl (`0x57`, `src/protocol.mjs`) führt Code aus dem RAM aus; die LED-Steuerung darüber ist am Gerät belegt ([LED-Execute](../messungen/2026-10-08-led-execute.md)). Ein Absturz ist nach dem Neustart weg, im Rahmen der Leitplanke.
3. **Flash zuletzt,** erst wenn der Rückweg geübt ist ([Firmware-Rückweg](../messungen/2026-10-08-firmware-rueckweg.md)). Hin und zurück über den Updateweg ist am Gerät einmal geübt ([Rückweg geübt](../messungen/2026-10-10-rueckweg-geuebt.md)); die Rettung, wenn die laufende Firmware nicht mehr startet, ist offen. Der Bootloader wird nie angefasst; danach hilft nur noch JTAG.

Korg-Code kommt nicht ins Repo. Wenn je etwas geteilt wird, dann als Patch, wie bei Hacktribe.

## Stand der eigenen Menüpunkte

Die Menüseiten brauchten den Menüzustand ([Menüzustand](../messungen/2026-10-09-menuezustand.md)), er ist gemessen. Gebaut und im Emulator geprüft sind die Seite SPLASH SCREEN (Idee 35), das Menü BLECH (Idee 50, [BLECH-Menü](../messungen/2026-10-14-blech-menue.md)) und der Schalter MFX 2 (Idee 44). Am Gerät läuft bisher nur MFX 2.
