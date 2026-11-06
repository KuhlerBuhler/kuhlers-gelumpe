# 83. Plugin: Werte eines Parts setzen, Steps lesen

Wunsch (Community, 30.10.): ein Plugin setzt einen Wert eines Parts, etwa Pitch oder Resonanz, auf eine bestimmte Zahl,
und liest die Steps eines Parts (Note, Gate, Velocity). Stand 2026-11-05: Part-Werte setzen ist ab API 14 gebaut und im
Emulator geprüft. Attack von Part-Index 1 wurde am Gerät gesetzt, während Part-Index 0 gewählt war. Marker: **gemessen**,
**hergeleitet**, **ungeprüft**.

## Was es schon gibt

- Lesen: `korg.parts[i].…` und `korg.read.patternValue(-1, i, wert)` lesen die Werte des Parts im laufenden Pattern,
  mit den ungespeicherten Änderungen. Liste und Orte in `data/script/contract.mjs` (`PART_FIELDS`), Offsets ab
  `0x800 + 0x330 * Part` aus `data/map/pattern.mjs`. (gemessen)
- Schreiben: `korg.parts[i].pitch = x` und die zehn weiteren freigegebenen Felder schreiben in den angegebenen Part
  des aktuellen Patterns im RAM, nicht in die Pattern-Bank. Für diese Felder wird auch das zweite Firmware-Byte
  synchronisiert. Bereiche werden geprüft, dynamische Ausreißer geklemmt und gezählt. API 14. (gebaut, Emulator)
- Der nächste Anschlag eines Pads liest die Bytes des Parts aus dem Pattern im RAM: nach EXIT + Pad schickt die Firmware
  beim nächsten Druck den zurückgeschriebenen Pitch an den DSP, ebenso Level und Filter. (gemessen im Emulator, 30.10.,
  Untersuchung zu EXIT + Pad)
- Schreibende Aufrufe gibt es schon für Mute (`korg.mute`), Steps (API 11) und die Einstellungen im Objektbaum (API 10).

## Offen

- Bekommt eine Stimme, die gerade klingt, den neuen Wert, oder erst der nächste Anschlag? Am Regler ändert sich der Klang
  sofort, die Firmware ruft dafür Setzfunktionen der Engine auf ([Modulation](../messungen/2026-10-15-modulation-stufe2.md)).
  Ob der Aufruf diese Funktionen braucht, ist **ungeprüft**.
- `sample` (u16), `filterType` und `ifxType`: die API schreibt die Felder, aber ob die Engine einen Wechsel sofort
  übernimmt, neu lädt oder mehr als das Feld braucht, ist **ungeprüft**.
- Die Anzeige: zeigt die Edit-Zeile den neuen Wert, oder erst nach einem Wechsel des Parts? (**ungeprüft**)
- Motion: spielt eine Motion-Spur den Wert, überschreibt sie das Setzen beim nächsten Schritt. (hergeleitet)

## Steps lesen

Heute gibt es nur `korg.read.step(part)`, den Schrittzähler (0 bis 63). Note, Gate und Velocity eines Steps lassen sich
schreiben (`korg.seq.setStep`, `korg.seq.setGate`, ab API 9), aber nicht lesen. (gemessen, `data/script/contract.mjs`)

- Die Bytes liegen im Pattern im RAM: Steps ab `0x800 + 0x330 * Part + 0x30`, je Step 12 Byte; +0 an, +1 Gate, +2
  Velocity, +3 Trigger, +4 bis +7 die vier Notenplätze (`data/map/pattern.mjs`). (gemessen)
- Note, Gate und Velocity lassen sich ab API 13 lesen (`korg.seq.getNote`, `korg.seq.getGate`, `korg.seq.getVelocity`);
  `korg.seq.getOn` liest den An-Schalter. (gebaut, Emulator)
- Vorschlag: `korg.seq.getNote(part, step, platz)` (Platz 0 bis 3, -1 wenn leer), `korg.seq.getVelocity(part, step)`,
  `korg.seq.getGate(part, step)` und `korg.seq.isOn(part, step)`, gelesen aus dem laufenden Pattern mit den ungespeicherten
  Änderungen, wie `korg.read.patternValue`. Dazu als Eigenschaft `korg.parts[i].steps[s].note` und so weiter, nur lesbar.
- Offen: was Gate 255 bedeutet (kommt oft vor, `data/map/pattern.mjs`), und ob das Plugin den Wert vor oder nach einer
  Motion-Spur sehen soll. (**ungeprüft**)
