# Patch-Effizienz: Platz und Rechenzeit der Patches

Was über Platzbedarf und Rechenzeit der eigenen Patches feststeht, welche Optimierungen gebaut sind und welche Wege
bewusst nicht gegangen werden. Alle Zahlen sind ARM-Befehle oder Bytes, **gemessen im Emulator**, keine Millisekunden
am Gerät. Die Rohnotizen stehen in der Git-Historie, zum Beispiel
`git show 03c7827adc7b:docs/messungen/2026-10-20-patch-performance.md`. Die Zahlenbasis liegt in
[2026-10-21-patch-effizienz-basis-zahlen.json](../messungen/2026-10-21-patch-effizienz-basis-zahlen.json), weitere
Einzelbefunde in [ARM-Optimierungen](../messungen/2026-10-20-arm-optimierungen.md), das Speicherbudget in
[Firmware-Speicherbudget](../messungen/2026-11-20-firmware-speicherbudget.md).

## Plugin-Laufzeit

### Prüfpuffer nur bis zur Codelänge vorbereiten (gebaut)

Beim Laden eines Plugins leert die Prüfung der [VM](../glossary.md#vm) Arbeitsbereiche (Befehlsgrenzen, Zustände der
Funktions- und Ereignisprüfung). Die fünf Füllaufrufe in `tools/patch/script_vm.s` nehmen die geprüfte Codelänge
`RT_CODESIZE`, nicht die Obergrenze `LIM_CODE` (16384 Byte). `LIM_CODE` steht nur noch in den Grenzprüfungen des Kopfs.

- Gewinn: Laden aller elf eigenen Presets 3498105 statt 16068540 ARM-Befehle (-78,23 %), die Laufzeit wird 12 Byte
  kleiner, das reservierte RAM bleibt gleich. Der erste Prototyp mit zehn Presets: 3558598 statt 15148903 (-76,5 %).
- Warum das trägt: Block- und Codelänge, Größenlimits, Prüfsumme und Abschnitte sind vor der Codeprüfung schon geprüft. Der
  ungenutzte Rest der Prüfpuffer wird nie gelesen, muss also nicht geleert werden. Laufzeitstart, neue Plugin-Einträge und
  Plugin-Variablen werden weiter ganz vorbereitet, Prüfsummen, Fehlercodes und Grenzen sind unverändert.
- Grenze: das betrifft nur das Prüfen und Eintragen von Blöcken, die schon im RAM liegen. SD-Lesen, Startdauer und
  Sample-Import werden dadurch nicht schneller.

Quelle: Messung 2026-10-20/patch-performance, Messung 2026-10-21/plugin-pruefung

### Operanddecoder ohne Stack (gebaut)

`decode_operands` in `tools/patch/script_vm.s` liest die Operanden eines Skriptbefehls nur mit frei verwendbaren
ARM-Registern, ohne Registersicherung auf dem Stack. Die vier Aufrufer behalten ihren Registervertrag. Operanden werden
byteweise gelesen, ein unausgerichteter Befehlsanfang bleibt also gültig.

- Prüfmatrix: alle 34 Opcodes, neun Randwerte, vier Ausrichtungen, 2376 Vektoren. Jeder Vektor prüft r4 bis r11,
  Stackpointer, Rücksprungadresse und die genaue Liste der gelesenen Bytes.
- Gewinn: im Mittel 17,61 statt 22,64 ARM-Befehle je Aufruf (-22,22 %), höchstens 22 statt 30, 0 statt 9504 Schreibzugriffe
  in der Matrix, VM-Code 32 Byte kleiner (11620 auf 11588), RAM unverändert. In den Apps: Mandelbrot und Life rund 5,8 %
  weniger Laufzeit-Befehle (1,6 % des ganzen Messfensters), Pong 3,0 % (0,18 %).
- Der native Lader lehnt jede abgeschnittene Operandenfolge und alle 222 nicht vergebenen Opcodes ab.

