# KEY PADS chromatisch

**Gemessen** im [Emulator](../glossary.md#emulator) mit [Hacktribe](../glossary.md#hacktribe) 2.02 (eigene Datei), Korgs Original 2.02 rot und blau, jeweils
mit dem [BLECH](../glossary.md#blech)-Satz. Fall: `tools/emu/shortcut_cases.py`, Gruppe `case_key_pads` (`--only 6`). **Am Gerät nicht geprüft.** Zu
[KEY PADS fest eingebaut](2026-11-07-key-pads-eingebaut.md).

Die Töne liegen in der Reihenfolge der Pads: Pad 1 C, Pad 2 C#, Pad 3 D bis Pad 12 B. Pad 13 bis 16 setzen den KEY nicht;
sie wirken auf die Oktave und das Transponieren ([Oktave](2026-11-12-key-pads-oktave.md), [Transponieren](2026-11-15-key-pads-transpose.md)). Die Messung unten gilt für Pad 1 bis 12.

## Belegung

| Pad | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 bis 16 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| KEY | C | C# | D | D# | E | F | F# | G | G# | A | A# | B | kein KEY |

Die Tabelle `kp_notes` in `tools/patch/script_shortcuts.s` hält je Pad den KEY plus 1, 0 heißt kein Ton. Pads 13 bis 16 setzen
nichts und öffnen kein Fenster; ihr Anschlag geht trotzdem nicht an die Firmware, solange KEYBOARD gehalten ist, und KEYBOARD
schaltet beim Loslassen nicht in den Modus, wie bei jedem anderen Pad.

## Ergebnisse

| Befund | Marker |
|---|---|
| KEYBOARD gehalten, Pads 1 bis 12 nacheinander: KEY `0` bis `11` | gemessen |
| Wertefenster: nach jedem der Pads 1 bis 12 genau eine Meldung `{0x5A, KEY}` an das Fenster, im Bildspeicher "KEY" und der Name des Tons (C bis B, auch C#, D#, F#, G#, A#) | gemessen |
| KEYBOARD kurz allein, SHIFT + KEYBOARD und KEY PADS OFF verhalten sich wie bei KEY PADS fest eingebaut | gemessen |
| Gleich auf Hacktribe, rot und blau | gemessen |
| Am Gerät | nicht geprüft |
