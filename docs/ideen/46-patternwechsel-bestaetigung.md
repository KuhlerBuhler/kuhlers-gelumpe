# Idee 46: Patternwechsel erst nach Bestätigung

Stand: gebaut und im Emulator geprüft, am Gerät nicht; Code-Patch. Zurück zu den [Ideen](../ideen.md).

Läuft ein Pattern, startet das am Rad gewählte nicht von selbst am Ende der Sequenz. Man kann das nächste ansehen (die Zeile unten sagt VIEW:); erst MENU (ENTER) auf dem Hauptbildschirm legt es fest (dann NEXT:, und Bank Select und Program Change gehen raus), es startet am nächsten Sequenzende. EXIT nimmt das Blättern oder die Bestätigung zurück. Im Stillstand, in Record, für Pads, MIDI Program Change und Ketten bleibt alles wie in der Firmware. Anlass: live reichte die Zeit bis zum Sequenzende nicht, um von 68 auf 211 zu drehen.

## Stand

- Die Recherche ([Patternwechsel](../hintergrund/patternwechsel.md)) hält den Wechsel nach Bestätigung für machbar und klein: die Firmware merkt sich beim Drehen nur eine Nummer und ein Flag und zeigt das gewählte Pattern schon als „NEXT:nnn“ an.
- Gebaut als Patch `data/patches/pattern-switch.json` (968 Byte Code, 8 Einhängestellen, Patch-Satz BLECH): [Messung](../messungen/2026-10-15-patternwechsel.md) mit allen Fällen (Blättern, Bestätigen, EXIT, STOP, Kette, Pad, MIDI, MFX 2, Stillstand, EXIT beim Einschalten, keine Karte). Er bricht keinen der Start- und Rettungswege und braucht keine Startphasen-Ausnahme.
- Er ist beim Start an (Voreinstellung für den Live-Betrieb), aber nur mit gemounteter Karte und ohne EXIT beim Einschalten; abschalten lässt er sich in der Seite PATTERN CONFIRM in der Liste des Menüs BLECH ([Patcher](../patcher.md), "Schalter, die das Menü ergänzen muss").
- Am Gerät ist nichts geprüft; die Schritte stehen in den [Gerätetests](../geraetetests/live.md).
- Solange ein Pattern angesehen (`VIEW:`) oder bestätigt ist (`NEXT:`), zeigen die Pads (Steps, Mutes) und, nach EDIT, die Info-Texte das nächste Pattern, nicht das laufende ([Messung](../messungen/2026-10-25-pattern-ansicht.md)). Im Emulator geprüft, am Gerät offen.
