# SOFTWARE UPDATE prüft die Dateigröße, im Emulator

[Patch](../glossary.md#patch) `update-guard` (`tools/patch/update_guard.py`), Fälle `tools/emu/update_guard_cases.py`.

## Anlass

Bricht ein Kopieren über USB ab, bleibt eine `KORG/blechtribe/System/SYSTEM.VSB` mit zu wenigen Bytes (zum Beispiel 10240) auf der
Karte. Korgs SOFTWARE UPDATE flasht sie; das Gerät startet dann nicht mehr und kommt nur über [JTAG](../glossary.md#jtag) zurück.

## Wie Korgs Update liest

In allen drei 2.02-Builds ([Hacktribe](../glossary.md#hacktribe), Korg rot, Korg blau) gleich gebaut, auf Hacktribe und rot an denselben Adressen:

| Weg | Funktion rot/HT | Funktion blau | f_read Kopf | f_read Bild |
|---|---|---|---|---|
| Versionsseite (Now/Next Version) | um 0xC0030900 | um 0xC002D700 | 0xC00309E0 / 0xC002D7C8 | - |
| DATA UTILITY nach "Are You Sure ?" | 0xC003AC74 | Pool 0xC00358DC | 0xC003AD4C / 0xC003579C | 0xC003AE24 / 0xC0035874 |
| Angebot beim Einschalten | 0xC003A8A0 | Pool 0xC00354B4 | 0xC003A968 / 0xC00353B4 | 0xC003A9FC / 0xC0035448 |

Jeder Weg öffnet `/SYSTEM.VSB`, liest 0x100 Bytes Kopf, prüft "KORG", "SYSTEM" und die Bildgröße (0x200000 an +0x34 gegen
die Blockgröße des Flash), liest dann das Bild mit f_read (rot/Hacktribe 0xC009DD74, blau 0xC008A8CC) und schreibt Block 2
(0xC0029CBC, blau 0xC0027000). Wie viele Bytes f_read wirklich gelesen hat, prüft keiner der Wege. Eine kurze Datei gibt
FR_OK mit weniger Bytes zurück, der Rest des Puffers wird mitgeflasht.

Eine Prüfsumme gibt es nicht: der Kopf hat keine, und nur Korgs eigene Bilder ergeben als 16-Bit-Wörter die Summe 0
(Hacktribe 0xCB83, jeder BLECH-Build anders). Eine Summenprüfung würde also jede gültige BLECH-Datei ablehnen.

## Was der Patch macht

Die fünf `bl f_read` werden zu `bl ug_read` (0xC014EE00, in allen drei Builds frei). ug_read ruft f_read wie vorher und prüft
danach, ob die Datei genau 0x200100 Bytes hat (FatFs-Dateiobjekt +0x0C) und ob f_read alle verlangten Bytes geliefert hat.
Wenn nicht:

- beim Kopf (0x100 Bytes) löscht es das erste Wort ("KORG"), Korgs eigene Kopfprüfung schlägt fehl und das Display zeigt
  Korgs "Error / Invalid File", vor "Are You Sure ?";
- beim Bild gibt es FR_DISK_ERR (1) zurück, das Update bricht mit Korgs Dateifehler vor dem Flash-Schreiben ab.

Der [Notschalter](../glossary.md#notschalter) (EXIT beim Einschalten) schaltet den Schutz nicht ab, er läuft nie beim Start.

## Fälle im Emulator

Je Build ([BLECH](../glossary.md#blech) auf Hacktribe, rot, blau) mit voller BLECH-Kette, DATA UTILITY > SOFTWARE UPDATE > MENU, die Datei in allen
Kartenordnern:

| Fall | Erwartung |
|---|---|
| 10240 Bytes | SYSTEM.VSB geöffnet, 0 Löschungen, 0 Schreibvorgänge, Firmware-Bereich gleich |
| leer | wie oben |
| 0x200200 Bytes | wie oben |
| 10240 Bytes, Versionsseite wie Korg | wie oben, abgelehnt beim Kopf nach "Are You Sure ?" |
| 10240 Bytes, beide Kopf-Lesungen wie Korg | wie oben, abgelehnt beim Bild |
| ganze Datei (ein Byte im freien Bereich geändert) | Update läuft, Firmware-Bereich ist die neue Datei |
| 10240 Bytes, alle fünf Lesungen wie Korg | Kontrolle: die Datei wird geflasht |

Ohne Patch (Hacktribe 2.02) zeigt der Emulator den Unfall: 512 Löschungen zu 4 KiB, 2 MiB geschrieben, "OK. Please
Reboot.". Eine leere Datei lehnt schon Korg ab.

Das Angebot beim Einschalten erreicht der Emulator nicht: dafür braucht es einen Flash ohne Firmware, und mit dem leeren
Flash lehnt der Emulator auch eine ganze Datei ab. Der Weg nutzt dieselbe ug_read wie DATA UTILITY.
