# Idee 52: Ton im Emulator

Stand: erster Versuch gemacht (24.10.), Empfehlung: erst DSP-Patches prüfen, dann offline rendern, nicht live; Aufwand für Klang in Wochen. Zurück zu den [Ideen](../ideen.md).

Den echten DSP-Code im Blackfin-Simulator aus gdb laufen lassen, dazu Modelle für Host-Port, Audioausgang und DMA. Kein DSP-Patch, nur Emulation. Einzelne Rechenfunktionen laufen im Simulator schon ([DSP, erster Blick](../hintergrund/dsp-erster-blick.md)).

## Erster Schritt

Ein Versuch von etwa einem Tag: eine Effekt-Schleife im Simulator laufen lassen und messen, wie viel langsamer als Echtzeit sie ist. Danach entscheiden, ob live oder nur gerendert wird.

## Kandidaten für den Kern

- Der GNU-Simulator aus gdb (der Stand heute).
- Der QEMU-Port für Blackfin von Mike Frysinger (github vapier/qemu). Er übersetzt den Befehlskern des GNU-Simulators nach TCG, also mit Übersetzer statt Interpreter. Systememulation ist laut Autor unzuverlässig; wir bräuchten nur den Prozessor, wie Unicorn beim ARM.

Im Versuch beides messen. Eine GPU hilft beim Emulieren nicht (eine Befehlskette, nicht parallel).

## Versuch vom 24.10.

Ein Tag, Firmware 2.02 mit Hacktribe (`hacktribe-original.VSB`), alles offline. Gemessen auf einem Apple M5, ein Kern.

Werkzeug, im Repository nur die Skripte, keine Korg-Daten:

- `tools/dsp/dsp_extract.py VSB OUTDIR` zerlegt den Boot-Strom in Speicherbereiche (ersetzt das verlorene Arbeitsskript gleichen Namens).
- `tools/dsp/bfsim_bench.py OUTDIR ADRESSE` ruft eine DSP-Funktion N-mal auf einem synthetischen Kontext auf, liest CYCLES um jeden Aufruf, misst die Wanduhr und bildet eine Prüfsumme über den Speicher danach. Mit `--qemu` dasselbe im QEMU-Port. Wie die Simulatoren gebaut werden, steht im Kopf des Skripts.

### Was herauskam

1. **Der GNU-Simulator rechnete auf dem Mac falsch.** Das Makro `SIGNEXTEND` in `sim/bfin/bfin-sim.c` schiebt einen 32-Bit-Wert um `64 - n` Bit. Auf x86 geht das zufällig gut, clang auf arm64 faltet es weg: `R1 = 7 (X)` setzte R1 nicht auf 7. Das ist die Ursache für den Umweg "Syscalls nur mit 32-Bit-Befehlen" in [DSP, erster Blick](../hintergrund/dsp-erster-blick.md) 1.4 und vermutlich auch für das Hängen beim geschützten Schreiben: nach der Korrektur läuft `0x1F0E54C` 63-mal durch (152 Takte) und bricht erst ab, wenn die Warteschlange voll ist und der Code Peripherie anfasst, die fehlt. Der QEMU-Port hat dasselbe Makro, beide sind korrigiert.
2. **Eine Effekt-Schleife ist pro Sample gebaut, nicht pro Block.** Die Audioschleife `0xFFA0010C` wartet auf ein Semaphor, liest dann 4 Frames zu je 16 Byte aus dem DMA-Puffer und ruft für jeden Frame einmal `0xFFA0141A` (alle Stimmen, alle Parts, Master). Insert- und Master-Effekte rechnen je Aufruf ein Sample. Ein DSP-Block wären damit 4 Samples, 83 µs bei 48 kHz, nicht 64 oder 128.
3. **Takt des DSP:** der Stufe-1-Code ruft `bfrom_SysControl` mit PLL_CTL `0x2A00` (MSEL 21) und PLL_DIV 5, danach 4. Bei 25 MHz Quarz wären das 525 MHz Kern und 131 MHz Bus, bei 24,576 MHz 516 MHz. Das Budget ist damit rund 10 900 Takte je Sample.
4. **Kosten je Sample** (Simulator-Takte inklusive Aufruf, Näherung des Simulators ohne Speicherwartezeiten): Insert-Effekte 129 bis 206 (Filter 129, Limiter 158, Short Delay 190, Chorus 182, Phaser 200, Distortion 201, Flanger 206), Filterkern electribe-Familie 149, Master-Effekte 374 bis 444 (Chorus 374, Mod.Delay 391, Room Reverb 431, Hall Reverb 444). Alle mit synthetischem Kontext: geprüft ist nur, dass die Funktionen sauber zurückkehren und von Aufruf zu Aufruf gleich viele Takte brauchen.
5. **Geschwindigkeit der Simulatoren** (je Aufruf, Rahmen des Prüfstands abgezogen):

