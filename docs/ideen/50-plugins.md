# Idee 50: Plugins für eigene Features

Stand: gebaut und im Emulator geprüft, am Gerät nichts davon getestet. Zurück zu den [Ideen](../ideen.md).

Wer will, schreibt eigene Plugins, eine Teilmenge von JavaScript. Der Editor übersetzt sie in Bytecode, den eine kleine VM in der Firmware ausführt; geladen werden sie über die SD-Karte. Ereignisse der Electribe (`ready`, `buttonPress` und weitere) rufen eigenen Code und springen zurück. `ready` läuft nach den Rettungswegen, also auch für Startbild und Menüeinträge. Variablen liegen im RAM (Zähler, „Korg Klicker“). Ein Fehler im Plugin zeigt eine Meldung am Gerät, statt die Electribe abstürzen zu lassen. Vor dem Einspielen läuft jede Zeile im Emulator.

Ziel: Zugriff auf alles, was die Electribe zeigt und schaltet (Tasten-LEDs an und aus sowie rot, blau und lila, das Display auch im Stromsparmodus, die unteren RGB-LEDs, das Display-Licht). Snake komplett als Plugin ist das erste Beispiel.

Das ist der Hauptfokus des Projekts, nachdem der Emulator steht.

## Stand

- Sprache, Ereignisse, Funktionen, Grenzen und Dateiformat: [Plugins](../plugins.md).
- Gebaut sind Compiler, Prüfer und eine Referenz-VM in JavaScript (`src/script/`) sowie die ARM-VM mit Eingangsfilter, Rahmenhaken, `korg.led`, `korg.display`, `korg.store`, Kartenlader und dem Menü BLECH. Im Editor gibt es die Seite Plugins. Im Quelltext heißt das Ganze noch `script`.
- Snake läuft als Plugin in der Firmware im Emulator ([Snake](../messungen/2026-10-14-skript-snake.md)); Klicker und Hörtest am Gerät sind offen.
- Hintergrund und Entscheidungen zur Laufzeit: [Plugin-Laufzeit](../hintergrund/skript-laufzeit.md).
