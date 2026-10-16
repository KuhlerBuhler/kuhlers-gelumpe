# Idee 48: Lücke beim Patternwechsel

Stand: Ursache hergeleitet, am Gerät offen. Zurück zu den [Ideen](../ideen.md).

Beim Patternwechsel entsteht eine Stille von etwa 100 ms (gehört). Im Club fällt sie kaum auf, in Aufnahmen deutlich. Gesucht: die Ursache (Laden des Patterns, DSP-Umbau) und ob Vorladen sie schließt.

## Befund

Auf der ARM-Seite gibt es keine Lücke: der MIDI-Takt läuft über den Wechsel ohne Sprung, das Pattern liegt schon im RAM, es gibt keinen Flash-Zugriff beim Wechsel. Vorladen schließt also nichts. Auffällig ist der Verkehr zum DSP: bei jedem Wechsel gehen 17 Mailbox-Frames mit den Part-Parametern hinaus, und immer wenn sich ein Insert- oder Master-Effekttyp ändert, kommt eine Effekt-Neuinitialisierung (insgesamt 21 bis 66 Frames). Das ist der wahrscheinlichste Ursprung der 100 ms, aber nur hergeleitet; ob und wie lange der DSP dabei Ton unterbricht, zeigt nur das Gerät. Die billigste Gegenprobe braucht keinen Code.

Belege und Messreihen: [Patternwechsel](../hintergrund/patternwechsel.md), [DSP, erster Blick](../hintergrund/dsp-erster-blick.md).
