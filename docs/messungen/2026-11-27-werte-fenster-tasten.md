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

**EXIT** kommt ebenfalls nicht an die Tasten-Funktion: Korgs Tasten-Verteiler (`0xC0070348`) ruft beim Druck die
EXIT-Funktion des obersten Objekts auf (Platz 2 der vtable), bei offenem Fenster also die des Fensters. Beim Werte-Fenster
ist das ein einzelnes `b 0xC0083E30` (rot `0xC0065434` für `0x17`, `0xC0065438` für `0x18`; blau `0xC005B8B0`), das nur
schließt. Folge: im Menü schließt EXIT nach einem Regler nur das Fenster, erst ein zweiter Druck verlässt das Menü
(gemessen: MENU, RIGHT, Regler, EXIT, mit und ohne Fenster verglichen, gestoppt und laufend). Diese Wörter stehen nur in
den vtables der Werte-Fenster; das Ende nach Zeit läuft über ein eigenes `b 0xC0083E30` (rot `0xC0065430`, blau
`0xC005B8AC`). Sonst ruft die EXIT-Funktion nur noch ein Rückruf, den der Konstruktor des Fensters daneben einträgt (rot
`0xC00653B8` und `0xC00653CC`, blau `0xC005B870`), mit beliebigen Werten in `r1` und `r2` (gemessen: `0x7ffe`).

**Patch `value-popup`** schreibt die Tasten-Funktion an derselben Stelle um, gleiche Länge, gleiche Aufrufe: ein Druck
schließt das Fenster und schickt denselben Druck erneut ab, der dann den Weg des Hauptbilds nimmt. Das gilt auch für SHIFT,
so geht SHIFT + Taste; ein Regler mit SHIFT öffnet sein Fenster neu. Die Filtertasten bleiben wie bei Korg. Dazu schreibt
er die Drehgeber-Funktion an derselben Stelle um: das Hauptrad schließt ein Werte-Fenster (`0x17`, rot auch `0x18`) und
geht an das Bild wie ohne Fenster. Das Fenster `0x2a` behält das Hauptrad, andere Fenster bleiben bei Korgs Weg, die
anderen Drehgeber gehen weiter an das Fenster. Die EXIT-Funktion der Werte-Fenster springt jetzt in ihre
Tasten-Funktion: EXIT schließt das Fenster, wird erneut abgeschickt und verlässt das Menü wie ohne Fenster. Der Rückruf
springt dafür direkt in Korgs Schließen, wie es seine EXIT-Funktion vorher tat, sonst käme ein Wert ohne Taste als
Tastendruck an.

Geprüft im Emulator (`tools/emu/value_popup_cases.py`, rot, Hacktribe, blau): jede Taste, SHIFT + Taste, Pads und Hauptrad
enden mit Fenster im selben Zustand wie ohne, auch Hauptrad, EXIT, LEFT und RIGHT in einer Menü-Seite (ohne Patch fällt
dort das Hauptrad durch und EXIT bleibt im Menü). Offen: die Tasten, die die Firmware vor dem Fenster nimmt, und die Pads
wirken, schließen das Fenster aber nicht (dafür müsste der Patch an den Verteiler der Panel-Nachrichten). Hauptrad und
EXIT im Menü sind am Gerät noch ungetestet.

