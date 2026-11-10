# 112. Aufnahme läuft über eine Kette in einer Sync Group weiter

Wunsch vom 10.11.: eine Melodie über mehrere Patterns aufnehmen. Heute geht eine Aufnahme nur in einem Pattern; für das
nächste Pattern einer Sync Group muss man wechseln und neu aufnehmen. Gewünscht: läuft eine Aufnahme und das Pattern ist
gekettet (CHAIN TO) **und** in einer Sync Group, wechselt es am Ende wie beim Abspielen ins nächste Pattern, und die
Aufnahme läuft dort weiter. Das vorige Pattern soll sich das Aufgenommene merken, ohne dass man beim Wechsel WRITE drückt.

Stand 2026-11-10: **aufgeschrieben, nichts gebaut, nichts gemessen.** Marker: **gemessen**, **hergeleitet**, **ungeprüft**.
Zurück zu den [Ideen](../ideen.md).

## Wann es gilt

- Gekettet und in einer Sync Group (die Gruppe des nächsten Patterns gleich der des laufenden, nicht OFF): die Aufnahme
  wechselt mit und läuft weiter.
- Nur gekettet, ohne Gruppe: wie bisher, die Aufnahme bleibt im Pattern und wechselt nicht zum geketteten.
- Nur in einer Gruppe, ohne Kette: wie bisher.

## Was es schon gibt

- Alle 250 Patterns liegen ab dem Start im RAM, `0xC08B2940 + n * 0x4000`; ein Wechsel kopiert den Platz ins
  Live-Pattern und liest nie aus dem Flash (**gemessen**, [Patternwechsel](../hintergrund/patternwechsel.md)).
- Die Sync Group gleicht beim Wechsel die geänderten Werte ins neue Pattern ab, Puffer `SG_BUF`, nur im RAM (**gemessen**,
  [Sync Groups](../messungen/2026-10-19-sync-groups.md)).
- "Ungespeichert" (`pc_dirty`) vergleicht das Live-Pattern mit seinem Bank-Platz im RAM
  ([Messung](../messungen/2026-10-25-sync-ungespeichert.md)).

## Vorschlag

- Beim Wechsel während der Aufnahme das Live-Pattern zurück in seinen Bank-Platz im RAM kopieren (16 KiB), dann das nächste
  laden wie immer. Kein Flash-Zugriff, kein WRITE. (hergeleitet)
- Das braucht keinen neuen Speicher: der Bank-Platz ist schon da. Der RAM, den der Sample-Swap will, wird nicht angetastet.
  (hergeleitet; prüfen, dass der Sample-Swap die Pattern-Bank im RAM nicht mitbenutzt)
- Eine Merkliste der Plätze, die im RAM geändert, aber nicht im Flash sind: 250 Bit, 32 Byte, im eigenen Puffer.
  (hergeleitet)

## Offen

- **Verlust ohne Warnung:** nach dem Zurückkopieren gleicht der Platz dem Live-Stand, `pc_dirty` sähe das vorige Pattern
  als gespeichert, obwohl es nur im RAM ist. Ausschalten heißt dann weg. Die Merkliste muss in `pc_dirty` und in die
  Rückfrage vor dem Wechsel (Idee 57) mit hinein.
- **Wie es ins Flash kommt:** WRITE am Ende speichert alle markierten Plätze, oder eine Frage beim Stoppen der Aufnahme,
  oder AUTO SAVE. Noch nicht entschieden.
- **Ob die Firmware die Aufnahme beim Wechsel abbricht** und an welcher Stelle (Wechsel am Sequenzende, CHAIN TO, Zustand
  REC). Erster Schritt: im Emulator messen, mit Kette plus Gruppe, nur Kette, nur Gruppe. (ungeprüft)
- Motion-Aufnahme und Step-Aufnahme getrennt betrachten, die Motion liegt in einem eigenen Bereich des Patterns.
- Rot und blau: Sync Groups gibt es auf beiden, die Adressen der blauen Firmware sind andere.
