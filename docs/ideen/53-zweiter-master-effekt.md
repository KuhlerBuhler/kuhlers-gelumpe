# Idee 53: Zweiter Master-Effekt, getrennt vom Touchpad

Stand: offen. Im Emulator ist gemessen, dass die zweite Stufe nicht übertragen wird; ob der DSP einen zweiten Master-Effekt rechnen kann, ist unbekannt. Diese Idee trug früher die Nummer 34 (die Nummer war doppelt vergeben). Zurück zu den [Ideen](../ideen.md).

Hall gibt es nur als MFX. Wer Hall auf den Synths will, hält MFX HOLD auf einer XY-Stelle, und das Touchpad ist für Live-Übergänge (Tape Delay und Co.) belegt. Wunsch: zwei Master-Effekte. SHIFT + MASTER FX lässt die Taste blinken und schaltet, welcher am Touchpad hängt.

## Bedienung und Ton

Die Bedienung ist ARM-Code: die Taste abfangen, den LED-Setter `0xC0028600` aufrufen, die Zuordnung umschalten. Das ist im Emulator baubar und der erste echte Code-Patch für Idee 17.

Der Ton ist die harte Seite: die Firmware schickt von einem Master-Preset nur die Master-Stufe an den DSP ([MFX und DSP](../messungen/2026-10-09-mfx-dsp.md)). Ein zweiter Master braucht also eine ARM- und eine DSP-Änderung.

Ein Teilschritt ohne DSP-Änderung ist Idee 44 (MFX 2, ein schneller Typwechsel statt zweier gleichzeitiger Effekte).
