# Pattern senden: Glide geht verloren

Gemessen 2026-09-22. Ein ganzer Pattern-Puffer per SysEx `0x40` geschrieben,
direkt zurückgelesen und verglichen: Name, Tempo, Länge, MFX-Typ, Mute,
Cutoff, Resonanz, Hüllkurve, Amp Level, IFX, Modulation und alle Steps kamen
an. Nur Part-Byte 37 (Glide) stand danach auf 0, auch bei Wiederholung und
mit bis zu 2 s Wartezeit. CC 81 auf dem Kanal des Parts setzt dasselbe Byte
und es bleibt stehen.
