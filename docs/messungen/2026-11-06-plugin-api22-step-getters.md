# Plugin API 22: Steps lesen

Stand 6. November 2026. **Gemessen** im Emulator mit Hacktribe 2.02 (eigene Datei), Korgs Original 2.02 rot und blau, jeweils
mit dem BLECH-Satz (blau mit `blech-synth.json`). Fälle: `tools/emu/plugin_api22_cases.py` (läuft als Gruppe von
`remote_cases`). **Am Gerät nicht geprüft.** Die Idee und die Mirror-Messung kommen aus PR #379, hier ist nur der Teil zum Lesen
übernommen.

## Frage

Ein Plugin kann Steps seit API 9 schreiben (`korg.seq.setStep`, `setGate`, `clearPart`), aber nicht lesen, außer über
`korg.read.patternBytes` mit einem Feld. Liefern `korg.seq.getOn`, `getGate`, `getNote` und `getVelocity` die Bytes des Steps
so, wie sie im Pattern im RAM stehen, und bleiben die Pads dabei in Ruhe?

## Weg

Das Pattern-Objekt steht hinter dem Zeiger bei `0xC033E6A4`, sein Block ab +4. Part `n` beginnt bei Block + 0x800 + 0x330 * n,
seine 64 Steps ab +0x30, je 12 Byte: an, Gate, Velocity, Trigger, vier Notenplätze (Note + 1, 0 heißt leer), vier Bytes, die
die Laufzeit stehen lässt.

1. Vier Step-Records direkt in den RAM geschrieben, darunter Gate 96, 127, 255 und 40, leere Notenplätze, Note 0 (Byte 1) und
   Note 127 (Byte 128), Part 0 bis 15 und Step 0 bis 63 als Ränder. Dann je Record die vier Glue-Funktionen der Laufzeit
   aufgerufen und mit dem RAM verglichen.
2. Den Merker der Laufzeit für "in diesem Rahmen Steps geschrieben" (`SQ_AT`, danach zeichnen sich die Pads neu) auf 0 gesetzt,
   alle Getter aufgerufen, Merker und Pattern-Block (0x4000 Byte) verglichen. Danach `setGate` als Gegenprobe.
3. Ein Plugin, das im Ereignis `ready` einen Step mit allen vier Aufrufen liest, über den Compiler gebaut und geladen.

## Ergebnis

Auf Hacktribe, rot und blau gleich, ohne Assertion:

| Fall | Ergebnis |
|---|---|
| `glue_reads_the_record` | alle vier Records gelesen wie im RAM; Gate 255 kommt als 255 zurück, nicht geklemmt; leere Notenplätze -1, Byte 1 Note 0, Byte 128 Note 127 |
| `reads_mark_nothing` | Merker nach den Lesungen 0, Block unverändert; nach `setGate` gesetzt |
| `plugin_reads_by_name` | das Plugin liest an 1, Gate 255, Velocity 101, Noten 60, -1, 127, 0 und Gate 40 auf Part 15 Step 63 |

Grenzen außerhalb von Part 0 bis 15, Step 0 bis 63 und Platz 0 bis 3 beenden das Plugin mit einem Argumentfehler (geprüft in
`tools/patch/test_script_hw.py` und `test/script-seq.test.mjs`).

## Umsetzung

`tools/patch/script_seq.s`: `seq_record` war Adressrechnung und Merker in einem. Es ist jetzt geteilt in `seq_address` (nur die
Adresse des Records) und `seq_record` (Adresse und Merker). Die Getter nehmen `seq_address`, die Setter wie bisher
`seq_record`. Die Getter laufen in jedem Ereignis, wie `korg.read.patternValue`, das denselben RAM liest; sie kosten 4 wie die
anderen kurzen Lesungen.

## Gate 255

Die Getter geben das Gate-Byte unverändert zurück. Was die Werte bedeuten, steht nicht im Getter:

- Die Step-Eingabe der Firmware klemmt den Wert (0, bis 96, darüber 127) und schreibt für TIE 127. Gelesen aus dem Code auf allen
  drei Firmwares (Handler bei `0xC008DE10` auf Hacktribe und rot, derselbe Code bei `0xC007C45C` auf blau, Setter
  `0xC0049214`), nicht im Emulator gefahren.
- Die Anzeige zeigt TIE für jeden Wert über 96 (Formatierer `0xC008D124`), also auch für 255. Ebenfalls nur aus dem Code.
- Gate 127 endet im MIDI-Ausgang genau am Beginn des nächsten Steps, wie ein Gate von 96 ([Würfeln](2026-10-16-wuerfeln.md)).
- **Gemessen** im Emulator (Hacktribe 2.02, Note-on und Note-off der Engine): die Step-Wiedergabe (`0xC005FC40`) setzt bei
  Gate über 96 die Restdauer auf -1, also TIE; 127 und 255 spielen gleich. Folgt ein Step mit derselben Note und Trigger 0,
  läuft die Note ohne neuen Anschlag weiter, mit Trigger 1 schlägt sie neu an. In der Werksbank des Samplers stehen nur
  0 bis 96, 127 (300 mal) und 255 (6447 mal). PR #379 nennt 255 als TIE, das passt.

## Offen

- Gerät: die Getter am Gerät lesen lassen, auch auf einem Pattern, das von Hand mit TIE eingegeben wurde.
- Gate 255 auf der blauen abspielen (gemessen ist nur Hacktribe).
