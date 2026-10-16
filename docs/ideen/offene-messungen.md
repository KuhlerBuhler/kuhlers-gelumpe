# Offene Messungen

Stand 2026-10-14. Zurück zu den [Ideen](../ideen.md).

Was als Nächstes am Gerät oder im Emulator gemessen werden sollte, nach Nutzen für den Editor geordnet. Gemessen und deshalb hier gestrichen: Gerätesuche (Byte 10 und 11), Antwortzeiten, größte RAM-Schreibnachricht, Antwort auf einen Pattern-Dump, Byte 7 und 8 einer Leseantwort und die MFX-Menülänge als Instruktion. Die Ergebnisse stehen im [Geräteprotokoll](../messungen/2026-10-08-geraeteprotokoll.md).

1. **Rückweg der Firmware, Rettung.** Hin und zurück über Korgs Update-Modus ist am Gerät geübt ([Rückweg geübt](../messungen/2026-10-10-rueckweg-geuebt.md)). Offen ist die Rettung, wenn die laufende Firmware nicht mehr startet, und ob die Datei unter `KORG/electribe sampler/System/` dafür taugt. Voraussetzung fürs Schreiben von Firmware-Dateien ist weiter der Rückweg, siehe [Firmware-Rückweg](../messungen/2026-10-08-firmware-rueckweg.md).
2. **Offene Pattern-Felder:** Part-Byte 38, Gate 255, Last Step, Touch Scale, Motion Sequences.
3. **Groove-Templates:** 96 oder 128 Plätze, Velocity absolut oder relativ, und ob ein RAM-Schreiben dort wirkt.
4. **Modulationstabelle:** ob ein RAM-Schreiben live wirkt, und die Felder ab `+0x29` ([Modulationstabelle](../messungen/2026-09-14-modulation-table.md)).
5. **FX:** `lfo_reset` 2 und 3 gegen das Resync-Problem, die Bausteinlücken (`mfx 0x30`, `ifx 0x0B` bis `0x0E`, `0x17`), die restlichen Bausteine in Stufe 2, der Decimator mit `0x10` und `0x06` dahinter.

Weitere offene Fragen: [Offene Punkte im Linter](../linter.md#offene-punkte) und der Abschnitt „Offene Messungen“ in [Patcher](../patcher.md). Was an einer einzelnen Idee am Gerät offen ist, steht auf ihrer Seite.
