# Karte gezogen, TAP blinkt

Zwei Verhalten von TAP Motion im [Emulator](../glossary.md#emulator) gemessen: die Funktionen bleiben an, wenn die Karte gezogen wird,
und die TAP-LED blinkt bei laufender Master-FX-Bewegung.

## Karte gezogen

Patternwechsel, TAP Motion, Notenassistent und Würfeln brauchen eine Karte (`tools/patch/card_gate.py`): auf den Sampler-Builds
zählt das Typ-Byte des [FatFs](../glossary.md#fatfs)-Volumes (`0xC06A010C`) oder der Kartenkontakt, beim Synth der Kartenkontakt
(`0x01E26070`, Bit 1; [später steckende Karte](2026-11-11-orig-und-karte-spaeter.md)). Ohne Karte gilt die Firmware.

Die Prüfung merkt sich eine einmal gesehene Karte: beim ersten Treffer schreibt sie `0x5A` in ein eigenes Wort des
[Patches](../glossary.md#patch) (`STATE + 0x3C`, im RAM, beim Einschalten FF), danach lässt dieses Wort allein durch. Wer die Karte
zieht, behält die Funktionen; ohne Karte seit dem Einschalten bleibt alles wie die Firmware. Die Einstellungen liest das Menü
nur beim Start; sie stehen danach im RAM.

**Gemessen** (`tapmotion:card_pulled_keeps_tap`, [BLECH](../glossary.md#blech) auf einer eigenen
[Hacktribe](../glossary.md#hacktribe)-Datei mit dem Flash-Abbild vom 09.10.). TAP mit Karte schaltet aus `(0, 0)`. Karte
ausgeworfen (`eject_card`, Kontakt hoch), eine Sekunde gewartet: das Typ-Byte stand im Emulator noch auf 24, es wurde von Hand
auf 0 gesetzt, wie FatFs es beim nächsten Zugriff tut. TAP danach: an `(1, 1)`, noch einmal: aus `(0, 0)`, keine Assertion. Die
Prüfung selbst ist in `tools/patch/test_card_gate.py` für beide Builds abgedeckt (ohne Karte nichts geschrieben, Karte gesehen
bleibt an). Nicht am Gerät geprüft.

## TAP blinkt bei laufender Master-FX-Bewegung

Die TAP-LED blinkt, solange die Master-FX-Bewegung an ist (Byte `+0x44` nicht 0), eine Spur eine Master-FX-Geste hält
(Part-Eintrag `0x104 + Spur` gleich 17, siehe [TAP-Motion-Recherche](2026-10-15-tap-motion.md#3-motion-sequence)) und MASTER FX
nicht gehalten ist. Ohne Geste blinkt nichts, denn das Byte steht in jedem neuen Pattern auf 1
([Patch-Messung](2026-10-15-tap-motion-patch.md)). Takt: 12 Ticks zu 40 ms (480 ms); mit Part-Bewegung aus 6 Ticks an, mit
Part-Bewegung an 10 Ticks an (kurze Lücke). Gehaltenes MASTER FX zeigt nur das Master-FX-Byte, ohne Blinken.

**Gemessen** (`tapmotion:mfx_motion_blinks`, Anteil leuchtender Proben in 1,92 s, Wechsel). Neues Pattern ohne Geste, Byte 1:
`(1.0, 0)`. Mit Geste: Part an `(0.83, 8)`, Part aus `(0.5, 8)`, Master-FX aus `(1.0, 0)`, beides aus `(0.0, 0)`, MASTER FX
gehalten `(1.0, 0)`.

**Blaue Electribe** (Korgs 2.02 mit `blech-synth.json`, ohne Flash-Abbild). Beide Fälle mit denselben Werten grün: Karte
gezogen `(0, 0)`, `(1, 1)`, `(0, 0)` (der Kontakt geht mit dem Auswurf hoch), Blinken wie oben. Die Spurtabelle liegt also auch
dort bei `0x104`. Nicht am Gerät geprüft.