Quelle: Messung 2026-10-21/patch-effizienz-decoder

### Die 160 KiB Prüfarbeitsbereiche

Die Prüfung der Plugins belegt 163840 Byte Arbeitsbereiche, die beim Ausführen der Plugins nicht gebraucht werden. Sie
sind trotzdem nicht frei verfügbar: jeder Import braucht sie wieder. Sie dürfen nicht einfach auf Variablen, laufende
Plugins, Dateipuffer oder die doppelte Einstellungsdatei gelegt werden. Nötig wäre ein ausdrücklich besessener
temporärer Bereich oder eine andere Prüfdatenstruktur, mit sicherem Fehlerfall während des Imports. Eine freigebbare Größe
ist nicht nachgewiesen. Entscheidung: so lassen, bis ein solcher Entwurf da ist.

Quelle: Messung 2026-10-20/patch-performance, Messung 2026-10-20/patch-effizienz-ausgang

## Pad-Farben: der eine Engpass im Betrieb

Im laufenden Betrieb war `pad-colors` der einzige echte Engpass. Beim Senden einer Pad-LED ruft der Patch `pc_follow`. Das
untersucht die nachfolgenden Pads, deren gebundene Noten wieder rückwärts und vorwärts verfolgt werden. Die vorhandene
Unterdrückung gleicher LED-Nachrichten spart Übertragungen, aber nicht diese Rechnung. Gemessen (Hacktribe, vier Noten mit
langen Bindungen, SEQUENCER): 19437547 Befehle in 2 s für `pad-colors`, bei normaler Wiedergabe 44502.

**Bindungs-Cache (gebaut):** `pc_chord` legt sein Ergebnis je Pad ab, solange ein Durchlauf durch `pc_tail` läuft. Der erste
Aufruf im Durchlauf bildet einen Schlüssel aus Taktabschnitt, Adresse des Parts und dessen 0x330 Byte (Voice Assign und alle
64 Steps). Weicht er ab, gelten alle Ergebnisse als ungültig. Außerhalb von `pc_tail` wird nichts behalten. Kosten: 80 Byte
Zustand, Code 3748 statt 3492 Byte. Wirkung (`tools/emu/arm_load.py`, Hacktribe): Anteil von `pad-colors` 0,174 statt
0,617 Prozentpunkte, p99 je 10 ms 24,5 statt 29,4 %. Korg rot und Synth gleich. In den anderen Szenen steigt der Anteil
um 0,001 bis 0,003 Punkte.

Quelle: Messung 2026-10-20/patch-performance

## SysEx-Puffer: wie groß er sein muss

