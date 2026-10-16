# Pad-LEDs: nur an oder aus

Stand 2026-10-16. Gemessen am Gerät (Firmware 2.02 mit Hacktribe, BLECH v21), Werkzeug
`tools/device/led_show.py` (Stub im RAM über Hacktribes Execute `0x57`, danach zurückgesetzt, kein
Flash), angesehen und fotografiert vom Besitzer.

## Was getan wurde

Über den LED-Setzer der Firmware `0xC0028600(objekt, index, helligkeit)` ging an jedes Pad genau eine
Panel-Nachricht `00 index helligkeit`, die rote LED (`0x2c + 2n`) von Pad 1 bis 8 und die blaue
(`0x2d + 2n`) von Pad 9 bis 16, alle anderen Pad-LEDs auf 0.

| Lauf | Werte Pad 1 bis 8 (rot) und 9 bis 16 (blau) | Beobachtet |
|---|---|---|
| 1 | 255, 128, 64, 40, 30, 21, 13, 6 | alle 16 Pads gleich hell |
| 2 | 1, 2, 3, 4, 5, 8, 16, 0 | Pad 1 bis 7 und 9 bis 15 gleich hell, Pad 8 und 16 dunkel |

## Ergebnis

**Gemessen:** Eine Pad-LED kennt pro Nachricht nur an oder aus. 0 ist aus, jeder Wert ab 1 leuchtet voll.
Der LED-Manager der Firmware schickt dieselbe Nachricht (`0xC0087578` ruft `0xC0028600`,
[LED-Zustand im RAM](2026-10-14-led-zustand-ram.md)); ein Wert wie 21 des Notenassistenten leuchtet also
ebenfalls voll, das Rosa kommt nur aus Rot und Blau zusammen.

**Offen:** Ein älteres Foto des Besitzers zeigt Pads in mehreren Helligkeiten. Woher die kamen (schnelles
An und Aus durch Firmware oder Werkzeug, oder ein anderer Befehl an den Chip), ist nicht geklärt. Die
übrigen LEDs (Tasten, untere RGB-LEDs) sind hier nicht gemessen.

## Folge im Emulator

Das Bedienfeld der Seite (`site/app/panel.mjs`, `showLeds`) zeigt Pad-LEDs seitdem nur an oder aus,
wie das Gerät. Die anderen LEDs zeigen weiter den Wert als Helligkeit.
