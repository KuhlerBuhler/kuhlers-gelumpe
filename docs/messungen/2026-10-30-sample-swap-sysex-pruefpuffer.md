# Sample-Swap: belegten Code im SysEx-Prüfaufbau erhalten

**Gemessen im Emulator**, Stand 30.10.2026. Eigene erzeugte Kartendateien
und ARM-Prüfprogramme, keine Gerätekontakte. Ergänzung zu den
[nativen Wartepfaden](2026-10-29-sample-swap-wartepfade.md).

## Gemessen vor der Korrektur

Die vollständige Patch-Prüfung meldet in beiden roten Builds drei
abgebrochene SysEx-Gruppen. Der einzelne Sampledatei-Fall reproduziert
einen ungültigen Lesezugriff auf `0xD3D3D3D3`. Er entsteht beim Lesen
einer Adresse aus dem eigenen Aufnahme-Wächter, nicht aus einem
festgehaltenen DSP-Wartepfad. Der DSP-Fehlerzustand ist dabei null.

Der SysEx-Prüfaufbau füllt vor der ersten Nachricht den Bereich zwischen
dem Ende seines Nachrichtenpuffers und seinem Dateiobjekt mit `0xD3`.
Das Ende des Nachrichtenpuffers liegt bei `0xC019A400`, das Dateiobjekt
bei `0xC019F000`. Der Swap besitzt darin `0xC019A400` bis `0xC019C400`
als Codefläche. Der Prüfaufbau überschreibt somit diese belegte Fläche,
einschließlich der Adresskonstanten der neuen Wächter.

Zwei Prüfungen mit vollständig erzeugtem Speicher reproduzieren die
Ursache: Das Installieren des Kontrollmusters verändert eigenen
Swap-Code, und dessen legitimes Lesen einer Adresskonstanten wird als
verbotener Zugriff auf freien Speicher gemeldet.

## Gemessen nach der Korrektur

Der Prüfaufbau erkennt den installierten Swap an dessen vorhandenem
Haken und berücksichtigt seine deklarierte Codefläche. Er schreibt
dort kein Kontrollmuster und lässt Code seine Konstanten lesen.
Ein Lesewächter prüft dafür den tatsächlich ausführenden Codebereich.
Ein fremder Leser oder ein unbeabsichtigter SysEx-Zugriff über das
Pufferende bleibt verboten. Eine reguläre ausdrücklich angeforderte
Speicherabfrage erhält nur für ihre gültige Adresse und Länge eine
vorübergehende Lesefreigabe. Nach Ende oder Ausnahme der Abfrage ist
diese Freigabe wieder aufgehoben; das nächste Wort wird nicht freigegeben.
CPU-Schreibzugriffe in diese Fläche bleiben verboten. Zusätzlich wird
die gesamte Fläche nach jeder Nachrichtenrunde mit ihrem ursprünglichen
Inhalt verglichen; auch direkte Änderungen durch den Emulator werden
dadurch erkannt.

Der verbleibende freie Rest erhält weiterhin das Kontrollmuster sowie
Lese- und Schreibwächter. Ohne Swap bleibt der gesamte bisherige Bereich
geschützt. Es wird kein fehlerhafter Zugriff abgefangen und anschließend
durch Zurückschreiben des Codes verdeckt.

Zehn Prüfungen mit erzeugtem Speicher bestehen: Codeerhalt bis an beide
Grenzen, Lesen einer eigenen Konstante, verbotene CPU-Codeänderung,
Erkennen direkter Emulatoränderungen, verbotene Lese- und Schreibzugriffe
im freien Rest und unveränderter Schutz ohne Swap. Dazu kommen der
verbotene fremde Leser, die genaue Grenze einer ausdrücklichen Abfrage,
das Ende ihrer Freigabe bei einer Ausnahme und ungültige Leselängen.
Die zunächst zu breite Ausnahme für fremde Leser wurde im Gegenversuch
reproduziert und durch diese Zuordnung geschlossen. Die Zuordnung der
Prüfgruppen berücksichtigt die neue gemeinsame Haken-Erkennung.

Die Fälle stehen in
[test_sysex_guards.py](../../tools/emu/test_sysex_guards.py) und laufen
über [emulator-sysex-guards.test.mjs](../../test/emulator-sysex-guards.test.mjs)
ohne Firmwaredaten. Der korrigierte Prüfaufbau liegt in
[sysex_cases.py](../../tools/emu/sysex_cases.py).

## Abschließende Prüfung

Die vollständigen SysEx- und Patch-Prüfungen des korrigierten Prüfaufbaus
bestehen: 740 Prüfungen für Stock und 715 für Hacktribe, jeweils ohne
Fehler und mit regulärem Abschluss. Die Änderung am Prüfaufbau verändert
keine gebaute Firmware. Zusätzlich bestehen 32 gezielte Swap-Prüfungen
pro rotem Build, 116 ARM-Prüfungen, 1360 Unit-Prüfungen bei 160
übersprungenen Fällen und 285 Browserprüfungen bei einem übersprungenen
Fall.

## Offen

Die dauerhaften Sample-Menüwege, der bisherige Gesamtexport und die
abschließenden Gerätetests bleiben offen. Es gibt keine Freigabe für 1.4.
