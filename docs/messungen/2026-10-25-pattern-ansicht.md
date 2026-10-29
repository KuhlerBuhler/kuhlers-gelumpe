# Die Ansicht des nächsten Patterns: Pads und Info-Texte (25.10.)

Wunsch: Ist ein Patternwechsel vorgemerkt (die untere Zeile sagt `VIEW:` oder `NEXT:`), sollen die Pads und die Info-Texte der Edit-Zeile
(`OSC:`, `Pitch:` und so weiter) das nächste Pattern zeigen. Gebaut und im Emulator geprüft (Hacktribe, Korgs Original und blau). Am Gerät
noch nicht geprüft. "Ansicht" ist kein Begriff der Firmware; gemeint ist der Zustand des Patternwechsels ([Idee 46](../ideen/46-patternwechsel-bestaetigung.md)),
also solange `S_BROWSE` oder `S_ARMED` gilt (auch gestoppt mit ungespeicherten Änderungen, [Idee 57](../ideen/57-ungespeichert-warnen.md)).

## Wie die Firmware die Daten liest (gemessen, Hacktribe, Emulator)

- Zwei Zeigerzellen, die nur Anzeige-Code liest (kein Schreibzugriff nach dem Start): `0xC0691388` zeigt auf das Zugriffsobjekt des
  Patterns (in der Pattern-Struktur bei `+0x400C`, bei `+4` steht das Pattern), `0xC069136C` auf das Pattern selbst. Aus der ersten Zelle
  lesen die Pad-LEDs (Part-Mutes, Steps, 6 Stellen im LED-Manager `0xC0087DF4` bis `0xC0089D78`), aus der zweiten die 26 Formatierer der
  Info-Texte (`0xC00801C0` bis `0xC0080EB0`).
- Die Engine, der Ton und alles andere liest das Pattern im RAM über `0xC033E6A4` und andere Wege. Mit den beiden Zellen auf einem anderen
  Block spielt das laufende Pattern unverändert weiter (Lesezugriffe der Engine gemessen: nur auf den Block im RAM).
- Blau: dieselben Stellen, gefunden mit `tools/patch/fwmap.py` ([data/synth-map/pattern-view.json](../../data/synth-map/pattern-view.json)).

## Was der Patch tut (`tools/patch/pattern_switch.py`)

- `pc_view_cells`: solange gebrowst oder bestätigt ist und die Nummer nicht die laufende ist, zeigt die erste Zelle auf eine Kopie des
  Zugriffsobjekts (`VIEW_W`, `0xC0173400`, nur im RAM), deren Pattern der Block der Pattern-Bank ist (Platz `0xC08B2940` + Nummer mal
  `0x4000`, minus 4); die zweite Zelle zeigt auf diese Kopie minus `0x400C`. Sonst stehen beide wie die Firmware sie hatte. `pc_led`
  ruft es nach jeder Änderung auf; der Engine-Task (Ende der Sequenz) setzt die Zellen nur zurück, das Neuzeichnen nach dem Laden macht
  die Firmware selbst.
- `pc_view_refresh`: ändert sich die Ansicht, zeichnet die Firmware die Pads in der Art des Pad-Modus neu (`0xC00892D4`, ihr eigenes
  Neuzeichnen nach einem Patternwechsel). Spielt das Pattern im SEQUENCER-Modus, kommen die Steps auch ohne Aufruf nach spätestens
  einer Sekunde nach.
- `info_hook` (`0xC008684C`): solange die Zeile `VIEW:` oder `NEXT:` sagt, tut der Bauer der Info-Zeile nichts (ein Merker bei `+0x5c`).
  Drückt man EDIT, während angesehen wird, gibt der Haken die Zeile frei: sie zeigt `OSC:`, `Pitch:`, `Glide:` und so weiter des Patterns,
  das angesehen wird. Das Rad auf ein anderes Pattern bringt die Zeile `VIEW:` zurück; endet die Ansicht, liest die Zeile wieder das
  Pattern im RAM.
- `pad_colors.py`: die Farben für Akkorde und gebundene Noten lesen die Steps über dieselbe Zelle, damit die Pads nicht zwei Patterns mischen.

## Entschieden und Grenzen

| Frage | Entscheidung |
|---|---|
| Die untere Zeile ist entweder das Etikett oder die Info-Zeile | das Etikett bleibt, bis EDIT gedrückt wird; erst dann zeigt die Zeile die Info-Texte des angesehenen Patterns. Beide Zeilen gleichzeitig gibt es nicht |
| Wer ändert während der Ansicht Werte (Regler, Pad-Druck im SEQUENCER) | Regler: das Pattern im RAM, das spielt; angezeigt wird weiter das nächste Pattern. Pads: seit 29.10. die des angesehenen Patterns, PART MUTE schaltet dessen Mutes, SEQUENCER verwirft den Druck ([Vorschau-Pads](2026-10-29-vorschau-pads.md)) |
| Andere Leser des Patterns im RAM, die zur Anzeige gehören | der Part, der als blaues Pad leuchtet, kommt aus dem Muster im RAM (`0xC0088AA4`), nicht gemessen wie sichtbar. TAP Motion und der Vergleich für ungespeicherte Änderungen lesen weiter das Pattern im RAM, sie sind keine Anzeige |
| Ende der Ansicht beim Wechsel | die Zellen gehen zurück, wenn das Ende der Sequenz die Bestätigung verbraucht; bis das neue Pattern geladen ist (Zehntel Sekunden, geschätzt), zeigt die Anzeige das Pattern, das noch im RAM liegt |
| Mit EXIT beim Einschalten, Einstellung OFF | nichts ändert sich, die Zellen bleiben, wie die Firmware sie setzt |

## Geprüft (`tools/emu/pswitch_cases.py`, `case_view`)

| Fall | Erwartung |
|---|---|
| `view_pads_show_the_browsed_pattern` | SEQUENCER, gestoppt mit ungespeicherten Änderungen: die Pads zeigen die Steps des angesehenen Patterns, mit EXIT die im RAM; die Zeiger sind zurück |
| `view_pads_show_the_browsed_mutes` | PART MUTE: die Pads zeigen die Mutes des angesehenen Patterns |
| `view_edit_key_shows_the_info_texts_of_the_browsed_pattern` | `VIEW:` in der Zeile; EDIT zeigt `Pitch:` mit dem Wert des Banks (20), nach EXIT dieselbe Zeile mit dem Wert im RAM (0) |
| `view_follows_the_confirmation_and_ends_at_the_switch` | `NEXT:` hält die Ansicht, mit dem Patternwechsel sind die Zeiger zurück |
| `view_kill_switch_is_stock`, `view_setting_off_is_stock` | die Zellen bleiben, wie die Firmware sie hatte |
