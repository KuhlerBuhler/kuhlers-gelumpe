# CUTOFF- und Glide-Mirror auf allen Parts

Stand 2026-11-06. Im Emulator mit eigener Hacktribe-`SYSTEM.VSB` und Firmware 2.02 gemessen, ohne Flash-Abbild und ohne Geraetezugriff. Der Emulator startet auf dem Hauptbild mit dem Startpattern. Die Offset-Angaben sind relativ zum Zeiger auf das aktive Pattern-Objekt.

## CUTOFF

Auf jedem der 16 Parts wurde der Encoder CUTOFF (Encoder-Index `2`) um einen Schritt nach unten bewegt. Auf allen Parts wechselten genau zwei Pattern-Bytes von 127 auf 126. Hauptbyte und Mirror hatten danach denselben Wert.

## Glide

Auf jedem der 16 Parts blieb SHIFT (`0x0A`) gedrueckt, waehrend der Regler OSC PITCH (Regler-Index `2`) bewegt wurde. Der Eingabewert war `200 + 2 * Part`. Die Firmware setzte Glide auf `100 + Part`. Auf allen Parts wechselten genau das Hauptbyte und sein Mirror, beide auf denselben Wert.

| Part (Index ab 0) | CUTOFF Hauptbyte | CUTOFF Mirror | Glide Hauptbyte | Glide Mirror |
|---:|---:|---:|---:|---:|
| 0 | `0x811` | `0x403F` | `0x829` | `0x4053` |
| 1 | `0xB41` | `0x4063` | `0xB59` | `0x4077` |
| 2 | `0xE71` | `0x4087` | `0xE89` | `0x409B` |
| 3 | `0x11A1` | `0x40AB` | `0x11B9` | `0x40BF` |
| 4 | `0x14D1` | `0x40CF` | `0x14E9` | `0x40E3` |
| 5 | `0x1801` | `0x40F3` | `0x1819` | `0x4107` |
| 6 | `0x1B31` | `0x4117` | `0x1B49` | `0x412B` |
| 7 | `0x1E61` | `0x413B` | `0x1E79` | `0x414F` |
| 8 | `0x2191` | `0x415F` | `0x21A9` | `0x4173` |
| 9 | `0x24C1` | `0x4183` | `0x24D9` | `0x4197` |
| 10 | `0x27F1` | `0x41A7` | `0x2809` | `0x41BB` |
| 11 | `0x2B21` | `0x41CB` | `0x2B39` | `0x41DF` |
| 12 | `0x2E51` | `0x41EF` | `0x2E69` | `0x4203` |
| 13 | `0x3181` | `0x4213` | `0x3199` | `0x4227` |
| 14 | `0x34B1` | `0x4237` | `0x34C9` | `0x424B` |
| 15 | `0x37E1` | `0x425B` | `0x37F9` | `0x426F` |

Alle Offset-Paare wurden durch den Vergleich der Pattern-RAM vor und nach der Eingabe bestimmt. Es gab keine weiteren geaenderten Pattern-Bytes und keine Emulator-Assertions. Die Ergebnisse bestaetigen die RAM-Kopien im Emulator, nicht die Klangwirkung auf dem Geraet, da der DSP im Emulator nicht nachgebildet ist. Eine Zusammenfassung steht in [Byte-Ziele der Plugin-Steuerungen](../../PARAMSET-BYTE-FINDINGS.md) und [English](../../PARAMSET-BYTE-FINDINGS.en.md).
