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
die Pads nimmt die Firmware schon vor dem Fenster: sie wirken, das Fenster bleibt bis zu seinem Ende stehen.

**Hauptrad**: es geht nicht an die Tasten-Funktion des Fensters, sondern an die Drehgeber-Funktion des Bildschirm-Verwalters
(rot `0xC006EB90`, blau `0xC0062030`; `r1` = 0 das Hauptrad). Bei offenem Fenster gibt Korgs Funktion das Hauptrad nur dem
Hauptbild (das Fenster bleibt stehen) oder dem Fenster `0x2a`; auf jedem anderen Bild, also in jedem Menü, geht der Dreh
verloren (gemessen: MENU, RIGHT, Regler, dann Hauptrad hoch und runter, mit und ohne Fenster verglichen; rot, Hacktribe mit
BLECHTRIBE 1.4.9 und blau gleich). Am Gerät: im Menü musste man warten, bis das Fenster weg war. Ohne Fenster ruft Korgs
Funktion bei jedem Dreh das Schließen auf und gibt den Dreh dann dem Bild.

**Patch `value-popup`** schreibt die Tasten-Funktion an derselben Stelle um, gleiche Länge, gleiche Aufrufe: ein Druck
schließt das Fenster und schickt denselben Druck erneut ab, der dann den Weg des Hauptbilds nimmt. Das gilt auch für SHIFT,
so geht SHIFT + Taste; ein Regler mit SHIFT öffnet sein Fenster neu. Die Filtertasten bleiben wie bei Korg. Dazu schreibt
er die Drehgeber-Funktion an derselben Stelle um: das Hauptrad schließt ein Werte-Fenster (`0x17`, rot auch `0x18`) und
geht an das Bild wie ohne Fenster. Das Fenster `0x2a` behält das Hauptrad, andere Fenster bleiben bei Korgs Weg, die
anderen Drehgeber gehen weiter an das Fenster.

Geprüft im Emulator (`tools/emu/value_popup_cases.py`, rot, Hacktribe, blau): jede Taste, SHIFT + Taste, Pads und Hauptrad
enden mit Fenster im selben Zustand wie ohne, auch Hauptrad, LEFT und RIGHT in einer Menü-Seite (ohne Patch fällt dort
das Hauptrad durch). Offen: EXIT schließt im Menü bei offenem Fenster nur das Fenster und verlässt das Menü nicht (Korgs
Tasten-Verteiler ruft das Schließen des Fensters selbst, `0xC0070348`). Offen auch, dass die Tasten, die die Firmware vor dem Fenster nimmt, und
die Pads das Fenster schließen (dafür müsste der Patch an den Verteiler der Panel-Nachrichten). Das Hauptrad im Menü ist am Gerät noch ungetestet.

