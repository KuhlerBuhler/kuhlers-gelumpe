# Modulation: Typ, Speed, Depth (Part-Bytes 16, 17, 18)

Gemessen 2026-09-17 mit laufendem Sequencer bei 120 BPM, Typ 32 (LFOTriB
Pitch).

Typ: Part-Byte 16 ist Korgs Typnummer minus eins, 72 Typen. Die Liste deckt
sich mit der Tabelle in der Firmware (siehe 2026-09-14-modulation-table).

Speed: Stufen zu je 8 Byte.

| Bytes | Notenwert |
|---|---|
| 0 bis 31 | nicht aufgelöst |
| 32 bis 39 | 1/2 |
| 40 bis 47 | 3/8 |
| 48 bis 55 | 1/3 |
| 56 bis 63 | 1/4 |
| 64 bis 71 | 3/16 |
| 72 bis 79 | 1/6 |
| 80 bis 87 | 1/8 |
| 88 bis 95 | 1/12 |
| 96 bis 103 | 1/16 |
| 104 bis 111 | 1/24 |
| 112 bis 119 | 1/32 |
| 120 bis 127 | 1/64 |

Zwölf Stufen auf unter 2 % genau. Die unteren vier sind nicht gemessen.

Depth: linear und einpolig, Hub 2,7 % bei 16 bis 17,0 % bei 127.
