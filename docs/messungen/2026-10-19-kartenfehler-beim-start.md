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
| Power-Taste bei 1,5 s gehalten | aus am Ende des Starts | aus am Ende des Starts | aus nach 5,1 s (5 s halten) |
| Power-Taste bei 1,5 s, nach 1 s losgelassen | aus am Ende des Starts | aus am Ende des Starts | bleibt an |

Die 4 s mehr mit BLECH sind die eigenen Kartenzugriffe nach den Samples (Plugins, Einstellungen), die auf die Karte warten.
Am Gerät dauert so ein Warten länger als im Emulator (hergeleitet: der Emulator gibt "keine Antwort" sofort zurück).

Die Firmware nimmt die Power-Taste während des Starts an, schaltet aber erst am Ende des Starts aus, auch ohne BLECH und auch
bei einem kurzen Druck: der Eingangsfilter `0xC002837C` sieht die Meldung `06 01`, die Ausschaltmeldung `0x18` geht gleich raus
(`0xC0028C18`), ihr Handler `0xC0038A54` läuft aber erst nach dem Start (Emulator, Karte ohne Antwort: bei 4,5 s). Hängt der Start
am Gerät, kommt der Handler nie dran. Die Taste selbst liest der Power-Manager der Firmware am Pin GPIO 7.15 (`0xC00172D0`,
IN_DATA67 Bit 31, low = gedrückt).

## Geändert

- **Ladebalken** (`tools/patch/load_bar.py`): endet der Lader mit einem Code, geht das Overlay sofort weg, und der
  Bildschirm wird neu gezeichnet. Gemessen: `loadbar:card_error_ends_the_overlay`.
- **Power-Taste beim Start** (`tools/patch/script_hooks.s`, Eingangsfilter): kommt `06 01`, solange noch kein Bildschirm
  da ist oder Bildschirm 0, liest BLECH den Pin der Taste alle 50 ms. Ist sie 5 s lang gedrückt, lässt BLECH den Haltepin der
  Stromversorgung los (GPIO 7.11), wie der Doom-Fehlerbildschirm. Wird sie vorher losgelassen, verwirft BLECH die Meldung, das
  Gerät schaltet dann auch am Ende des Starts nicht aus (Rückmeldung 19.10.: nur 5 s halten soll ausschalten).
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

## Ein/Aus beim Sample-Laden (25.10.)

Am Gerät: Ein/Aus während der Ladeanimation 30 s gehalten, die Electribe blieb an. Die Abschaltung beim Start
(`script_hooks.s`) wartet auf die Meldung des Bedienfelds, die am Gerät in dieser Phase nicht kommt. Jetzt liest die
Ladeanimation in jedem ihrer Bilder den Pin der Taste (GPIO 7.15) selbst: 7 s ohne Unterbrechung gehalten (wie die Firmware:
2 s bis zur Meldung, dann 5 s), geht die Stromhaltung (GPIO 7.11) aus. Emulator, Hacktribe und Korgs Original:
`loadbar_cases.case_power_while_loading`, nur der Pin geht runter, keine Meldung: aus nach 7,1 s; nach 3 s losgelassen bleibt
sie an. Mit der alten Fassung bleibt sie im selben Fall an, wie am Gerät. Am Gerät noch nicht geprüft.
