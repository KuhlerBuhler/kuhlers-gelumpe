# Idee 101: Nach dem Resampling auf dem Pad bleiben

Stand: Ursache offen, nichts gebaut. Zurück zu den [Ideen](../ideen.md).

Nach dem Resampling springt die Auswahl auf Pad 1 (oben links). Sie soll auf dem Pad bleiben, auf dem geresampled wurde.

## Warum noch kein Patch

Der Fehler lässt sich im Emulator nicht nachstellen. Eine Aufnahme, auch RESAMPLING, ist dort nicht erreichbar: REC wartet auf Audio vom DSP, und die DSP-Attrappe liefert keins ([Sample-Speicher voll](../messungen/2026-10-14-sample-speicher-voll.md), [Task-Stack](../messungen/2026-10-24-ram-task-stack.md)). Ohne den Moment, in dem die Firmware die Aufnahme abschließt und die Auswahl setzt, gibt es keinen Fall, der vor dem Patch scheitert und danach besteht, und keine gemessene Stelle zum Einhaken.

## Was gelesen wurde (hergeleitet, Hacktribe 2.02)

- Die Texte "Resampling", "Sampling Mode", "Sampling Source" und "Now Sampling!" liegen bei `0xC00A734C` bis `0xC00A738F`. Ihre einzigen Verweise stehen bei `0xC008C2D8`, `0xC008C774`, `0xC008C778`, `0xC008C5FC` und `0xC008C790`.
- Dort sitzt die Oberfläche des SAMPLING-Fensters (Quellenwahl, Anzeige "Now Sampling!"). Die Routine bei `0xC008C2A0` setzt nur den Text für die Quelle. Das Wählen der Auswahl nach dem Abschluss steht nicht in diesem Code.
- Eine Stelle, die nach der Aufnahme den Part oder das Pad zurücksetzt, wurde nicht gefunden.

## Nächste Schritte

1. Den Abschluss der Aufnahme finden: der Weg vom Fenster bis zum Schreiben in den Sample-Speicher (Host-Port-Schreiben mit Kommando `0xAB`, siehe [DSP-Audiopfade](../messungen/2026-10-08-dsp-audiopfade.md)) und von dort zurück zur Pattern-Ansicht.
2. Die DSP-Attrappe so erweitern, dass sie eine Aufnahme meldet (Pegel, Endmeldung), damit REC und RESAMPLING im Emulator bis zum Ende laufen. Erst dann ist ein Fall mit Pad 5 möglich.
3. Im Fall Part und Pad vor und nach dem Resampling lesen, die Schreibstelle der Auswahl suchen und dort einhaken (neuer Code in MORE3, Zustand nach den Regeln in [Speicherbereiche](../speicherbereiche.md)).
