# KEY PADS fest eingebaut

Nur [Emulator](../glossary.md#emulator) ([Hacktribe](../glossary.md#hacktribe) 2.02, Korgs Original 2.02 rot und blau), kein Gerät. Die Funktion ist im
[BLECH](../glossary.md#blech)-Satz eingebaut (kein Plugin mehr). Die Belegung der Pads steht in der
[chromatischen Messung](2026-11-08-key-pads-chromatisch.md), die Oktaven und das Transponieren auf Pad 13 bis 16 in
[Oktave](2026-11-12-key-pads-oktave.md) und [Transponieren](2026-11-15-key-pads-transpose.md); der Weg vom Pad zum KEY ist unverändert.

## Was es tut

KEYBOARD gehalten auf dem Hauptbildschirm, ein Pad gedrückt: der KEY des Patterns springt auf den Ton des Pads. Das Wertefenster der Firmware zeigt "KEY" und den Ton, wie beim Drehen eines Werts.
KEYBOARD kurz allein geht beim Loslassen an die Firmware und schaltet wie immer den Modus. SHIFT + KEYBOARD und alles bei
offener App, im Menü oder auf anderen Bildschirmen bleibt bei der Firmware. BLECH > FEATURES > KEY PADS (letzte Seite)
schaltet es aus, WRITE behält das in Bit 4 von Byte 5 der Einstellungsdatei. Vor dem Scharfschalten des Menüs (EXIT beim
Einschalten) liest `MENU_STATE` überall FF, der Schalter würde als ON gelesen und jeden Pad-Druck schlucken; darum prüft
`kp_input` zuerst `M_ON` (`tools/patch/script_shortcuts.s`).

## Wie es gebaut ist

| Teil | Wo | Marker |
|---|---|---|
| Eingang: KEYBOARD (Taste 23) und die Pads im Eingangsfilter `shortcut_input`, vor der Firmware; ein Pad, dessen Anschlag genommen wurde, nimmt auch sein Loslassen (Maske `KP_PADS`), Druckwerte dazwischen ebenso | `tools/patch/script_shortcuts.s:kp_input` | gemessen (Emulator) |
| Setzen: im Bildtakt (`shortcut_tick`), `script_seq_set_pattern_value_glue(4, Ton)`, derselbe Setter wie die Seite KEY im Pattern-Menü | `kp_tick` | gemessen (Emulator) |
| Kurzer Druck: `script_press_key_glue(23)` beim Loslassen ohne Pad, markiert (0xB7), läuft am Filter vorbei | `kp_tick` | gemessen (Emulator) |
| Fenster: Nachricht `{Code 0x5A, Wert}` an `0xC0070688` (Beobachter = Wertefenster + 4); das Fenster merkt Code und Wert bei +0x318 und +0x31C | `kp_tick` | gemessen (Emulator) |
| Titel, Wert, Markierung: drei Haken in der Zeichenfunktion des Fensters. Bei Code 0x5A liefern sie "KEY", den Tonnamen (C bis B) und 0, sonst springen sie in die Funktion der Firmware | `kp_title_hook`, `kp_value_hook`, `kp_check_hook`, `script_hooks.py:KEY_PADS_SAMPLER` / `KEY_PADS_SYNTH` | gemessen (Emulator) |

Adressen (Sampler; die blaue in Klammern):

| Was | Adresse |
|---|---|
| Zeiger auf das Wertefenster | `0xC03487EC` (`0xC0348500`) |
| Haken Titel, gerufene Funktion | `0xC008A1C8` -> `0xC0078744` (`0xC0079AD8` -> `0xC006B404`) |
| Haken Wert, gerufene Funktion | `0xC008A1F4` -> `0xC0078E2C` (`0xC0079B04` -> `0xC006B864`) |
| Haken Markierung, gerufene Funktion | `0xC008A244` -> `0xC00783EC` (`0xC0079B5C` -> `0xC006B454`) |

Ob die Firmware den Code 0x5A irgendwo selbst schickt, ist nicht geprüft (offen); die Haken antworten nur, solange
er im Fenster steht. Der Wert-Haken löscht das Flag +0x320 (geändert), damit das
Fenster den Wert nicht als ungespeichert markiert.

## Prüfung

`tools/emu/shortcut_cases.py` (Gruppe `case_key_pads`) und `tools/emu/menu_cases.py` (`key_pads_menu_cases`), je
Hacktribe, rot und blau:

| Fall | Ergebnis | Marker |
|---|---|---|
| KEYBOARD gehalten, ein Pad nach dem anderen: KEY springt auf den Ton des Pads, KEYBOARD geht nicht an die Firmware | wie erwartet | gemessen (Emulator) |
| Wertefenster nach einem Pad mit Ton: "KEY" und der Name des Tons im Bildspeicher (auch "C#", das Zeichen # gibt es in der großen Schrift) | wie erwartet | gemessen (Emulator) |
| KEYBOARD kurz allein: geht markiert als Druck und Loslassen durch, die Firmware schaltet in KEYBOARD (Pad-Modus 5) | wie erwartet | gemessen (Emulator) |
| SHIFT + KEYBOARD + Pad und KEY PADS OFF + KEYBOARD + Pad 13: KEY bleibt 0, die Firmware wählt still Part 13 | wie erwartet | gemessen (Emulator) |
| Seite KEY PADS: ON ohne Datei, das Rad schaltet sofort, WRITE schreibt Bit 4, der nächste Start liest OFF und ON | wie erwartet | gemessen (Emulator) |
| Am Gerät | nicht geprüft | offen |

## Grenzen

- Korgs blaue 2.02 zeichnet ihren Hauptbildschirm etwa alle 2,4 s ganz neu. Fällt das in das Bild direkt nach der Anfrage
  des Wertefensters, fällt das Fenster weg, der Wert ist trotzdem gesetzt (gemessen im Emulator).
  Auf einer blauen kann das KEY-Fenster daher selten einen Pad-Druck auslassen. `shortcut_cases.py` drückt das Pad dann noch
  einmal;
- Ein BLECH vor dieser Version lehnt eine Einstellungsdatei mit Bit 4 in Byte 5 ab und startet mit den Vorgaben, wie bei
  den früheren Bits (hergeleitet aus `menu_load`).
