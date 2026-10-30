# Vorschau: die Pads gehören dem angesehenen Pattern (29.10.)

Entschieden am 29.10.: Solange ein anderes Pattern angesehen wird (`VIEW:` oder `NEXT:`, [Ansicht](2026-10-25-pattern-ansicht.md)),

- lassen sich die Pads des laufenden Patterns nicht mehr schalten,
- schalten die Pads im Modus PART MUTE die Mutes des angesehenen Patterns,
- übernimmt das angesehene Pattern beim Wechsel diese Mutes,
- haben die Pads des angesehenen Patterns eine eigene Farbe.

Gebaut in `tools/patch/pattern_switch.py` und `tools/patch/pad_colors.py`, im Emulator geprüft mit Hacktribe, Korgs Original rot und blau.
Am Gerät noch nicht geprüft.

Seit 30.10. holt das Entstummen eines Parts ihn zusätzlich ins laufende Pattern
([Part reinholen](2026-10-30-vorschau-part-reinholen.md)).

## Was vorher war (gemessen, Emulator, Hacktribe)

- Ein Pad im Modus PART MUTE schaltet beim Drücken das Mute im Pattern im RAM: Byte 1 des Parts (Block `+0x801 + 0x330 * Part`, 1 heißt
  stumm), geschrieben bei `0xC0049354`, aufgerufen von `0xC0060D38`. Das Loslassen schreibt nichts.
- Die Pads der Ansicht zeigen die Mutes aus dem Block der Bank, der Druck ging aber an das laufende Pattern. Im SEQUENCER genauso mit den
  Steps (so stand es schon in der Tabelle der Ansicht).

## Die neue Stelle: der Getter der Part-Mutes

| Sampler | blau | Was | Wie gefunden |
|---|---|---|---|
| `0xC0048CFC` | `0xC0042ED8` | Getter der Part-Mutes (Zugriffsobjekt, Part): `ldr r3, [r0, #4]`, `mla` mit `0x330`, `ldrb r0, [r1, #0x805]` | gelesen (Hacktribe und Korgs Original rot gleich, Wort für Wort); die Mute-Schleife der Pad-LEDs `0xC0087D9C` ruft ihn bei `0xC0087DB4` mit dem Inhalt der Zelle `0xC0691388`; blau: `fwmap.py`, 16 Worte gleich |
| `0xC0048D00` | `0xC0042EDC` | die Anweisung danach, wo der Haken weitergeht | ebenso |

Die Engine und alles andere rufen den Getter mit dem Zugriffsobjekt des Patterns im RAM. Mit dem Zugriffsobjekt der Ansicht (`VIEW_W`)
ruft ihn nur, wer über die Zelle liest, also die Anzeige (hergeleitet aus der Ansicht: die Zelle hat außer dem Patch keine Schreiber).

## Was der Patch tut

- `pad_gate`: ist eine Ansicht offen, geht jeder Druck erst an `view_pad`. Im Modus PART MUTE kippt er das Mute des Parts in der Ansicht
  (der erste Druck auf einen Part beginnt bei seinem Mute in der Bank), zeichnet die Pads neu und geht nicht weiter an die Firmware. Im
  SEQUENCER wird der Druck verworfen. Loslassen und alle anderen Modi gehen wie immer weiter. Der Modus steht im LED-Manager bei
  `+0xB58` (0 PART MUTE, 4 SEQUENCER).
- `view_mute` am Getter: ruft ihn jemand mit `VIEW_W`, antwortet ein angefasster Part mit dem Mute aus der Ansicht. Die Bank und das
  Pattern im RAM bleiben unberührt, bis gewechselt wird.
- Neuer Zustand hinter `VIEW_W` (`0xC0173400`, jetzt 0x5C Byte): bei `+0x4C` die Nummer, zu der die Mutes gehören, `+0x50` je Part ein Bit
  "angefasst", `+0x54` je Part ein Bit "stumm", `+0x58` 1 vom Wechsel bis zum Laden. Der Code liegt bei `0xC0173480` bis höchstens
  `0xC0173800` (dort beginnt die Tabelle des SysEx-Patches); im Abbild aller drei Builds `FF`, gemessen mit den gepatchten Dateien.
- Wechsel: das Sequenzende mit `NEXT:`, STOP mit `NEXT:` und MENU im Stand (ungespeichert, lädt sofort) setzen `+0x58`. `copy_hook`
  schreibt nach der Kopie (und nach dem Mitnehmen einer Sync Group) die angefassten Mutes ins Pattern im RAM, wenn die Quelle der
  Block der angesehenen Nummer ist. Jedes Laden beendet das.
- Endet die Ansicht ohne Wechsel (EXIT, ein anderes Pattern am Rad, Pad, Program Change, STOP beim Blättern), sind die Mutes weg.
- Farbe (`pad_colors.py`, `pc_chord`): zeigt die Zelle nicht auf das Zugriffsobjekt im RAM (`[0xC033E6A4] + 0x400C`) und ist der Modus
  PART MUTE oder SEQUENCER, gehen alle Pads durch die Farbe der Akkorde (pink bei den Werksfarben). Liegt der Cursor auf einem leuchtenden
  Pad, nimmt es die übrige Farbe (rot bei den Werksfarben), damit man beim gewählten Part weiter sieht, ob er leuchtet. Bei jedem Wechsel
  der Ansicht werden alle 32 Pad-LEDs erzwungen neu gesendet (`0xC00875F4` mit force 1), sonst bliebe ein Pad, dessen Wert gleich bleibt,
  in der alten Farbe.

## Gemessen (`tools/emu/pswitch_cases.py`, `case_view_pads`)

Pattern 1 spielt im Modus PART MUTE, in Pattern 2 sind in der Bank die Parts 2 und 3 stumm, das Rad zeigt Pattern 2.

| Fall | Ergebnis (Hacktribe, rot, blau gleich) |
|---|---|
| `view_pads_switch_the_viewed_mutes_not_the_playing_ones` | Pads 1 und 2 gedrückt: im RAM `[0, 0, 0]`, in der Bank `[0, 1, 1]`, Pads rot `[0, 255, 0]` |
| `view_pads_have_their_own_colour` | spielend: alle Pads rot, Part 1 dazu blau; angesehen: leuchtende Pads rot und blau (pink), Part 1 (Cursor) nur rot |
| `view_switch_takes_the_mutes_set_on_the_pads` | nach MENU und Wechsel: Pattern 2 spielt, im RAM `[1, 0, 1, 0]`, die Bank unverändert, die Pads wieder in den Farben des laufenden Patterns |
| `view_exit_drops_the_mutes_set_on_the_pads` | Pad 1, dann EXIT: im RAM nichts geändert; erneut angesehen zeigen die Pads die Mutes der Bank |
| `view_sequencer_pads_leave_the_playing_steps` | SEQUENCER, Pattern 2 angesehen, Pads 1 und 2: Steps im RAM `[1, 0]` unverändert; nach EXIT setzt Pad 2 seinen Step |
| `view_pads_kill_switch_is_stock` | EXIT beim Einschalten: Pad 1 schaltet das Mute im RAM wie die Firmware |

## Offen

- Gerät: alles oben.
- Sync Group: das Mitnehmen setzt die Mutes des spielenden Patterns ins neue, die Ansicht zeigt aber die der Bank. Angefasste Parts
  gewinnen beim Wechsel, die übrigen kommen aus dem spielenden Pattern. Nicht am Gerät gesehen, ob das stört.
- Im SEQUENCER sind in der Ansicht die Akkorde nicht mehr von einfachen Steps zu unterscheiden, beide haben die Farbe der Ansicht.
