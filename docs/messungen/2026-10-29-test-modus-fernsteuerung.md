# Test-Modus und Fernbedienung aller Bedienelemente

Stand 29. Oktober 2026. Gemessen im Emulator mit Hacktribe 2.02 (eigene Datei), Korgs Original 2.02 rot und blau, jeweils
mit dem BLECH-Satz. Fälle: `tools/emu/remote_cases.py`, `tools/emu/testmode_cases.py`. **Am Gerät nicht geprüft.**
Beschreibung für Nutzer: [Test-Modus](../test-modus.md).

## Der Weg der Nachricht

- Die CsTask holt jede Nachricht des Panels aus der Warteschlange `0xC033E57C` (rot und blau dieselbe Adresse) und gibt sie
  an den Verteiler `0xC002837C` (blau `0xC00257E8`). **Offline** gelesen: die Schleife bei `0xC002A50C`, Literal bei `0xC002A594`.
- Gefüllt wird die Warteschlange vom Leser des Panels mit `0xC0024AFC(queue, 8 Byte)` (blau `0xC0020424`): Typ, vier
  Datenbytes, drei ungenutzte. Beim ersten Eintrag setzt die Funktion das Ereignis, das die CsTask weckt.
- Der Rahmenhaken der Laufzeit läuft **außerhalb eines Tasks**: die Nummer des laufenden Tasks (`0xC06A2894`) ist dort 0
  (**gemessen**, im Leser des Panels 2). Der Aufruf für Ereignisse aus einem Task (`0xC0000F78`) antwortet dort mit -25
  und weckt nichts (**gemessen**: zwei Nachrichten lagen in der Warteschlange, die CsTask lief nicht). Der Aufruf für den
  Kontext außerhalb eines Tasks ist `0xC0000E9C` (blau `0xC0000CC4`, dieselben 92 Byte); damit holt die CsTask die
  Nachricht sofort (**gemessen**).
- Die Warteschlange hat keinen Schutz gegen zwei Schreiber. Die Laufzeit kopiert deshalb mit gesperrten Interrupts und
  setzt das Ereignis danach.
- Jedes Byte vom Panel startet die 4 Stunden von Auto Power Off neu (`0xC00282D8`, **offline**). Die Warteschlange
  umgeht das, die Laufzeit setzt den Zähler deshalb selbst zurück.

## Ergebnis Fernbedienung (gemessen)

| Fall | Hacktribe | Korg rot | Korg blau |
|---|---|---|---|
| MENU, Edit ►, Rad +1, +1, -1, EXIT: Bildschirm, Seitenzähler, Display wie mit dem Panel | ja | ja | ja |
| Regler LEVEL, Drehgeber CUTOFF -3, Pad 5 an und aus, Touchpad mit zwei Lagen, SHIFT gehalten mit Edit ►: der Verteiler bekommt jede Nachricht Byte für Byte wie vom Panel, Display gleich | ja | ja | ja |
| Jeder Befehl genau einmal gezählt, Wort ohne Kennung nicht genommen | ja | ja | ja |
| `remote_press.py --emu` über BLECHs SysEx (WRITE, EXEC): Tasten, Rad, Drehgeber, Regler, Pads, Touchpad, SHIFT gehalten, Test-Modus, Display gelesen | ja | nicht gelaufen | nein (EXEC gesperrt) |

Über die Warteschlange braucht es keinen eigenen Handler je Bauteil, auch auf der blauen nicht.

## Ergebnis Test-Modus (gemessen)

| Fall | Hacktribe | Korg rot | Korg blau |
|---|---|---|---|
| Über USB an: 0 leuchtende LCD-Pixel (Controller bekam `0xAE`), Licht-Pins 0 %, alle 88 LEDs 0, Bildpuffer der Firmware gefüllt | ja | ja | ja |
| Dabei PLAY, Regler, STOP: bleibt dunkel | ja | ja | ja |
| Aus: Display, Licht und LEDs wie bei einem zweiten Gerät mit denselben Schritten ohne Test-Modus | ja | ja | ja |
| Auto Power Off 1 s vor Ablauf gesetzt: ohne Test-Modus aus, mit Test-Modus nach 2,5 s an und Zähler wieder bei 4 Stunden; danach zählt er wieder | ja | ja | ja |
| Plugin setzt `korg.system.testMode = 1`, ruft `korg.system.keepAwake()` und danach jedes Bild `korg.backlight(1, 1, 1)`, `korg.led(9, 255)`, `korg.ledHold(0)`: bleibt dunkel; nach `= 0` hell, LED 9 mit dem Wert des Plugins | ja | ja | ja |

Die Firmware sendet eine Seite des Displays nur, wenn sie sich gegenüber der Kopie bei `0xC031B710` (rot und blau) geändert
hat. Beim Umschalten ändert die Laufzeit in jeder Seite der Kopie ein Byte, damit alle acht Seiten neu gehen und mit der
ersten der Befehl `0xAE` oder `0xAF` (**gemessen**: ohne das kam er erst mit der nächsten Änderung des Bildes).

## Offen am Gerät

- Ob der Controller des Displays mit `0xAE` ganz dunkel ist (im Emulator nur nachgebildet: leerer Bildschirm).
- Ob die Nachrichten aus dem Rahmenhaken am Gerät so wirken wie im Emulator (gemessen am Gerät sind bisher nur Tasten
  über `korg.play`).
- Eine Nacht im Test-Modus: bleibt das Gerät an und dunkel.
