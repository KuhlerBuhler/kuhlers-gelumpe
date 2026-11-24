# Sequencer-Timing: Auflösung, MIDI-Clock, Tempo

Hintergrund zur Frage, wie fein der Sequencer intern rechnet, wie die MIDI-Clock
entsteht und wie genau sie ist, wie die Firmware einer externen Clock folgt. Alle Adressen gelten für Korg electribe sampler, Firmware 2.02 mit Hacktribe.

Grundlage: offline gelesener Code der eigenen `SYSTEM.VSB` (Disassembly nur im Scratch, nicht im Repository),
der Emulator (`tools/emu`, Unicorn 2.1.4) mit dem eigenen Flash-Dump vom 9.10. und eine passive Messung am Gerät
(USB-MIDI, nur gelesen, nichts gesendet). Das Messskript ist
[`tools/emu/seq_timing_probe.py`](../../tools/emu/seq_timing_probe.py); es schreibt nur in den RAM des Emulators.

Markierungen: **gemessen** (im Emulator oder am Gerät ausgeführt und gesehen, dann steht "Gerät"), **offline**
(Code gelesen), **hergeleitet** (aus beidem geschlossen), **geschätzt**, **offen**.

Verwandt: [skript-laufzeit.md](skript-laufzeit.md) (Tasks, SeqTask, Haken), [patternwechsel.md](patternwechsel.md)
(Clock über den Patternwechsel), [../messungen/2026-10-12-emulator-takt.md](../messungen/2026-10-12-emulator-takt.md)
(Emulator-Takt).

## Kurzfassung

- **Intern 2304 Ticks je Viertel.** Ein Taktgeber rechnet in Pikosekunden und wird vom 1-kHz-Timer-Interrupt
  weitergeschoben. Jeder fällige Tick wird **im Interrupt am Millisekundenraster** ausgelöst, bis zu 1 ms zu
  früh. Die SeqTask holt die Ticks alle 2 ms ab und rechnet daraus 96 Sequencer-Ticks je Step.
- **Noten** kommen damit auf einem **2-ms-Raster** (Jitter 0 bis 2 ms), **MIDI-Clock** auf einem
  **1-ms-Raster** (bei 120 BPM abwechselnd 20 und 21 ms statt 20,83). Über lange Zeit läuft nichts weg: der
  Rest wird mitgetragen, der Rundungsfehler des Tempos liegt unter 10 ns je Takt.
- **Swing und Gate** sind in 1/96 Step aufgelöst, landen aber auf dem 2-ms-Raster. Gate 1 wird zu 0 oder 2 ms.
- **Clock aus**: im Interrupt erzeugt, aber über denselben DIN-Ringpuffer wie die Noten, ohne Vorrang für
  Echtzeit-Bytes. Am Gerät über USB kommt sie auf einem **2-ms-Raster** an (14 und 16 ms bei 160 BPM).
- **Clock ein**: jeder Puls setzt das Tempo neu, **ohne Glättung**, gemessen auf dem 1-ms-Raster. Eine
  saubere 120-BPM-Clock wird zu 119,05 / 125,0 BPM von Puls zu Puls, 0,5 ms Eingangsjitter zu 113,6 bis
  125,1 BPM. Die Schritte bleiben trotzdem im Mittel synchron, weil Ticks je Puls freigegeben werden.
- **Tempo**: Bedienung und Pattern in 0,1 BPM (20,0 bis 300,0), der Taktgeber intern in 0,01 BPM.

## Messen

`tools/emu/seq_timing_probe.py` fährt die Messungen im Emulator (es schreibt nur in dessen RAM): `clock` (Abstände der
MIDI-Clock je Tempo), `notes` (Noten, Swing und Gate gegen das ideale Raster) und `ext` (externe Clock). Aufruf:
`tools/emu/.venv/bin/python tools/emu/seq_timing_probe.py --vsb <VSB> --flash <Flash-Dump> clock --tempo 1200 --seconds 8`
(Tempo in 0,1 BPM). Die Messung am Gerät lief passiv: USB-MIDI am Linux-Rechner, nur lesen, 160 BPM gestoppt, 385 Clocks,
dann 60 s mit 3841 Clocks gegen die Uhr des Rechners.

## 1. Interne Auflösung

**Taktgeber.** Timer 0 löst 1000-mal je Sekunde INT 21 aus (**gemessen**, PRD 23999 bei 24 MHz). Der Handler
`0xC0025798` schiebt die Zeit des Taktgebers `0xC0340380` um 10^9 ps weiter und fragt in einer Schleife, ob der
nächste Tick fällig ist; höchstens 21 Ticks je Interrupt, genug für 300 BPM (11,5 je ms) (**offline**). Die
Periode eines Ticks steht als 64-Bit-Wert in Pikosekunden bei `+8`, das Tempo in 0,01 BPM bei `+0x2C`.

