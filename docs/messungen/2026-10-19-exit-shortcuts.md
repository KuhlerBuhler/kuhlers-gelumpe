# EXIT-Shortcuts: speichern und Part zurücksetzen (19.10.)

Wunsch vom 18.10.: ein Kürzel, das die offenen Änderungen speichert (SHIFT + WRITE ist mit der Namenseingabe belegt), und eins,
das ein Pad auf seine ursprünglichen Werte zurücksetzt. EXIT hat auf dem Hauptbildschirm keine Haltefunktion
([Tastenkombinationen](../tastenkombinationen.md), Abschnitt 4), deshalb EXIT gehalten für beides.

## Was die Firmware tut (Hacktribe 2.02, Emulator und Disassembly)

- **WRITE** öffnet das Fenster 0x12 (Bildschirm 18, Ziel ist das laufende Pattern), der zweite WRITE speichert. Der Befehl
  läuft in der CommandTask: `0xC0038304` ruft `0xC004C28C(?, Nummer, Quelle, 1)`, das kopiert 0x4000 Byte in die Bank
  (`0xC08B2940 + Nummer * 0x4000`) und schreibt sie mit `0xC002A0C4` in den Flash. Die Globals schreibt das nicht mit.
- **Pattern laden** ist `0xC004AB84(Pattern, Quelle, 1)` (CommandTask, gerufen von `0xC0079C04`): 0x4000 Byte von der Quelle
  ins Pattern im RAM (`[0xC033E6A4] + 4`), danach wendet die Firmware das Pattern an (Kopf-Setter, Parts, Effekte). Mit der
  eigenen Kopie als Quelle wendet sie das Pattern im RAM auf sich selbst an.
- Regler ändern nur die Bytes im Pattern, der DSP bekommt dabei nichts (6 Regler, 0 Übertragungen); das Laden schickt die
  Effekte neu.
- Pad-Modus beim LED-Manager `[0xC0345A1C] + 0xB58`: 0 PART MUTE, 2 PART ERASE, 3 TRIGGER, 4 SEQUENCER, 5 KEYBOARD, 6 CHORD,
  7 STEP JUMP, 9 PATTERN SET (gemessen nach dem Druck auf die Taste, 30.10.); `+0xB60` der gewählte Part.

## Der Patch (`tools/patch/script_shortcuts.s`, Laufzeit des BLECH-Menüs)

- Der Eingangsfilter merkt sich EXIT (gedrückt, losgelassen).
- **EXIT + WRITE** auf dem Hauptbildschirm: WRITE geht wie immer an die Firmware, das Fenster geht auf; der nächste Takt
  (40 ms, UiTask) sieht Bildschirm 18 und gibt dem Fenster den zweiten WRITE über den Tasten-Handler `0xC0042BB8`. Wartet
  höchstens 1 s auf das Fenster.
- **EXIT + Pad** auf dem Hauptbildschirm: das Pad geht nicht an die Firmware (klingt nicht, setzt keinen Schritt). Der
  nächste Takt kopiert die Bytes 2 bis 0x2F des Parts (alles außer Last Step und Stumm, die Steps bleiben) aus dem
  gespeicherten Pattern in der Bank ins Pattern im RAM und ruft `0xC004AB84(Pattern, Pattern + 4, 1)`. Welcher Part: in
  SEQUENCER und STEP JUMP der gewählte, dort steht ein Pad für einen Step. In allen anderen Modi (PART MUTE, PART ERASE, TRIGGER,
  KEYBOARD, CHORD, PATTERN SET) der Part des Pads, Pad 6 setzt Part 6 zurück. Der gewählte Part bleibt in jedem Modus, wie er war.
  Bis 30.10. nahm nur TRIGGER den Part des Pads, in PART MUTE und KEYBOARD setzte Pad 6 den gewählten Part zurück (gemessen).
- Nicht mit EXIT beim Einschalten, nicht auf der blauen (dort nicht gemessen, `SHORTCUTS 0`). Drei Bytes vor `MENU_STATE`.

