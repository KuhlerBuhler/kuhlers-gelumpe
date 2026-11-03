# Vorschau: die Pads der Parts, die im angesehenen Pattern an sind, blinken (02.11.)

Entschieden am 02.11.: In der Vorschau (`VIEW:` oder `NEXT:`, Modus PART MUTE, die Pads gehören dem angesehenen Pattern) blinken
die Pads der Parts, die im angesehenen Pattern an sind.

- Ein Druck auf so ein Pad holt den Part ins laufende Pattern ([Part reinholen](2026-10-30-vorschau-part-reinholen.md)), das Pad
  hört auf zu blinken und leuchtet.
- Der nächste Druck schaltet ihn aus, das Pad ist dunkel.
- Parts, die im angesehenen Pattern stumm sind, bleiben wie bisher dunkel, ein Druck holt sie, dann leuchtet das Pad.
- Takt wie das Blinken von MENU: 7 Takte des LED-Managers zu 40 ms, also 280 ms an und 280 ms aus. Blinkt MENU (`VIEW:`), blinken
  die Pads im selben Takt mit. Leuchtet MENU (`NEXT:`), blinken sie im selben Takt für sich.
- Auf der Seite des laufenden Patterns (SHIFT + PART MUTE), im SEQUENCER, nach EXIT, nach dem Wechsel und mit EXIT beim Einschalten
  blinkt nichts.

Gebaut in `tools/patch/pattern_switch.py`, im Emulator geprüft mit Hacktribe, Korgs Original rot und blau. Am Gerät noch nicht geprüft.

## Der LED-Manager (gelesen, Hacktribe und rot gleich)

Jede LED hat bei `Manager + 0x4C + 8 * LED` einen Eintrag: `+1` Modus (1 normal, 2 blinkt, 3 einmal), `+2` Helligkeit, `+3` an oder
aus, `+4` die Takte je Hälfte, `+6` die Takte bisher. Bei `+0x30C + 8 * LED` liegt eine Kopie der Tabelle, die Zeichner der Pads
schreiben beide Helligkeiten. Die rote LED von Pad n ist `0x2C + 2 * n`, die blaue `0x2D + 2 * n`, MENU ist LED 7.

Der Takt `0xC0087740` (blau `0xC00777FC`) läuft alle 40 ms über die 88 LEDs. Bei Modus 2 und 3 zählt er `+6` hoch, erreicht der
Zähler `+4`, setzt er ihn zurück, kippt `+3` und schreibt die Helligkeit neu.

## Die Stelle

| Sampler | blau | Was | Wie gefunden |
|---|---|---|---|
| `0xC008774C` | `0xC0077808` | `mov r5, #0` im Takt, vor der Schleife über die LEDs, `r4` und `r6` halten da schon den Manager | gelesen; blau: die Worte um die Stelle sind in beiden Abbildern gleich |

Die erste Anweisung des Takts (`0xC0087740`) hat TAP Motion, sein Ende (`0xC00877D4`) der Notenassistent, den LED-Timer IFX Idle.
Darum hängt der Patch an `0xC008774C`, ein `bl` statt `mov r5, #0`, der Patch setzt `r5` am Ende selbst auf 0.

## Was der Patch tut

- `view_tick` läuft ab dem Start alle 40 ms. Bis zur ersten Vorschau steht im Zustand `FF` (aus dem Abbild), dann liest er nur zwei
  Worte und geht zurück, ohne Literal (die Prüfung der Startphase).
- Er blinkt nur, solange die Pads die Ansicht lesen (die Zelle `0xC0691388` zeigt auf `VIEW_W`) und der Modus PART MUTE ist
  (`Manager + 0xB58` ist 0). Blinkt MENU, nimmt er die Hälfte, die MENU nach diesem Takt hat, sonst zählt er selbst bis 7.
- Wechselt die Hälfte, geht `blink_draw` über die 16 Parts: in der dunklen Hälfte bekommt jedes Pad eines Parts, der in der Ansicht
  an ist und nicht geholt wurde, die Helligkeit 0. Jedes andere Pad, das der Patch dunkel hielt, bekommt die Helligkeit aus der Kopie
  der Tabelle zurück. Gesendet wird wie bei der Firmware, nur wenn sich etwas ändert.
- Welche Pads der Patch dunkel hält, steht als Maske in `VIEW_W + 0x6C`. Endet die Vorschau, PART MUTE oder die Seite, gehen diese
  Pads beim nächsten Takt wieder an.
- Zeichnet die Ansicht die Pads neu (`view_refresh`, nach einem Druck oder SHIFT + PART MUTE), ruft sie `blink_draw` auch, damit die
  Pads in der richtigen Hälfte stehen.
- Der Code liegt bei `0xC0177A00` bis `0xC0177E00`, im `FF`-Lauf hinter den Insert-Records der Preset-Tabellen (in allen drei Builds
  `FF`, kein anderer Patch nennt ihn).

## Im Emulator geprüft (`tools/emu/pswitch_cases.py`, Gruppe `case_view_blink`)

- Die Pads der Parts, die an sind, wechseln zwischen 0 und 255, alle 0,28 s, im Takt von MENU; das Pad des stummen Parts bleibt 0.
- Druck auf ein blinkendes Pad: es leuchtet fest, der Part ist im laufenden Pattern nicht stumm. Zweiter Druck: dunkel und stumm.
- Druck auf das Pad des stummen Parts: es leuchtet fest.
- Nach MENU (`NEXT:`): MENU leuchtet, die Pads blinken weiter mit 0,28 s.
- Nach dem Wechsel, auf der Seite des laufenden Patterns, nach EXIT in der dunklen Hälfte, im SEQUENCER und mit EXIT beim Einschalten:
  kein Blinken, die Pads leuchten wieder.

## Grenzen

- Der LED-Takt und die Bedienung laufen in zwei Tasks. Zeichnet die Firmware die Pads selbst neu, während der Patch sie dunkel hält,
  können sie bis zur nächsten Hälfte leuchten, also höchstens 280 ms. (hergeleitet, am Gerät ungeprüft)
- Mit den Pad-Farben (`pad_colors.py`) blinkt nur die rote LED eines Pads, die blaue zeigt die Farbe weiter. Wie das am Gerät aussieht,
  ist offen. (hergeleitet, ungeprüft)
