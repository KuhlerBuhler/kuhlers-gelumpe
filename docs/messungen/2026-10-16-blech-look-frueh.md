# Aussehen früh im Start: Zeitlinie und der früheste Punkt

Stand 2026-10-16. Alles im Emulator (`tools/emu`, Unicorn), eigene `SYSTEM.VSB` (Hacktribe 2.02), virtuelle Karte mit
einer `e2sSample.all` (20 Samples, 4 s), die Zeiten sind Emulatorzeit ab dem Einsprung in die Firmware. **Am Gerät nichts
geprüft.** Was vor dem Einsprung läuft (Bootloader, Entpacken) ist im Emulator nicht abgebildet und wurde nicht gemessen.
Markierungen: **gemessen**, **hergeleitet**, **offen**.

## Zeitlinie (gemessen, Satz BLECH, Karte mit Sample-Datei)

| Emulator-ms | Was |
|---:|---|
| 0 bis 50 | die Firmware wartet in einer Schleife bei `0xC00297xx`, nichts am Display, Hintergrundlicht aus |
| 52,5 | erster Befehl an das Display (`0xB0`, Seite wählen): die Firmware löscht das Display seitenweise |
| 54,6 | Hintergrundlicht an (alle drei Pins) |
| 56,6 | das Panel-Objekt (`0xC033E6F8`) ist da |
| 59 | der Start erreicht die Rettungswege, danach Karte und Startbild-Editor |
| 86 | die Frage nach `e2sSample.all` (`0xC0035440`) mountet die Karte |
| 109,8 | erster Aufruf der Bildfunktion (`0xC003F650`), 122,9 erste nicht leere Bilddaten: das Startbild |
| 231 | die Oberfläche zeichnet zum ersten Mal, die Überlagerung des Ladebalkens liegt über dem Bild |
| 357 | der Ladebefehl ruft den Sample-Lader auf, bis etwa 1510 ms läuft er |
| 353 (neu) gegen 1511 (vorher) | das Menü ist scharf und die Einstellungen gelten (Hintergrundlicht, LEDs, Anzeige) |

Das Display ist also von 52,5 bis 122,9 ms leer bei eingeschaltetem Licht, das sind rund 70 ms, in denen es weiß leuchtet;
davor läuft nichts, das wir erreichen. Der Startbild-Editor zeichnet das Bild absichtlich erst nach der Kartenfrage (er
braucht die Karte für ein gespeichertes Bild, [Startbild auf der Karte](2026-10-15-startbild-karte.md)); das Bild der
Firmware käme ohne ihn bei etwa 53 ms ([gleiche Messung](2026-10-15-startbild-karte.md): 65 ms gegen 95 bis 100 ms mit Karte).
**Offen** (Entscheidung des Besitzers): das VSB-Bild schon bei 53 ms zeichnen und ein gespeichertes Bild später darüberlegen
brächte das Bild rund 50 ms früher, ein Nutzer mit eigenem Startbild sähe aber erst kurz das Standardbild.

## Das Aussehen gilt jetzt vor dem Sample-Laden

Vorher las das Menü seine Einstellungen hinter dem Sample-Lader (ein Haken bei `0xC0038D68`, im Emulator bei 1511 ms), das
Hintergrundlicht, die LEDs und die Anzeige blieben bis dahin auf den Werten der Firmware. Jetzt liest ein Haken am ersten
Befehl des Ladebefehls (`0xC0038D34`) die Einstellungen, 4 ms bevor der Lader startet (353 ms); der Haken dahinter findet das
Menü scharf und lässt es.

| | Lader startet | Hauptbildschirm |
|---|---:|---:|
| ohne den frühen Haken (Befehl zurückgesetzt) | 356,8 ms | 1566,8 ms |
| mit dem frühen Haken | 363,3 ms | 1572,4 ms |

Der Unterschied (rund 6 ms) ist das Lesen der Einstellungsdatei, das vorher hinter dem Lader und vor dem Hauptbildschirm lag; die
Prüfung `menu:early_look_main_screen_not_later` lässt höchstens 15 ms Abweichung zu (Rauschen des Emulators etwa 10 ms).

## Früher geht es nicht (gemessen)

Ein Versuch, das Menü schon hinter der Kartenfrage im Start-Task zu scharf zu schalten (`0xC002AE68`, 123 ms, nur bei
gemounteter Karte, `FatFs`-Objekt hat Typ 3), **hängt**: das Scharfschalten allein geht, aber das erste `f_open` der
Einstellungsdatei wartet im Kartentreiber (Ereigniswarten bei `0xC001C7E4`, Zeitlimit 1000) und kehrt in 3 s Emulatorzeit
nicht zurück, das Gerät bleibt im Startbild (Bildschirm 46). Der Startbild-Editor liest an derselben Stelle seine Dateien,
dort geht es; warum es bei uns hängt, ist **offen**. Der früheste Punkt, an dem das Lesen nachweislich geht, ist darum der
Ladebefehl vor dem Lader.
