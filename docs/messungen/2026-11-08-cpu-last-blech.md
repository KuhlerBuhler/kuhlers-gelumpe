# CPU-Last mit BLECH: was es am Gerät zu sehen gibt und was BLECH kostet

Stand 8. November 2026, develop `46ae7a61`. **Gemessen** im Emulator mit Hacktribe 2.02 (eigene Datei) und Korgs Original 2.02 rot,
jeweils ohne und mit dem ganzen BLECH-Satz (`data/patches/blech.json`). **Offline gelesen** an denselben Dateien. **Am Gerät nicht
geprüft.** Werkzeug: [arm_load.py](../../tools/emu/arm_load.py), Vorarbeiten: [CPU-Last und Laden](2026-10-18-cpu-last-und-laden.md),
[Laufzeit und Platz der Patches](2026-10-20-patch-performance.md), [Vergleichsbasis](2026-10-21-patch-effizienz-basis.md).

## Frage

Es kam die Meldung, die CPU-Last stehe mit BLECH dauerhaft auf 100 % und die Firmware tauge nicht für live. Gespielt wurde damit
aber schon live ohne Probleme. Drei Fragen: welche Anzeige sieht man da überhaupt, wie misst man die Last verlässlich, und wenn
BLECH Last zufügt, welcher Patch wie viel.

## 1. Welche Anzeige?

| Befund | Marker |
|---|---|
| Die Firmware hat keine CPU- oder Lastanzeige. In Hacktribe 2.02 und Korgs Original 2.02 kommt kein Text mit `CPU`, `Load` oder `Usage` vor; der einzige Prozenttext ist `Loading 000%` des Sample-Ladens beim Start, dazu Prozentwerte von Effektparametern | offline gelesen (`strings`) |
| Auch BLECH zeigt keine Last. Die Texte des BLECH-Menüs (`tools/patch/script_menu.s`) haben nur `%` für LED DIMMING; METER unter BOTTOM LEDS ist der Pegel des Audiosignals, keine Last | offline gelesen |
| Die Firmware hat einen Leerlauf: wenn keine Aufgabe bereit ist, setzt der Verteiler das Wort `0xC06A2894` auf 1, schläft mit Wait-for-Interrupt (`0xC0001808`) und setzt das Wort nach dem Aufwachen auf 0 (`0xC00017EC` bis `0xC0001820`). Gleicher Code auf Hacktribe und rot | offline gelesen |
| In jedem Abschnitt, in dem der Emulator die Gerätezeit bis zum nächsten Interrupt vorspringen lässt (die Firmware schläft), steht dieses Wort auf 1: 79,76 % der Zeit im Stand, 79,20 % beim Spielen, jeweils gleich viel Zeit gesprungen wie mit Wort 1 | gemessen |
| Wer in der App GELUMPE den Emulator laufen lässt, sieht im Taskmanager oder in der Aktivitätsanzeige seines Rechners eine Last. Der Emulator läuft in der App, bis er ausgeschaltet oder neu gestartet wird; beim Wechsel der Seite hält er nicht an (`site/app/emulator.mjs` schickt `/stop` nur vor einem Neustart) | offline gelesen |
| Diese Last ist bei vollem Pattern 100 % eines Kerns, mit und ohne BLECH (Tabelle unten) | gemessen |

Welche Anzeige die Meldung meint, steht nicht fest. Am Gerät gibt es keine. Die naheliegende Stelle, an der man dauerhaft 100 %
sieht, ist der Rechner mit laufendem Emulator. Das ist eine Vermutung, solange keine Rückfrage mit Bildschirmfoto da ist
(**hergeleitet**).

### Rechnerlast des Emulators

Verhältnis Gerätezeit zu CPU-Zeit des Prozesses über 5 s Gerätezeit, ohne Zählhaken, Apple-Rechner mit 10 Kernen, Lastmittel 6
durch andere Läufe (die Werte schwanken darum um 15 bis 30 %). Liegt das Verhältnis unter 1, kommt der Emulator nicht mit und
belegt einen Kern ganz; darüber bremst er auf Gerätezeit (`server.py`, `time.sleep`) und belegt den Kehrwert.

| Szene | Hacktribe | Hacktribe mit BLECH |
|---|---:|---:|
| Hauptbild, steht | 2,71, ein Kern zu 37 % | 3,49, ein Kern zu 29 % |
| ein Part spielt | 1,04, 96 % | 1,46, 68 % |
| 16 Parts spielen | 0,39, 100 % | 0,51, 100 % |

**Gemessen:** ein volles Pattern hält einen Kern dauerhaft bei 100 %, egal ob mit oder ohne BLECH. Der Unterschied zwischen den
Spalten ist die Schwankung durch die Last des Rechners, nicht BLECH (die Befehlszahlen unten sind mit BLECH höher, nicht niedriger).
**Hergeleitet:** auf einem langsameren Rechner steht schon ein einzelner spielender Part bei 100 %, und der emulierte Ablauf wird
langsamer als das Gerät.

## 2. Messen

### Im Emulator

