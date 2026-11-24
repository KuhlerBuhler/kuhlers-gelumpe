# Modulationstabelle in der Firmware

Gelesen 2026-09-14 aus der Firmware-Datei ([VSB](../glossary.md#vsb)), gegengeprüft mit Korgs Liste.

- 72 Einträge ab Dateioffset `0xD82EC`, je `0x58` Byte.
- Name als Text ab `+4`.
- Zielbyte bei `+25`: über alle 72 Einträge das Muster `03 01 02 04 00 05`,
  passend zu 12 Quellen mal 6 Zielen.
- `+27` Vorgabetiefe, `+28` Kurvenform.
- Felder ab `+0x29` sind nicht zugeordnet.
- Direkt hinter Eintrag 71 beginnt die Namenstabelle der Oszillatoren; die
  Tabelle lässt sich nicht verlängern.

Das ist die Kopie, die Korgs Firmware liest. Die Firmware von [Hacktribe](../glossary.md#hacktribe) liest eine
zweite Kopie ab `0x1A00FC` (`data/map/firmware.mjs`, `table.modType`).

Ob ein RAM-Schreiben in diese Tabelle live wirkt, ist nicht geprüft.
