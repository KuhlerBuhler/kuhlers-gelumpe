# Idee 52: Ton im Emulator

Stand: Idee, zurückgestellt; Aufwand geschätzt in Wochen. Zurück zu den [Ideen](../ideen.md).

Den echten DSP-Code im Blackfin-Simulator aus gdb laufen lassen, dazu Modelle für Host-Port, Audioausgang und DMA. Kein DSP-Patch, nur Emulation. Einzelne Rechenfunktionen laufen im Simulator schon ([DSP, erster Blick](../hintergrund/dsp-erster-blick.md)).

## Erster Schritt

Ein Versuch von etwa einem Tag: eine Effekt-Schleife im Simulator laufen lassen und messen, wie viel langsamer als Echtzeit sie ist. Danach entscheiden, ob live oder nur gerendert wird.

## Kandidaten für den Kern

- Der GNU-Simulator aus gdb (der Stand heute).
- Der QEMU-Port für Blackfin von Mike Frysinger (github vapier/qemu). Er übersetzt den Befehlskern des GNU-Simulators nach TCG, also mit Übersetzer statt Interpreter. Systememulation ist laut Autor unzuverlässig; wir bräuchten nur den Prozessor, wie Unicorn beim ARM.

Im Versuch beides messen. Eine GPU hilft beim Emulieren nicht (eine Befehlskette, nicht parallel).
