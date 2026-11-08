# KEY PADS fest eingebaut

Stand 07.11.2026, nur Emulator (Hacktribe 2.02, Korgs Original 2.02 rot und blau), kein Gerät. Zu
[Idee 85](../ideen/85-keyboard-tonart.md). Vorher gab es das als Plugin Key Pads im Katalog (API 15,
[Messung](2026-11-03-plugin-api15.md)); das Plugin ist aus dem Katalog genommen. Die Belegung der Pads unten ist der Stand
vom 07.11.; seit dem 08.11. liegen die Töne chromatisch auf den Pads ([Messung](2026-11-08-key-pads-chromatisch.md)).

## Was es tut

KEYBOARD gehalten auf dem Hauptbildschirm, ein Pad gedrückt: der KEY des Patterns springt auf den Ton des Pads. Untere
Reihe (Pads 9 bis 16) C D E F G A B C, obere Reihe die schwarzen Tasten darüber (Pads 2, 3, 5, 6, 7 = C#, D#, F#, G#, A#),
Pads 1, 4 und 8 tun nichts. Das Wertefenster der Firmware zeigt "KEY" und den Ton, wie beim Drehen eines Werts.
KEYBOARD kurz allein geht beim Loslassen an die Firmware und schaltet wie immer den Modus. SHIFT + KEYBOARD und alles bei
offener App, im Menü oder auf anderen Bildschirmen bleibt bei der Firmware. BLECH > FEATURES > KEY PADS (letzte Seite)
schaltet es aus, WRITE behält das in Bit 4 von Byte 5 der Einstellungsdatei.

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
| KEYBOARD gehalten, Pads 1 bis 16 nacheinander: KEY nach jedem Pad `[0,1,3,3,6,8,10,10,0,2,4,5,7,9,11,0]`, KEYBOARD geht nicht an die Firmware | wie erwartet | gemessen (Emulator) |
| Wertefenster nach einem Pad mit Ton: "KEY" und der Name des Tons im Bildspeicher (auch "C#", das Zeichen # gibt es in der großen Schrift) | wie erwartet | gemessen (Emulator) |
| KEYBOARD kurz allein: geht markiert als Druck und Loslassen durch, die Firmware schaltet in KEYBOARD (Pad-Modus 5) | wie erwartet | gemessen (Emulator) |
| SHIFT + KEYBOARD + Pad und KEY PADS OFF + KEYBOARD + Pad 13: KEY bleibt 0, die Firmware wählt still Part 13 | wie erwartet | gemessen (Emulator) |
| Seite KEY PADS: ON ohne Datei, das Rad schaltet sofort, WRITE schreibt Bit 4, der nächste Start liest OFF und ON | wie erwartet | gemessen (Emulator) |
| Am Gerät | nicht geprüft | offen |

## Grenzen

- Ein BLECH vor dieser Version lehnt eine Einstellungsdatei mit Bit 4 in Byte 5 ab und startet mit den Vorgaben, wie bei
  den früheren Bits (hergeleitet aus `menu_load`).
- Im Objektbaum der Plugin-API (`korg.object`) gibt es noch keinen Eintrag für KEY PADS; dafür bräuchte es eine neue
  API-Version.
