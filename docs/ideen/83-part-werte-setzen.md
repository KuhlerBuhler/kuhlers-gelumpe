# 83. Plugin: Werte eines Parts setzen

Wunsch (Community, 30.10.): ein Plugin setzt einen Wert eines Parts, etwa Pitch oder Resonanz, auf eine bestimmte Zahl.
Heute lassen sich die Werte nur lesen (`korg.parts[i].pitch`, seit API 8). Geplant für 1.3.9. Stand 2026-10-30:
**aufgeschrieben, nichts gebaut, am Gerät nichts.** Marker: **gemessen**, **hergeleitet**, **ungeprüft**.

## Was es schon gibt

- Lesen: `korg.parts[i].…` und `korg.read.patternValue(-1, i, wert)` lesen die Werte des Parts im laufenden Pattern,
  mit den ungespeicherten Änderungen. Liste und Orte in `data/script/contract.mjs` (`PART_FIELDS`), Offsets ab
  `0x800 + 0x330 * Part` aus `data/map/pattern.mjs`. (gemessen)
- Der nächste Anschlag eines Pads liest die Bytes des Parts aus dem Pattern im RAM: nach EXIT + Pad schickt die Firmware
  beim nächsten Druck den zurückgeschriebenen Pitch an den DSP, ebenso Level und Filter. (gemessen im Emulator, 30.10.,
  Untersuchung zu EXIT + Pad)
- Schreibende Aufrufe gibt es schon für Mute (`korg.mute`), Steps (API 11) und die Einstellungen im Objektbaum (API 10).

## Vorschlag

- `korg.parts[i].pitch = x` und die übrigen Werte aus `PART_FIELDS`, als Zuweisung wie bei `korg.parts[i].muted`. Der
  Compiler macht daraus einen neuen Aufruf, etwa `korg.write.partValue(part, wert, x)`.
- Bereich je Wert aus `PART_FIELDS` (vorzeichenbehaftete Werte -63 bis 63, sonst meist 0 bis 127). Außerhalb wird auf
  die Grenze geklemmt und in `korg.system.repairs` gezählt, wie im Objektbaum.
- Geschrieben wird nur ins Pattern im RAM. Das Pattern weicht danach von der Bank ab, die WRITE-Taste atmet, wie nach
  einem Dreh am Regler.

## Offen

- Bekommt eine Stimme, die gerade klingt, den neuen Wert, oder erst der nächste Anschlag? Am Regler ändert sich der Klang
  sofort, die Firmware ruft dafür Setzfunktionen der Engine auf ([Modulation](../messungen/2026-10-15-modulation-stufe2.md)).
  Ob der Aufruf diese Funktionen braucht, ist **ungeprüft**.
- `sample` (u16) und `filterType`: braucht ein Wechsel mehr als das Byte, etwa Laden oder Umschalten des Filters?
  (**ungeprüft**)
- Die Anzeige: zeigt die Edit-Zeile den neuen Wert, oder erst nach einem Wechsel des Parts? (**ungeprüft**)
- Motion: spielt eine Motion-Spur den Wert, überschreibt sie das Setzen beim nächsten Schritt. (hergeleitet)