Ein Tick gilt als fällig, wenn er **vor dem nächsten Interrupt** käme. Er wird also im aktuellen Interrupt
ausgelöst, bis zu 1 ms zu früh, und der (dann negative) Rest wird für den nächsten Tick mitgetragen
(**offline**). Das Raster ist damit 1 ms, aber es läuft nichts weg (**gemessen**, siehe 3).

Pro Tick verteilt `0xC002BBA4` je nach Clock-Modus: im Modus Internal zählt er den Tick für die SeqTask
(`0xC0340370+4`), schickt alle 96 Ticks ein F8 und teilt für Sync Out. Im Modus External MIDI/USB geht der Tick
nur durch, solange der Folger ihn freigibt (siehe 2.2) (**offline**).

**SeqTask.** Sie wird alle 2,00 ms geweckt (**gemessen**, siehe auch [skript-laufzeit.md](skript-laufzeit.md)),
liest in `0xC005F2E8` die neuen Ticks, nimmt höchstens 96 je Durchlauf (der Rest kommt im nächsten) und gibt
sie an `0xC005E914`. Bei 160 BPM sind das 12 oder 13 je 2 ms, nach einer Verzögerung 19 (**gemessen**).

**Engine.** `0xC005E914` sammelt die Ticks und teilt sie durch einen Wert aus einer Tabelle je Beat: 6 (16tel),
3 (32tel), 8 (8tel-Triole), 4 (16tel-Triole). Jedes Ergebnis ist ein Sequencer-Tick; 96 davon sind ein Step
(Zähler `0xC068FC80`, Ereignisse bei 48 und 24) (**offline**). Ein Step sind also 576, 288, 768 oder 384 Ticks,
der Sequencer rechnet bei 16tel mit **384 Schritten je Viertel**. Alle Sequencer-Ticks, die in einem
2-ms-Durchlauf fällig sind, laufen in diesem Durchlauf. Die Note geht deshalb **auf dem 2-ms-Raster der
SeqTask** raus (**gemessen**: Streuung 0 bis 2 ms bei 133,3 BPM).

**Swing.** Der Wert ±48 ist in Sequencer-Ticks, also 1/96 Step: +48 verschiebt den ungeraden Step um einen
halben Step (bei 120 BPM 62,5 ms, gemessen 62,9 mit Raster). Der gerade Step wird dabei länger, der ungerade
kürzer, und das Gate rechnet mit der veränderten Länge: Gate 48 gibt bei Swing +48 rund 94 und 30 ms statt
62,5 (**gemessen**). Swing +1 (1,3 ms) wird durch das Raster zu 2,9 ms Unterschied (**gemessen**).

**Gate.** 0 bis 96 in 1/96 Step, 127 laut Korg gebunden. Gate 48 gibt bei 120 BPM 61,96 oder 63,93 ms (ideal
62,5). Sehr kurze Gates fallen in denselben 2-ms-Durchlauf wie die Note: **Gate 1 ist 0,01 ms oder 1,93 ms
lang, Gate 2 0,13 / 1,96 / 3,93 ms** (**gemessen**). Ob eine 0,01-ms-Note am DSP noch klingt, ist **offen**.

**Groove und Motion.** Die Groove-Templates verschieben je Step in 96 Einheiten (Karte `groove.offset`), das
passt zum Teiler der Engine (**hergeleitet**). Motion Sequence hat einen Wert je Step (korg-spec); wie "Smooth"
dazwischen rechnet und in welchem Takt die Werte zum DSP gehen, ist **offen**.

## 2. MIDI-Clock

### 2.1 Clock aus

Das F8 entsteht im Timer-Interrupt, alle 96 Ticks (`0xC0025DC0`), und geht über `0xC0027EE0` an DIN und USB
(**offline**). Es geht auch im Stopp raus (**gemessen**, Emulator und Gerät). Die Abstände sind ganze
Millisekunden, abwechselnd abgerundet und aufgerundet:

| Tempo | ideal | gemessen (Emulator, DIN, 8 s) |
|---|---|---|
| 20,0 | 125,0 ms | 125,0 |
| 120,0 | 20,833 ms | 20 (57x), 21 (293x) |
| 120,1 | 20,816 ms | 20 / 21 |
| 133,3 | 18,755 ms | 18 (99x), 19 (301x) |
| 160,0 | 15,625 ms | 15 (180x), 16 (302x) |
| 300,0 | 8,333 ms | 8 / 9 |

