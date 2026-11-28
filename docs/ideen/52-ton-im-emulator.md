# Idee 52: Ton im Emulator

Status: der Emulator führt den echten DSP-Code aus, aber ohne Ton. Zurück zu den [Ideen](../ideen.md).

Ziel: den echten [DSP](../glossary.md#dsp)-Code (Blackfin) im Emulator rechnen lassen und das Ergebnis hören. Kein DSP-Patch,
nur Emulation.

## Was steht

- Der Blackfin-Worker, den `tools/emu` an den ARM-Emulator koppelt, rechnet die Befehle mit einem QEMU-Port und behält
  Geräte, Zeit und Protokoll aus dem GNU-Simulator im selben Prozess. Er rechnet bit-gleich mit dem GNU-Simulator
  (gemessen) und ist im [Emulator](../emulator.md) der Standard; GNU bleibt Referenz und Rückfall
  ([QEMU als DSP-Kern](../messungen/2026-11-16-qemu-dsp-kern.md), QEMU gegen GNU-Simulator).
- Tempo gegen Echtzeit (gemessen, Tempo): der Worker allein spielt eine
  Hacktribe-Aufnahme von 14,84 s in 98,9 s ab, 6,7-mal langsamer als Echtzeit (GNU-Simulator 62,9-mal). Live ist das
  nicht zu halten, Klang gäbe es nur offline gerendert.
- Kosten je Sample (gemessen im Simulator, synthetischer Kontext): Insert-Effekte 129 bis 206 Takte, Master-Effekte 374
  bis 444. Ein ganzer Patch mit 16 Parts und Master liegt hergeleitet bei 10 000 bis 15 000 Takten je Sample, also nahe
  am Budget des DSP.

## Fehler im GNU-Simulator auf arm64

Das Makro `SIGNEXTEND` in `sim/bfin/bfin-sim.c` (gdb) schiebt einen 32-Bit-Wert um `64 - n` Bit. Auf x86 geht das zufällig
gut, clang auf arm64 faltet es weg: ein Testprogramm `R1 = 7 (X); [P1] = R1;` mit `exit([P1])` gab 0 statt 7 zurück. Der
QEMU-Port hat dasselbe Makro. Beide sind korrigiert: der GNU-Simulator beim Bau durch `tools/dsp/build_blackfin.py`, der
QEMU-Port durch `tools/dsp/qemu-bfin.patch` (gemessen: nach der Korrektur 7).

## Was fehlt

- Die Ausgangswörter der seriellen DSP-Schnittstelle (SPORT) je Frame als WAV schreiben.
- Geprüfte Sample-Wiedergabe: die Stimmen lesen Samples aus dem SDRAM des DSP, die der ARM über den
  [Host-Port](../glossary.md#host-port) hinschreibt. Wann und wie viel beim Start oder beim Patternwechsel
  hinüberkommt, ist offen.
- Ein Modell für DMA und die Taktung zwischen ARM und DSP, soweit ein hörbares Ergebnis davon abhängt.

Aufwand: ohne Messung nur Schätzung (**geschätzt**: einige Wochen bis zu einer offline gerenderten WAV).
Vorarbeit: [DSP, erster Blick](../hintergrund/dsp-erster-blick.md), [DSP im Simulator](../messungen/2026-11-12-dsp-im-simulator.md).
