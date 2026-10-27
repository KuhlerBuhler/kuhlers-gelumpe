# Plugins schreiben Steps: korg.seq

Stand 2026-10-26. Kein Gerätezugriff, alles im Emulator (Firmware 2.02 mit Hacktribe, Korgs eigene 2.02 und die blaue
Electribe 2.02, eigene `SYSTEM.VSB`, ohne eigenen Flash). Am Gerät ist nichts gehört. Marker: **gemessen** (im Emulator),
**hergeleitet**, **offen**.

Wunsch: Plugins sollen in den Sequencer schreiben können, etwa für Melodie- oder Arpeggio-Generatoren. Gebaut ist API Version 9
mit drei Aufrufen (`data/script/contract.mjs`, Code in `tools/patch/script_seq.s`):

| Aufruf | schreibt |
|---|---|
| `korg.seq.setStep(part, step, note, velocity)` | Note 0 bis 127 mit Velocity 1 bis 127: An, Velocity, Trigger und den ersten Notenplatz (Note plus eins), die drei anderen Notenplätze 0. Note -1 oder Velocity 0: nur das An-Byte auf 0 |
| `korg.seq.setGate(part, step, gate)` | das Gate-Byte, 0 bis 127 |
| `korg.seq.clearPart(part)` | das An-Byte aller 64 Steps auf 0 |

## Wo die Steps liegen

**Hergeleitet aus dem Würfeln** ([Würfeln](2026-10-16-wuerfeln.md)), dort mit einem Schreibwächter gemessen und von der Gerätekarte
(`data/map/pattern.mjs`, `step.*`) getragen: Part n ab `0x800 + 0x330 * n` im Pattern-Block, Step k darin ab `0x30 + 12 * k`, je Step
An, Gate, Velocity, Trigger und vier Notenplätze. Der Test `test/script-seq.test.mjs` hält `PATTERN_STEPS` des Vertrags gegen diese
Felder der Karte. Geschrieben wird in den Block des Pattern-Objekts (`0xC06B2798`, Block 4 Byte weiter), den auch
`korg.read.patternValue(-1, …)` liest. **Gemessen:** der Zeiger der Firmware auf das Pattern (`0xC033E6A4`) zeigt in allen drei
Builds genau dorthin (`seq-schreibt-wie-der-browser`), auf der blauen Electribe über die Adresse aus `data/synth-map/`.

## Was im Emulator geprüft ist

`tools/emu/script_cases.py`, `seq_cases`, über `test/script-runtime.test.mjs`. Das Plugin ist `seqwrite` aus
`test/fixtures/script-runtime-programs.mjs`: in `ready` leert es Part 1 und schreibt die Noten 60, 62, 64 und so fort bis 74 auf jeden zweiten Step von 1 bis 15,
Gate 48; TAP schaltet Step 1 aus (Velocity 0) und Step 6 mit Note 65 an; läuft der Sequencer nach TAP über Step 9, schreibt es Step 2
mit Note 50.

| Fall | Ergebnis (gemessen, alle drei Builds gleich) |
|---|---|
| `seq-schreibt-wie-der-browser` | die 64 Steps von Part 1 im RAM nach `ready`: jedes An-Byte und jedes Byte eines Steps, der an ist, wie im Browsermodell (`src/script/hardware.mjs`) |
| `seq-tap-wie-der-browser` | nach TAP ebenso |
| `seq-pads-zeigen-die-steps` | SEQUENCER-Modus: die Pads zeigen die Steps 1, 3, 5, 7, 9, 11, 13 und 15; nach TAP ohne weitere Taste 3, 5, 6, 7, 9, 11, 13 und 15 |
| `seq-ungespeichert` | das Wort der Laufzeit für ungespeicherte Änderungen (`SC_DIRTY`, die atmende WRITE-LED) ist 1, ohne das Plugin 0 |
| `seq-spielt-was-geschrieben-ist` | PLAY, ein Takt: die ersten Note-ons auf dem MIDI-Kanal von Part 1 sind 62, 64, 65, 66, 68, 70, 72, 74 |
| `seq-schreibt-waehrend-es-laeuft` | die nächsten sind 50, 62, 64, …: der während des Laufs geschriebene Step klingt im nächsten Durchgang |

**Die Pads (gemessen).** Wie beim Würfeln zeichnen die Pads nicht von selbst neu. Die Laufzeit merkt sich in einem Wort im
Arbeitsbereich des Kartenladers (`SQ_AT`, hinter dem Eintrag von `korg.remapKey`), dass in diesem Rahmen Steps geschrieben wurden, und
schickt am Ende des Rahmens einmal die Nachricht der Firmware für den Taktabschnitt, der schon gewählt ist (Typ `0x0B` an die
Beobachter des Modells über `0xC0070688`), nur auf dem Hauptbildschirm. Gegenprobe: mit `bx lr` am Anfang dieser Funktion bleiben die
Pads nach TAP beim alten Bild (`seq-pads-zeigen-die-steps` schlägt fehl). Das Wort steht beim Einschalten auf FF; als Marke zählt nur
seine eigene Adresse, FF löst also nichts aus (`tools/patch/test_script_hw.py`).

**Kosten (gemessen, Hacktribe, SEQUENCER-Modus).** Die Nachricht samt Neuzeichnen der Pads kostet 22 129 Befehle, einmal im Rahmen
nach einem Schreiben, gleich wie viele Steps es waren; ein Rahmen ohne Schreiben kostet 5. Das läuft nach den Plugins und zählt nicht
zu ihrem Budget. **Hergeleitet** aus den Befehlen der Aufrufe: `setStep` rund 35 Befehle, `setGate` rund 20, `clearPart` rund 280;
der Vertrag rechnet 6, 4 und 30 Einheiten.

**Platz.** Der Code liegt im dritten Codebereich (`0xC0188A00` bis `0xC0188F00`) hinter den Farbseiten, 360 Byte; frei bleiben dort
192 Byte. Im ersten Bereich kommen zwei Befehle im Rahmenende dazu.

## Offen

- Am Gerät gehört: ob ein Arpeggio, das ein Plugin schreibt, klingt wie im Emulator, und ob das Neuzeichnen der Pads während der
  Wiedergabe sichtbar ruckelt.
- Schreiben, während die Firmware selbst einen Step schreibt (Aufnahme, Pad im SEQUENCER-Modus): beide schreiben einzelne Bytes, das
  letzte gewinnt; nicht eigens geprüft.
