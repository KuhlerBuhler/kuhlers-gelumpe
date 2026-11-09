# Vorschau: ein gedrückter Part kommt ins laufende Pattern (30.10.)

Entschieden am 30.10. ([Idee 82](../ideen/82-vorschau-part-reinholen.md)): Wird in der Vorschau (`VIEW:` oder `NEXT:`,
[Vorschau-Pads](2026-10-29-vorschau-pads.md)) ein Pad im Modus PART MUTE zum ersten Mal gedrückt (seit dem Test am Gerät
am 30.10. auch bei einem Part, der in B nicht stumm ist), kopiert die Firmware-eigene Funktion Copy
Part diesen Part des angesehenen Patterns in das laufende Pattern, und er spielt sofort, ohne Patternwechsel.

Gebaut in `tools/patch/pattern_switch.py`, im Emulator geprüft mit Hacktribe, Korgs Original rot und blau. Am Gerät noch nicht
geprüft.

## Copy Part in der Firmware (gemessen, Emulator)

Ablauf am Gerät: SHIFT + Pad 13 (Part Util 1/4, COPY PART), MENU, Rad auf das Quell-Pattern, MENU, Pad des Quell-Parts, Pad des
Ziel-Parts. Im Emulator so durchgespielt (Hacktribe, ungepatcht), mit einem Schreib-Haken auf den Ziel-Part im Pattern im RAM:
der erste Schreiber ist `memcpy` (`0xC000985C`) mit 0x330 Byte, Rücksprung `0xC0066908`, danach schreiben die Setter der
Part-Werte (`0xC0049F7C`, das Mute über `0xC0049330`). Die Banken im RAM bleiben dabei unverändert.

| Sampler (Hacktribe, rot) | blau | Was | Wie gefunden |
|---|---|---|---|
| `0xC00667D4` | `0xC005C49C` | Copy Part: liest am Objekt `+0x40` das Quell-Pattern, `+0x41` den Quell-Part, `+0x42` den Ziel-Part (blau: der Ziel-Part in `r1`). Ist das Quell-Pattern die gewählte Nummer (`PSEL + 0x318`), liest es den Part aus dem Pattern im RAM, sonst aus der Bank. Dann `memcpy` 0x330 Byte, die Setter, die Motion (`0xC0058FB0`) | gemessen: der `memcpy` in den Part kommt aus `0xC0066904` (blau `0xC005C548`); gelesen in beiden; rot gleich Hacktribe (0x2C0 Byte gleich); aufgerufen von der Seite COPY PART bei `0xC0066E4C` (blau `0xC005CFF0`) |
| `0xC0049330` | `0xC00434F0` | Setter des Part-Mutes (Zugriffsobjekt, Part, Mute, Melden) | gelesen (`strb` bei `+0x805`), blau: `fwmap.py`, 16 Worte gleich |
| `0xC0060D34` | `0xC00577A4` | der Hauptbildschirm setzt beim Pad im Modus PART MUTE das umgekehrte Mute über diesen Setter | gelesen in beiden (Getter, `rsbs r2, r0, #1`, Setter); gemessen: der Druck kommt dort an (Fälle unten) |

Copy Part läuft im UI-Task (Stapel der Seite COPY PART), der Pad-Handler `0xC0044874`, in dem die Vorschau den Druck sieht, in einem
anderen (anderer Stapel, gemessen). Darum kopiert der Patch nicht im Pad-Handler, sondern dort, wo der Hauptbildschirm das Mute setzt.

Während gespielt wird, direkt aufgerufen (ungepatcht, Pattern 1 spielt, Quelle Pattern 2 Part 2): das Transport läuft weiter, der
Part im RAM gleicht dem der Bank Byte für Byte, beide Banken unverändert. Das Mute kommt aus der Quelle mit.

## Was der Patch tut

- `view_pad` (Pad-Handler): der erste Druck auf einen Part in der Ansicht setzt dessen Mute in der Ansicht auf "an", merkt den Part
  in `V_PEND` und `V_COPY` (hinter `VIEW_W`, `+0x5C` und `+0x60`, je Part ein Bit) und geht weiter an die Firmware, egal ob der Part
  in der Bank stumm ist. Ein Part in `V_COPY` geht mit jedem weiteren Druck weiter: die Firmware schaltet sein Mute im laufenden
  Pattern, die Ansicht kippt ihres mit, beide bleiben gleich.
- Bis zum Test am Gerät (30.10.) schaltete der erste Druck auf einen Part, der in B nicht stumm ist, ihn nur in der Ansicht stumm, das
  Pad ging aus. Gemeldet als Fehler: ein leuchtender Part in B soll beim Druck auch im laufenden Pattern angehen.
- `view_copy` am Aufruf des Setters (`0xC0060D34`): steht der Part (oder bei einem Stereo-Paar der rechts daneben) in `V_PEND`, ruft
  der Patch Copy Part mit Quelle angesehenes Pattern und Part, Ziel derselbe Part, dann den Setter mit "nicht stumm". Copy Part liest
  die Quelle aus dem RAM, wenn sie die gewählte Nummer ist, und das ist in der Ansicht die angesehene: für den Aufruf steht dort die
  laufende Nummer, danach wieder die alte.