Der Jitter auf DIN ist damit bis zu 1 ms (Raster) plus die Wartezeit im Ringpuffer. DIN-Echtzeit-Bytes und Noten
gehen in denselben Ring `0xC033E5FC`, ein F8 wird hinten angehängt (**offline**). In den gemessenen Pattern kam
das nicht vor, weil die Noten eines Steps in der SeqTask erst nach dem F8 desselben Interrupts eingereiht werden
(**gemessen**, `--bank 221` mit 8 Parts: keine verspätete Clock, die MIDI-Noten selbst bis 3,9 ms hinter dem
Engine-Aufruf). Fällt ein F8 in einen vollen Ring, wartet es 0,32 ms je Byte davor (**hergeleitet**); das trifft
am ehesten Note-Offs zwischen den Clocks und dichte Akkorde bei hohem Tempo.

**Gerät über USB** (**gemessen**, 160 BPM, gestoppt, passiv am Linux-Laptop): die Abstände liegen in zwei Gruppen
um 14 und 16 ms (Anteile 19 und 81 %, passt zu 15,625 = 0,1875 x 14 + 0,8125 x 16), Streuung ±0,3 ms durch den
Host. Auf USB kommt die Clock also auf einem **2-ms-Raster** an, nicht auf dem 1-ms-Raster des Interrupts.
Woher das kommt (USB-Treiber, Abholung im 500-Hz-Takt?) ist **offen**. Über 60 s läuft das Gerät 32 ppm
langsamer als die Uhr des Laptops (deren Genauigkeit ist nicht geprüft).

### 2.2 Clock ein

Der F8-Empfang `0xC0026DDC` läuft in einer Task, nicht im Interrupt (**gemessen**). Er prüft den Clock-Modus
(Global-Byte `+44`: 0 Internal, 1 Auto, 2 External USB, 3 External MIDI, 4 External Sync, **hergeleitet**) und
ruft den Folger `0xC002C1C4` (**offline**):

1. Der Abstand zum letzten Puls wird aus der Zeit des Taktgebers gerechnet. Die wächst nur im 1-kHz-Interrupt,
   **der Abstand ist also auf 1 ms gerastert**, egal wie genau das Byte ankam.
2. Periode je Tick = Abstand / 96 (bei Sync In ein anderer Teiler), **ohne Mittelwert über mehrere Pulse**.
   Die Periode wird sofort in den Taktgeber geschrieben und das angezeigte Tempo daraus gerundet.
3. Grenzen: Pulsabstand für unter 10 BPM oder 320 bis 1000 BPM -> 120 BPM, 10 bis 20 -> 20, 300 bis 320 -> 300,
   über 1000 BPM wird ignoriert. Der erste Puls nach START oder CONTINUE setzt kein Tempo.
4. Jeder Puls gibt 96 weitere Ticks frei; der Taktgeber erzeugt sie mit der neuen Periode. Fehlen beim nächsten
   Puls welche, werden sie auf einmal nachgeholt.

Folge (**gemessen**, Emulator, External MIDI, F8 zeitgenau auf DIN):

| Eingang | Tempo je Puls in der Firmware | Mittel |
|---|---|---|
| 120,0 BPM exakt | 119,0 bis 125,0 | 120,05 |
| 125,0 BPM exakt (20 ms, ganzzahlig) | 125,0 | 124,98 |
| 133,3 BPM exakt | 131,5 bis 138,9 | 133,33 |
| 300,0 BPM exakt | 277,8 / 300,0 | |
| 120,0 BPM, ±0,5 ms Jitter | 113,6 bis 125,1 | 120,10 |

Weil Ticks je Puls freigegeben werden, bleiben die Steps im Mittel am Puls: die Noten kommen 1 bis 2 ms nach dem
Puls (**gemessen**). Innerhalb einer Clock (96 Ticks, bei 16tel 1/6 Step) laufen die Ticks aber mit dem falschen
Tempo, und alles, was das Tempo direkt liest (Tempo-Sync von Delay und LFO, Anzeige), springt mit
(**hergeleitet**; ob man das hört, ist **offen**). Im Modus External MIDI geht keine Clock auf DIN raus
(**gemessen**).

## 3. Tempo

