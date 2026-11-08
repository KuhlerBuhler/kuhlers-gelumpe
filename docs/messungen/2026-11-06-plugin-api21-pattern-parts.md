# Plugin API 21: Pattern und Parts schreibbar

Stand 6. November 2026. **Gemessen** im Emulator mit Hacktribe 2.02 (eigene Datei), Korgs Original 2.02 rot und blau, jeweils
mit dem BLECH-Satz. Fälle: `tools/emu/pattern_parts_cases.py` (läuft als Gruppe von `remote_cases`). **Am Gerät nicht geprüft.**

## Frage

Plan Phase 7: welche Werte des laufenden Patterns und seiner Parts kann ein Plugin so setzen, dass sie ohne Neustart wirken und das
Menü sie zeigt wie nach dem eigenen Drehen? Wo gibt es einen Setter der Firmware, wo bleibt ein Wert nur lesbar und warum?

## Weg

Das Pattern-Objekt steht hinter dem Zeiger bei `0xC033E6A4` (im Emulator `0xC06B2798`), sein Block ab +4, die Kopie der
Klangerzeugung ab Block + 0x4000. Je Wert eine Zwillingsprobe: die Seite im Menü um eins gedreht (nach unten, wenn der Wert oben
anschlägt), Block und Kopie (0x4274 Byte) und das Bild der Seite nach Verlassen und Wiederöffnen gemerkt, zurückgedreht, dann
derselbe Wert durch den Aufruf des Plugins gesetzt. Beide Wege müssen denselben Block, dieselbe Kopie und dasselbe Bild geben,
ohne Assertion. Bei Tasten (MFX SEND) statt Seite dieselbe Probe mit der Taste.

## Seiten des Pattern-Menüs

Der Seitenzähler des Pattern-Menüs (Bildschirm 3), gleich auf Hacktribe, rot und blau:

| Seite | Feld | Offset im Block |
|---|---|---|
| 0 | tempo | 0x22 |
| 1 | swing | 0x24 |
| 2 | beat | 0x26 |
| 3 | length | 0x25 |
| 5 | mfxType | 0x3D |
| 7 | key | 0x27 |
| 8 | scale | 0x28 |
| 9 | chordSet | 0x29 |
| 10 | gateArp | 0x31 |
| 13 | chainTo | 0x3B00 |
| 14 | chainRepeat | 0x3B02 |
| 15 | syncGroup | 0x3B80 (u16) |

Seite 16 und 17 sind schon Part-Seiten. Das Part-Menü (Bildschirm 7) zählt von 16 weiter: 16 lastStep (0x800), 17 groove (0x81C),
18 grooveDepth (0x81D), 19 voiceAssign (0x802).

## Ergebnisse

| Befund | Marker |
|---|---|
| Alle zwölf Felder der Tabelle oben: Zwillingsprobe gleich in Block, Kopie und Bild, auf Hacktribe, rot und blau | gemessen |
| `level` (keine eigene Seite) durch den Setter: Byte 0x2A und die Kopie ändern sich, zurückgelesen 77 | gemessen |
| `syncGroup` hat keinen Setter. Die Seite SYNC GROUP schreibt den u16 direkt; der Aufruf schreibt ihn genauso (Setter-Wert 1 in `PATTERN_SETTERS` heißt direktes Schreiben). 5000 wird auf 999 geklemmt | gemessen |
| `voiceAssign` über den direkten Setter (`0xC00493A0` Sampler, `0xC0043560` blau) mit `(Objekt + 0x400C, Part, Wert, 1)`: Zwillingsprobe gleich, auf allen drei Firmwares, auch auf blau | gemessen |
| `mfxSend` über den direkten Setter (`0xC00496D4` Sampler, `0xC00437F0` blau): gleich wie die Taste MFX SEND, Byte 0x81B und Kopie | gemessen |
| `ifxOn`: der Setter `0xC0049DEC` schreibt Byte 0x820 und eine Kopie, die Taste IFX ON ruft danach aber noch die Klangerzeugung (`0xC00405EC`, Parameter 0x11) und MIDI (`0xC0059720`) mit 127 statt 1. Mit dem Setter allein steht in der Kopie 1, nach der Taste 127. Darum bleibt `ifxOn` nur lesbar | gemessen (Kopie), offline gelesen (Tastenweg) |
| `ifxType`: der Drehgeber springt am Ende um, die Firmware hat 59 Typen auf Hacktribe (0 bis 58), 48 auf rot, 38 auf blau; die Gerätekarte nennt 0 bis 99. Dazu fehlt auf blau der Part-Edit. Nur lesbar | gemessen |
| `sample`: u16 von 0 bis 999, der Aufruf schreibt ein Byte; was ein leerer Slot macht, ist nicht gemessen. Nur lesbar | Urteil |
| `sample`, `ifxOn` und `ifxType` gesetzt: Block und Kopie unverändert, keine Assertion | gemessen |
| Ein Plugin setzt und liest über `korg.pattern.current.*`, `korg.current.*` und `korg.parts[1].*`: Tempo, Tonart, Sync Group, Level, Voice Assign und MFX Send stehen im RAM und kommen gelesen zurück | gemessen |
| Die 15 Reglerwerte der Parts (Part-Edit) schreiben auf blau nichts, weil der Part-Edit dort nicht vermessen ist; das galt schon vor API 21 | aus API 14 übernommen |

Nachtrag 7. November 2026: `sample`, `ifxOn` und `ifxType` sind ab API 23 schreibbar, die Rollen von `0xC00405EC` (MIDI) und
`0xC0059720` (Klangerzeugung) sind dort richtiggestellt ([Messung](2026-11-07-plugin-api23-part-writes.md)).

## Abweichung von der Spec

Die Spec nennt für `syncGroup` die Werte OFF, ONCE und ON. Die Firmware kennt das Feld nicht, es ist ein Gelumpe-Feld: ein u16 bei
0x3B80 von 0 (aus) bis 999, das die Seite SYNC GROUP im EDIT-Menü schreibt. Der Baum folgt der Firmware.

## Namen

`korg.pattern.current.*` ist der neue Name des laufenden Patterns und braucht API 21; `korg.current.*` bleibt gültig, Setzen darüber
braucht API 15 (wie `korg.seq.setPatternValue`). `syncGroup` braucht unter beiden Namen API 21.

## Offen

- **Am Gerät**: keine Zeile.
- **IFX ON** schreibbar machen hieße den ganzen Tastenweg (Setter, Klangerzeugung, MIDI) je Firmware nachzubauen.
- **IFX TYPE** braucht die Typenzahl je Firmware in der Karte, bevor er schreibbar wird.