- Eine gehaltene Pad-Eingabe, die nachgereicht wird (Patternladen läuft), geht nicht ein zweites Mal durch `view_pad`.
- Jede neue Ansicht und ihr Ende ohne Wechsel löschen `V_PEND` und `V_COPY`. Der kopierte Part bleibt im laufenden Pattern bis zum
  nächsten Laden. Nichts geht in die Bank, auf die Karte oder ins Flash.

## SHIFT + PART MUTE: die Pads zwischen B und A umschalten (30.10.)

Entschieden am 30.10.: in der Vorschau schaltet SHIFT + PART MUTE, wem die Pads gehören. Die Vorschau beginnt beim angesehenen
Pattern B (alles oben). Nach SHIFT + PART MUTE zeigen und schalten die Pads die Mutes des laufenden Patterns A, wie ohne Vorschau.
Noch einmal, und sie gehören wieder B.

Was die Firmware damit tut (gemessen, Emulator, alle drei Builds, Fälle unten): SHIFT + PART MUTE hebt die Stummschaltung aller
16 Parts im laufenden Pattern auf, auch während eine Vorschau offen ist (mit EXIT beim Einschalten gemessen). Das steht schon in den
[Tastenkombinationen](../tastenkombinationen.md). In der Vorschau ersetzt der Patch diese Bedeutung, ohne Vorschau bleibt sie.

| Sampler (Hacktribe, rot) | blau | Was | Wie gefunden |
|---|---|---|---|
| `0xC007042C` | `0xC0063480` | in der Funktion der Modustasten bei PART MUTE gedrückt: `ldr r3, [r0, #0x358]` liest am Objekt von `0xC0040F04` (blau `0xC003BA4C`), ob SHIFT gehalten ist; mit SHIFT ruft eine Schleife über 16 Parts den Setter des Mutes mit 0 | gelesen in beiden; rot gleich Hacktribe (0x1B0 Byte ab `0xC00703E0` gleich); gemessen: alle Mutes 0 |
| `0xC0070430` | `0xC0063484` | die Anweisung danach (`cmp r3, #0`), dort geht der Haken weiter | gelesen in beiden |
| `0xC0070558` | `0xC0063584` | hier enden beide Wege von PART MUTE, die Taste geht weiter an den Bildschirm | gelesen in beiden |

Was der Patch tut:

- `view_shift` am Lesen von SHIFT: ohne SHIFT oder ohne Vorschau weiter wie die Firmware. Mit SHIFT und Vorschau kippt er `V_SIDE`
  (hinter `VIEW_W`, `+0x64`, 1 heißt Seite A), löscht `V_PEND` und `V_COPY`, setzt den Zeiger der Pad-LEDs (`0xC0691388`) auf das
  Pattern im RAM (Seite A) oder auf die Ansicht (Seite B), zeichnet die Pads neu und springt dorthin, wo beide Wege der Firmware enden.
  Die Mutes aufheben fällt in der Vorschau also weg.
- Seite A: `view_pad` gibt jeden Druck an die Firmware, wie ohne Vorschau (auch im SEQUENCER, dann schalten die Pads die Steps von A).
  Die Farbe der Pads ist die normale, weil der Zeiger auf das Pattern im RAM zeigt. Die Infotexte der Edit-Zeile bleiben bei B.
- Zurück auf B: weil `V_COPY` leer ist, holt der erste Druck einen Part wieder, auch einen, der vorher schon geholt war. Die auf B
  gesetzten Mutes bleiben und gehen beim Wechsel mit.
- Das Rad innerhalb der Vorschau behält die Seite (`pc_view_cells` lässt auf Seite A den Zeiger der Pads beim Pattern im RAM). Endet
  die Vorschau, auch wenn das Rad auf das laufende Pattern zurückgeht, setzt `view_new` die Seite auf B.
- Neuer Zustand: `VIEW_W` hat jetzt 0x68 Byte. Der Code liegt weiter zwischen `0xC0173480` und `0xC0173800`.

| Fall (`case_view_side`) | Hacktribe | rot | blau |
|---|---|---|---|
| `view_shift_part_mute_turns_the_pads_to_the_playing_pattern`: Pattern 1 spielt (Part 6 stumm), Pattern 2 angesehen (Parts 2 und 3 stumm), Pads 1 bis 3 rot `[255, 0, 0]`; SHIFT + PART MUTE: Pads rot wie A (nur Pad 6 aus), blau nur der gewählte Part, Part 6 bleibt stumm (kein Aufheben aller), Ansicht bleibt | ja | ja | ja |
| `view_playing_side_pad_switches_the_playing_mute_without_copy`: Pad 2 auf Seite A: Mute von Part 2 im RAM 1, Step 1 von Part 2 bleibt 0 (nichts kopiert), `V_COPY` 0, Banken gleich | ja | ja | ja |
| `view_shift_part_mute_again_brings_parts_in`: noch einmal SHIFT + PART MUTE: Pads 1 bis 3 rot `[255, 0, 0]`, Pads 4 bis 6 in der Farbe der Ansicht; Pad 2: der Part gleicht Pattern 2 bis auf Byte 1, Mute 0, Pad 2 an | ja | ja | ja |
| `view_wheel_keeps_the_side_a_new_preview_starts_on_the_viewed_pattern`: Seite A, Rad auf Pattern 3: Pads bleiben bei A; EXIT, Pattern 2 neu angesehen: Seite B | ja | ja | ja |
| `shift_part_mute_without_preview_is_stock`: ohne Vorschau, Parts 1 und 6 stumm, SHIFT + PART MUTE: alle Mutes 0 | ja | ja | ja |
| `view_shift_part_mute_kill_switch_is_stock`: EXIT beim Einschalten, Pattern 2 angesehen, SHIFT + PART MUTE: alle Mutes 0 | ja | ja | ja |