Bedienung und Pattern speichern das Tempo in 0,1 BPM (Pattern-Offset 34, 200 bis 3000). `0xC002B988` macht
daraus 0,01 BPM, `0xC002BA7C` nimmt 2000 bis 30000 und setzt die Periode
`2604166666600 / Tempo` ps, ganzzahlig abgeschnitten (**offline**). Bei 120,0 BPM sind das 217013888 ps statt
217013888,89 (**gemessen**). Der Fehler je Tick ist unter 1 ps, über alle Tempi 20,0 bis 300,0 höchstens
**9,3 ns je 4/4-Takt** (bei 25,3 BPM) (**hergeleitet**, Rechnung). Der Timer selbst ist exakt 1 ms
(24 MHz / 24000), der Rest im Taktgeber wird mitgetragen: über 8 s bleibt die Clock bei allen gemessenen Tempi
in einem 1-ms-Fenster um die ideale Zeit (**gemessen**). Die wirkliche Genauigkeit bestimmt der Quarz: am Gerät
+32 ppm gegen den Laptop, das sind 64 µs je Takt bei 120 BPM (**gemessen**, Gerät).

## 4. Was ein Patch verbessern könnte

Alles hier ist **hergeleitet**, nichts gebaut. Reihenfolge nach Nutzen.

1. **Clock ein genau messen und glätten.** Den Pulszeitpunkt nicht aus dem 1-ms-Taktgeber nehmen, sondern aus
   einem freilaufenden Zähler (Timer 0 zählt mit 24 MHz, der Timer bei `0x01F0D000` mit 150 MHz und 1 s
   Periode, sein Interrupt ist aus; beides **gemessen** im Emulator) und die Periode über 24 Pulse mitteln oder
   mit einer einfachen PLL nachführen. Das nimmt den Sprung 119/125 BPM weg (Raster 41 ns statt 1 ms). Eingriff:
   der Folger `0xC002C1C4`, ein Haken.
2. **F8 am Ring vorbei.** Ist der DIN-Sender frei, das F8 direkt ins Senderegister schreiben, sonst an den Anfang
   des Rings. MIDI erlaubt Echtzeit-Bytes zwischen den Bytes einer Nachricht. Nimmt die Wartezeit hinter Noten
   (0,32 ms je Byte) weg, nicht das 1-ms-Raster.
3. **Feineres Raster für Ticks und Clock.** Den Taktgeber in einem eigenen, schnelleren Timer-Interrupt rechnen
   (zum Beispiel 10 kHz, Zuwachs 10^8 ps), die übrigen Aufgaben im 1-kHz-Handler (Zähler, Sync-Pulslänge
   und zwei weitere Aufrufe, nicht gelesen) unverändert lassen. Die Clock auf DIN käme dann auf 0,1 ms genau. Risiko: mehr Interruptlast,
   und für Noten bringt es nichts, solange die SeqTask im 2-ms-Takt abholt.
4. **SeqTask im 1-ms-Takt.** Halbiert den Notenjitter (2 ms -> 1 ms). Die SeqTask hängt am 500-Hz-Takt der
   PeriodicTask; ein schnellerer Takt kostet CPU in einer Task mit Priorität 2 (siehe
   [skript-laufzeit.md](skript-laufzeit.md)). Ob das hörbar besser ist, hängt davon ab, wann der DSP die Note
   auslöst (**offen**).
5. **Mindest-Gate.** Note-Off nicht im selben Durchlauf wie die Note-On schicken (Gate 1 und 2 werden zu
   0,01 ms). Klein, in der Engine.

Feinere Swing- oder Gate-Werte als 1/96 Step brauchen nichts davon, die Auflösung ist schon da; begrenzt wird
alles vom 2-ms-Raster.

## 5. Am Gerät messen (offen)

Diese Schritte sind am Gerät noch nicht gelaufen. Die DIN-Clock geht ohne Bedienung (die Clock läuft auch im Stopp), nur lesen:

1. **DIN-Clock:** ein USB-MIDI-Interface am Linux-Laptop an MIDI OUT, `/dev/snd/midiC<n>D0` lesen und die
   F8-Abstände wie oben auswerten. Erwartung: ganze Millisekunden (15/16 ms bei 160 BPM), nicht 14/16 wie auf USB.
2. **Noten-Jitter:** braucht PLAY durch den Nutzer und ein Pattern mit Noten auf jedem Step; dann Note-On gegen
   F8 auf DIN. Erwartung: 0 bis 2 ms Streuung.
3. **Clock ein:** braucht Clock Mode External MIDI (Einstellung durch den Nutzer); dann vom Laptop nur F8, FA, FC
   schicken (zum Beispiel exakt 120 BPM) und das angezeigte Tempo beobachten. Erwartung: es springt zwischen
   119,0 und 125,0.
