# Grooves und Skalen auf der roten Firmware

[Emulator](../glossary.md#emulator) mit Korgs Original 2.02 (rot) und [Hacktribe](../glossary.md#hacktribe) 2.02. Auf der
roten Firmware gibt es 62 statt 25 Grooves und 70 statt 35 Skalen, die neuen hinter Korgs Werkseinträgen.
[Patch](../glossary.md#patch) `data/patches/grooves-scales.json`, gebaut von `tools/patch/grooves_scales.py`, Fälle in
`tools/emu/grooves_scales_cases.py`. Am Gerät nicht geprüft.

Zählweise: Groove und Skala nullbasiert wie in der Firmware. Groove 0 bis 24 und Skala 0 bis 34 sind Korgs Werkseinträge.

Marker: **gemessen** (im Emulator ausgeführt oder in den Dateien verglichen), **hergeleitet** (aus Code oder Messung
geschlossen), **Urteil** (Produktentscheidung), **offen**.

## Belegtabelle

| Behauptung | Marker | Beleg |
|---|---|---|
| Korgs Groove-Bauer `0xC0051334` holt seine Basis aus dem Wort `0xC0052338` (`0xC068A03C` im RAM), löscht und schreibt dort 25 Vorlagen zu je `0x140` Byte | gemessen (Wörter in der VSB), hergeleitet (Rolle aus dem Code) | `grooves_scales.py` prüft jedes Wort vor dem Bauen |
| Vorlage: `GVST` bei 0, Name bei `+0x10` (16 Byte), Länge bei `+0x22`, Step i bei `+0x30 + 4 * i` mit Versatz (vorzeichenbehaftet, 96 pro Step), Velocity, Gate (96 ist voll), `GVED` bei `+0x13C` | gemessen | Korgs 25 Vorlagen im RAM nach dem Start |
| Die Leser Versatz `0xC00479CC`, Velocity `0xC0047A2C`, Gate `0xC0047A8C` und der Name (`0xC0080AF8`) nehmen dieselbe Basis über eigene Wörter (`0xC0047A28`, `0xC0047A88`, `0xC0047AE8`); der Step ist Step modulo Länge | gemessen (Wörter), hergeleitet (Code) | `GROOVE_LITERALS` in `grooves_scales.py` |
| Der Patch lenkt alle fünf Wörter auf eine Tabelle im Bild bei `0xC013C100` (62 Vorlagen); Korgs Bauer füllt 0 bis 24 dort selbst, 25 bis 61 sind eigene Daten. Kein neuer ARM-Code | gemessen | Fall `factory_grooves_built_in_the_table`: 25 `GVST`, gleich der Tabelle, die eine ungepatchte Kopie in Korgs RAM baut |
| Korgs alter Groove-Speicher bei `0xC068A03C` bleibt mit dem Patch leer | gemessen | Fall `old_groove_ram_untouched`: 0 Byte geschrieben |
| `0xC013C0B0` bis `0xC014EE00` ist `FF` in Korgs rotem 2.02 hinter dem DSP-Strom; bei Hacktribe liegen dort dessen Grooves und Skalen | gemessen | Bytevergleich der VSB; `STOCK_FREE_RUNS` in `data/patch-ram.mjs`, `test/patch-ram.test.mjs` |
| Grenzen: Setter `0xC0049DA4` `cmp r2, #0x18` wird `#0x3D`; GROOVE-Seite `0xC007BB88` bis `0xC007BB94` läuft bis 61 und wieder auf 0 | gemessen | Fälle `setter_takes_25_to_61` (25, 40, 61 bleiben, 62 und 200 werden 0), `menu_wraps_and_steps` (von 0 abwärts 61, dann 0, 25, 26, 27) |
| Die Groove-Leser liefern für 25, 33, 45 und 61 über 64 Steps genau die eigenen Daten; ein Pattern mit Groove 61 spielt ohne Assert | gemessen | Fälle `engine_plays_new_grooves`, `plays_with_groove_61` |
| Die 37 neuen Grooves sind eigene, keine Kopie von Hacktribe: Swing in Stufen, Humanize (feste Zufallsfolge), Akzente, Ghost Notes, Push und Drag, Crescendo, Staccato, Legato, Feels | Urteil | `GROOVE_LIST` in `grooves_scales.py` |
| Skalen: Stufen `0xC00DCF70` (13 Byte je Skala), Fang-Tabelle `0xC00DD148` (12 Byte), Namen `0xC00DD330`, Akkord-Objekte `0xC00DDB18`, KEYBOARD-Pads `0xC00C5DB8` (16 Byte, gelesen vom Pad-Bauer `0xC0044D28` über `0xC0044DA4`); der Patch lenkt die sieben Wörter darauf auf neue Tabellen ab `0xC0141000` | gemessen (Wörter), hergeleitet (Code) | `SCALE_LITERALS` in `grooves_scales.py` |
| KEYBOARD-Pads: Pad 8 bis 15 sind die untere Reihe (die ersten 8 Töne der Skala ab Grundton), Pad 0 bis 7 dieselben eine Oktave höher. Korgs Tabelle folgt dieser Regel bis auf Skala 0 (chromatisch) und 31/32; die neuen Skalen bekommen sie nach der Regel | gemessen | Fall `keyboard_plays_new_scales`; `pad_notes` in `grooves_scales.py` |
| Korgs 35 Einträge der Stufen-, Fang-, Namen- und Pad-Tabelle kommen beim Anwenden aus der Datei des Nutzers (`copy`), nicht aus dem Repo | gemessen | Fall `factory_scale_entries_copied` |
| Grenzen: Skalen-Seite `0xC007CF24`/`28` und Setter `0xC004860C`/`10` gehen bis 69 | gemessen | Fall `menu_reaches_69` (von 34 aufwärts 35, 36, Ende bei 69) |
| Die Stufen der 35 neuen Skalen sind dieselben wie die zusätzlichen Skalen von Hacktribe; Namen eigene Kürzel (12 Zeichen) | gemessen | `grooves_scales.py --hacktribe HACKTRIBE.VSB`: 35 von 35 gleich |
| Akkord-Objekt: Vtable, Zeilen, Varianten; eine Zeile 64 Byte, 8 Einträge zu 8 Byte (Name, Grundton und Bass, Anzahl, Noten); die neuen Skalen teilen eine Methode `ldr r0, [r0, #12]; add r0, r0, r1, lsl #6; bx lr` | gemessen (Korgs Objekte), hergeleitet (Rolle) | `chord_table` in `grooves_scales.py` |
| Akkorde der neuen Skalen nach einer eigenen Regel: Stufen-Terzschichtung aus der Skala, Name nach Tonklassen. Korgs Tabellen folgen keiner festen Regel (Moll-Penta 6 Zeilen, Dur-Penta nutzt Ionisch) | Urteil | `VOICINGS`, `chord_name` in `grooves_scales.py` |
| KEYBOARD und CHORD auf den Pads spielen die Töne der neuen Skalen | gemessen | Fälle `keyboard_plays_new_scales`, `chord_pads_play_our_chords` |
| Pattern aus Hacktribe mit Groove über 24 klingen anders, die Grooves sind eigene | hergeleitet | eigene `GROOVE_LIST` |
| Kein Schalter: wo der Satz den Patch hat, sind die Grooves und Skalen immer da | hergeleitet | der Patch ändert nur Wörter und Daten, keine Hooks |
| Wie die Grooves und Akkorde am Gerät klingen | offen | nur am Gerät |