[arm_load.py](../../tools/emu/arm_load.py) startet bis zum Hauptbild (Netzteil, Karte), schreibt ein eigenes Pattern in den RAM und
misst je Szene 2 s Gerätezeit in Scheiben zu 10 ms. Last ist das Modell aus der Vorarbeit: ausgeführte ARM-Befehle mal 5 ns über
die Gerätezeit. Das sind keine Prozente des echten Geräts (Cache, Speicherwarten und die Wartezeit auf den DSP bildet der Emulator
nicht ab), aber derselbe Maßstab für Original und BLECH. Die Befehlszahlen sind von Lauf zu Lauf gleich (bestätigt in der
[Vergleichsbasis](2026-10-21-patch-effizienz-basis.md)). Stand und ein Part liegen auf 0,02 Prozentpunkte bei den Werten dort; die
Bindungsszene liegt hier um 1,7 Punkte höher, im Original wie mit BLECH, vermutlich weil vorher das volle Pattern lief (nicht geklärt).
Ein zweiter Lauf mit dem eingecheckten Werkzeug gab für BLECH auf Hacktribe in allen Szenen dieselben Werte.

Szenen: Stand; ein Part mit einer Note auf jedem vierten Step; dasselbe in KEYBOARD; 16 Parts, Parts 1 bis 4 auf jedem Step und
die anderen auf jedem zweiten (rund 160 Noten je Takt); dasselbe in KEYBOARD; vier Noten mit langen
Bindungen über 64 Steps im SEQUENCER, der teuerste bekannte Fall der Pad-Farben.

### Am Gerät

| Weg | Stand |
|---|---|
| Eine Lastanzeige am Gerät gibt es nicht, auch nicht über SysEx | offline gelesen |
| Das Leerlaufwort `0xC06A2894` über BLECH-SysEx READ (0x61) abfragen: zeigt immer 0, denn die Antwort entsteht in der CommandTask, also während die CPU arbeitet. Taugt nicht | hergeleitet |
| Ein kleiner Haken im Zeitgeber-Interrupt, der bei jedem Tick zählt, ob das Leerlaufwort auf 1 steht, und zwei Zähler (Ticks, davon im Leerlauf) in eigenem RAM. Die App liest beide über SysEx READ und zeigt Last = 1 minus Leerlaufanteil, ein Plugin könnte sie über einen neuen Lesewert zeigen. Ein Interrupt im Schlaf trifft das Wort auf 1, also ist das eine Stichprobe der echten ARM-Last | hergeleitet, nicht gebaut |
| Die DSP-Last (der Klang, die Stimmen, die Effekte) ist damit nicht zu sehen. Dafür ist im DSP-Programm kein Zähler bekannt | offen |

## 3. Was BLECH kostet

### Gesamt

Mittel in Prozent des Modells, in Klammern das 99. Perzentil der 10-ms-Scheiben.

| Szene | Hacktribe | mit BLECH | rot | rot mit BLECH |
|---|---:|---:|---:|---:|
| Stand | 4,02 (4,7) | 4,14 (6,7) | 4,02 (4,7) | 4,14 (6,7) |
| ein Part spielt | 10,71 (11,6) | 10,81 (12,1) | 10,70 (12,0) | 10,80 (12,1) |
| dasselbe, KEYBOARD | 10,68 (11,8) | 11,03 (13,9) | 10,68 (12,4) | 11,03 (13,6) |
| 16 Parts spielen | 31,60 (51,0) | 31,92 (51,8) | 32,49 (52,9) | 32,82 (54,7) |
| dasselbe, KEYBOARD | 31,60 (51,0) | 31,90 (52,6) | 32,46 (53,0) | 32,82 (53,6) |
| vier Noten, lange Bindungen | 19,55 (22,4) | 20,17 (28,9) | 19,71 (22,9) | 20,32 (29,5) |

| Befund | Marker |
|---|---|
| BLECH kostet je nach Szene 0,1 bis 0,6 Prozentpunkte, das sind 1 bis 3 % der Arbeit des Originals | gemessen |
| Die Last kommt vom Pattern, nicht von BLECH: 16 volle Parts verdreifachen die Arbeit gegenüber einem Part, im Original wie mit BLECH | gemessen |
| Auch im dichtesten Pattern schläft der ARM im Mittel rund zwei Drittel der Zeit, in der vollsten 10-ms-Scheibe noch knapp die Hälfte | gemessen (Modell) |
| Keine Firmware-Assertion in allen 84 Messfenstern (14 Firmwares mal 6 Szenen) | gemessen |
| Der DSP ist im Emulator eine Attrappe, über die DSP-Last sagen diese Zahlen nichts | offline gelesen (`docs/hintergrund/skript-laufzeit.md`) |
| BLECH ändert das DSP-Programm nicht: im DSP-Strom (`0xC00F9E10`, `0x422A0` Byte) ist nach dem Patchen kein Byte anders, auf Hacktribe und rot (Bytevergleich der ganzen Dateien, außerhalb davon sind es rund 118000 Byte). Der fx-Katalog fügt Presets hinzu, die vorhandene Effektbausteine des DSP nutzen | gemessen (Bytevergleich), offline gelesen (`data/patches/fx-catalog.json`) |

### Je Patch

