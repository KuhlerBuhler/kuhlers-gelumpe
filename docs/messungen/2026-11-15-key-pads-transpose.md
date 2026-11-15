# KEY PADS: Pads 13 bis 16 transponieren um Oktaven (15.11.)

Stand 15.11.2026, Emulator mit Hacktribe 2.02 (163d1d8d), Korgs rotem 2.02 und Korgs blauem 2.02, jeweils mit BLECH
(release/1.4.6). Anlass: Gerätetest 1.4.6, Punkt 5.3. Pads 13 bis 16 setzten seit
[2026-11-12](2026-11-12-key-pads-oktave.md) nur die Oktave der Tastatur, das können die Takt-Tasten schon. Gewünscht war, dass
die Oktave die gespielte Melodie und die Sequenz verschiebt. Entschieden: Weg A, Verschiebung dort, wo die Firmware den KEY
dazurechnet. Code `tools/patch/script_shortcuts.s` (`kp_tick_octave`, `kp_key`), Adressen `tools/patch/script_hooks.py`
(`KP_KEY_*_AT`, `SITES`), Fälle `tools/emu/shortcut_cases.py` (`case_key_pads`, `case_key_pads_transpose`). Am Gerät
nichts getan.

Marker: **gemessen** heißt im Emulator ausgeführt und gesehen, **hergeleitet** heißt aus dem Code geschlossen, **ungeprüft**
heißt offen, vor allem am Gerät.

## Was "Oktave" in der Firmware ist

| Befund | Marker |
|---|---|
| Der KEY ist Byte 39 des Patterns (0 bis 11), Getter `0xC004A388` (`ldrb r0, [r0, #0x2B]`), blau `0xC0044488` | gemessen |
| Der KEY verschiebt die Sequenz nur bei Parts mit SCALE MODE ON: Wiedergabe = Skalen-Abbildung der gespeicherten Note (`0xC0054494`) + KEY, nur wenn `0xC0048D4C` SCALE MODE meldet. Zwei Parts mit Note 60/62: KEY C spielt 59/61, KEY E 63/65, der Part mit SCALE MODE OFF bleibt | gemessen, Hacktribe |
| Die Oktave der Tastatur (Setter `0xC00818E0`) ändert die Sequenz nicht, nur die Pads im Modus KEYBOARD | gemessen |
| Osc Pitch je Part ist +-63 Cent, der KEY hat keine Oktave, eine globale Transponierung gibt es nicht | hergeleitet aus dem Code |

## Die vier Rechenstellen des KEY

| Stelle (rot/Hacktribe, blau) | Was | Marker |
|---|---|---|
| `0xC005A2B8`, `0xC0050EAC` | Wiedergabe eines Steps: Note + KEY | gemessen |
| `0xC005AE00`, `0xC0051960` | Pad im Modus KEYBOARD: Note + KEY | gemessen |
| `0xC00607A8`, `0xC0057260` | Aufnahme: gespielte Note - KEY (`rsb`) | gemessen |
| `0xC0088784`, `0xC0078968` | Pad zu Note für die Pad-LEDs: - KEY | gemessen |

Die übrigen Aufrufer des Getters sind Anzeige und bleiben. Hinter den beiden Additionen verwirft die Firmware Noten außerhalb
0 bis 127 (`cmp #0x7F; bhi`), eine verschobene Note fällt dort also weg statt umzubrechen. (hergeleitet aus dem Code)

## Der Umbau

Pad 13 bis 16 schreiben -1, 0, +1, +2 in das Byte `KP_OCT` (`MENU_STATE + 0x10D`), den Setter der Takt-Tasten rufen sie nicht
mehr. `menu_arm` nullt den Bereich beim Start, die Verschiebung ist also nach dem Einschalten 0 und wird nicht gespeichert.
Die vier Stellen springen in `kp_key`: der liest den KEY wie der Getter und rechnet, wenn BLECH aktiv und KEY PADS an ist,
`12 * KP_OCT` dazu. Weil alle vier denselben Wert sehen, verschieben sich Wiedergabe, Tastatur, Aufnahme und LEDs gemeinsam.
(hergeleitet aus dem Code, Wirkung unten gemessen)

## Gemessen

| Befund | Marker |
|---|---|
| Nach dem Start Verschiebung 0; KEYBOARD gehalten, Pads 1 bis 16: Pads 1 bis 12 lassen sie bei 0, Pad 13 bis 16 geben -1, 0, +1, +2; die Oktave der Takt-Tasten bleibt 4 | gemessen, Hacktribe, rot, blau |
| Sequenz, Part 1 SCALE MODE ON mit gespeicherter Note 61, Part 2 SCALE MODE OFF mit 63: Part 1 spielt bei Pad 14 60, bei Pad 13 48, bei Pad 16 84; Part 2 bleibt bei 62 | gemessen, Hacktribe, rot, blau |
| Modus KEYBOARD auf einem Part mit SCALE MODE ON: Pad 1 spielt bei +1 eine Oktave höher (60 zu 72), bei +2 zwei | gemessen, Hacktribe, rot, blau |
| Modus KEYBOARD auf einem Part mit SCALE MODE OFF: Pad 1 bleibt bei jeder Verschiebung gleich, wie beim KEY | gemessen, Hacktribe |
| Aufnahme bei +1: gespeichert wird dieselbe Note wie bei 0, die Wiedergabe klingt wie gespielt | gemessen, Hacktribe, rot, blau |
| Die LED des gehaltenen Pads ist bei jeder Verschiebung dieselbe | gemessen, Hacktribe |
| Am Gerät: Klang, Aufnahme, Anzeige | ungeprüft |