## Ungespeichert anzeigen (19.10., Vorschlag 1)

Die WRITE-LED (`0x0B`) atmet, solange das Pattern im RAM von seinem Platz in der Bank abweicht: alle 8 Frames vergleicht BLECH
beide Wort für Wort, die LED läuft in 32 Frames (1,3 s) von 1 bis 61 und zurück, nur ungerade Werte. Ein Wert der Firmware (gerade
oder 255) bleibt stehen, ebenso alles, solange ein Plugin die LED-Sperre hält. Nur auf dem Hauptbildschirm. Gemessen
(`shortcut:write_led_breathes_while_unsaved`, am Netzteil): gespeichert 0; Regler gedreht, 2 s: 1, 5, ... 61; nach EXIT + WRITE 0.
Auf Batterie mit Power Save kommt sie wie jede LED mit einem Viertel an.

**Byte `0x3C` zählt nicht (Gerätemeldung 19.10.).** Von Pattern 7 auf 8 gewechselt, nichts angefasst, und die LED atmete. Im
Emulator mit dem Flash vom 09.10. nachgestellt: danach weicht genau ein Byte ab, `0x3C` (Bank 1, RAM 0). Es ist der Zustand "MFX-Pad
berührt": das Laden (`0xC004AB84`) setzt ihn nach dem Kopieren neu, 1 nur mit HOLD (Byte `0x41`), sonst 0 (`0xC004AD84`, dazu
Pad aus an die Klangerzeugung). Pattern 8 war mit berührtem Pad gespeichert. Der Vergleich lässt dieses Byte jetzt aus, ebenso der
des Patternwechsels im Stand (`pc_dirty`, `tools/patch/pattern_switch.py`), der sonst nach so einem Pattern nur noch geblättert
hätte. Geprüft: `shortcut:pad_state_is_not_an_edit` und `pswitch:pad_state_saved_wheel_loads`, Hacktribe und rot.

## Emulator (`tools/emu/shortcut_cases.py`, 8 von 8, Hacktribe mit BLECH, Flash vom 09.10.)

| Fall | Ergebnis |
|---|---|
| Regler gedreht, EXIT + WRITE | gespeichert an den eigenen Platz, Bildschirm 1, Platz 1 und 2 unverändert |
| WRITE ohne EXIT | Fenster bleibt offen, nichts gespeichert (wie bei Korg) |
| TRIGGER, Part 1 und 6 bearbeitet, EXIT + Pad 1 | Klang von Part 1 zurück, sein Schritt bleibt geändert, Part 6 bleibt bearbeitet, gewählter Part bleibt 1 |
| EXIT + Pad 6 | Part 6 zurück, gewählter Part bleibt 1 |
| SEQUENCER, EXIT + Pad 10 | der gewählte Part zurück, Schritt 10 nicht gesetzt |
| PART MUTE, KEYBOARD, PART ERASE, CHORD, PATTERN SET, Part 1 und 6 bearbeitet, EXIT + Pad 6 | Part 6 zurück, Part 1 bleibt bearbeitet, gewählter Part bleibt 1 (30.10.) |
| STEP JUMP, ebenso | Part 1 (der gewählte) zurück, Part 6 bleibt bearbeitet (30.10.) |
| beim Abspielen EXIT + Pad 3 | Part 3 zurück, spielt weiter, gleiches Pattern |
| EXIT beim Einschalten | Fenster bleibt offen, nichts gespeichert, Pad setzt nichts zurück |

Auf Korgs Original sind `0xC004AB84` und `0xC000985C` Byte für Byte gleich.

## Offen

- Am Gerät nicht geprüft.
- `0xC004AB84` läuft sonst in der CommandTask, hier im UiTask-Takt. Im Emulator ohne Fehler (auch beim Abspielen), eine
  Kollision mit einem gleichzeitigen Laden der CommandTask ist nicht ausgeschlossen.
- "Speichern" heißt das Pattern. Die Globals speichert weiter WRITE im Global-Menü.
