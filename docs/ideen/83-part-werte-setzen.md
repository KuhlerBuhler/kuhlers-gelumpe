# 83. Plugin: Werte eines Parts setzen, Steps lesen

Wunsch (Community, 30.10.): ein Plugin setzt einen Wert eines Parts, etwa Pitch oder Resonanz, auf eine bestimmte Zahl,
und liest die Steps eines Parts (Note, Gate, Velocity).
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

## Steps lesen

Heute gibt es nur `korg.read.step(part)`, den Schrittzähler (0 bis 63). Note, Gate und Velocity eines Steps lassen sich
schreiben (`korg.seq.setStep`, `korg.seq.setGate`, ab API 9), aber nicht lesen. (gemessen, `data/script/contract.mjs`)

- Die Bytes liegen im Pattern im RAM: Steps ab `0x800 + 0x330 * Part + 0x30`, je Step 12 Byte; +0 an, +1 Gate, +2
  Velocity, +3 Trigger, +4 bis +7 die vier Notenplätze (`data/map/pattern.mjs`). (gemessen)
- Vorschlag: `korg.seq.getNote(part, step, platz)` (Platz 0 bis 3, -1 wenn leer), `korg.seq.getVelocity(part, step)`,
  `korg.seq.getGate(part, step)` und `korg.seq.isOn(part, step)`, gelesen aus dem laufenden Pattern mit den ungespeicherten
  Änderungen, wie `korg.read.patternValue`. Dazu als Eigenschaft `korg.parts[i].steps[s].note` und so weiter, nur lesbar.
- Nur Lesen, kein Eingriff in die Engine: das ist der kleinere Teil der Idee und kann zuerst kommen.
- Offen: was Gate 255 bedeutet (kommt oft vor, `data/map/pattern.mjs`), und ob das Plugin den Wert vor oder nach einer
  Motion-Spur sehen soll. (**ungeprüft**)
