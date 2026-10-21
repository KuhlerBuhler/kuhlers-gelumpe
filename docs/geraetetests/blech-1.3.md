# BLECHTRIBE 1.3: Bedienung am Gerät prüfen

**Am Gerät noch offen.** Diese Liste bereitet den Test vor; ein bestandener Emulatortest
ist kein bestandener Gerätetest. Sie ist für eine Electribe mit bereits installierter,
zuvor im Patcher geprüfter BLECHTRIBE-Datei gedacht. Die Installation und der Rückweg
stehen unter [BLECH-Datei](blech-datei.md).

## Vorher und Rückweg

Original-Firmware, komplette SD-Karte und Global-Einstellungen sichern. Beim Test
Netzteil verwenden. Für den ersten Vergleich keine wichtigen Patterns bearbeiten oder
speichern. Das Malen eines Startbilds und WRITE ändern gespeicherte Einstellungen oder
Dateien; nur mit Sicherung ausführen.

Bei einer Abweichung nicht weiter speichern. EXIT beim Einschalten hält die BLECHTRIBE-
Erweiterungen für diesen Start aus; danach kann die gesicherte Firmware wieder eingespielt
werden. Vorher den [dokumentierten Rückweg](../messungen/2026-10-10-rueckweg-geuebt.md) lesen.

## Testfolge

| Schritt | Bedienung | Erwartet | Am Gerät |
|---|---|---|---|
| 1 | Normal einschalten | Blechy und Ladebild erscheinen, danach der Hauptbildschirm | offen |
| 2 | Beim Sampler mit vorhandenen Samples starten | Ladefortschritt bis zum vollständigen Abschluss, danach Bedienung möglich | offen |
| 3 | Blechy im Menü öffnen, streicheln, TAP und EXIT benutzen | Reaktionen und Rückweg ohne Hänger | offen |
| 4 | PATTERN CONFIRM einschalten, ein ungespeichertes Testpattern anhalten und das Rad drehen | Nummer blinkt; MENU lädt die Auswahl, EXIT behält das bisherige Pattern | offen |
| 5 | Am roten Sampler die zusätzlichen Synth-Filter durchschalten | Anzeige und hörbare Filterwirkung passen zusammen, auch nach erneutem Auswählen | offen |
| 6 | Am Sampler unter BLECH, CUSTOMIZATION, SPLASH DRAW ein Testbild malen und mit WRITE sichern | Working endet, Bild bleibt nach Neustart; danach Sicherung wiederherstellen | offen |
| 7 | Global, LCD CONTRAST öffnen | CALIBRATE DISPLAY und drei unterschiedlich schnelle Bälle | offen |
| 8 | Bei der Kalibrierung den bisherigen Wert notieren und das VALUE-Rad drehen | Kontrast 1 bis 25, Bewegung läuft weiter; keine andere Global-Einstellung ändert sich | offen |
| 9 | Einen gut lesbaren Wert wählen, WRITE, EXIT und erneut öffnen | Original-Speicherweg, gewählter Kontrast bleibt; Rückweg funktioniert | offen |
| 10 | Mit EXIT gehalten neu starten und dieselbe Kontrastseite öffnen | Originaldarstellung ohne Kalibrierungsanimation, Kontrast weiter einstellbar | offen |
| 11 | Nur am Sampler mit bereits vorhandenem Doom-Paket: SHIFT + TAP beim Einschalten halten | Doom startet nach dem Laden; bei einer Fehlermeldung Code und Ablauf festhalten | offen |

Die blaue Electribe lädt keine Samples und hat keinen Startbild-Editor am Gerät. Dort
entfallen Schritt 2, 6 und 11; ihre Original-Synth-Filter werden bei Schritt 5 als Gegenprobe
benutzt. Die Kalibrierung wird auch auf der blauen geprüft.

## Ergebnis festhalten

Hardwaretyp, Firmware-Prüfsumme, Netzteil oder Batterie und pro Schritt "ok", "anders"
oder "nicht geprüft" notieren. Bei einer Abweichung die Meldung und den genauen Ablauf
festhalten. Für die Kalibrierung den bisherigen und den gewählten Kontrastwert sowie die
Lesbarkeit jedes Balls angeben. Keine Firmware, Samples oder Flash-Dumps veröffentlichen.