| Funktion | DSP-Takte ohne Aufruf | DSP bei 525 MHz | GNU-Simulator | QEMU-Port |
|---|---|---|---|---|
| Short Delay (Insert) | 178 | 0,34 µs | 20,5 µs (60x) | 0,39 µs (1,1x) |
| Filterkern electribe | 137 | 0,26 µs | 22,7 µs (87x) | 0,30 µs (1,1x) |
| Chorus (Insert) | 170 | 0,32 µs | 18,2 µs (56x) | 0,39 µs (1,2x) |
| Distortion (Insert) | 189 | 0,36 µs | 44,0 µs (122x) | 0,59 µs (1,6x) |
| Hall Reverb (Master) | 432 | 0,82 µs | 71,2 µs (87x) | 1,18 µs (1,4x) |

Der GNU-Simulator schafft 4 bis 9 Millionen DSP-Takte je Sekunde, der QEMU-Port 320 bis 460 Millionen. Auf einen Block von 64 Samples (1,33 ms Echtzeit) umgerechnet braucht ein einzelner Insert im GNU-Simulator schon 1,2 bis 2,8 ms, der Hall 4,6 ms. Im QEMU-Port sind es 19 bis 75 µs.

6. **Ganzer Patch (Schätzung):** pro Sample etwa 500 Takte fest (Audioschleife, Mischer), je aktivem Part etwa 300 Takte Rahmen plus Filterkern plus Insert (zusammen 600 bis 700), dazu Master 370 bis 450 und die Stimmen. 16 Parts plus Master ergeben 10 000 bis 15 000 Takte je Sample, also ungefähr das ganze Budget. Daraus: eine Sekunde Klang braucht im GNU-Simulator 1 bis 2 Minuten, im QEMU-Port 1,1 bis 1,6 Sekunden. Ein leichter Patch (ein Part, ein Insert, Hall, rund 1 800 Takte je Sample) braucht im GNU-Simulator 10 bis 20 Sekunden je Sekunde Klang, im QEMU-Port 0,2 Sekunden.
7. **QEMU-Port (vapier/qemu, Zweig `bfin`, Stand Januar 2024, auf QEMU 8.2):** baut auf dem Mac in rund 10 Minuten (ohne Audio, vmnet und Cocoa; Objective-C-Compiler ausdrücklich angeben). Nur das Board BF537 ist da, für den reinen Prozessor reicht es. Es fehlte ein Befehl, den 5 von 13 Effekten benutzen (`ASHIFT ... BY Rx.L (S)`), nachgerüstet als Hilfsfunktion. Danach rechnen Short Delay, Distortion, Chorus und (beim ersten Aufruf) Hall bit-gleich zum GNU-Simulator, der Filterkern schon beim ersten Aufruf nicht, der Hall nach 1000 Aufrufen auch nicht mehr. Welcher der beiden richtig rechnet, sagt nur das Gerät. CYCLES zählt im QEMU-Port Nanosekunden, keine Takte.

### Was ein voller DSP-Emulator braucht (Skizze, nichts gebaut)

| Teil | Was | Aufwand (Schätzung) |
|---|---|---|
| Kern | GNU-Simulator als Bibliothek (`sim_open`, `sim_resume`, `sim_read`, `sim_write`) über ctypes aus `tools/emu` steuern; QEMU nur, wenn live gewollt ist, dann als eigener Prozess mit fehlenden Befehlen und einem Vergleich gegen den GNU-Simulator | 2 bis 4 Tage, QEMU Wochen |
| Laden | Den Strom nicht über SPI1 und Boot-Rom schicken, sondern mit `dsp_extract.py` direkt in den Speicher legen und bei `0xFFA00000` starten (Stufe 1 überspringen). Nebenbei die Bytes prüfen, die der ARM in `0xC0011AB8` senden würde (Kopf-XOR, `0xAD`, FINAL-Block), das schließt die Lücke aus Abschnitt 4.2 von [DSP, erster Blick](../hintergrund/dsp-erster-blick.md) auch ohne Klang | 1 bis 2 Tage |
| Host-Port | Den Briefkasten in `machine.py` (`dsp_read`, Steuerwörter `0xA9`/`0xAB`) auf Lese- und Schreibzugriffe im DSP-Speicher umlenken; im Simulator ein kleines Gerät für HOSTDP (`0xFFC03404` Bit 4 fragt die Audioschleife ab) und den Bereit-Ausgang (GPIO, `0xC00171A8` Bit 12 auf der ARM-Seite) | 2 bis 4 Tage |
| DMA und SPORT | Der GNU-Simulator hat DMA, aber kein SPORT. Ein SPORT-Modell, das alle 4 Frames den Puffer abholt und den Interrupt hebt, der das Semaphor der Audioschleife setzt | 3 bis 5 Tage |
| Zeit | ARM (Unicorn, 5 ns je Instruktion) und DSP im Gleichschritt, je DSP-Block (83 µs, rund 43 700 DSP-Takte) eine Scheibe | 2 bis 3 Tage |
| Samples | Die Stimmen lesen Samples aus dem SDRAM des DSP, die der ARM über den Host-Port hinschreibt. Ob das beim Start oder beim Patternwechsel passiert und wie viel, ist offen | offen |
| Ausgabe | Ausgangswörter je Frame (Stereo, 32-Bit-Plätze) in eine WAV schreiben | 0,5 Tage |

