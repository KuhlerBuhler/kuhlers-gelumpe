# Stimmen beim Wechsel innerhalb einer Sync-Gruppe

Stand 25.10.2026. Im Emulator geprüft; der Übergang am Gerät ohne Schnitt und Klick gehört.

Zwei Patterns derselben Sync-Gruppe sollen als eine längere Sequenz spielen. Ein bereits
gestartetes Sample soll über den Wechsel weiterlaufen, auch wenn der Part im zweiten Pattern
ein anderes Sample hat. Der nächste Trigger soll das neue Sample starten. Das gilt für alle
16 Parts. Ein Wechsel in eine andere Gruppe oder ein Pattern ohne Gruppe behält das bisherige
Verhalten.

## Befund

**Im Emulator gemessen:** Die Firmware schaltet beim Patternladen vor der Kopie alle Parts
stumm und setzt die Stimmenverwaltung zurück. Nach der Kopie und der Aufbereitung der neuen
Part-Sounds folgt eine zweite globale Rücksetzung. Beide laufen auch beim Wechsel innerhalb
derselben Sync-Gruppe. Die bisherige Behandlung der Sample-Nummer in `sg_sample` verhindert
diese Abschaltungen nicht. Zusätzlich räumt der Ladepfad gehaltene Pad-Noten und deren
Zuordnung auf. Die Setter für Tonart, Skala und Voice-Modus lösen weitere Freigaben aus.
Auch die erneute Einrichtung der Notenplätze gibt bestehende Noten frei, obwohl ihre Zahl
gleich bleibt. Nur die beiden globalen Resets auszulassen reicht deshalb nicht: In der
Gegenprobe verschwindet die Stimme erst einige Millisekunden nach dem Laden.

| Stelle im Sampler 2.02 | Aufgabe | Stelle im Synth 2.02 |
|---|---|---|
| `0xC0079B90` | Einstieg vor Pad- und Notenbereinigung | `0xC006C51C` |
| `0xC0045DAC` | Gehaltene Notenquellen aufräumen | `0xC0040078` |
| `0xC004A728`, `0xC004A7A8`, `0xC00492F4` | Notenfreigaben aus drei Settern | `0xC0044808`, `0xC0044888`, `0xC00434B4` |
| `0xC005A884` | Notenplätze für den Voice-Modus neu einrichten | `0xC005140C` |
| `0xC0079BE0` | Aufruf der Abschaltung vor der Kopie | `0xC006C56C` |
| `0xC0098CA8` | Parts stummschalten, Stimmen zurücksetzen, Parts stoppen | `0xC00860EC` |
| `0xC004AC44` | Pattern aus der RAM-Bank kopieren | bestehender Kopieraufruf des Patches |
| `0xC0079C2C` | Part-Sounds nach der Kopie aufbereiten | `0xC006C5B8` |
| `0xC0098C84` | Zweite globale Stimmenrücksetzung | `0xC00860C8` |
| `0xC0091F5C` | Globale Stimmenverwaltung zurücksetzen | `0xC007FFE0` |

In der Aufzeichnung eines Gruppenwechsels beginnt die Abschaltung vor der Kopie bei
10.973,003 ms der Emulatorzeit. Die zweite globale Rücksetzung folgt bei 10.977,203 ms.
Diese Zeitpunkte belegen die Reihenfolge der ARM-Aufrufe, keine hörbare Unterbrechungsdauer.

**Aus dem Code hergeleitet:** Das Part-Objekt hält seine zugeteilten Stimmen als Bitmaske
bei `+0x04`. Die Rücksetzung gibt diese Stimmen frei und löscht weitere Zustände. Die
Aufbereitung liest die neue Sample-Nummer aus dem Pattern und legt sie bei `+0x34` des
Part-Objekts ab. Das beschreibt die ARM-Seite; der Emulator berechnet keinen Ton.

## Patch

