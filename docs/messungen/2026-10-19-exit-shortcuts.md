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
- Pad-Modus beim LED-Manager `[0xC0345A1C] + 0xB58`: 3 TRIGGER, 4 SEQUENCER, 5 KEYBOARD; `+0xB60` der gewählte Part.

## Der Patch (`tools/patch/script_shortcuts.s`, Laufzeit des BLECH-Menüs)

- Der Eingangsfilter merkt sich EXIT (gedrückt, losgelassen).
- **EXIT + WRITE** auf dem Hauptbildschirm: WRITE geht wie immer an die Firmware, das Fenster geht auf; der nächste Takt
  (40 ms, UiTask) sieht Bildschirm 18 und gibt dem Fenster den zweiten WRITE über den Tasten-Handler `0xC0042BB8`. Wartet
  höchstens 1 s auf das Fenster.
- **EXIT + Pad** auf dem Hauptbildschirm: das Pad geht nicht an die Firmware (klingt nicht, setzt keinen Schritt). Der
  nächste Takt kopiert die Bytes 2 bis 0x2F des Parts (alles außer Last Step und Stumm, die Steps bleiben) aus dem
  gespeicherten Pattern in der Bank ins Pattern im RAM und ruft `0xC004AB84(Pattern, Pattern + 4, 1)`. TRIGGER: der Part des
  Pads; die anderen Modi: der gewählte Part.
- Nicht mit EXIT beim Einschalten, nicht auf der blauen (dort nicht gemessen, `SHORTCUTS 0`). Drei Bytes vor `MENU_STATE`.

## Emulator (`tools/emu/shortcut_cases.py`, 7 von 7, Hacktribe mit BLECH, Flash vom 09.10.)

| Fall | Ergebnis |
|---|---|
| Regler gedreht, EXIT + WRITE | gespeichert an den eigenen Platz, Bildschirm 1, Platz 1 und 2 unverändert |
| WRITE ohne EXIT | Fenster bleibt offen, nichts gespeichert (wie bei Korg) |
| TRIGGER, Part 1 und 6 bearbeitet, EXIT + Pad 1 | Klang von Part 1 zurück, sein Schritt bleibt geändert, Part 6 bleibt bearbeitet, gewählter Part bleibt 1 |
| EXIT + Pad 6 | Part 6 zurück, gewählter Part bleibt 1 |
| SEQUENCER, EXIT + Pad 10 | der gewählte Part zurück, Schritt 10 nicht gesetzt |
| beim Abspielen EXIT + Pad 3 | Part 3 zurück, spielt weiter, gleiches Pattern |
| EXIT beim Einschalten | Fenster bleibt offen, nichts gespeichert, Pad setzt nichts zurück |

Auf Korgs Original sind `0xC004AB84` und `0xC000985C` Byte für Byte gleich.

## Offen

- Am Gerät nicht geprüft.
- `0xC004AB84` läuft sonst in der CommandTask, hier im UiTask-Takt. Im Emulator ohne Fehler (auch beim Abspielen), eine
  Kollision mit einem gleichzeitigen Laden der CommandTask ist nicht ausgeschlossen.
- "Speichern" heißt das Pattern. Die Globals speichert weiter WRITE im Global-Menü.
