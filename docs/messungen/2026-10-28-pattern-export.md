# Pattern-Export unter BLECH: wohin, und was in der Datei steht

Stand 28.10.2026, Emulator mit dem vollen BLECH-Satz auf vier Basen: Korgs Original rot, Hacktribe rot, Hacktribe auf
der blauen, Korgs Original blau (Synth-Satz). Anlass: zwei Meldungen im Discord, der Export komme nicht auf der Karte an
und der Import zeige nur alte Patterns. Die Prüfskripte lagen außerhalb des Repos und sind nicht eingecheckt.

| Befund | Marker |
|---|---|
| EXPORT PATTERN und EXPORT ALL PATTERN schreiben unter BLECH nach `KORG/blechtribe/`, byte-gleich zu dem, was Korgs Firmware ohne BLECH exportiert | gemessen (Emulator, alle vier Basen) |
| Liegt dort schon eine Datei mit demselben Namen, wird sie überschrieben: gleicher Name, gleiche Größe, festes Datum, nur der Inhalt ist neu. Keine Meldung am Gerät | gemessen (Emulator, Hacktribe rot mit übernommenem Ordner, Plugins und Samples) |
| EXPORT PATTERN schreibt das gespeicherte Pattern. Ein geändertes Pattern ohne WRITE ergibt beim zweiten Export eine byte-gleiche Datei, mit WRITE eine neue | gemessen (Emulator, rot und blau, mit BLECH und mit Korgs und Hacktribes Firmware ohne BLECH) |
| Die Übernahme beim ersten Start kopiert den alten Ordner nach `KORG/blechtribe/` und lässt ihn stehen; danach gibt es dieselben Dateinamen zweimal | offline (Code, `tools/patch/script_migrate.s`, [Patcher](../patcher.md)) |
| Auf dem Synth-Satz (blau ohne Hacktribe) ist die Übernahme aus (`MG_WORK 0`): der Export legt `KORG/blechtribe/` selbst an, `KORG/electribe/` bleibt unberührt | gemessen (Emulator), offline (Code) |
| Dateien, die das Gerät schreibt, tragen den 01.01.2014; die Electribe hat keine Uhr | gemessen (Foto vom Explorer, blaue Electribe) |
| Welche Ordner der Dateibrowser von IMPORT PATTERN am Gerät zeigt | offen |

Folgerung (hergeleitet): Kein Fehler in BLECH. Wer ohne WRITE exportiert, bekommt den alten Stand; wer nach Datum oder
nach neuen Dateien sucht, sieht keinen Unterschied; wer aus dem alten Ordner importiert, liest die alte Kopie. Die
Rettung und die [Häufigen Fragen](../faq.md) sagen deshalb: erst WRITE, dann EXPORT PATTERN, nur aus `KORG/blechtribe/`
importieren.
