# KEY PADS: Pads 13 bis 16 setzen die Oktave (12.11.)

Stand 12.11.2026, Emulator mit Hacktribe 2.02 (163d1d8d), Korgs rotem 2.02 und Korgs blauem 2.02, jeweils mit BLECH. Wunsch
(Idee 85): KEYBOARD gehalten + Pad 13 bis 16 wählt die Oktave der Tastatur, Pad 14 ist die nach dem Start. Code
`tools/patch/script_shortcuts.s` (`kp_notes`, `kp_tick_octave`), Adressen `tools/patch/script_hooks.py` (`KP_OCT_SET`,
`KP_OCT_OBJ`), Fälle `tools/emu/shortcut_cases.py` (`case_key_pads`). Am Gerät nichts getan.

Marker: **gemessen** heißt im Emulator ausgeführt und gesehen, **hergeleitet** heißt aus dem Code geschlossen, **ungeprüft** heißt
offen, vor allem am Gerät.

## Der Setter der Firmware

| Befund | Marker |
|---|---|
| Im Modus KEYBOARD rufen die Takt-Tasten (`0x1C` bis `0x1F`) bei `0xC006F9D8` (blau `0xC0062AF4`) über eine Sprungtabelle: Takt 1 Oktave - 1, Takt 2 setzt 3, Takt 3 setzt 4, Takt 4 Oktave + 1 | gemessen |
| Ziel ist `0xC00818E0` (blau `0xC00723EC`): (Objekt, Oktave), klemmt auf 0 bis 7, schreibt Objekt `+0x324` und schickt bei einer Änderung `{0, Oktave}` an die Beobachter des Objekts (`0xC0070688`) | gemessen |
| Das Objekt steht in `0xC06912E0` (blau `0xC056B58C`). Hacktribe hat dieselben Adressen wie rot | gemessen |
| Ein Beobachter (`0xC0044E30`, Nachricht 0) ruft `0xC0044DE8`: schreibt die Oktave in die Tastatur (`+0x1C`), rechnet deren Noten neu und setzt das Wort `+0x18` im Touch-Scale-Objekt (`0xC06911E4`, [Touch Scale 0](2026-10-30-touch-scale-null.md)) | gemessen |

KEY PADS ruft denselben Setter mit 3, 4, 5 und 6. Damit läuft alles wie bei einer Takt-Taste; die Noten gehen erst beim Anschlag an
den Klangprozessor, ein eigener Befehl an den DSP ist nicht nötig. (hergeleitet aus dem Setter und den Beobachtern)

## Gemessen

| Befund | Marker |
|---|---|
| Nach dem Start Oktave 4; KEYBOARD gehalten, Pads 1 bis 16 nacheinander: Pads 1 bis 12 lassen sie bei 4, Pad 13 bis 16 geben 3, 4, 5, 6 | gemessen, rot, Hacktribe, blau |
| Danach Modus KEYBOARD: Pad 1 spielt nach Pad 16 (Oktave 6) MIDI-Note 95, nach KEYBOARD + Pad 14 (Oktave 4) Note 71, 24 auseinander (KEY ist D#) | gemessen, rot |
| Pads 13 bis 16 ändern den KEY nicht, das Wertefenster öffnet sich für sie nicht, KEYBOARD kurz allein schaltet weiter den Modus | gemessen |
| Am Gerät: Oktave, Noten und Anzeige | ungeprüft |
