# BLECH: Operanddecoder ohne Stackzugriffe

Stand 21.10.2026. **Im Emulator gemessen.** Der Decoder liest die Operanden
eines Skriptbefehls mit frei verwendbaren ARM-Registern. Er benötigt keine
Registersicherung auf dem Stack. Die vier vorhandenen Aufrufer behalten ihren
Registervertrag; Operanden werden weiterhin byteweise gelesen. Damit bleibt
auch ein unausgerichteter Befehlsanfang gültig.

Verglichen wird ausschließlich diese Änderung mit der bereits geprüften
[develop-Basis](2026-10-21-patch-effizienz-basis.md). Die dort enthaltenen
Verbesserungen an Pads, Plugin-Prüfung und Multiplikation werden nicht erneut
als Gewinn gezählt. Basis der Firmwarequellen ist
`21cf0ceaada9ff6410c48b85022ad98c8bc8b939`, der Kandidat
`83d5036e34d5573da578c409d322a5560a908a86`.

## Gewinn in den Apps

Jeder Build wurde mit drei unabhängigen Starts von Original und Kandidat
gemessen. Profilformat 4, Eingänge und Messmethode entsprechen der Basis.
Die drei Apps liefern je acht Vorlaufbilder und danach 50 vollständig
abgeschlossene Messbilder. Insgesamt sind das 18 Starts, 126 Messfenster und
1350 gemessene App-Bilder. Alle Wiederholungen liefern gleiche Zähler,
App-Zustände und Bildpuffer. Auch zwischen Basis und Kandidat sind Zustände und
Bilder identisch.

Die erste Zahl zählt nur Befehle innerhalb des Skript-Laufzeitpatches. Die
zweite zählt das gesamte Messfenster einschließlich der unveränderten
Firmwarearbeit. Beide Zahlen bedeuten weniger ARM-Befehle, keine gemessenen
Millisekunden am Gerät.

| Build | App | Weniger Runtime-Befehle, Prozent | Weniger Befehle insgesamt, Prozent |
|---|---|---:|---:|
| Hacktribe | Mandelbrot | 5,81 | 1,60 |
| Hacktribe | Life | 5,87 | 1,56 |
| Hacktribe | Pong | 2,98 | 0,18 |
| Korg rot | Mandelbrot | 5,81 | 1,60 |
| Korg rot | Life | 5,87 | 1,56 |
| Korg rot | Pong | 2,98 | 0,18 |
| Synth | Mandelbrot | 5,83 | 1,37 |
| Synth | Life | 5,89 | 1,34 |
| Synth | Pong | 3,05 | 0,15 |

Das Ziel von mindestens drei Prozent weniger Runtime-Befehlen bei Mandelbrot
und Life wird auf allen drei Builds erreicht. Sämtliche anderen Szenen,
einschließlich langer Bindungen und Pong, bleiben innerhalb des Budgets von
höchstens einem Prozent Mehrarbeit. Der strenge Vergleich weist keinen
Fehler aus. Die [Messdatei](2026-10-21-patch-effizienz-decoder-zahlen.json)
enthält die genauen Zähler, Firmwarehashes und Platzwerte.

## Einzeldecoder und Schutzgrenzen

Die aus dem aktuellen Vertrag erzeugte Matrix umfasst alle 34 Opcodes,
neun Randwerte und vier Ausrichtungen. Bei zwei Operanden werden alle
Wertepaarungen geprüft. Das ergibt 2376 Vektoren. Werte werden ihrer
Operandenbreite entsprechend kodiert. Die Ergebnisse stimmen mit dem Vertrag
und über ihren Hash mit dem bisherigen Decoder überein.

| Einzelmessung | Basis | Kandidat |
|---|---:|---:|
| Mittlere ARM-Befehle pro Aufruf | 22,636364 | 17,606061 |
| Maximale ARM-Befehle pro Aufruf | 30 | 22 |
| Schreibzugriffe in der Matrix | 9504 | 0 |
| Decoder mit Literalbereich, Byte | 124 | 92 |
| VM-Code, Byte | 11620 | 11588 |

Der Einzeldecoder benötigt damit 22,22 Prozent weniger Befehle. Der Code des
vollständigen Satzes schrumpft auf jedem Build um 32 Byte; das reservierte RAM
bleibt gleich. Die Opcode- und Operandentabellen, Budget- und
Bereichsprüfungen werden nicht geändert. Alle vier Aufrufstellen wurden auf
ihr Registerverhalten geprüft.

Jeder Vektor kontrolliert r4 bis r11, Stackpointer, Rücksprungadresse,
Eingabewächter und die genaue Liste der gelesenen Operanden- und Tabellenbytes.
Der neue Test für fehlende Schreibzugriffe war mit dem bisherigen Decoder rot
und ist nach der Änderung grün. Der native Lader lehnt außerdem jede
abgeschnittene Operandenfolge und alle 222 nicht vergebenen Opcodes ab.

## Vollständige Sätze

Alle drei Manifeste wurden aus den Quellen neu erzeugt. RAM-Reservierungen,
Hookstellen und gemeinsame Bereiche sind unverändert. `check.py` lief ohne
Kurzprüfung und ohne Ergebniscache. Alle erforderlichen Gruppen sind
vollständig, keine Satzprüfung wurde ausgelassen und die überwachten Quellen
blieben unverändert.

| Build | Bestanden |
|---|---:|
| Hacktribe | 443/443 |
| Korg rot | 468/468 |
| Synth | 347/347 |

20 native Tests und 38 gezielte Node-Tests bestehen, bei einer vorgesehenen
Auslassung für den separaten Firmware-Emulationstest `test:emu`. Die nativen Prüfungen haben keine
Auslassung. Nach der Änderung bestehen außerdem 959 Unit-Tests und 164
Browsertests ohne Fehler, mit 143 beziehungsweise einer vorgesehenen Auslassung. Die Umsetzung steht in
[script_vm.s](../../tools/patch/script_vm.s), die Matrix und Zugriffswächter in
[test_script_vm_optimizations.py](../../tools/patch/test_script_vm_optimizations.py).

## Grenzen

Diese Messung belegt weniger ARM-Arbeit bei identischen geprüften Ergebnissen.
Reale CPU-Zyklen und Audiolatenzen wurden nicht gemessen. Eine Geräteabnahme
steht aus. Sample-Import, Sample-Export und SysEx-Puffer sind unverändert.
Originale, erzeugte VSBs und vollständige Profile liegen außerhalb des
Repositorys; hier stehen nur eigene Messwerte und Hashes.
