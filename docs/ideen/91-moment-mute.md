# 91. Part-Mute nur solange gedrückt

Wunsch aus der Community (Oktober 2026): wie beim Korg ESX schaltet ein Pad im Modus PART MUTE seinen Part nur stumm,
solange es gehalten wird. Loslassen holt den Part zurück.
Stand 2026-11-03: **als Plugin im Katalog gebaut (Momentary Mute), im Simulator geprüft, im Emulator und am Gerät
nicht.** Marker: **gemessen**, **hergeleitet**, **ungeprüft**.

## Was es schon gibt

- PART MUTE ist in der Firmware ein Pad-Modus wie SEQUENCER oder KEYBOARD: die LED bleibt nach dem Loslassen an, eine
  andere Modus-Taste beendet ihn ([Plugins](../plugins.md), Part Mute auf Part Erase). (gemessen im Emulator)
- Die Firmware kennt für Mute nur Umschalten; `korg.mute` liest den Zustand zuerst und drückt das Mute-Pad der Firmware
  nur, wenn er nicht schon stimmt. (gemessen)
- `korg.padHold` hält Pad-Anschläge von der Firmware fern, das Plugin bekommt `pad` weiter; das Loslassen folgt seinem
  Anschlag. Schließt eine App, gibt die Laufzeit die Pads zurück. (gemessen)

## Gebaut

- Katalog-Plugin **Momentary Mute** (`data/script/presets.mjs`, Hintergrund, keine App).
- Nur im Modus PART MUTE aktiv. Das Plugin folgt den Modus-Tasten: PART MUTE schaltet es ein, PART ERASE, TRIGGER,
  SEQUENCER, KEYBOARD, CHORD, STEP JUMP und PATTERN SET aus. Nur dann hält es die Pads mit `korg.padHold` fern.
- Druck dreht den Part um, Loslassen stellt ihn zurück: ein spielender Part ist gehalten still, ein gemuteter spielt
  gehalten. Mehrere Pads gleichzeitig gehen, jedes Loslassen stellt nur seinen Part zurück.
- SHIFT gehalten gibt die Pads der Firmware zurück, SHIFT + Pad bleibt wie ohne Plugin.
- Die Seite MOMENT MUTE im Menü BLECH: 1 an (Vorgabe), 0 aus, dann rasten die Pads wie ohne Plugin.
- Tests: `test/script-moment-mute.test.mjs` (Druck mutet, Loslassen holt zurück, zwei Pads, andere Tasten und Modi
  ändern nichts, Menü aus).

## Entscheidung: nur im Modus PART MUTE

Immer aktiv im Hintergrund würde die Pads auch in SEQUENCER, TRIGGER oder KEYBOARD nehmen, dort sind sie Steps und Töne.
Darum nur im Modus, in dem die Pads ohnehin Parts muten. Wer rastende Mutes will, schaltet MOMENT MUTE auf 0. (Urteil)

## Offen

- Im Emulator mit der Firmware nicht geprüft, am Gerät nicht. (**ungeprüft**)
- Den Pad-Modus beim Start des Plugins kennt es nicht: erst ein Druck auf PART MUTE schaltet es scharf. (hergeleitet)
- Solange eine App offen ist, sieht die Firmware die Modus-Tasten nicht, das Plugin aber schon: ein Modus-Wechsel bei
  offener App kann den gemerkten Modus verschieben. (hergeleitet)
- SHIFT und Pad im selben Rahmen: das Pad kann noch gehalten werden, bevor das Plugin SHIFT sieht. (hergeleitet)
- Mit PATTERN CONFIRM gehören die Pads beim Ansehen eines anderen Patterns dessen Mutes; das Plugin schaltet die Mutes
  des laufenden Patterns. (**ungeprüft**)
