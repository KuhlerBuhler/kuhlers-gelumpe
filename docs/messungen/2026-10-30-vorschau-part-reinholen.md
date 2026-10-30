# Vorschau: ein entstummter Part kommt ins laufende Pattern (30.10.)

Entschieden am 30.10. ([Idee 82](../ideen/82-vorschau-part-reinholen.md)): Wird in der Vorschau (`VIEW:` oder `NEXT:`,
[Vorschau-Pads](2026-10-29-vorschau-pads.md)) ein Part im Modus PART MUTE entstummt, kopiert die Firmware-eigene Funktion Copy
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

- `view_pad` (Pad-Handler): ein Druck, der in der Ansicht einen Part entstummt, setzt wie bisher das Mute der Ansicht, merkt den Part
  in `V_PEND` und `V_COPY` (hinter `VIEW_W`, `+0x5C` und `+0x60`, je Part ein Bit) und geht weiter an die Firmware. Stummschalten
  bleibt in der Ansicht, wie bisher. Ein Part in `V_COPY` geht mit jedem Druck weiter: die Firmware schaltet sein Mute im laufenden
  Pattern, die Ansicht kippt ihres mit, beide bleiben gleich.
- `view_copy` am Aufruf des Setters (`0xC0060D34`): steht der Part (oder bei einem Stereo-Paar der rechts daneben) in `V_PEND`, ruft
  der Patch Copy Part mit Quelle angesehenes Pattern und Part, Ziel derselbe Part, dann den Setter mit "nicht stumm". Copy Part liest
  die Quelle aus dem RAM, wenn sie die gewählte Nummer ist, und das ist in der Ansicht die angesehene: für den Aufruf steht dort die
  laufende Nummer, danach wieder die alte.
- Eine gehaltene Pad-Eingabe, die nachgereicht wird (Patternladen läuft), geht nicht ein zweites Mal durch `view_pad`.
- Jede neue Ansicht und ihr Ende ohne Wechsel löschen `V_PEND` und `V_COPY`. Der kopierte Part bleibt im laufenden Pattern bis zum
  nächsten Laden. Nichts geht in die Bank, auf die Karte oder ins Flash.

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
| `view_copy_kill_switch_is_stock`: EXIT beim Einschalten: Pad 2 schaltet das Mute im RAM wie die Firmware, nichts kopiert | ja | ja | ja |

Die Fälle von [Vorschau-Pads](2026-10-29-vorschau-pads.md) (`case_view_pads`) und der Ansicht (`case_view`) bestehen unverändert auf
allen drei.

Nebenbei gemessen: ein Part, dessen Steps nur im ersten Takt stehen, klingt nach der Kopie erst, wenn das Pattern wieder dort ist.
Das ist kein Warten der Kopie, mit Steps in allen Takten kommen die Stimmen sofort.

## Offen

- Gerät: alles oben, besonders ob man beim Kopieren einen Knacks oder eine Lücke hört. Copy Part ruft vor und nach der Kopie
  `0xC009B5E0` und `0xC009B5EC` mit dem Part (blau `0xC00881CC`, `0xC00881D4`), was die genau tun, ist nicht gelesen.
- Während des Aufrufs steht in der gewählten Nummer kurz die laufende. Liest der Engine-Task sie genau dann, sieht er sie. Der
  eigene Haken am Sequenzende liest sie in der Ansicht nicht (hergeleitet aus `seq_hook`).
- Stereo-Paare: Copy Part behandelt sie selbst, der Patch gibt nur den Part; nicht geprüft.
- Läuft die Motion des Quell-Parts mit und meldet die Firmware bei vollem Motion-Speicher ihren Fehler (`0xC0083DB0`), erscheint das
  Fenster über dem Hauptbildschirm; nicht geprüft.