## Gemessen (`tools/emu/pswitch_cases.py`, `case_view_copy`)

Pattern 1 spielt im Modus PART MUTE, Part 2 hat dort keine Steps. In Pattern 2 ist Part 2 in der Bank stumm, hat auf allen 64 Steps
eine Note und den Klang von Part 5. Das Rad zeigt Pattern 2. "Stimmen" ist die Maske der Stimmen am Part-Objekt von Part 2
(`0xC009AF20`, `+4`, wie in der [Sync Group](2026-10-25-sync-group-stimmen.md)), alle 10 ms über 1 s gesammelt.

| Fall | Hacktribe | rot | blau |
|---|---|---|---|
| `view_unmute_brings_the_part_into_the_playing_pattern`: vorher Stimmen 0; Pad 2: der Part im RAM gleicht Pattern 2 bis auf Byte 1 (Mute 0), die Ansicht bleibt, Transport läuft, beide Banken gleich | Stimmen `0x2` | `0x2` | `0x1FF0` |
| `view_second_press_mutes_the_brought_part`: Pad 2 noch einmal: Mute 1, Stimmen 0, Pad 2 aus | ja | ja | ja |
| `view_switch_after_bringing_in_loads_the_viewed_pattern`: Pad 2 ein drittes Mal, MENU: Pattern 2 spielt, Part 2 wie in der Bank, Mute 0 (wie auf den Pads) | ja | ja | ja |
| `view_exit_keeps_the_brought_part`: Pad 2, EXIT: Ansicht zu, der Part bleibt, Mute 0, Stimmen ungleich 0, Banken gleich | ja | ja | ja |
| `view_press_on_a_lit_part_brings_it_in`: Part 2 in Pattern 2 und im laufenden nicht stumm, Pad 2 an; Pad 2: der Part gleicht Pattern 2 ganz, Mute 0, Pad 2 an, Stimmen ungleich 0, Ansicht bleibt | ja | ja | ja |
| `view_copy_kill_switch_is_stock`: EXIT beim Einschalten: Pad 2 schaltet das Mute im RAM wie die Firmware, nichts kopiert | ja | ja | ja |

Die Fälle der Ansicht (`case_view`) bestehen unverändert auf allen drei. In `case_view_pads` holt Pad 1 (in der Bank nicht stumm)
jetzt Part 1, statt ihn in der Ansicht stumm zu schalten: Pads rot `[255, 255, 0]`, nach dem Wechsel im RAM `[0, 0, 1, 0]`, auf allen
drei so gemessen.

Nebenbei gemessen: ein Part, dessen Steps nur im ersten Takt stehen, klingt nach der Kopie erst, wenn das Pattern wieder dort ist.
Das ist kein Warten der Kopie, mit Steps in allen Takten kommen die Stimmen sofort.

## Offen

- Gerät: SHIFT + PART MUTE in der Vorschau, besonders ob die Farben beim Umschalten sofort folgen. (ungeprüft)
- Ein Druck auf B, dessen Kopie noch wartet, während SHIFT + PART MUTE kommt: die Kopie fällt weg, die Firmware schaltet dann nur das
  Mute in A. Im Emulator nicht nachgestellt, das Fenster ist ein paar Millisekunden. (hergeleitet)

- Gerät: alles oben, besonders ob man beim Kopieren einen Knacks oder eine Lücke hört. Copy Part ruft vor und nach der Kopie
  `0xC009B5E0` und `0xC009B5EC` mit dem Part (blau `0xC00881CC`, `0xC00881D4`), was die genau tun, ist nicht gelesen.
- Während des Aufrufs steht in der gewählten Nummer kurz die laufende. Liest der Engine-Task sie genau dann, sieht er sie. Der
  eigene Haken am Sequenzende liest sie in der Ansicht nicht (hergeleitet aus `seq_hook`).
- Stereo-Paare: Copy Part behandelt sie selbst, der Patch gibt nur den Part; nicht geprüft.
- Läuft die Motion des Quell-Parts mit und meldet die Firmware bei vollem Motion-Speicher ihren Fehler (`0xC0083DB0`), erscheint das
  Fenster über dem Hauptbildschirm; nicht geprüft.
