# Karte gezogen, TAP blinkt (18.10.)

Zwei Rückmeldungen vom Gerät (Pascal, 18.10.):

1. TAP Motion war an, die Karte wurde gezogen, danach war TAP Motion aus.
2. Läuft die Master-FX-Bewegung, sieht man das nicht, ohne MASTER FX zu halten.

## Karte gezogen

**Ursache (Code gelesen).** Patternwechsel, TAP Motion, Notenassistent und Würfeln fragten bei jedem Aufruf die Karte
live ab (`tools/patch/card_gate.py`): beim Sampler das Typ-Byte des FatFs-Volumes (`0xC06A010C`), beim Synth den
Kartenkontakt (`0x01E26070`, Bit 1). Ohne gemountete Karte galt die Firmware, also war die Funktion aus, sobald die
Karte fehlte.

**Neu.** Die Prüfung merkt sich eine einmal gesehene Karte: beim ersten Treffer schreibt sie `0x5A` in ein eigenes Wort
des Patches (`STATE + 0x3C`, im RAM, beim Einschalten FF), danach lässt dieses Wort allein durch. Ohne Karte seit dem
Einschalten bleibt alles wie die Firmware. Die Einstellungen liest das Menü ohnehin nur beim Start; sie stehen danach im
RAM und gehen mit der Karte nicht verloren.

**Gemessen (Emulator, `tapmotion:card_pulled_keeps_tap`, BLECH auf Pascals Hacktribe-Datei mit dem Flash-Abbild vom
09.10.).** TAP mit Karte schaltet aus `(0, 0)`. Karte ausgeworfen (`eject_card`, Kontakt hoch), eine Sekunde gewartet:
das Typ-Byte stand im Emulator noch auf 24, es wurde von Hand auf 0 gesetzt, wie FatFs es beim nächsten Zugriff tut.
TAP danach: an `(1, 1)`, TAP noch einmal: aus `(0, 0)`, keine Assertion. Die Prüfung selbst ist in
`tools/patch/test_card_gate.py` für beide Builds abgedeckt (ohne Karte nichts geschrieben, Karte gesehen bleibt an).

Nicht am Gerät geprüft.

## TAP blinkt bei laufender Master-FX-Bewegung

**Neu.** Die TAP-LED blinkt, solange die Master-FX-Bewegung an ist (Byte `+0x44` nicht 0), eine Spur eine
Master-FX-Geste hält (Part-Eintrag `0x104 + Spur` gleich 17, siehe
[TAP-Motion-Recherche](2026-10-15-tap-motion.md#3-motion-sequence)) und MASTER FX nicht gehalten ist. Ohne Geste blinkt
nichts, denn das Byte steht in jedem neuen Pattern auf 1 ([Patch-Messung](2026-10-15-tap-motion-patch.md)). Takt: 12
Ticks zu 40 ms (480 ms); mit Part-Bewegung aus 6 Ticks an, mit Part-Bewegung an 10 Ticks an (kurze Lücke). Gehaltenes
MASTER FX zeigt wie bisher nur das Master-FX-Byte, ohne Blinken.

**Gemessen (Emulator, `tapmotion:mfx_motion_blinks`, Anteil leuchtender Proben in 1,92 s, Wechsel).** Neues Pattern
ohne Geste, Byte 1: `(1.0, 0)`. Mit Geste: Part an `(0.83, 8)`, Part aus `(0.5, 8)`, Master-FX aus `(1.0, 0)`, beides
aus `(0.0, 0)`, MASTER FX gehalten `(1.0, 0)`.

**Blaue Electribe (Emulator, Korgs 2.02 mit `blech-synth.json`, ohne Flash-Abbild).** Beide Fälle mit denselben Werten
grün: Karte gezogen `(0, 0)`, `(1, 1)`, `(0, 0)` (der Kontakt geht mit dem Auswurf hoch), Blinken wie oben. Die
Spurtabelle liegt also auch dort bei `0x104`. Nicht am Gerät geprüft.