Der Schutz wird unmittelbar vor dem tatsächlichen Laden entschieden. Er gilt nur bei
laufender Wiedergabe, wenn die Quelle ein anderer Block der Patternbank ist und beide
Patterns dieselbe von null verschiedene Gruppe haben. Die Gruppe des laufenden Patterns
wird aus dem RAM gelesen. Ein noch nicht gespeicherter Gruppenwechsel zählt damit mit.

Innerhalb dieses einen Ladevorgangs entfallen die globalen Abschaltungen sowie die genannten
Bereinigungen der gehaltenen Noten und ihrer Zuordnung. Der übernommene Voice-Modus braucht
keine neuen Notenplätze. Die Kopie des Patterns und die Aufbereitung der Part-Sounds laufen
weiter. Danach wird der Schutz gelöscht.
Normale Stopps und spätere Ladevorgänge bleiben davon unabhängig. EXIT beim Einschalten
schaltet auch diesen Schutz aus. Die Einstellung für die Bestätigung des Patternwechsels
ist davon unabhängig, wie bei der bisherigen Übernahme der Gruppenwerte.

Die Sample-Auswahl folgt weiterhin `sg_sample`: Ein live geändertes Sample wird mitgenommen.
Ohne solche Änderung behält das neue Pattern sein eigenes Sample. Steps und Länge bleiben
ebenfalls die des neuen Patterns.

Code und Zustand liegen weiterhin im bisherigen Bereich des Patternwechsel-Patches. Die
kleinen Schutzfunktionen liegen bei `0xC0180F40`, hinter dessen Zustand und vor dem Code
der Ladeanzeige. Puffer und Einstellungsadressen sind unverändert. Es gibt keine Schreibzugriffe
auf Flash oder Karte.

## Prüfungen

Die Gegenprobe ohne den Schutz schlägt innerhalb einer Gruppe sowohl bei gleichen als auch
bei unterschiedlichen Samples fehl. Andere Gruppe, Gruppe OFF und EXIT beim Einschalten
bestehen bereits ohne den Schutz. Mit dem Schutz bestehen diese fünf Fälle auf Hacktribe, Stock und Synth.
Eine tatsächlich gehaltene Pad-Note behält sowohl ihre Stimmenzuordnung als auch die alte
Sample-Nummer, unmittelbar nach dem Laden und nach weiteren 500 ms. Nach Loslassen und
erneutem Drücken enthält die neu zugeteilte Stimme das neue Sample. Bei jedem Wechsel werden
zusätzlich alle 16 Part-Sounds aufbereitet und ihre erwarteten Sample-Nummern geprüft.

STOP beendet den Transport und der Schutz ist danach aus. Eine weiterhin physisch gehaltene
Pad-Note bleibt auch in der unveränderten Firmware bis zum Loslassen aktiv; die Prüfung
verlangt deshalb getrennt den gestoppten Transport und die Freigabe nach dem Loslassen.

Die eigenen ARM-Prüfungen decken alle drei Builds ab: laufender Gruppenwechsel, gestoppte
Wiedergabe, Gruppe null, andere Gruppe, Neuladen desselben Bankblocks, Quelle außerhalb der
Bank und EXIT beim Einschalten. Sie prüfen außerdem Register, Stack, Aufbereitung und das
Löschen des Schutzes. Ein anschließender normaler Reset muss wieder ausgeführt werden.

Die Startprüfung hatte eine zusätzliche Lücke: Ein zusammenhängender ausgeführter Block,
der zwei angrenzende erlaubte Bereiche überspannt, wurde trotz vollständiger Abdeckung
abgelehnt. Die Bereichsprüfung zieht jetzt die Vereinigung der erlaubten Bereiche ab. Fünf
eigene Gegenproben prüfen auch, dass eine echte Lücke weiterhin als Fehler erscheint.

