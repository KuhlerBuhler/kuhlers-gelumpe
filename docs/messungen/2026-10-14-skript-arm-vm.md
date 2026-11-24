# Plugin ARM-VM

Prüfumfang: die native ARM-[VM](../glossary.md#vm) der [Plugin](../glossary.md#plugin)-Laufzeit in Unicorn ohne Firmware gegen die
JS-Referenzlaufzeit. Kein Schreiben oder Ausführen am Gerät. Hintergrund zur Laufzeit:
[`../hintergrund/skript-laufzeit.md`](../hintergrund/skript-laufzeit.md).

## Ergebnis und Grenzen

Der ARM-Lader prüft [GSCR](../glossary.md#gscr) Format 2 einschließlich CRC, Abschnitten,
Operanden, Sprunggrenzen, Stapel, Aufrufgraph, Ereignisrechten und
Zeilentabelle selbst. Python stellt nur Speicher, Timer und API-Gegenstellen
für Unicorn bereit. Ein Produktionsschalter zum Umgehen des Prüfers existiert
nicht. Der Testadapter hat einen gesonderten Weg für absichtlich ungültige
Programme, um Laufzeitprüfungen unabhängig vom Lader zu prüfen.

Alle 34 Opcodes (`data/script/contract.mjs`) und die API-Einträge werden gegen die JS-VM verglichen:
Ladefehler, Laufzeitfehler, Variablen, Zustand, API-Aufrufe, Operationszahlen, Kosten und Quellzeilen.
Der Korpus enthält Zahlenränder, Division, verschachtelte Aufrufe, 16-Bit-Operanden, kaputte Blöcke
und viele gleichzeitig geladene Plugins. 65535 als Variablenindex wird im Testadapter geprüft; ein normaler Block
mit 65536 Variablen passt nicht in den gemeinsamen 128-KiB-Pool.

Blöcke, Variablen und die Metadaten je Plugin teilen sich den Pool von 131072 Byte
(`SCRIPT_POOL_BYTES`). Es gibt keine zusätzliche feste Plugin-Anzahl. Fehlerhafte Blöcke reservieren
nichts; Laufzeitfehler schalten nur den betroffenen Eintrag ab. Quelltext
hinter `totalSize` bleibt außerhalb des Geräteblocks.

Timer 3 liegt bei `0x01F0D010` und zählt laut Gerätemessung ([Tempo der Plugin-VM](2026-10-12-vm-tempo.md))
mit 150 MHz. Die 5 ms Zeitlimit je Handler entsprechen daher hergeleitet 750000 Ticks. Exakt 5 ms sind
erlaubt, erst darüber stoppt die VM mit `TIME` (JS-Referenz, Vertrag und ARM-VM stimmen darin überein;
ein endliches Programm prüft 750000 Ticks als erfolgreich und 750001 mit `TIME`, auch bei Timerüberlauf).
Das gemeinsame Rahmenbudget aller Plugins und die Haken: [Plugin-Haken](2026-10-14-skript-haken.md).
Zeitmaxima je Handler, Kostenmaxima und Fehler liegen im RAM-Status. Die API-Version wird mit
vollen 16 Bit verglichen (gerichtete Tests mit 257 und 65535).

## Prüfungen

Die nativen Prüfungen laufen mit `tools/emu/.venv/bin/python`, das Unicorn enthält: Pool, Compiler und Vertrag,
Grenzen, Zeit, Register, Glue, API-Versionen bis 65535, und der Vergleich der nativen VM mit der JS-Referenz.
Die CI installiert die gepinnte Abhängigkeit und verlangt mit `E2_ARM_REQUIRED=1`, dass der native Vergleich
tatsächlich läuft. Ohne Unicorn darf eine lokale optionale Prüfung überspringen; sie gilt dann nicht als
nativer Beleg. `E2_EMU_PYTHON` muss ein absoluter Pfad sein, weil die Unterprozesse ihren Arbeitsordner wechseln.

Vier Kontrollfragen, gegen Code und Tests geprüft:

1. Reserviert ein abgelehnter Block Speicher? Nein, Prüfung vor Allokation.
2. Beendet ein Plugin-Fehler weitere Plugins? Nein, Fehlerzustand je Eintrag.
3. Ist der Bare Build relocatable? Ja, die Platzierung am Gerät legt der Patch fest.
4. Gilt ein gemeinsames Rahmenbudget für alle Plugins? Ja, mit den Haken.
