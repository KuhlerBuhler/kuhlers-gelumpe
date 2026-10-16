# FX-Tabellen im RAM, live beschrieben

Gemessen 2026-09-14 und danach mehrfach wiederholt.

- Die Master-Tabelle liegt bei RAM `0xC00B4F30`, die Insert-Tabelle bei
  `0xC00A80F0`. Je 100 Plätze à `0x20C` Byte. In der Firmware-Datei liegen sie
  bei `RAM - 0xC0000000 + 0x100`.
- Ein Preset wurde per `0x53`/`0x54` in zwei Hälften geschrieben,
  zurückgelesen und war identisch. Das Menü zeigte es sofort, ohne Neustart.
- Die Länge des Master-Menüs steht in einem Byte bei RAM `0xC003EFE4`.
- Die Länge des Insert-Menüs steht an dreizehn Stellen der Datei: sieben
  tragen die Anzahl (`0x3F0DC`, `0x98250`, `0x98294`, `0x981EC`, `0x9819C`,
  `0x9821C`, `0x98238`), sechs den letzten Index (`0x49080`, `0x49FF0`,
  `0x4A2F8`, `0x9824C`, `0x98288`, `0x981E8`). Werden nicht alle geändert,
  wählt das Menü einen Eintrag aus und spielt einen anderen.
- Nach dem Ausschalten ist alles, was ins RAM geschrieben wurde, weg,
  einschließlich der Zählerbytes.
