# Sample-Swap: Zusammenführung der Sicherheitskorrekturen

## Hergeleitet: Stand und Konfliktauflösung

Die Änderungen aus [PR 309](https://github.com/KuhlerBuhler/kuhlers-gelumpe/pull/309)
sind in den Sample-Swap-Zweig übernommen. Der vorherige Arbeitsstand mit
Namenskatalog, Schutz der physischen Sample-Zeilen und RAM-Diagnosen ist
zuvor gesichert. Die Zusammenführung umfasst auch den im PR enthaltenen
Develop-Abgleich.

Zehn Dateien haben textuelle Konflikte. Die spätere Namens- und
Schutzlogik bleibt erhalten. Die wesentlichen Export-, Journal- und
Gate-Korrekturen aus dem PR sind darin bereits enthalten. Zwei zusätzliche
automatische Einfügungen werden entfernt:

- Das Auffrischen der Part-Bindungen bestätigt keine neue Dateiversion.
  Ein zusätzlicher Aufruf von `mark_clean` in `refresh_ready_parts` wäre
  damit unvereinbar.
- Die Ausgangsversion einer Zeile wird je erfolgreich abgeschlossenem
  Parser-Aufruf mit passender Schutzrevision registriert. Ein nachträglicher
  Gesamtdurchlauf über `finish_pins` ersetzt diesen Nachweis nicht.

Die fünf gekoppelten Module für Swap, native DSP-Transaktionen, Aufnahme,
Einzelexport und Transport bleiben bytegleich zum gesicherten Stand.
Ebenso bleibt die erzeugte Sample-Swap-Datei mit 131 Haken erhalten.
Die Skript-Runtime wird für Stock, Hacktribe und Synth neu gebaut.

Die neu hinzugekommene Sidecar-Prüfung erkennt zunächst nur doppelt
zitierte Python-Pfade. Sie wird für einfache und gemischte, korrekt
geschlossene Literale erweitert. Unbekannte Ausdrücke bleiben abgewiesen;
kein Modul wird von der Pfadprüfung ausgenommen. Der gezielte Test zeigt
zuerst den Fehler und besteht nach der Korrektur mit zwei Prüfungen.

## Gemessen: Prüfungen des kombinierten Stands

| Prüfung | Ergebnis |
|---|---|
| `GELUMPE_JOBS=1 npm test` | 1.393 bestanden, 161 übersprungen, kein Fehler |
| `npm run test:e2e`, einschließlich ausdrücklich aktivierter nativer Stock-Firmware | 288 bestanden, keine Auslassung, kein Fehler |
| Startprüfung mit unveränderten Ausgangsdateien, Stock, Hacktribe und Synth | je 15 Startfälle und sechs statische Prüfungen bestanden |
| Native DSP-Wartepfade auf Stock und unveränderter Hacktribe-Basis | beide Läufe bestanden |
| INFO, READ, WRITE und EXEC auf Stock und unveränderter Hacktribe-Basis | beide gezielten Emulatorläufe bestanden |
| Vollständige ausgewählte Start- und SysEx-Fälle auf Synth | bestanden |
| Sidecar-Pfadprüfung und Startgrenze mit erzeugten Daten | Fehler vor Korrektur nachgewiesen, danach bestanden |
| Reine PCM-Änderung auf Stock und unveränderter Hacktribe-Basis | Schutzlücke erneut bestätigt, weiterhin offen |

Die Emulatorfälle verwenden erzeugte Daten und eigene Firmwaredateien
außerhalb des Repos. Für die abschließenden Integrationsprüfungen werden
Stock, Synth und Hacktribe anhand ihrer bekannten Originalsignaturen geprüft.
Die zuvor verwendete Hacktribe-Datei war bereits verändert. Die neuen
Hacktribe-Ergebnisse beziehen sich ausdrücklich auf das unveränderte Original,
das mit dem vorhandenen Konverter aus der eigenen Stock-Datei und dem
öffentlichen Hacktribe-Patch erzeugt und gegen die bekannte Signatur geprüft wird.
Die Ergebnisse der veränderten Variante bleiben als solche erhalten.

Die zusätzlichen breiten Läufe über Menü-, Swap- und weitere Develop-Fälle
sowie die großen roten SysEx-Gruppen wurden bei der Eingrenzung auf die
Integrationsschnittstellen beendet. Deren Teilergebnisse werden nicht als
bestandene vollständige Läufe gewertet. Die Auswahl ist keine erneute
vollständige Release-Zertifizierung aller Patchfälle.
`data/patches/verified.json` erhält durch diese Teilprüfung keine neue
Freigabe für den kombinierten Stand.

## Gemessen im Emulator: Grenze der Startbeobachtung

Die Hacktribe-Startprüfung zeichnet bisher in Schritten von 20 ms auf.
Nach der Zusammenführung erfasst der letzte Schritt bereits Arbeit des ersten
Hauptseiten-Frames. Alle 62 zunächst beanstandeten Codeziele werden erst mit
`screen() == 1` betreten. Mit Schritten von 2 ms endet die Aufzeichnung vor
diesem Frame. Der normale Start besteht dann den Code- und Datenvergleich,
ohne zusätzliche erlaubte Bereiche.

`bootmap.py` verwendet deshalb für alle drei Builds die bereits für Stock und
Synth geltenden 2 ms. Der Test mit einer erzeugten Maschine belegt, dass Arbeit
vor dem Wechsel enthalten bleibt und der erste Hauptseiten-Frame ausgeschlossen
wird. Ein Startmodus ohne Hauptseite bleibt über die volle Beobachtungsdauer
erfasst. Firmware, Startfreigaben und RAM-Besitz werden dadurch nicht geändert.
Dies ist eine Korrektur der Emulatorbeobachtung und keine Gerätemessung.

## Offen: Freigabe und Gerät

Die [vorherige Gesamtprüfung](2026-11-09-sample-swap-pruefung.md) bleibt
maßgeblich für die noch offenen Schutzlücken. Die Zusammenführung behebt
sie nicht zusätzlich. Insbesondere bleiben reine PCM-Änderungen,
Besitzerprüfung nach Ressourcenwarten und die Schutzrevision neuer
Aufnahmen gesondert zu schließen. Dauerhaftes Speichern aller nativen
Sample-Änderungen und der Start nur mit Index und aktivem Pattern für
jede Dateigröße sind ebenfalls noch nicht vollständig angeschlossen.

Es wird bei dieser Zusammenführung kein Gerät angesprochen und keine
Firmware installiert. Nach dem zuvor unbestätigten EXIT-Aufruf bleibt die
Gerätekommunikation bis zum bestätigten Neustart gesperrt. Eine Freigabe
für die Veröffentlichung ist mit dieser Integration nicht verbunden.
