BLECHTRIBE 1.5.0 und die App 1.5.0.

**Neu**
- IDLE SAVE: Licht und LEDs dimmen, wenn keiner spielt, auf Wunsch nur auf Batterie
  - Was: BLECH > CUSTOMIZATION > POWER SAVE > IDLE SAVE dimmt ohne Bedienung Displaylicht und LEDs nach 2, 3 und 4 Minuten auf 75, 50 und 25 %, nach 5 Minuten gehen sie aus. Drei Werte: OFF (nie), ON (am Netzteil und auf Batterie) und BATTERY ONLY (nur auf Batterie). Mit BATTERY ONLY bleibt das Gerät am Netzteil wach, Einstecken weckt ein gedimmtes Gerät sofort, nach dem Abziehen laufen die 2 Minuten von vorn.
  - Gut zu wissen: BATTERY ONLY ist die Vorgabe ohne Einstellungsdatei; wer schon eine hat, behält ON oder OFF. Gilt sofort, WRITE behält es. Mit BATTERY ONLY schreibt BLECHTRIBE die Einstellungen als Version 6; ein BLECHTRIBE bis 1.4.8 lehnt diese Datei ab und nimmt die andere Kopie oder die Standardwerte. Wer zurück auf 1.4.8 will, stellt vorher ON oder OFF ein und drückt WRITE. Plugins lesen und setzen es über `korg.menu.blech.customizations.powerSave.idleSave` (0 OFF, 1 ON, 2 BATTERY ONLY).

## English

**New**
- IDLE SAVE: the light and the LEDs dim while nobody plays, on battery only if you like
  - What: BLECH > CUSTOMIZATION > POWER SAVE > IDLE SAVE dims the display light and the LEDs to 75, 50 and 25 % after 2, 3 and 4 minutes without a touch, after 5 minutes they go dark. Three values: OFF (never), ON (on the adapter and on battery) and BATTERY ONLY (on battery only). With BATTERY ONLY the device stays awake on the adapter, plugging it in wakes a dimmed device at once, pulling it starts the 2 minutes again.
  - Good to know: BATTERY ONLY is the default without a settings file; a file you already have keeps ON or OFF. Applies at once, WRITE keeps it. With BATTERY ONLY BLECHTRIBE writes the settings as version 6; a BLECHTRIBE up to 1.4.8 refuses that file and takes the other copy or the defaults. To go back to 1.4.8, set ON or OFF first and press WRITE. Plugins read and set it with `korg.menu.blech.customizations.powerSave.idleSave` (0 OFF, 1 ON, 2 BATTERY ONLY).
