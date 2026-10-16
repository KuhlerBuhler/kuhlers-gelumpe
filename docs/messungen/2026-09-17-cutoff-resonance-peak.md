# Cutoff (Part-Byte 13) und Resonanz (Part-Byte 14)

Gemessen 2026-09-17 am electribe LPF, über den Resonanzgipfel bei Resonanz
auf Maximum (die Filterflanke zu suchen lieferte widersprüchliche Werte).

Cutoff: `f = 654 Hz * 2 ** ((Byte - 64) / 12.09)`, ein Halbton je Schritt.
Über Byte 16 bis 120 höchstens 10 % Abweichung, in der Mitte 1 bis 2 %.
Messpunkte: 16 -> 41 Hz, 48 -> 263 Hz, 64 -> 652 Hz, 84 -> 2106 Hz,
120 -> 14739 Hz.

Resonanz als Überhöhung an der Eckfrequenz: 8 -> +1,9 dB, 64 -> +12,5 dB,
112 -> +24,1 dB. Bei 127 Selbstoszillation (+33,6 dB an der Ecke und
zusätzlich +37,9 dB oberhalb 5 kHz).
