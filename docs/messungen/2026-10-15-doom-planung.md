# Doom Startmodus: Prüfung vor der Umsetzung

**Historischer Befund vor der Integration von `integ/overnight`.** Die hier
genannten BLECH-v8-Artefakte und alten Speicheradressen sind kein aktueller
Gerätekandidat. Neue Firmware muss separat gebaut und geprüft werden.

Stand: 15.10.2026. Kein Gerätezugriff, keine Firmware- oder Runtimeänderung.
Geprüfter Repo-Stand: `3fc6f58`, Branch `feature/script-runtime`.

## Auftrag

Der Auftrag hat die frühere App-/Skriptvariante ersetzt: Originales Doom soll
über eine Tastenkombination beim Einschalten als alternative Anwendung
auf der Electribe starten. Der bestehende Sprachauftrag ist abgeschlossen.

## Befunde und Grenze

Aus Code gelesen: Die vorhandene Startmatrix, EXIT und Rettungsmodi sind
in `tools/emu/bootmap.py` beschrieben. Der Startbildhaken liegt bei
`0xC002ADAC` nach den Rettungsentscheidungen, ist aber bereits belegt.
Eine unabhängige zweite Änderung derselben Stelle wäre eine Kollision.

Bestehender Messbeleg: die damalige Startbildmessung
beschreibt dort noch keinen laufenden RTOS Zeitgeber und den späteren
Sample-/Dateilader im Taskkontext. Deshalb ist ein SD-Aufruf aus einem
frühen Doom-Sprung nicht automatisch funktionsfähig.

Hergeleiteter Vorschlag: Der unveränderte Bootloader lädt BLECH. BLECH
wählt Doom oder die Sampleranwendung und startet im Doom-Zweig nur die
benötigten Dienste. Ob diese Trennung tatsächlich gelingt, ist offen und
die erste Abnahme. Ein vollständig eigenständiger Bootloader gehört nicht
zu diesem Vorschlag.

Aus Code gelesen: Display 128 mal 64 Pixel, ein Bit je Pixel; die
Skript-VM hat einen gemeinsamen 128 KiB Pool und 5 ms Rahmenbudget.
Original-Doom soll als natives ARM Programm außerhalb dieser VM laufen.
Der Emulator bildet zwar 128 MiB ab; daraus folgt keine RAM-Freigabe.
Enginegröße, freier Heap, Bildrate, Treiberstart und Ton sind unbestätigt.

Externe Primärquelle: [doomgeneric](https://github.com/ozkl/doomgeneric)
stellt eine portable Doom-Basis bereit. Die
[Plattformschnittstelle](https://github.com/ozkl/doomgeneric/blob/master/doomgeneric/doomgeneric.h)
nennt Bildausgabe, Schlafen, Zeit und Tasten. C Laufzeit, Dateizugriff und
Speicherverwaltung müssen zusätzlich für die Zielumgebung funktionieren.
Kein Quellcode und keine Spieldaten wurden daraus übernommen.

## Ausgeführte Prüfung

Gemessen, Befehl:

```sh
node --test test/blech-set.test.mjs
```

Exit 0: zwei Tests bestanden, ein Test ohne `E2_VSB` übersprungen.
Geprüft sind Patchreihenfolge, Hookverträglichkeit und Übereinstimmung des
Runtimebuilders mit dem eingecheckten Patch. Das Anwenden auf ein
Firmwareabbild wurde in diesem Lauf nicht geprüft. Das ist eine Baseline,
kein Doom-Nachweis.

Vollständiges Log:
`$doom_plan_artifacts/blech-baseline.log`.
`git diff --check` ohne Befund; Plan und Tracker werden zusätzlich auf
gültiges JSON und verbotene Gedankenstriche geprüft.

## Nächste Entscheidung

Der konkrete Plan liegt in
der internen Startmodusplanung mit zugehörigem JSON-Tracker. Vor Produktcode ist der native Startpfad abzustimmen: Er betrifft
Startcode und Patchbau außerhalb der Skript-VM, für die eine
ausdrückliche Stopp-Regel galt. Es wurde nichts gelöscht, keine
Git-Historie geändert und nichts gepusht.
