# KEY PADS chromatisch

Stand 8. November 2026. **Gemessen** im Emulator mit Hacktribe 2.02 (eigene Datei), Korgs Original 2.02 rot und blau, jeweils
mit dem BLECH-Satz. Fall: `tools/emu/shortcut_cases.py`, Gruppe `case_key_pads` (`--only 6`). **Am Gerät nicht geprüft.** Zu
[KEY PADS fest eingebaut](2026-11-07-key-pads-eingebaut.md) und [Idee 85](../ideen/85-keyboard-tonart.md).

## Frage

Beim Test am Gerät lagen die Töne wie auf einer Klaviatur: untere Reihe C D E F G A B C, obere Reihe die schwarzen Tasten,
Pads 1, 4 und 8 ohne Ton, Pad 9 war C. Gewünscht ist die Reihenfolge der Pads: Pad 1 C, Pad 2 C#, Pad 3 D bis Pad 12 B.

## Belegung

| Pad | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 bis 16 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| KEY | C | C# | D | D# | E | F | F# | G | G# | A | A# | B | nichts |

Die Tabelle `kp_notes` in `tools/patch/script_shortcuts.s` hält je Pad den KEY plus 1, 0 heißt kein Ton. Pads 13 bis 16 setzen
nichts und öffnen kein Fenster; ihr Anschlag geht trotzdem nicht an die Firmware, solange KEYBOARD gehalten ist, und KEYBOARD
schaltet beim Loslassen nicht in den Modus, wie bei jedem anderen Pad. Sonst ist nichts geändert.

## Ergebnisse

| Befund | Marker |
|---|---|
| KEYBOARD gehalten, Pads 1 bis 16 nacheinander: KEY nach Pad 1 bis 12 `0` bis `11`; vor Pad 13 bis 16 steht KEY auf 3 und bleibt 3 | gemessen |
| Wertefenster: nach jedem der Pads 1 bis 12 genau eine Meldung `{0x5A, KEY}` an das Fenster, im Bildspeicher "KEY" und der Name des Tons (C bis B, auch C#, D#, F#, G#, A#); nach Pad 13 bis 16 keine Meldung | gemessen |
| KEYBOARD kurz allein, SHIFT + KEYBOARD und KEY PADS OFF verhalten sich wie am 07.11. gemessen | gemessen |
| Gleich auf Hacktribe, rot und blau | gemessen |
| Am Gerät | nicht geprüft |
