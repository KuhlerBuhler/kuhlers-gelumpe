# Plugin-Prüfung: weniger Speicherarbeit beim Laden

Stand 21.10.2026. **Im Emulator gemessen**, ohne Gerätetest. Derselbe aktuelle Compiler
übersetzt dieselben elf eigenen Presets für beide Fassungen. Nur fünf Löschlängen in
`tools/patch/script_vm.s` unterscheiden sich.

## Ergebnis

| Messung | Vorher | Nachher |
|---|---:|---:|
| ARM-Befehle zum Laden aller elf Presets | 16068540 | 3498105 |
| Code der nackten Laufzeit | 11632 Byte | 11620 Byte |
| Laufzeitabschnitte, Hacktribe und Korg rot | 50308 Byte | 50296 Byte |
| Laufzeitabschnitte, Synth | 50340 Byte | 50328 Byte |
| Reservierter Laufzeitbereich | 163 KiB | 163 KiB |

Der geprüfte Ladeabschnitt braucht **78,23 Prozent weniger ARM-Befehle**. Jede der drei
Wiederholungen liefert dieselben Zahlen. Gezählt wird der vollständige native Blocklader
nach der einmaligen Laufzeitinitialisierung, einschließlich Prüfsumme, Codeprüfung und
Ablage im Plugin-Pool. Das ist kein Nachweis für schnelleren Sample-Import, Sample-Export,
SD-Transfer oder die gesamte Startdauer.

Die Laufzeit wird **12 Byte kleiner** und reserviert genauso viel RAM wie vorher. Beide
verglichenen Abschnittsgrößen enthalten dieselbe neue Display-Kalibrierung. Deren eigener
Codebedarf wird [getrennt beschrieben](2026-10-21-display-kalibrierung.md).

## Warum die Begrenzung trägt

Vor der Codeprüfung sind Block- und Codelänge, Größenlimits, Prüfsumme und Abschnitte
bereits validiert. Die fünf Füllaufrufe verwenden die gültige Codelänge für Befehlsgrenzen,
Argumentzahlen, Funktionszustände und die besuchten Befehle der Stack- und Ereignisprüfung.

Befehls-, Sprung-, Aufruf-, Handler- und Zeilenpositionen werden gegen die Codelänge geprüft.
Funktionszusammenfassungen werden erst nach einem erfolgreich abgeschlossenen Funktionslauf
verwendet. In der Arbeitsliste stehen nur zuvor geprüfte Befehlspositionen. Der unbenutzte
Rest der Prüfpuffer wird nicht gelesen und muss deshalb beim Laden nicht erneut gelöscht werden.

Die vollständige Initialisierung der Laufzeit, neuer Plugin-Einträge und Plugin-Variablen
bleibt erhalten. Prüfsummen, Fehlercodes, Speicherlimits und Ausführungsbudgets ändern sich nicht.

## Absicherung

`tools/patch/test_script_vm_validator.py` füllt alle sieben Prüfpuffer mit alten Daten und
überwacht Lese- und Schreibzugriffe. Kein Zugriff darf hinter der aktuellen Codelänge liegen;
ungenutzte Reste müssen bytegleich bleiben. Geprüft werden lange, kurze und fehlgeschlagene
Ladevorgänge hintereinander, verschachtelte Funktionen, Arbeitslisten, Rekursion, ungültige
Sprünge, Handler und Zeilentabellen sowie Codegrößen 0, 1, 16384 und 16385 Byte.

Fehler dürfen bereits geladene Plugins nicht verändern; ein vorher geladenes Plugin bleibt
ausführbar. Register, Stack und CPU-Steuerzustand werden kontrolliert. Die JavaScript-Referenz
wird zusätzlich mit der nativen Laufzeit verglichen. Die Prüfungen sind in den regulären
Laufzeittest eingebunden.

[Messzahlen, Block-Prüfsummen und Wiederholungen](2026-10-21-plugin-pruefung-zahlen.json).
Die vollständigen Firmware- und Geräteprüfungen werden beim jeweiligen Teststand angegeben;
diese lokale Lademessung ersetzt sie nicht.
