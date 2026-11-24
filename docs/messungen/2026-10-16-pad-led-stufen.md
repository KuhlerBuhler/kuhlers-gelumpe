# Pad-LEDs: Helligkeitsstufen

Die Pad-LEDs der Electribe 2 kennen Zwischenstufen. Das Bedienteil ([Panel-Controller](../glossary.md#panel-controller)) dimmt sie per PWM; nur 32 Tasten-LEDs kennen nur an oder aus ([Panel-Controller](../hintergrund/panel-controller.md#leds)).

## Messungen am Gerät

- **Gemessen (18.10.):** Das Plugin Pulsieren schickt jeden Rahmen (25 Hz) dieselbe Panel-Nachricht `00 index helligkeit` mit 0 bis 255 an die roten Pad-LEDs (`script_led_try_send` in `tools/patch/script_led.s`). Am Gerät pulsiert es flüssig.
- **Gemessen (16.10.):** Ein Probelauf (`tools/device/led_show.py`, Stub im RAM über Hacktribes Execute `0x57`, kein Flash) schickte über den LED-Setzer der Firmware `0xC0028600(objekt, index, helligkeit)` je Pad eine Nachricht mit den Werten 255, 128, 64, 40, 30, 21, 13, 6, und alle 16 Pads leuchteten gleich hell; mit 1, 2, 3, 4, 5, 8, 16, 0 waren nur Pad 8 und 16 dunkel. Warum dieser Lauf keine Stufen zeigte, ist **offen** (Vermutung, nicht geprüft: der LED-Manager der Firmware schickte danach seine eigenen Werte).
- Der LED-Manager der Firmware schickt dieselbe Nachricht (`0xC0087578` ruft `0xC0028600`, [LED-Zustand im RAM](2026-10-14-led-zustand-ram.md)). Das Rosa des Notenassistenten kommt aus Rot und Blau zusammen.

## Im Emulator

Das Bedienfeld der Seite (`site/app/panel.mjs`, `showLeds`) zeigt Pad-LEDs gestuft als Anteil von 255; nur die LEDs in `LED_ON_OFF` (`data/panel.mjs`) sind ab 1 voll an.