Jeder Patch einmal aus dem Satz genommen (Hacktribe), die Differenz zum ganzen Satz ist das, was er kostet. Das schließt die
Arbeit der Firmware ein, die ein Haken anstößt (zum Beispiel LED-Nachrichten), anders als das Zählen nur im Code des Patches.
`script-runtime` geht nur zusammen mit `script-runtime-stock` aus dem Satz, beide zusammen.

| Patch | Stand | ein Part | KEYBOARD | 16 Parts | 16 Parts, KEYBOARD | Bindungen |
|---|---:|---:|---:|---:|---:|---:|
| `script-runtime` (Plugins, BLECH-Menü, Tastenkürzel, Key Pads, Vorschau) | 0,13 | 0,11 | 0,11 | 0,10 | 0,14 | 0,11 |
| `pad-colors` | 0,01 | 0,01 | 0,03 | 0,03 | 0,01 | 0,52 |
| `note-assistant` | 0,01 | 0,01 | 0,26 | 0,23 | 0,21 | 0,01 |
| `load-bar` | unter 0,03 in allen Szenen | | | | | |
| `pattern-switch`, `stereo-pad`, `tap-motion`, `mfx-switch`, `beat-eighth`, `sample-errors` | unter 0,02 in allen Szenen | | | | | |

| Befund | Marker |
|---|---|
| Spitzen im Stand (99. Perzentil 6,7 statt 4,7) kommen aus `script-runtime`: ohne sie 5,0. Hergeleitet: der Vergleich des ungespeicherten Patterns alle acht Frames (`script_shortcuts.s`) | gemessen (Ursache hergeleitet) |
| Spitzen bei langen Bindungen (28,9 statt 22,4) kommen aus `pad-colors`: ohne sie 23,1. Seit der Messung vom 20.10. ist der Mehraufwand dort von 4,25 auf 0,6 Prozentpunkte gesunken (lokale Geometrie) | gemessen |
| `note-assistant` kostet in KEYBOARD zehnmal mehr, als in seinem eigenen Code läuft (0,26 gegen 0,02): die Arbeit liegt in der Firmware, die er anstößt | gemessen |
| Laufende Plugins kommen dazu: die Hintergrundszene der Vergleichsbasis (acht Apps geladen, dazu `lauflicht`, `pulsieren`, `bpmglide`, `taktblinker` laut `patch_performance.py`) liegt rund 0,7 Prozentpunkte über dem Stand mit BLECH (19,2 gegen 16,5 Millionen Befehle in 2 s, umgerechnet). Offene Apps wie Mandelbrot rechnen in jedem Frame mit Budget | hergeleitet |

## Optionen zum Senken (für 1.5, nicht 1.4.5)

| Option | Wirkung | Aufwand (geschätzt) |
|---|---|---|
| Rückfrage an die Meldenden: Bildschirmfoto der 100 %, Gerät oder Rechner, welches Pattern | klärt Frage 1 | keiner |
| App: Emulator anhalten, wenn er nicht zu sehen ist (Seite gewechselt, Fenster verborgen), und in der App sagen, wenn er langsamer als das Gerät läuft (das Verhältnis `speed` liefert `server.py` schon) | nimmt die Rechnerlast weg, die als 100 % auffällt | klein, rund ein halber Tag mit Browsertest |
| Lastmesser in der Firmware: Haken im Zeitgeber-Interrupt mit zwei Zählern, Anzeige in der App über SysEx READ, optional als Plugin-Lesewert | macht die ARM-Last am Gerät messbar | rund ein Tag mit Emulatorfall, dazu ein Gerätetest mit Zustimmung |
| `pad-colors`: Bindungen einmal je LED-Update berechnen statt je gesendeter LED | bis 0,5 Prozentpunkte und die Spitze von 29 auf 23 im Bindungsfall | mittel, zwei Tage mit Fällen auf allen drei Builds |
| `note-assistant`: in KEYBOARD nur bei geänderten Hinweisen LEDs schicken | bis 0,25 Prozentpunkte in KEYBOARD | klein bis mittel, ein Tag |
| `script-runtime`: den Pattern-Vergleich über die Frames verteilen statt alle acht Frames am Stück | glättet die 2-Punkte-Spitze im Stand, der Mittelwert bleibt | klein, ein halber Tag |

Die Firmware-Optionen sparen zusammen unter einem Prozentpunkt des Modells. Für das, was am Gerät hörbar wäre (Aussetzer, gestohlene
Stimmen), ist der DSP zuständig, und den ändert BLECH nicht. Ein Vergleich am Gerät mit demselben vollen Pattern auf Hacktribe
ohne und mit BLECH bleibt der einzige Beleg dafür.

## Offen

- **Am Gerät**: keine Zeile. Ladezeit, DSP-Last, Aussetzer und die echte ARM-Last sind dort nicht gemessen.
- **Welche Anzeige** die Meldung meint.
- **Blau** (Synth) ist in dieser Messung nicht dabei; dort laufen weniger Patches (12 statt 18), die alten Zahlen in der
  [Vergleichsbasis](2026-10-21-patch-effizienz-basis.md) zeigen dasselbe Bild.
