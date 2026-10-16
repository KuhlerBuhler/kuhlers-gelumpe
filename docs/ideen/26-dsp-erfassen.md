# Idee 26: Den DSP (Blackfin) erfassen

Stand: Werkzeug steht, der DSP-Code ist teilweise gelesen; eine eigene Baustelle. Zurück zu den [Ideen](../ideen.md).

Das DSP-Image steckt in der VSB (`0xC00F9E10`, rund `0x422A0` Byte) und lässt sich extrahieren. Eine echte Emulation wäre ein eigener Blackfin-Emulator, sehr schwer, Unicorn kann es nicht (siehe Idee 52). DSP-Patches sind theoretisch möglich, aber im Emulator nicht verifizierbar. Voraussetzung für Mods der Sound-Engine.

Was bisher steht (Extraktion, Disassembler, einzelne Rechenfunktionen im GNU-Simulator, Effektwechsel, Filter, Risiko eines ersten DSP-Patches): [DSP, erster Blick](../hintergrund/dsp-erster-blick.md).
