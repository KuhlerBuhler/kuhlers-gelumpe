# MFX HOLD je Effekt: MFX 1 und MFX 2 halten getrennt

Stand 25. November 2026. **Gemessen** im Emulator mit Hacktribe 2.02 (eigene Datei) und dem BLECH-Satz von `develop`.
**Am Gerät:** Sampler mit Hacktribe 2.02, 25. November 2026, Rückmeldung des Besitzers: das Halten je Effekt
funktioniert. Blau: der Patch ist für die blaue Electribe nicht neu gebaut, siehe "Offen".
Marker: **gemessen**, **offline gelesen**, **hergeleitet**, **offen**.

## Frage

Die Firmware hat einen Master-Effekt und darum ein Halten: Pattern-Byte 65, dazu X und Y des Touchpads in den
Bytes 62 und 63. Der Patch [MFX 2](2026-10-10-mfx-umschalter.md) wechselt nur den Typ. Ein in MFX 1 gehaltener
Effekt lief deshalb nach TOUCH SCALE als MFX 2 weiter, und umgekehrt. Gewünscht: jeder der beiden behält sein
eigenes Halten und seine eigene Stelle auf dem Pad.

Zwei Effekte gleichzeitig halten geht damit nicht. Es bleibt ein Effekt im DSP.

## Was die Firmware tut

| Befund | Marker |
| --- | --- |
| Die Taste MFX HOLD (Taste 7) läuft durch den Tastenverteiler `0xC00700D8` wie jede andere. Ein Druck kippt Byte 65 und die LED `0x1D`, auch ohne Finger auf dem Pad; gehalten wird dann an der letzten Stelle (Bytes 62, 63) | gemessen |
| Das Objekt des Verteilers ist bei jedem Tastendruck dasselbe (`r0` am Einsprung) | gemessen |
| Der Setter von Byte 65 allein schaltet weder LED noch Touchpad, nur der Handler der Taste | [offline gelesen](2026-11-08-plugin-api24-part-cc.md) |
| X und Y setzen `0xC0048924` und `0xC0048984` mit dem Objekt des Typ-Setters; die Bytes 62 und 63 folgen, mit und ohne Halten | gemessen |
| MFX HOLD kippt Byte 65 auch im Modus Touch Scale | gemessen |

## Was der Patch jetzt tut

Der Patch merkt sich für MFX 1 und MFX 2 je ein Wort im eigenen Zustand (`S_HA`, `S_HB`): Halten, X, Y und ein
Merker "gesetzt".

| Wechsel | Ablauf |
| --- | --- |
| TOUCH SCALE (MFX 1 nach MFX 2) | Halten, X und Y von MFX 1 merken; ein gehaltener Effekt wird mit einem Druck auf MFX HOLD gelöst; Typ wechseln; X, Y und Halten von MFX 2 zurückholen |
| MASTER FX, SHIFT + TOUCH SCALE, GATE ARP (MFX 2 verlassen) | dasselbe umgekehrt, solange das Pad noch im Master-FX-Modus ist |
| Pattern geladen | das gemerkte Halten von MFX 2 verfällt. Ist MFX 2 an, gilt das geladene Halten als das von MFX 1, und MFX 2 beginnt gelöst |
| WRITE bei MFX 2 | das Pattern bekommt Halten, X und Y von MFX 1 (Bytes 65, 62, 63), wie schon den Typ von MFX 1 |
| Modus auf anderem Weg verlassen | der Patch merkt sich das Halten von MFX 2 und drückt nichts |

Ein MFX 2, das noch nie verlassen wurde, beginnt gelöst. Der Druck auf MFX HOLD geht durch den Verteiler der
Firmware, mit dessen Objekt aus dem letzten Tastendruck (`S_DISP`); LED, Effekt und Touchpad stehen danach wie
nach der Taste. Das Halten von MFX 2 steht nur im RAM, nicht im Flash.

Der neue Code liegt in einem zweiten freien Bereich, `0xC01A5E20` bis `0xC01A6000`, weil hinter dem ersten bei
`0xC01A5800` der Code des Ausschaltbilds beginnt.

## Messung

`tools/emu/mfx_cases.py`, Fall `mfx:hold_each` (läuft in `check.py`) und die Abschnitte `hold` und `write` des
langen Laufs.

| Fall | Ergebnis | Marker |
| --- | --- | --- |
| In MFX 1 gehalten, TOUCH SCALE: Byte 65 und LED aus; MASTER FX: wieder an, X und Y von MFX 1 | wie erwartet | gemessen |
| In MFX 2 gehalten, in MFX 1 gelöst: jeder Wechsel bringt das eigene Halten, X und Y zurück | wie erwartet | gemessen |
| GATE ARP aus MFX 2: es gilt das Halten von MFX 1; danach TOUCH SCALE: das von MFX 2 ist wieder da | wie erwartet | gemessen |
| Die echte Taste MFX HOLD kippt danach weiter wie vorher | wie erwartet | gemessen |
| Patternwechsel bei gehaltenem MFX 2: gelöst; MASTER FX zeigt das Halten des neuen Patterns | wie erwartet | gemessen |
| WRITE bei MFX 2 mit gehaltenem MFX 1: das gespeicherte Pattern ist Byte für Byte das der Firmware | wie erwartet | gemessen |

## Offen

- **Am Gerät:** die Rückmeldung nennt keine Einzelheiten. Offen bleibt, ob beim Lösen und erneuten Halten
  etwas zu hören ist (Knacken, kurzer Effekt), und ob das Zurückholen von X und Y ohne Halten hörbar ist.
  Der Emulator rechnet keinen DSP.
- **Blau:** `data/patches/mfx-switch-synth.json` ist mit dieser Quelle nicht neu gebaut. Die beiden Setter
  haben dort Einträge in `data/synth-map/`, gemessen ist auf blau nichts davon.
- Das Halten von MFX 2 überlebt keinen Patternwechsel und kein Ausschalten.