Die vollständige Firmwareprüfung besteht auf Hacktribe und Stock mit je 77 Prüfungen, auf
Synth mit 76. Dazu gehören Start, Rettungswege und die bisherigen Gruppenfälle. Die
eigenen ARM-Gegenproben bestehen in 24 Kombinationen aus Build und Ladezustand; die fünf
Bereichsprüfungen bestehen ebenfalls. Der unten beschriebene Hörvergleich am Gerät ist abgeschlossen.
Die vollständige Unit-Suite besteht mit 1089 bestandenen und 147 übersprungenen Prüfungen,
die Browsersuite mit 213 bestandenen und einer übersprungenen Prüfung, jeweils ohne Fehler.
Die bekannten Abschaltungen zu unterdrücken und die neue Sample-Nummer vorzubereiten beweist
allein weder einen erhaltenen DSP-Samplezeiger noch einen klickfreien Übergang.

## Gegenprobe am Gerät

Verwendet werden Pattern 135 und 136, beide bereits in Gruppe 1, mit Part 8 aus Pattern 6.
Das gewählte Sample hat 840292 PCM-Bytes bei 44100 Hz, mono. Bei 16 Bit und Originaltonhöhe
sind das hergeleitet etwa 9,5 Sekunden. Änderungen erfolgen ausschließlich im RAM, ohne
WRITE und ohne Änderung der Karte. Part 8 enthält im zweiten Pattern am Übergang keinen neuen Trigger.

**Am Gerät gehört:** Mit dem bisherigen Code bricht der Sound am Patternwechsel ab. Der
Testaufbau wurde am Gerät manuell korrigiert, nachdem die bestehende Sample-Übernahme beim
Einrichten noch die alte Zuordnung mitgenommen hatte. Ein automatischer Ausleselauf während
der Wiedergabe verlor eine USB-Antwort und ist kein gültiger Kontinuitätsnachweis. Das Gerät
antwortete danach wieder und war gestoppt.

Der neue Code und alle 21 Einsprungstellen sind im RAM installiert und zurückgelesen. Für
den Transfer dient nur der vorgesehene 1-KiB-Puffer, der danach wiederhergestellt wurde.
Die bisherigen Einsprungstellen werden vor dem Austausch des Codes gemeinsam deaktiviert
und die neuen nach dem vollständigen Laden gemeinsam aktiviert. Die manuelle Korrektur des
Testpatterns bleibt dabei bestehen.

**Am Gerät gehört:** Mit dem RAM-Patch läuft Part 8 beim Wechsel 135 nach 136 sauber weiter,
ohne Schnitt oder Klick. Part 8 hat im vorbereiteten Paar dieselbe Sample-Zuordnung.
Der direkte Vergleich zum zuvor gehörten Abbruch bestätigt diesen
einen Übergang auf dem roten Sampler mit Hacktribe.

**Offen:** Ein wirklich acht Takte langes Vocal ist noch nicht vorbereitet. Unterschiedliche
Samples beim nächsten Trigger und alle 16 gleichzeitig gehaltenen Parts sind am Gerät nicht
getrennt geprüft; die Sample-Zuordnung aller 16 Parts ist im Emulator geprüft. Der gewählte
Part aus Pattern 6 reicht beim geprüften Tempo über die Vier-Takt-Grenze. Acht Takte
bei anderem Tempo sind damit nicht nachgewiesen. Unterschiede der Effekttypen
können unabhängig von der Stimmenabschaltung eine Neuinitialisierung auslösen.

## Dateien und Zusammenhang

- [Builder](../../tools/patch/pattern_switch.py)
- [Gruppenfälle im Emulator](../../tools/emu/pswitch_cases.py)
- [Eigene ARM-Gegenproben](../../tools/patch/test_sync_voices.py)
- [Gegenproben der erlaubten Bereiche](../../tools/emu/test_allowed_spans.py)
- [Bisheriger Hintergrund zum Patternwechsel](../hintergrund/patternwechsel.md)
- [Sample-Übernahme und Pad-Eingaben](2026-10-25-sync-sample-und-pad-xy.md)
