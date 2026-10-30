# Sample-Swap: Schutz der Daten im DSP und auf der Karte

Stand 30.10.2026. Alles hier ist im Emulator gemessen, mit erzeugten Samples und Patterns
(`tools/emu/sampleset.py`), mit Hacktribe 2.02 und Korgs roter 2.02. Kein Gerät wurde
angesprochen. Jeder Fall lief zuerst gegen den Swap ohne diese Korrektur und danach mit ihr.

## Gemessen: EXPORT ALL SAMPLE kürzte die Sammlung

`case_full_session` in `tools/emu/swap_cases.py`, Sammlung mit sechs Samples (500 bis 505),
DSP-Budget 256 KiB, der Swap ist an. Danach `DATA UTILITY -> EXPORT ALL SAMPLE`.

| | Slots in `e2sSample.all` danach | Bytes danach | Datei unverändert |
|---|---|---|---|
| ohne Korrektur | 1 | 45328 | nein |
| mit Korrektur | 6 | 491488 | ja |

Der Export schrieb nur, was gerade im DSP lag. Der Fall hatte das gemessen, aber nicht geprüft.
Er verlangt jetzt dieselbe Datei wie vorher.

Die Korrektur hängt am `f_open` des Gesamtexports (`0xC0039FB0`). Solange der Swap an ist oder
gescheitert ist (MODE 1 oder 2), gibt der Haken den FatFs-Code 10 zurück, ohne die Datei zu öffnen.
Die Firmware wandelt ihn in ihren eigenen Fehler und zeigt "Card Write Protected". Mit kleiner
Sammlung (MODE 0) exportiert sie wie immer.

## Gemessen: ein importiertes Sample wurde verdrängt

`case_import_kept`: `IMPORT SAMPLE` legt `imp.wav` (40000 Byte PCM) auf Slot 500, danach Wechsel auf
die Patterns 1, 2, 3 und 0. Budget 384 KiB, damit beim Wechsel auf 3 ein Sample den DSP verlassen muss.

| | Slot 500 nach Pattern 3 | Name nach Pattern 0 | Länge nach Pattern 0 |
|---|---|---|---|
| ohne Korrektur | nicht im DSP | s500 | 80000 |
| mit Korrektur | im DSP | imp | 40000 |

Ohne Korrektur verdrängte der Swap den importierten Slot und lud später die alte Fassung von der
Karte. Der Import war verloren, denn er schreibt nur in den DSP
([Speichergrenzen](2026-10-30-sample-speichergrenzen.md)).

Mit Korrektur merkt sich der Swap für jede Zeile, die der Lader beim Start oder der Swap selbst in
den DSP gebracht hat, eine Prüfsumme über die Metadatenzeile und den Namen. Verdrängt wird nur eine
Zeile, deren Summe noch stimmt. Import, Aufnahme, Resampling und jede Änderung in SAMPLE EDIT ändern
die Zeile oder geben dem Slot eine neue, also bleibt sie bis zum Neustart. Im Fall oben ging beim
Wechsel auf 3 statt 500 der Slot 501.

Aufnahme, Resampling und SAMPLE EDIT sind nur im Modell geprüft (`tools/patch/test_sample_swap.py`,
`ChangedRows`), nicht als echter Ablauf im Emulator. **hergeleitet**

## Gemessen: Frist der nativen DSP-Aufrufe nur während eines Swap-Schritts

`tools/emu/native_dsp_scope_cases.py`: der Statusport meldet 1.200.000 Abfragen lang "beschäftigt",
dann "bereit". Das dauert im Emulator rund 123 ms, länger als die Frist von 100 ms.

| | im Swap-Schritt | außerhalb |
|---|---|---|
| ohne Korrektur | Fehler gesetzt, MODE 2 | Fehler gesetzt, MODE 2 |
| mit Korrektur | Fehler gesetzt nach 100 ms, MODE 2 | läuft durch, kein Fehler, MODE bleibt 1 |

Die Frist gilt jetzt nur, solange MODE 1 ist und der Befehlsschritt des Swaps läuft (Statuswort
`INSTEP`). Alle anderen nativen DSP-Aufrufe laufen wie in Korgs Firmware. Die 100 ms selbst sind
weiter nicht am Gerät gemessen. **offen**

## Gemessen: ein gesetzter DSP-Fehler sperrte auch Werkssamples

`case_factory_after_fault`: Fehlerwort gesetzt, Part 0 bekommt Werkssample 10.

| | Part danach |
|---|---|
| ohne Korrektur | 500 (alt) |
| mit Korrektur | 10 |

Ein indiziertes Nutzersample, das nicht im DSP liegt, bleibt dabei weiter gesperrt (505 im selben Fall).

## Gemessen: ein defektes Journal verhinderte jedes Laden

`case_bad_journal`: neben `e2sSample.all` liegt eine `e2sSample.txn` mit 4160 Byte, die keine
gültige Wiederherstellungsdatei ist.

| | mit Swap | ohne Swap |
|---|---|---|
| ohne Korrektur | MODE 2, kein Sample im DSP | MODE 2, kein Sample im DSP |
| mit Korrektur | MODE 1, 500 und 501 im DSP | MODE 0, alle vier Samples im DSP |

Eine Wiederherstellung, die abgelehnt wird, bevor sie etwas schreibt, lässt den Index unverändert.
Dann lädt die Sammlung normal und die Datei bleibt liegen. Scheitert erst das Schreiben des
wiederhergestellten Index, bleibt das Laden gesperrt wie bisher.

## Offen

- Die 100-ms-Frist und echte Übertragungszeiten am Gerät.
- Aufnahme und Resampling als echter Ablauf, Klang und Stimmenausklang.
- Die Sammlung wird weiter nur durch Verdrängungsschutz gesichert, nicht gespeichert: ein
  importiertes Sample ist nach einem Neustart weg, solange Import und WRITE nicht auf die Karte
  schreiben.
