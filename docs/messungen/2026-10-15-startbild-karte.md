# Startbild auf der Karte statt im Flash (Idee 35): gebaut und im Emulator geprüft

Stand 2026-10-15. Alles im Emulator (`tools/emu`, Unicorn 2.1.4) mit der eigenen `SYSTEM.VSB`
(Hacktribe 2.02) und dem eigenen Flash-Dump vom 9.10., virtuelle Karte (`tools/emu/fat32.py`).
**Am Gerät nichts geprüft.** Der Editor selbst ist in [Startbild-Editor](2026-10-10-startbild-editor.md) beschrieben,
dort steht noch der alte Speicherort (Flash `0x7F0000`); dies hier ersetzt ihn. Idee:
[Idee 35](../ideen/35-startbild-am-geraet.md). Markierungen: **gemessen**, **hergeleitet**, **offen**.

## Was sich geändert hat

WRITE im Editor schreibt jetzt auf die Karte, nicht mehr in den Flash. Der Patch
`data/patches/splash-editor.json` (`tools/patch/splash_editor.py`) schreibt keinen Flash-Sektor mehr selbst, die eigene
WRITE-Behandlung der Firmware im Menü Global (Globals bei `0x230000`) läuft wie vorher.

**Dateien:** `KORG/blechtribe/splash.a.bin` und `splash.b.bin`, zusammen mit der Schreibregel aus
[Patcher](../patcher.md) (zwei Dateien im Wechsel, nie eine ersetzt, Prüfsumme, Generation). Eine Datei ist ein Satz von
1040 Byte: Kennung `GLSP`, Version `2` (16 Bit), Länge `1024` (16 Bit), Generation (32 Bit), das Bild (1024 Byte, wie in der VSB:
8 Seiten zu 128 Spalten, Bit 7 oben) und die CRC-32 über alles davor. Beim Start gilt die gültige Datei mit der
höchsten Generation. WRITE liest zuerst beide Dateien (eine inzwischen gewechselte Karte kann eine spätere Generation
tragen), schreibt Generation plus eins in die Datei, in der die höchste **nicht** steht (ungerade nach `b`, gerade nach `a`),
und stellt das Bild danach als aktuelles Startbild ein. Der Ordner `KORG/blechtribe` muss auf der Karte sein, der Patch legt keinen an.
Geht das Schreiben schief (keine Karte, kein Ordner, geschützt), bleibt alles wie vorher und das Bild kommt nach dem
Fenster "Working" nicht zurück, so sieht der Nutzer, dass es nicht ankam.

## Wann das Startbild kommt

Die Karte läuft beim Zeichnen des Startbildes noch nicht (die Firmware mountet sie bei etwa 75 ms, das erste Bild
kam bei etwa 59 ms). Das Bild wird darum jetzt direkt hinter der Frage der Firmware nach der `e2sSample.all`
gezeichnet (`0xC002AE64`, die Frage bei `0xC002AE60` mountet die Karte), also nach den Rettungswegen und mit gemounteter
Karte; der Haken am Anfang (`0xC002ADAC`) zeichnet nur noch das VSB-Bild, wenn EXIT beim Einschalten gehalten wird oder
das Panel aktualisiert wird, sonst setzt er den Editor nur auf. Ohne gemountete Karte (`FatFs[0]->fs_type` ist 0,
`0xC06A010C`) fragt der Patch nicht erst die Karte, das würde nur einen neuen Startversuch der Karte auslösen.

Gemessen (Emulatorzeit, eigener Flash, 1-ms-Schritte; Zahlen auf etwa 10 ms genau):

| Fassung | erstes Bild | Hauptbildschirm |
|---|---:|---:|
| unverändert (frühes Bild der Firmware) | 65,4 ms | 311,0 ms |
| alter Editor, Flash, keine Karte | 72,7 ms | 312,4 ms |
| neuer Editor, keine Karte | 73,2 ms | 299,5 ms |
| neuer Editor, Karte ohne Dateien | 94,9 ms | 314,5 ms |
| neuer Editor, Karte, eine gültige Datei | 92,7 ms | 315,8 ms |
| neuer Editor, Karte, beide Dateien gültig | 100,0 ms | 320,5 ms |
| neuer Editor, EXIT gehalten, Karte | 71,7 ms | 320,9 ms |

Das Bild kommt mit Karte also rund 20 bis 30 ms später als ohne, der Hauptbildschirm nicht später als mit
gehaltenem EXIT (der den Patch auslässt). Die Zahlen schwanken um etwa 10 ms, schon ohne Patch.

