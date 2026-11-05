# Plugin API 17: alle Seiten von CUSTOMIZATION und FEATURES als Blätter

Stand 5. November 2026. **Gemessen** im Emulator mit Hacktribe 2.02 (eigene Datei), Korgs Original 2.02 rot und blau,
jeweils mit dem BLECH-Satz. Fälle: `tools/emu/objects_cases.py` (läuft als Gruppe von `remote_cases`). **Am Gerät
nicht geprüft.**

## Frage

Welche Seiten des Menüs BLECH ein Plugin setzen kann, und ob die Seite danach den neuen Wert zeigt, ohne dass jemand am
Rad dreht.

## Ergebnis

Je Seite ein Blatt unter `korg.menu.blech.` (Liste in [Plugins](../plugins.md), Abschnitt "Die Electribe als Objektbaum").
Ein Plugin setzt jedes Blatt, liest es zurück, und die Seite zeigt danach den Wert (Fälle `objects:page_*`, auf der blauen
ohne STEREO 1 PAD, das dort kein Patch hat). Die Farbseiten zeigen Farbton, Sättigung und Helligkeit des gespeicherten
Rot, Grün, Blau; der Fall rechnet sie wie `look_hsv_get`. PATTERN CONFIRM, TAP MOTION und NOTE ASSIST schreiben zusätzlich
das Wort, das ihr Patch liest (`objects:patch_words_follow`). PAD COLOR und SELECT COLOR sind nie gleich: ein Schreiben, das
sie gleich machte, vertauscht sie (`objects:pad_colors_swap`).

## Nur im RAM, bis WRITE

Die Blätter ändern den Stand im RAM und rufen die Anwendefunktion der Seite. Auf die Karte kommt er mit WRITE im Menü oder mit
`korg.menu.blech.write()`. Der Aufruf setzt nur eine Anfrage. Der Rahmenhaken schreibt die Einstellungsdatei, sobald der
Hauptbildschirm oder BLECH offen ist und seit dem letzten Schreiben 50 Rahmen (2 Sekunden) vergangen sind, wie der
Speicher der Plugins. Nach einem Neustart zeigen alle Seiten den geschriebenen Wert (`objects:write_saved`,
`objects:write_then_restart`). SET INIT PATTERN liegt in den Global-Einstellungen der Firmware und folgt deren Speichern beim
Ausschalten.

## Nicht als Blatt

SPLASH IMPORT, DRAW und RESET und die Exporte sind Aktionen mit Dateien, PLUGIN RUNTIME würde dem Gerät beim nächsten Start
die Plugins nehmen, SYNC GROUP ist ein Wert des Patterns.