Der Nachrichtenpuffer von [BLECHTRIBE SysEx](../glossary.md#blechtribe-sysex) ist 37632 Byte groß (36,75 KiB), von
`0xC0191100` bis `0xC019A400` (`BUF_END`). Hergeleitet, im Code als `BUFFER_REQUIRED` in `tools/patch/blech_sysex.py`:

- FILE READ hat mit 20 Byte den längsten Antwortkopf für Daten, ein voller Block 32768 Datenbytes: Rohantwort 32788 Byte.
- 7-Bit-Packing: ein Byte mehr je angefangene sieben Rohbytes, 4684 Byte. Dazu sieben Rahmenbytes und das Abschlussbyte:
  37480 Byte auf der Leitung.
- Drei Byte für die Rundung des Rohdatenanfangs auf eine Wortgrenze: 37483 Byte, auf 256 Byte aufgerundet 37632 Byte.

Die SysEx-Reservierung insgesamt sind damit 41 KiB statt 60 KiB. Zwischen `0xC019A400` und dem Dateibereich
`0xC019F000` bis `0xC01A0000` werden 19456 Byte (19 KiB) zusammenhängend frei.

Das Packen läuft vorwärts im selben Puffer. Für beide Antwortköpfe H = 16 und H = 20 und jede Länge n von 0 bis 32768
prüft der Test (`tools/patch/test_blech_sysex_buffer.py`):

```text
R = H + n
G = ceil(R / 7)
S = align_down(BUFFER_REQUIRED - n, 4) - H
S >= 7 + G                    (ungelesene Rohbytes werden nicht überschrieben)
8 + R + G <= BUFFER_REQUIRED  (der fertige Rahmen passt in den Puffer)
```

DATA-Anfragen brauchen höchstens 32768 entschlüsselte Bytes. FLASH bleibt auf 4096 Byte je Anfrage begrenzt.

**Falle im Parser der Firmware** (gemessen im Emulator, vor und nach der Pufferänderung gleich): zu kurze und zu lange
abgeschlossene Anfragen bekommen Korgs Formatfehler `0x26`. Fehlt das Abschlussbyte F7 ganz, verschluckt der Parser die
nächste INFO-Anfrage bis zu deren F7, ohne INFO-Antwort. Erst die zweite INFO-Anfrage geht wieder.

Grenze: der Emulator hat keinen USB-Controller. USB-Endpunkte, Rückstau und echte Übertragungszeit sind nur am Gerät zu
prüfen.

Quelle: Messung 2026-10-21/patch-effizienz-sysex

## Was nicht geht oder bewusst nicht gemacht wird

- **Die VSB kann nicht einfach größer werden.** Unterstützt ist 2 MiB Abbild plus 256 Byte Kopf (so auch die
  Hacktribe-Dokumentation). Im Flash liegen direkt hinter dem Firmwarebereich Nutzerdaten. Eine größere Datei schafft
  weder einen größeren Ladebereich noch eine neue Flash-Aufteilung; Updater, Bootloader, Prüfsummen, Grenzen und Layout
  müssten zusammen umgebaut werden. Einen geprüften Weg gibt es nicht. Der andere Weg ist, Daten von der Karte
  nachzuladen, wie bei den Plugins. Hergeleitet. Siehe [Flash-Karte](../speicherbereiche.md#flash-bekannte-karte-und-dauerhafte-wirkung).
- **Kein Dirty-Merker statt Vergleich:** die Anzeige ungespeicherter Änderungen (`tools/patch/script_shortcuts.s`)
  vergleicht das Pattern nur alle acht Frames und bricht beim ersten Unterschied ab. Ein Merker müsste Sequencer, MIDI und
  alle nativen Editierwege sicher erfassen, ein unvollständiger wäre schlechter.
- **Vorhandene Optimierungen behalten:** die Display-API arbeitet mit Seitenmasken und Bitmaps in Byte-Spalten,
  geschlossene Apps bekommen keine `frame`-Handler.
- **Gemeinsame CRC nicht zusammenlegen:** die CRC nicht mit den getrennt wählbaren Patches SysEx, Startbild und MFX teilen,
  das schafft Abhängigkeiten zwischen den Besitzern der Bytes. Die Füllroutine von Korg hat einen anderen Registervertrag
  als die der VM, ein direkter Tausch wäre falsch.

Quelle: Messung 2026-10-20/patch-effizienz-ausgang, Messung 2026-10-20/patch-performance, Messung 2026-10-22/patch-effizienz-helfer

## Falle beim Testen: `--test-concurrency` an der falschen Stelle

`npm test -- --test-concurrency=2` begrenzt die Parallelität nicht: Node ignoriert den Schalter, wenn er hinter dem
Dateimuster steht (gemessen mit drei selbst erzeugten Testdateien: drei gleichzeitige Starts). Der Schalter muss vor dem
Muster stehen, wie in [development.md](../development.md):
`node --test --test-concurrency=2 "test/*.test.mjs"`. Unter paralleler Last erreicht die native Assemblersuite sonst ihr
300-s-Limit.

Quelle: Messung 2026-10-20/patch-effizienz-ausgang