## Gemessen (Prüfungen `splash:*` in `check.py`, `tools/emu/splash_cases.py`)

Jede Prüfung bootet ein Gerät und sieht sich jedes Bild vom ersten gezeichneten Pixel bis zum Ende des Startbildes an
(alle 10 ms, mindestens 5 Bilder, alle müssen das erwartete Bild sein):

| Fall | Datei auf der Karte | Bild |
|---|---|---|
| `empty` | keine | VSB |
| `valid`, `valid_in_b` | gültig in a, gültig in b | gespeichertes |
| `bit_flipped` | ein Bit gekippt | VSB |
| `half_written` | auf 512 Byte abgeschnitten | VSB |
| `longer_file` | vier Byte zu lang | VSB |
| `wrong_id`, `wrong_version`, `wrong_length` | CRC stimmt, Kopf nicht (Version 1, Länge 512) | VSB |
| `newest_wins`, `newest_wins_in_a` | a Generation 5, b Generation 6, und umgekehrt 8 und 7 | das der höheren Generation |
| `newer_damaged_falls_back` | b neuer, aber ein Bit gekippt | das der älteren gültigen Datei |
| `newer_half_written_falls_back` | b neuer, nur 700 Byte | das der älteren gültigen Datei |
| `exit_held` | gültig, EXIT beim Einschalten | VSB, Editor nicht scharf |
| `no_card` | keine Karte | VSB, Gerät startet normal |
| `card_without_folder` | Karte, aber ohne `KORG/blechtribe` | VSB |
| `old_flash_record_ignored` | ein gültiger Satz der alten Fassung bei Flash `0x7F0000` | VSB (der Flash wird nicht gelesen) |
| `exit_held_menu` | | Global hat mit EXIT 20 Originalseiten, keine Seite 20, keinen Editor |

In allen Fällen wird das DSP-Programm genau einmal geladen und der alte Sektor `0x7F0000` bleibt unverändert (die Firmware selbst schreibt beim Start auf einem leeren Flash etwas, daher wird nicht der ganze Abzug verglichen; im Bedienlauf unten schon).

Der Bedienlauf `splash_cases.py run` (40 Schritte) geht durch Global, Seite 20, den Editor, WRITE und zurück: WRITE schreibt
`splash.b.bin` mit Generation 1 (1040 Byte, gültig, das editierte Bild), im Flash ändert sich nichts außer der eigenen
WRITE-Behandlung der Firmware, ein zweites WRITE geht nach `splash.a.bin` mit Generation 2 und lässt `b` unverändert, ein
drittes nach `b` mit Generation 3, nach einem Neustart zeigt das Display das neueste Bild, und WRITE ohne Karte oder auf einer Karte
ohne den Ordner speichert nichts, das Bild kommt nicht zurück und nichts bricht.

## Grenzen und offen

- **Am Gerät nichts geprüft:** nicht das Lesen und Schreiben über FatFs (wie überall, siehe
  [Schreibregel](../patcher.md)), nicht der Zeitpunkt der Karte beim Start.
- Die gemessenen Zeiten sind Emulatorzeit; wie lange das Öffnen zweier Dateien an einer echten Karte dauert (Verzeichnisse
  durchlaufen), ist offen. Mit der Karte ohne den Ordner wird nichts gelesen, mit dem Ordner zwei Dateien.
- Ein früherer Stand mit dem Satz im Flash wurde nie am Gerät geschrieben (ob der Sektor `0x7F0000` dort beschreibbar ist, war offen);
  dieser Ort ist damit nicht mehr nötig und wird nicht gelesen.
- Wer die Karte wechselt, bekommt das Bild der neuen Karte (oder das der VSB); es ist nicht an das Gerät gebunden.
- **RAM-Lage (nach dem Merge mit dem Power-Off-Bild):** Zustand und Puffer des Editors (`STATE`, `RECBUF`, `ACTIVE`, `EDIT`, `FIL`, zusammen 4 KiB) liegen bei `0xC0182000` bis `0xC0183000`. Bei `0xC01A4000` bis `0xC01A5000` überdeckten sie den Code und das Bild des Power-Off-Patches (`0xC01A4A00` bis `0xC01A5000`); der Patcher prüfte nur Änderungen an der Datei, nicht die RAM-Puffer, die Überdeckung fiel beim Vergleich der Adressen auf. Seither nennt jeder Patch seinen RAM und `test/patch-ram.test.mjs` prüft ihn ([RAM der Patches](../patcher.md)).
