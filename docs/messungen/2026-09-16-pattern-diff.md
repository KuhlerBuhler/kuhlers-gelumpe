# Pattern-Block, mit Differenzproben bestätigt

Gemessen 2026-09-16 an acht Backup-Dateien, die sich jeweils in einer Sache
unterscheiden, und an der entpackten Werksbank (250 Patterns, 4000 Parts,
25209 aktive Steps).

- Backup `.e2sallpat`: Kopf `0x10100` Byte, beginnt mit `KORG` und
  `e2sampler`; danach 250 Blöcke à `0x4000`. Gesamtgröße 4.161.792 Byte.
- Block: `PTST` bei 0, `PTED` bei 15356.
- Name ab 16, NUL-terminiert. Tempo bei 34, `uint16 LE`, BPM mal 10.
- Master FX ab 60 (nicht 52 wie in Korgs Tabelle): 61 Typ, 62 Pad X, 63 Pad Y,
  64 konstant 1, 65 Hold. An zwei Backups desselben Geräts bestätigt.
- Parts ab `0x800`, Abstand `0x330`, 16 Stück: Part 1 und Part 16 tragen in
  `firstpadallsteps` und `lastpadallsteps` dasselbe Offsetmuster.
- Steps ab Part `+0x30`, 12 Byte breit: `firstpadfirststep` trifft `+0x30`,
  `+0x33`, `+0x34`; `firstpadlaststep` trifft `+0x324`, `+0x327`, `+0x328`.
  (0x324 - 0x30) / 12 = 63, also Step 64.
- Step-Byte 0 An, 3 Trigger, 4 bis 7 Notenplätze mit Notennummer plus 1, 0 ist
  leer. Häufigster Wert in Platz 1 ist 61 (14837 von 25209), also C4.
- Step-Byte 3 ist ein eigenes Feld: bei 7731 der aktiven Steps steht es auf 0.
- Step-Bytes 8 bis 11 sind über alle aktiven Steps 0.
- Part-Bytes 15, 25 und 36 sind Zweierkomplement mit 0 als Mitte; Höchstwerte
  235, 254, 255 ergeben nur so Sinn.
- Part-Byte 38 ist belegt (2135 mal 255, 1704 mal 0, 25 weitere Werte),
  Bedeutung unbekannt.
- Gate Time: Werte bis 255, 255 in 6447 Steps, 127 nur 300 mal. Bedeutung von
  255 offen.
- Part-Byte 0 (Last Step) ist in allen 4000 Werks-Parts 0; Bedeutung offen.
- IFX-Typ in Part-Byte 33 geht mit Hacktribe über 37 hinaus (44, 45, 47
  beobachtet).