Zusammen 3 bis 5 Wochen bis zu einer offline gerenderten WAV, ohne die Samples.

### Empfehlung

- **Live:** nein. Der GNU-Simulator ist 56- bis 122-mal langsamer als der echte DSP. Der QEMU-Port käme in die Nähe von Echtzeit, rechnet aber nicht überall gleich, hat Lücken und bräuchte Peripherie in C, dazu die Kopplung zweier Prozesse.
- **Offline rendern:** machbar mit dem GNU-Simulator, eine Sekunde Klang in 10 Sekunden (leichter Patch) bis 2 Minuten (voller Patch). Ein Pattern von 8 Sekunden mit allen Parts wäre in 10 bis 15 Minuten fertig. Das ist der Weg, wenn es Klang sein soll.
- **Zuerst:** nur DSP-Patches prüfen. Mit `bfsim_bench.py` lässt sich eine geänderte Funktion gegen die originale stellen: gleiche Prüfsumme heißt gleiches Ergebnis, die Taktzahl zeigt, wie viel vom Budget sie kostet. Dazu die Prüfung des Boot-Stroms. Das kostet 1 bis 2 Tage und deckt das ab, was bei einem DSP-Patch am meisten weh tut.

### Belegtabelle

| Behauptung | Status | Beleg |
|---|---|---|
| Strom bei `0xC00F9E10`, 157 Blöcke, alle Kopf-XOR stimmen, 6 Speicherbereiche (L1 Code `0xFFA00000` +`0xBFF8`) | gemessen | `tools/dsp/dsp_extract.py VSB OUT` |
| `SIGNEXTEND` im GNU-Simulator (gdb 14.2) liefert auf arm64 mit clang falsche Werte für 16-Bit-Konstanten | gemessen | Testprogramm `R1 = 7 (X); [P1] = R1;` dann `exit([P1])`: Rückgabe 0 statt 7, nach der Korrektur 7 |
| Geschütztes Schreiben `0x1F0E54C` läuft im korrigierten Simulator, 152 Takte, ab dem 64. Eintrag Busfehler | gemessen | `bfsim_bench.py OUT 1f0e54c --calls 63 --reg R0=0xFF800B9C --reg R1=0x7fffffff`, mit `--calls 64` Busfehler |
| Das frühere Hängen kam von `SIGNEXTEND` | hergeleitet | der alte Build ist nicht mehr da, nicht nachgestellt |
| Insert-Effekte 129 bis 206, Master-Effekte 374 bis 444 Takte je Aufruf, Filterkern 149 | gemessen (Simulator) | `bfsim_bench.py OUT ADRESSE --calls 5 --reg R0=soup`, Adressen aus der Deskriptortabelle SDRAM `0x4C30` (`+0x18`) |
| Diese Taktzahlen gelten für den echten Kontext | offen | synthetischer Kontext, Simulator ohne Cache und SDRAM-Wartezeit |
| GNU-Simulator 4 bis 9, QEMU-Port 320 bis 460 Millionen DSP-Takte je Sekunde | gemessen | `bfsim_bench.py` mit `--calls 200000` (Simulator) und `--calls 2000000 --qemu` (QEMU), Lauf mit `--calls 1` und der leere Aufruf `ffa0010a` abgezogen |
| 4 Frames je Block, ein Aufruf von `0xFFA0141A` je Frame | hergeleitet | Disassembly `0xFFA001B0` bis `0xFFA00236` (Zähler bis 4, Zeiger + 16), offline gelesen |
| DSP-Kern rund 525 MHz | hergeleitet | Stufe 1 (Block 2) setzt PLL_CTL `0x2A00`; Quarzfrequenz offen |
| Ganzer Patch 10 000 bis 15 000 Takte je Sample | hergeleitet | Befehle gezählt (`0xFFA0141A`: 66 + 393 fest, 313 je Part, 58 je Stimme) plus gemessene Kerne; Kosten der Stimmen offen |
| QEMU-Port baut auf dem Mac, fehlender Befehl `ASHIFT ... (S)` | gemessen | Abbruch "unhandled exception type=33" bei `0x12BD2`, `0xFFA0923A`, `0xFFA07936`, `0xFFA08780`, `0x1C79C0E` |
| QEMU rechnet Short Delay, Distortion, Chorus gleich, Filterkern nicht | gemessen | Prüfsumme in `bfsim_bench.py` mit und ohne `--qemu` |
| Welcher Simulator beim Filterkern richtig liegt | offen | braucht das Gerät |
| Aufwand der Teile | geschätzt | Urteil, nichts davon gebaut |

Hinweis zu [DSP, erster Blick](../hintergrund/dsp-erster-blick.md) 2.6: die Rechnung dort nimmt Blöcke von 64 bis 128 Samples an. Wenn der DSP-Block 4 Samples hat, stimmt die Herleitung der 100 ms über "ein Frame je Audioblock" nicht mehr; wie oft der Frame-Task Rechenzeit bekommt, bleibt offen.
