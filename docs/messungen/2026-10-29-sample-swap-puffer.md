# Sample-Swap: Alte Kopien nach einer Pufferübergabe stoppen

Stand: 29.10.2026. Beleg: `measure:2026-10-29/sample-swap-puffer`.
Fortsetzung der [Korrekturprüfung](2026-10-29-sample-swap-korrektur.md).
Die Versuche benutzen ausschließlich erzeugte Sampledaten im Emulator.

## Gemessen vor der Korrektur

Vier neue ARM-Tests prüfen die Übergabe des unteren Cachebereichs vor
einer Kopie und zwischen Lesen und Schreiben. Sie prüfen außerdem alte
Aufträge, Registererhalt und die Interruptmaske einer großen Kopie.
Mit der bisherigen Kopierfunktion schlagen sieben Teilfälle fehl.

Der neue native Emulatorfall ruft bei freigegebenen Interrupts den echten
Puffergeber bei `0xC00369F0` auf und setzt dessen neuen Arbeitsbereich auf
ein eigenes Kontrollmuster. Anschließend läuft der unterbrochene Auftrag
weiter. Im bisherigen Stock-Patch überschreibt die alte PCM-Kopie danach
24 Wörter, die Deskriptorkopie 296 Wörter. Beide Fehler treten sowohl vor
der Kopie als auch nach ihrem ersten Lesezugriff auf. Die Metadatentabelle
bleibt dabei unverändert. Eine verhinderte Tabellenveröffentlichung schützt
also nicht vor diesen fremden RAM-Schreibzugriffen.

## Hergeleitet: Prüfung und Schreiben unteilbar machen

Eine einzelne Prüfung vor der Kopierschleife reicht nicht: Eine andere
Task kann den Arbeitsbereich danach übernehmen. Die gemeinsame Funktion
`copy32` prüft deshalb vor jedem 32-Byte-Schritt die Auftragsgeneration
bei kurz gesperrten IRQs. Nur bei unveränderter Generation liest und
schreibt sie diesen Schritt. Vor dem nächsten Schritt stellt sie den
ursprünglichen Interruptzustand wieder her.

Eine inzwischen übergebene Fläche erhält dadurch keine weiteren
Schreibzugriffe des alten Auftrags. Die vorhandenen Generationsprüfungen
der Aufrufer verhindern anschließend dessen Veröffentlichung. Auch die
Deskriptorkopie beim Vorausladen benutzt denselben Schutz. Eine ganze
64-KiB-Kopie läuft nicht mit durchgehend gesperrten IRQs.

## Gemessen nach der Korrektur

- Alle 71 ARM-Tests bestehen. Dazu gehören Übergaben vor dem ersten
  Schritt und zwischen Lesen und Schreiben von PCM und Deskriptor.
- Eine 64-KiB-Kopie übernimmt alle erzeugten Daten. Ihre Schreibzugriffe
  liegen innerhalb des IRQ-Schutzes; zwischen den kleinen Schritten sind
  Interrupts wieder zugelassen. Der Test begrenzt die zusammenhängend
  maskierten Befehle auf höchstens 16. Das ist keine Zeitmessung am Gerät.
- Bereits maskierte und unmaskierte Aufrufe erhalten ihren ursprünglichen
  Interruptzustand, Stack und die Register r4 bis r10, auch bei einem
  bereits veralteten Auftrag.
- Stock und Hacktribe bestehen jeweils fünf native Integritätsprüfungen.
  Der neue Übergabefall enthält vier Teilfälle je Build. Der echte
  Puffergeber wird ausgeführt; danach bleiben das Kontrollmuster und die
  gesamte Metadatentabelle erhalten. Es gibt keine nachträglichen
  Schreibzugriffe in die übergebene Fläche und keinen neuen Cache-Eintrag.

Die neue Regression liegt in
[test_sample_swap.py](../../tools/patch/test_sample_swap.py) und
[swap_integrity_cases.py](../../tools/emu/swap_integrity_cases.py).
Der native Fall gehört zur bereits eingebundenen Integritätsgruppe der
[Swap-Prüfung](../../tools/emu/swap_cases.py).

## Offen

Der Stand mit alleiniger Kopierkorrektur bestand anschließend die
vollständigen Patch-Prüfungen mit 713 Checks auf Stock und 688 auf
Hacktribe sowie 1358 Unit- und 285 Browserprüfungen. 160 Unit-Fälle mit
zusätzlichen lokalen Voraussetzungen und ein Browserfall waren
übersprungen. Diese Ergebnisse gehören zu diesem Zwischenstand;
spätere Änderungen sind gesondert vollständig zu prüfen.
Die nativen Versuche bilden eine Task-Unterbrechung mit
dem echten Puffergeber nach, keinen gleichzeitigen DMA-Schreibzugriff.
Freier RAM in allen Hardwaremodi, Klang, Durchsatz und Stimmenlebensdauer
bleiben gesonderte Gerätetests. Am Gerät wurde für diese Korrektur nichts
ausgeführt.

Der Gesamtexport, der frühe EXIT-Weg, kontrollierte Abbrüche unerfüllbarer
Ziele, die Unterscheidung von Karten- und DSP-Fehlern sowie der Wiederanlauf
verlorener Ladeaufträge werden durch diese Kopierkorrektur nicht behoben.
Die anschließende [Prüfung von EXIT und Part-Auswahl](2026-10-29-sample-swap-exit-parts.md)
beschreibt die nächsten beiden Korrekturen getrennt.
Die vollständige Sample-Speicherung und die native Einbindung der
Timeout-Helfer bleiben ebenfalls offen. Das ist keine Freigabe für 1.4.
