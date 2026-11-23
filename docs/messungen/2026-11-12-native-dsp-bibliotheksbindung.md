# Native DSP-Aufträge und die Sample-Bibliothek

## Gemessen im Emulator und mit erzeugten Daten

Die [Zusammenführung auf der Grundlage von 1.4.5](2026-11-11-sample-swap-develop-final.md)
hat einen falschen DSP-Abbruch gezeigt: Beim Stock-Dauerwechsel blieb der
Task gleich, ebenso Bibliotheksgeneration, Modus und Sitzung. Nur die Epoche
eines unabhängigen Dateilesers wechselte von 328 auf 329. Der laufende native
Schreibauftrag nach `0xC00142D8` traf DSP-Register bei `0xFF900018` mit
64 Halbwörtern. Die Zeitgrenze und das Pollbudget waren nicht erschöpft.

Zwei gezielte Teilfälle bestätigten den Fehler vor der Korrektur erneut:
Eine fremde Leseepoche konnte den Registerauftrag sowohl nach dem
Ressourcenerwerb als auch während des Protokolls abbrechen.

Nach der Korrektur bestehen 49 gezielte ARM-Prüfungen. Registerzugriffe
bleiben bei fremden Leseepochen gültig. Sample-Daten und der eigene
Swap-Schritt brechen dagegen weiterhin ab. Gegenproben prüfen beide
Richtungen an den Bereichsgrenzen, Adressüberlauf, Taskwechsel, eine fremde
Schrittbesitzerschaft, gesperrte IRQs und die bestehende Zeitgrenze.
Der Stock-Dauerwechsel besteht mit acht Wechseln und identischen PCM-Daten.

Der Patch lässt sich mit dem vollständigen BLECH-Satz auf beide roten
Original-Firmwares anwenden. Seine Erzeugung aus Stock und Hacktribe liefert
dieselbe Patchdatei. Die kombinierte Prüfung des vollständigen Patchsatzes
mit Swap-, SysEx- und Startfällen besteht:

| Prüfung | Bestanden | Ausgelassen |
|---|---:|---:|
| Stock | 257 | 0 |
| Hacktribe | 257 | 0 |
| Synth | 75 | 0 |
| Unit | 1590 | 172 |
| Browser | 339 | 1 |

Die Synth-Prüfung ist eine Gegenprobe für gemeinsame Änderungen. Sample Swap
selbst bleibt auf die beiden roten Firmwarefassungen begrenzt. Die unabhängige
Quellprüfung ergibt keinen Befund; die sieben erzeugten Codeabschnitte stimmen
mit dem aktuellen Builder überein.

## Hergeleitet

Die nativen Sample-Funktionen halten die DSP-Adresse bei `FP-16` und die
Anzahl der Halbwörter bei `FP-22`. Die Ressourcenaufrufe liegen bei
`0xC0014248` und `0xC00142D4`. Die bestehende Prüfung der Originalbytes
sichert die verwendeten Frames beider roten Firmwarefassungen ab.

Die Bibliotheksbindung gilt weiterhin für jede native Spanne, die den
bisherigen User-Sample-Bereich `[0x00365EC0, 0x01C65EC0)` überschneidet,
und für den eigenen Swap-Schritt. Ein überlaufender Bereich oder ein anderer
Aufrufer bleibt ebenfalls streng gebunden. Die Grenzen beschreiben den
bisher verwendeten Bereich, keinen neu gemessenen DSP-Ausbau.

Nur die beiden bekannten nativen Sample-Funktionen dürfen bei einer Spanne
vollständig außerhalb dieses Bereichs unabhängig von fremden Datei- und
Cache-Epochen arbeiten. Task, IRQ-Zustand, Ressourcenbesitz, terminaler
Fehlerzustand, Zeitgrenze und Pollbudget bleiben geschützt.

Der Ressourcenerwerb gibt dieselbe Bindung an den Transaktionskontext weiter.
Die Entscheidung liegt im bereits reservierten Stackbereich bei Kontextoffset
120; zusätzlicher globaler RAM wird nicht belegt. Wartefristen werden nicht
erhöht und ein gesetzter DSP-Fehler wird nicht zurückgesetzt.

## Wiederholen

Die Originaldateien bleiben außerhalb des Repositorys. Die direkten
ARM-Prüfungen benötigen keine Originaldaten:

```sh
PYTHONPATH=tools/patch:tools/emu tools/emu/.venv/bin/python -m unittest test_native_dsp_scope test_native_dsp_acquire
GELUMPE_LOAD_GATE=off GELUMPE_JOBS=6 node tools/verify-patches.mjs --cases swap_cases,sysex_cases "$E2_STOCK_VSB" "$E2_VSB" "$E2_BLUE_VSB"
GELUMPE_LOAD_GATE=off GELUMPE_JOBS=1 npm test -- --test-concurrency=1
GELUMPE_LOAD_GATE=off GELUMPE_JOBS=2 npm run test:e2e
```

## Offen

Der Emulator besitzt weder Klang noch DMA und bildet den DSP nur nach.
Gerätetests mit genau der kombinierten Firmware bleiben erforderlich:
Start, Auswahl bisher ungeladener Samples, wiederholte Pattern- und
Chain-Wechsel, ausklingende Stimmen, Import, Bearbeiten und WRITE.
Die vollständige RAM- und DMA-Freigabe sowie die Releasefreigabe folgen
daraus nicht. Vor einem Release sind außerdem der vollständige Emulatorlauf
und die Erneuerung von `data/patches/verified.json` nötig; die hier gewählten
Prüfgruppen schreiben diese Datei nicht. Bei dieser Prüfung wurde nicht auf
das Gerät zugegriffen.
