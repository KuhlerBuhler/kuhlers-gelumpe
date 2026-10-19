# Kartenfehler beim Start (19.10.)

Rückmeldung vom Gerät (18.10.): kann die Karte beim Start nicht gelesen werden, kommt kein "Card error", das Gerät bleibt
beim BLECH-Startbild stehen, und Ausschalten geht nur mit Batterien raus. Doom meldet dazu `DOOM ERROR 00000100`: die Karte
war beim Start des Laders nicht gemountet.

## Gemessen (Emulator, eigene Hacktribe-Datei, Karte mit 20 Samples)

Eine Karte, die ab 0,5 s auf Lesebefehle nicht mehr antwortet (`tools/emu/loadbar_cases.py`, `FailingCard`):

| | ohne BLECH (EXIT beim Einschalten) | BLECH bisher | BLECH jetzt |
|---|---|---|---|
| Rückgabe des Laders | 4 (Card Error) bei 4,5 s | 4 bei 4,5 s | 4 bei 4,5 s |
| Bild nach dem Fehler | das der Firmware | das BLECH-Bild des Ladebalkens, bis der Hauptbildschirm kommt | das der Firmware (Ladebalken sofort aus) |
| Hauptbildschirm | 4,6 s | 8,6 s | 8,6 s |
| Power-Taste bei 1,5 s | erst nach dem Start | erst nach dem Start | aus nach 0,05 s |

Die 4 s mehr mit BLECH sind die eigenen Kartenzugriffe nach den Samples (Plugins, Einstellungen), die auf die Karte warten.
Am Gerät dauert so ein Warten länger als im Emulator (hergeleitet: der Emulator gibt "keine Antwort" sofort zurück).

Die Firmware nimmt die Power-Taste während des Starts nicht an, auch ohne BLECH: sie kommt in der Warteschlange an (der
Eingangsfilter `0xC002837C` sieht die Meldung `06 01`), wird aber erst nach dem Start bearbeitet.

## Geändert

- **Ladebalken** (`tools/patch/load_bar.py`): endet der Lader mit einem Code, geht das Overlay sofort weg, und der
  Bildschirm wird neu gezeichnet. Gemessen: `loadbar:card_error_ends_the_overlay`.
- **Power-Taste beim Start** (`tools/patch/script_hooks.s`, Eingangsfilter): kommt `06 01`, solange noch kein Bildschirm
  da ist oder Bildschirm 0, lässt BLECH den Haltepin der Stromversorgung los (GPIO 7.11), wie der Doom-Fehlerbildschirm.
  Nicht mit EXIT beim Einschalten, nicht auf der blauen (dort ist der Pin nicht gemessen). Gemessen:
  `loadbar:power_key_during_the_start`.
- **Mounten wiederholen** (`load_bar.py`, Haken an der Frage nach `e2sSample.all`): steckt eine Karte (GPIO 4.1 low), ist
  ihr Volume danach aber nicht gemountet, fragt BLECH bis zu drei Mal nach, 500 ms auseinander. Ohne Karte kostet das nichts.

## Offen

- **Das Mounten-Wiederholen ist nicht gemessen.** Im Emulator kommt die Firmware nach einem ersten Lesebefehl ohne Antwort nie
  aus dieser Frage zurück, auch die unveränderte Firmware nicht: nach dem Befehl (`0xC0017978`) wartet der Treiber, und die
  Aufgabe läuft nicht weiter. Ob das am Gerät genauso ist oder eine Grenze des Emulators, ist nicht geklärt. Wenn am Gerät
  genauso, hängt der Start im SD-Treiber, und dann hilft nur die Power-Taste von oben; ein Fix müsste das Warten im Treiber
  begrenzen.
- Doom: der Lader prüft das Volume direkt nach der Frage. Mit dem Wiederholen davor sollte `00000100` bei einer langsamen
  Karte seltener kommen. Am Gerät prüfen.
