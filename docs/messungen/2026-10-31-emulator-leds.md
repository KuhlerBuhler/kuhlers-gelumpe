# Emulator-LEDs: nur was die Firmware schickt

Stand 2026-10-31. **Nur im Emulator gemessen** (`tools/emu/machine.py`, leerer Flash, Netzteil), kein
Zugriff aufs Gerät. Drei eigene Firmware-Dateien, je 2.02:

| Datei | Build | SHA-256 (Anfang) |
|---|---|---|
| Hacktribe | hacktribe | `7cb4825c184a7e3f` |
| Korg rot | stock | `1d0f0689d5a12c8a` |
| Korg blau | synth | `41fc5f1c33209ef3` |

Markierungen: **gemessen** (Lauf im Emulator), **hergeleitet** (aus dem Code gelesen), **offen**. Keine
Firmware-Bytes im Repo, nur Adressen und Zahlen.

## Anlass

Ein Plugin mit `korg.padHold` (API 12) sah im Emulator anders aus als am Gerät. Grund: Die Zeichnung des
Geräts in der App (`site/app/panel.mjs`) hat ein gedrücktes Pad selbst rot gemalt, egal was die Firmware
an die Pad-LEDs schickte. Am Gerät leuchtet ein Pad nur, wenn die Firmware es einschaltet; hält ein Plugin
den Anschlag von der Firmware fern, bleibt es dunkel.

## Weg einer LED bis in die Seite

1. **Hergeleitet** ([LED-Zustand im RAM](2026-10-14-led-zustand-ram.md)): Der LED-Manager der Firmware
   (Zeiger bei `0xC0345A1C`, Hacktribe) reiht über den LED-Setzer `0xC0028600` die Panel-Nachricht
   `00 LED Helligkeit` in die Sendequeue `0xC0024BF4` ein, die über UART0 zum Bedienfeld geht.
2. **Hergeleitet** (`tools/emu/machine.py`, `Machine.panel`): Der Emulator nimmt jede 5-Byte-Nachricht
   an UART0 entgegen. Bei `00` setzt er `leds[LED] = Helligkeit`, sonst nichts. Eine andere Quelle für
   `leds` gibt es dort nicht; Tasten, Pads und Regler gehen nur als Nachricht an die Firmware.
3. **Hergeleitet** (`tools/emu/server.py`, `_run`): Nach jedem Rechenschritt schickt der Server die ganze
   Tabelle als Ereignis `leds`, wenn sie sich geändert hat; beim Ausschalten eine leere.
4. **Hergeleitet** (`site/app/emulator.mjs`): Die Seite gibt das Ereignis an `showLeds(..., true)` weiter.
   Jede LED, die nicht in der Tabelle steht, wird dunkel.
5. Die Zeichnung (`site/app/panel.mjs`) malt Tasten und Pads nur noch aus diesen Werten. Ein Druck
   färbt nur den Rand eines Pads, wie schon bei den Tasten; das ist keine LED.

## Messung: Tabelle gleich gesendeter Nachricht

**Gemessen** mit `tools/emu/led_mirror_probe.py`: 6 s booten, dann Pad 2 drücken und loslassen. Nach jedem
Schritt ist `Machine.leds` gleich dem letzten `00 LED Wert`, den die Firmware für jede LED an UART0 gab,
in allen drei Builds.

| Schritt | Pads (rot, blau), alle drei Builds |
|---|---|
| Stand | Pad 1 (0, 255) |
| Pad 2 gedrückt | Pad 2 (192, 255) |
| Pad 2 losgelassen | Pad 2 (0, 255) |

Die Firmware schaltet beim Druck also selbst die rote LED des Pads ein (Wert 192) und wählt den Part. Der
Emulator zeigt den Druck darum weiter an, aber nur, weil die Firmware es tut. Nur Korgs rotes Original
schaltet beim Druck zusätzlich LED `0x14` ein.

Die Firmware schickt ans Bedienfeld außerdem `02`, `80`, `85`, `86`, `90`, `91` und `A0`. Davon betrifft
nur `02 flag` vielleicht die LEDs (Energiesparen); seine Wirkung ist **offen**
([Panel-Controller](../hintergrund/panel-controller.md)). Im Lauf mit Netzteil kam `02 00 00 00 00`.

## Was die Seite noch umrechnet

Pad-LEDs zeigt die Zeichnung als an oder aus (jeder Wert ab 1 voll), nach der Messung
[Pad-LED-Stufen](2026-10-16-pad-led-stufen.md). Die ist am 18.10. teils widerlegt, das Bedienfeld rechnet
laut Code linear (**hergeleitet**). Ob die Zeichnung Pads gestuft zeigen soll, ist **offen** und hier nicht
geändert: es ändert nicht, ob ein Pad leuchtet.

## Prüfung

`test/e2e/support/emulator-suite.mjs`, Test "buttons and pads show only the firmware's LEDs": Ein Druck
auf ein Pad ohne LED-Nachricht lässt es dunkel, ein blaues Pad bleibt beim Druck blau, und WRITE folgt
der Helligkeit 64 so, wie sie kommt. Mit der alten Zeichnung schlägt der Test fehl.

**Gemessen** im Browser mit `npm start` und Hacktribe 2.02 im Emulator: Die Seite zeigt genau die LEDs der
Tabelle aus dem Ereignis `leds` (Pad 1 blau, Tasten mit LED 12, 15, 27, 34 und 40/22). Pad 2 gedrückt:
direkt nach dem Druck noch dunkel, sobald die Firmware rot 192 und blau 255 schickt lila. Losgelassen:
blau, wie die Firmware es schickt.
