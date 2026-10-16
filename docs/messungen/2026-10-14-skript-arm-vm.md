# Plugin ARM-VM

Stand 2026-10-14. Prüfumfang: native ARM-VM in Unicorn ohne Firmware und JS-Referenzlaufzeit.
Keine Gerätedatei erzeugt, kein Schreiben oder Ausführen am Gerät. Hintergrund zur Laufzeit:
[`../hintergrund/skript-laufzeit.md`](../hintergrund/skript-laufzeit.md).

## Ergebnis und Grenzen

Der ARM-Lader prüft GSCR Format 2 einschließlich CRC, Abschnitten,
Operanden, Sprunggrenzen, Stapel, Aufrufgraph, Ereignisrechten und
Zeilentabelle selbst. Python stellt nur Speicher, Timer und API-Gegenstellen
für Unicorn bereit. Ein Produktionsschalter zum Umgehen des Prüfers existiert
nicht. Der Testadapter hat einen gesonderten Weg für absichtlich ungültige
Programme, um Laufzeitprüfungen unabhängig vom Lader zu prüfen.

Alle 34 Opcodes und acht bestehenden API-Einträge werden verglichen.
506 Fälle vergleichen Ladefehler, Laufzeitfehler, Variablen, Zustand,
API-Aufrufe, Operationszahlen, Kosten und Quellzeilen gegen die JS-VM.
Der Korpus enthält Zahlenränder, Division, verschachtelte Aufrufe,
16-Bit-Operanden, kaputte Blöcke und 33 gleichzeitig geladene Plugins.
65535 als Variablenindex wird im Testadapter geprüft; ein normaler Block
mit 65536 Variablen passt nicht in den gemeinsamen 128-KiB-Pool.

Blöcke, Variablen und 196 Byte Metadaten je Plugin teilen 131072 Byte.
Es gibt keine zusätzliche feste Plugin-Anzahl. Fehlerhafte Blöcke reservieren
nichts; Laufzeitfehler schalten nur den betroffenen Eintrag ab. Quelltext
hinter `totalSize` bleibt außerhalb des Geräteblocks.

Timer3 liegt bei `0x01F0D010` und zählt laut vorangegangener Gerätemessung
mit 150 MHz. Die 5 ms entsprechen daher hergeleitet 750000 Ticks.
Aktuell gilt das Zeitlimit pro VM-Aufruf. Das gemeinsame Rahmenbudget
aller Plugins und Ereignisse ist hier noch nicht umgesetzt (es kommt mit den
Firmware-Haken, siehe `2026-10-14-skript-haken.md`).
Zeitmaxima je Handler, Kostenmaxima und Fehler liegen im RAM-Status.
Ringüberläufe starten bei null; Ring und Firmware-Lesezugriff folgen später.

Gemessene Buildgrößen: Code und Tabellen 8288 Byte, Laufzeit einschließlich
wiederverwendetem Prüferspeicher 164128 Byte, Pool 131072 Byte.
Die Summe ist 303488 Byte, ohne spätere Haken und API-Glue.
Dies ist keine RAM-Belegung am Gerät. Eine physische Adresse und freie
Fläche neben MFX 2 und Startbild müssen mit den Haken belegt werden.

## Prüfungen

| Prüfung | Ergebnis |
|---|---|
| öffentliche Pool-, Compiler- und Vertragsprüfungen | 82 bestanden |
| native Grenzen, Zeit, Pool, Register, Glue, API-Versionen bis 65535 | 16 bestanden |
| native VM gegen JS-Referenz | 506 Vergleiche bestanden |
| `E2_ARM_REQUIRED=1 npm test` | 350 bestanden, 58 ohne Firmware übersprungen, null Fehler |

Native Prüfungen laufen mit `tools/emu/.venv/bin/python`, das Unicorn enthält.
Die CI installiert die gepinnte Abhängigkeit und verlangt mit
`E2_ARM_REQUIRED=1`, dass der native Vergleich tatsächlich läuft.
Ohne Unicorn darf eine lokale optionale Prüfung überspringen; sie gilt dann
nicht als nativer Beleg.

Ein erster Gesamtlauf scheiterte an vier Unterprozessen, weil die Umgebungsvariable
`E2_EMU_PYTHON` einen relativen Pfad enthielt. Die Unterprozesse wechseln ihren
Arbeitsordner. Mit absolutem Pfad sowie ohne diese Variable liefen anschließend
348 Tests durch, 58 ohne Firmware übersprungen, null Fehler. Dies war ein
Aufruffehler und erforderte keine Laufzeitänderung.

## Unabhängige Prüfung

Eine getrennte Prüfung von Vollständigkeit, Korrektheit und Zusammenhang
fand eine Warnung zur verkürzten
API-Versionsdarstellung. Sie wurde behoben: Tabellen und native Vergleiche
verwenden jetzt vollständige 16 Bit. Gerichtete Tests prüfen 257 und 65535.
Diese interne Tabelle ändert weder GSCR Format 2 noch API-Version 1.

Eine weitere Prüfung fand eine Zeitgrenzenabweichung: ARM verwendete
zunächst `>=`, JS-Referenz und Vertrag erlauben exakt 5 ms und stoppen erst darüber.
ARM verwendet jetzt `>`. Ein endliches Programm prüft 750000 Ticks erfolgreich
und 750001 Ticks mit `TIME`, jeweils auch bei Timerüberlauf. Die Gleichheitsfälle
waren vor der Korrektur rot; die nativen Abschlussläufe sind danach grün.

Vier Kontrollfragen, gegen Code und Tests geprüft:

1. Reserviert ein abgelehnter Block Speicher? Nein, Prüfung vor Allokation.
2. Beendet ein Plugin-Fehler weitere Plugins? Nein, Fehlerzustand je Eintrag.
3. Ist die Arena bereits am Gerät platziert? Nein, Bare Build ist relocatable.
4. Belegt dieser Stand ein gemeinsames Rahmenbudget? Nein, das folgt mit den Haken.

Die vollständige Sprache, Firmware-Haken, SD-Lader, Display, Export und
Gerätebetrieb bleiben offen. Die Abschlussbewertung gilt nur für die ARM-VM.
