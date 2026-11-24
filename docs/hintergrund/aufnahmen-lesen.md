# Aufnahmen über USB lesen

Die native Aufnahme (1.6) schreibt jeden Take als `SD:Recordings/REC0001.WAV` bis `REC9999.WAV` an die Wurzel der Karte, auf der roten
und der blauen Electribe gleich (`tools/patch/recording_writer.s`, `rec_directory`). FILE READ (`0x65`) von BLECHTRIBE liest diese
Dateien und listet sie, ohne Karte umzustecken. Nur lesen: kein anderer FILE-Befehl nimmt den Selektor.

**gemessen im Emulator** (Fälle unten), am Gerät **nicht** gemessen.

## Der Selektor

| Wort der Anfrage | Bedeutung |
|---|---|
| Offset, Bits 31, 30 und 29 gesetzt (`0xE0000000`) | eine Aufnahme statt der Update-Datei. Bis 1.5 nannte diese Kombination keine Datei und wurde abgelehnt |
| Offset, Bits 0 bis 28 | der Offset in Schritten zu 8 Byte, also bis 4 GiB (so groß kann ein Take werden). Die Antwort trägt den Offset in Byte |
| Länge, Bits 16 bis 29 | die Nummer der Aufnahme, 1 bis 9999; 0 heißt die Liste |
| Länge, Bits 0 bis 15 | die Länge, bis 32768; 0 fragt nur die Größe |

Die Antwort ist die von FILE READ: Status, Offset, Länge, CRC-32, Größe der Datei, dann die Bytes. Neu ist Status 7 (busy): die Aufnahme
wird gerade geschrieben. Das gilt für die Nummer, die die laufende Aufnahme veröffentlicht (`NR_NUMBER` bei `0xC018E9D0` + 28), und alle
darüber, solange ihr Kontext steht (`NR_CONTEXT` ungleich 0, `tools/patch/recording_runtime.s`). Direkt nach dem Start zählt so auch der
vorige Take kurz als busy, bis der Schreiber die neue Datei offen hat; zu vorsichtig, nie zu lax. Eine fehlende Datei gibt Status 6 mit
dem FatFs-Ergebnis im CRC-Wort, eine Nummer über 9999 Status 3.

## Die Liste

Nummer 0 liest `SD:Recordings` mit `f_opendir` und `f_readdir` der Firmware (`0xC009E660`, `0xC009E740`, auf der blauen über
`tools/patch/fwmap.py` gefunden) und gibt je Take 8 Byte: die Nummer (Bit 31 gesetzt, wenn er gerade geschrieben wird) und seine
Größe. Gezählt wird jeder Eintrag, dessen kurzer Name `REC` plus vier Ziffern plus `.WAV` ist, außer `REC0000`; andere Dateien bleiben
draußen. Die Reihenfolge ist die des Ordners. Offset und Länge müssen ganze Einträge sein (Vielfache von 8), die Größe in der Antwort
ist die der ganzen Liste. Fehlt der Ordner, kommt Status 6.

FILE READ und der Schreiber der Aufnahme laufen beide im CommandTask, ihre FatFs-Aufrufe kommen sich also nicht in die Quere.

## Code und Speicher

Die zwei Abschnitte von BLECH SysEx sind voll (`0xC0172100` hat noch 0x24 Byte, `0xC017B950` noch 0x90). Der Code für die Aufnahmen
liegt deshalb als dritter Abschnitt in der Arbeitsfläche der FILE-Befehle, bei `0xC019F700` bis `0xC01A0000` (740 Byte), hinter dem
zweiten Dateiobjekt; erklärt bleibt als RAM nur `0xC019F000` bis `0xC019F700`. Im ersten Abschnitt stehen zwei Befehle, die zu ihm
springen, in `file_path` einer für den Pfad. INFO meldet Bit 12 der Flags (`FLAG_REC`).

`sel_decode` (FILE COPY, DELETE, CRC) lehnt jetzt jeden Selektor mit Bit 29 ab. Vorher hat es Bit 29 übersehen, so dass COPY auf
`0x60000000` (die Effekt-Sammeldatei) bei `e2sSample.all` gelandet wäre.

## Auf dem Rechner

```bash
python3 tools/device/usbfile.py list-rec
python3 tools/device/usbfile.py get-rec 5 REC0005.WAV
```

`list-rec` zeigt Nummer, Größe und `busy`, `get-rec` liest einen Take in Blöcken mit CRC. Beides braucht eine Firmware mit Bit 12 in INFO.

## Prüfungen

| Fall | Was er zeigt |
|---|---|
| `tools/patch/test_blech_sysex_buffer.py`, `test_recordings_read_list_busy_and_refusals` | Pfad, Offset in 8 Byte, Liste mit fremden Namen, busy für die laufende und höhere Nummern, kein Ordner, COPY, DELETE, CRC und BEGIN abgelehnt, keine Wache verletzt |
| `sysex:rec_list`, `rec_read`, `rec_tail`, `rec_missing_take`, `rec_read_only`, `rec_no_folder` (`tools/emu/sysex_cases.py`, `rec_read_cases`) | dasselbe mit dem FatFs der Firmware auf einer FAT32-Karte im Emulator, rot, und als `synth_rec_*` auf der blauen |

Busy ist im Emulator nicht mit dem echten Firmware-Ablauf geprüft: ein vorgetäuschter Kontext lässt den Rekorder abstürzen, ein echter
Take dafür ist zu teuer. Die Regel selbst prüft der Fall in `test_blech_sysex_buffer.py`.
