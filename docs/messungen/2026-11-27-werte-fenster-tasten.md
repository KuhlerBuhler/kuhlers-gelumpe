# Werte-Fenster nach einem Regler: Tasten gehen verloren

Ein Dreh an einem Regler oder Drehgeber zeigt den neuen Wert in einem Fenster über dem Hauptbild (Fenster `0x17`, beim
Sample-Drehgeber `0x18`). Es bleibt im Emulator etwa 1,7 s, am Gerät etwa 5 s stehen; das passt zum gemessenen Faktor 3,45
zwischen Gerät und Emulator (hergeleitet).

**Korgs Firmware** (rot, Hacktribe und blau 2.02 gleich): die Tasten-Funktion des Fensters (rot `0xC006543C` für `0x17`,
`0xC0065498` für `0x18`; blau nur eine, `0xC005B8B4`) ignoriert jeden Druck. Erst beim Loslassen schließt sie das Fenster
(`0xC0083E30`, setzt das Merkmal "kein Fenster" sofort) und schickt das Loslassen erneut ab (`0xC00839F0`). LPF, HPF und
BPF gehen beim Loslassen an den Filter und lassen das Fenster stehen. Folge: der Druck ist verloren. Im Emulator verlieren
so MENU und WRITE ihren ersten Druck, und SHIFT + Taste (etwa SHIFT + LEFT, SHIFT + PART ERASE) wirkt nur wie die Taste
allein, weil das Hauptbild das SHIFT nie sieht (gemessen: jede Taste `0x00` bis `0x23`, SHIFT + Taste, Pads, Hauptrad,
gestoppt und laufend, mit und ohne Fenster verglichen). Die Part-Tasten, TRIGGER, SEQUENCER, KEYBOARD, CHORD, PATTERN SET,
die Pads und das Hauptrad nimmt die Firmware schon vor dem Fenster: sie wirken, das Fenster bleibt bis zu seinem Ende stehen.

**Patch `value-popup`** schreibt die Tasten-Funktion an derselben Stelle um, gleiche Länge, gleiche Aufrufe: ein Druck
schließt das Fenster und schickt denselben Druck erneut ab, der dann den Weg des Hauptbilds nimmt. Das gilt auch für SHIFT,
so geht SHIFT + Taste; ein Regler mit SHIFT öffnet sein Fenster neu. Die Filtertasten bleiben wie bei Korg.

Geprüft im Emulator (`tools/emu/value_popup_cases.py`, rot, Hacktribe, blau): jede Taste, SHIFT + Taste, Pads und Hauptrad
enden mit Fenster im selben Zustand wie ohne. Offen: dass auch die Tasten, die die Firmware vor dem Fenster nimmt, und die
Pads das Fenster schließen (dafür müsste der Patch an den Verteiler der Panel-Nachrichten); am Gerät ungetestet.

