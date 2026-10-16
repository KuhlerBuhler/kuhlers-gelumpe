# Emulator-Zeit gegen Gerätezeit: vier kleine Schleifen

Stand 2026-10-16. Eigenes Gerät (Electribe 2 Sampler, BLECH v21 auf Hacktribe-2.02-Basis), nur RAM, und der
Emulator (`tools/emu/machine.py`, Unicorn) mit derselben Firmware (`SYSTEM-blech-v21.VSB`, Flash-Dump vom
9.10.). Grob gemeint, nicht taktgenau. Skript: `tools/device/timing_probe.py`. Markierungen: **gemessen**,
**hergeleitet**, **offen**.

## Ergebnis

| Last | Gerät, ns je Runde | Emulator, ns je Runde | Gerät zu Emulator | Gerät ns je Befehl |
|---|---|---|---|---|
| `alu` (4 Befehle, ein Sprung) | 20,15 | 20 | 1,01 | 5,04 |
| `mul` (4 Befehle, ein Multiply) | 26,82 | 20 | 1,34 | 6,71 |
| `memh` (8 Befehle, 16 Byte lesen, Cache trifft) | 47,88 | 40 | 1,20 | 5,99 |
| `mem` (7 Befehle, 16 Byte lesen, Cache verfehlt) | 143,43 | 35 | 4,10 | 20,5 |
| `memu` (7 Befehle, 16 Byte ungecacht) | 234,1 | nicht vorhanden | | 33,4 |

- **Gemessen:** Reine Rechenschleifen laufen am Gerät in der Zeit, die der Emulator rechnet (5 ns je Befehl,
  Faktor 1,01). Der Grundwert `NS_PER_INSN = 5` bleibt deshalb unverändert.
- **Gemessen:** Ein abhängiges Multiply kostet 6,7 ns mehr als ein einfacher Befehl.
- **Gemessen:** Lesen aus dem Speicher ist das, was der Emulator nicht kennt. Trifft der Daten-Cache (4 KiB
  immer wieder), kostet es 0,5 ns je Byte extra. Ein Durchlauf über 256 KiB (mehr als der Cache fasst, jede
  Zeile verfehlt) kostet 6,8 ns je Byte extra, das sind rund 110 MB/s; über den ungecachten Alias 12,4 ns
  je Byte extra (rund 68 MB/s). Faktor Gerät zu Emulator für so einen Durchlauf: rund 4.
- **Hergeleitet:** Die frühere Messung der Skript-VM (`2026-10-12-vm-tempo.md`: Faktor 1,33 bis 1,57, 7 bis 8 ns je
  Emulator-Befehl) passt dazu: ein Interpreter hat Sprünge, Ladezugriffe auf kleine heiße Daten und Multiplies,
  aber keine Durchläufe über Speicher größer als der Cache.
- **Hergeleitet:** Es gibt keinen einzelnen Faktor für alles. Für Code aus Rechnen, Sprüngen und kleinen heißen
  Daten reicht 1,0 bis 1,4, für Code, der große Speicherbereiche durchläuft (Sample kopieren, Puffer
  summieren, Karte lesen), liegt der Emulator um etwa den Faktor 4 zu schnell.

## Was im Emulator geändert wurde

- Der Grundwert bleibt. Ein Wechsel auf zum Beispiel 7 ns je Befehl würde jede gemessene Zeit des Emulators
  verschieben (Boot, Ladebalken, Karten- und Sample-Abläufe, die Tests auf Zeiten und Raten), und die
  Rechenschleife zeigt, dass 5 ns dafür stimmt. Ein Speichermodell (Zugriffe zählen, Cache nachbilden) wäre
  ein größerer Umbau und kein Platz für eine Konstante.
- Neu: `tools/emu/devicetime.py` mit den gemessenen Zuschlägen und `estimate_device_ns(emulator_ns, mul_insns,
  read_hit_bytes, read_stream_bytes, read_uncached_bytes)`. Sie rechnet eine Emulator-Zeit auf eine geschätzte
  Gerätezeit hoch. Der Emulator selbst benutzt sie nicht. Test: `test_devicetime.py` (der Grundwert gleicht
  `machine.NS_PER_INSN`, die vier Schleifen kommen auf die gemessenen Werte).

## Methode

- Ein Stub (348 Byte mit Datenblock) geht nach `0xC1000000`, wie in `vm_bench.py` (Hacktribe Execute `0x57`,
  Stub-Bereich, Schreiben immer ab `0xC1000000`, Cache-Abgleich über den Alias `0xC4000000`, Rückgabewert 0).
  Er liest vor und nach der Last Timer 3 (`0x01F0D010`, 150 MHz) und den OS-Tick (`0xC06A292C`, 1 ms) und legt
  beide, CPSR und eine Prüfsumme im eigenen Datenblock ab. Vor jedem Schreiben stimmen drei Firmware-Stellen
  mit ihrer SHA-256 überein (dieselben wie `vm_bench.py`), die Originalbytes werden vorher gelesen und im
  `finally` zurückgeschrieben. Kein Flash, kein Bootloader, nur Lesen oberhalb des Stub-Bereichs.
- Lasten (`alu`, `mul`, `memh`, `mem`, `memu`) laufen je in fünf Größen (bis 1,5 ms, `mem` höchstens 256 KiB),
  je Größe fünfmal. `alu` und `mul` prüft das Skript gegen eine Python-Referenz der Prüfsumme.
- **ns je Runde = die schnellste Einzelmessung durch ihre Rundenzahl** über alle Läufe und Größen. Ein
  Interrupt, der in einen Lauf fällt (CPSR `0x80000053`, IRQ an, am Gerät wie im Emulator; Timer-Interrupt
  alle 0,5 ms), macht ihn nur langsamer. Die Steigung über die Größen (`fit`) liegt wegen dieser Interrupts
  1 bis 8 % höher und ist in den JSON-Dateien enthalten.
- Emulator: dieselbe Datei, dieselben Größen. Die Befehle zählt ein Code-Hook im Stub-Bereich (exakt:
  4,000, 4,000, 8,000 und 7,000 je Runde); Emulator-ns je Runde = Befehle mal `NS_PER_INSN`. Die Zeit, die der
  Zähler im Emulator zeigt, ist in Scheiben gerastert (Achsenabschnitt minus 45 bis 75 µs) und für so kurze
  Läufe unbrauchbar.
- Ergebnisse vergleichen: `python3 timing_probe.py --report device.json emu.json`.

## Rohwerte (Gerät, drei volle Läufe nacheinander, ns je Runde, schnellste Messung)

| Last | Lauf 1 | Lauf 2 | Lauf 3 | Streuung |
|---|---|---|---|---|
| alu | 20,07 | 20,26 | 20,13 | 0,9 % |
| mul | 26,75 | 26,84 | 26,85 | 0,4 % |
| memh | 47,81 | 47,95 | 47,89 | 0,3 % |
| mem | 144,08 | 141,02 | 145,19 | 3,0 % |
| memu | 235,39 | 234,04 | 232,87 | 1,1 % |

Steigung (`fit`) in den Läufen: alu 20,9 bis 21,3, mul 27,7 bis 28,8, memh 45,0, mem 148 bis 152, memu 242 bis 252.

- **Gemessen:** Zeitbasis geprüft: ein 21-ms-Lauf zeigt 21,06 bis 21,14 ms nach Timer 3 mit 150 MHz und 21 bis 22 ms
  nach dem OS-Tick (alle drei Läufe). Im Emulator 22,04 ms gegen 22 ms.
- **Gemessen:** Das Gerät antwortete nach allen Läufen weiter; `--dry-run` danach lief durch.

## Grenzen und offen

- Vier Schleifen, kein echter Firmware-Pfad. Die optionale Last (eine harmlose Firmware-Funktion in einer
  Schleife aufrufen) ist **offen**: ohne eine als harmlos belegte Funktion nicht gemacht.
- **Offen:** Schreibzugriffe (Write-Buffer, Rückschreiben), Sprünge, die oft danebenliegen, Funktionsaufrufe mit
  Stack, Zugriffe auf Peripherie und die DSP-Schnittstelle sind nicht gemessen. Bei der Karte und beim DSP
  kommt die Wartezeit ohnehin von der Gegenstelle.
- Der Cache-Fall hängt an der Größe des Daten-Caches, die hier nicht ermittelt ist: 4 KiB trafen, 256 KiB
  verfehlten. Wo dazwischen die Grenze liegt, ist **offen**.
- Interrupts laufen mit (IRQ an). Die Werte sind interruptfrei (schnellste Messung); echter Code zahlt die
  Interrupt-Last zusätzlich, im Emulator wie am Gerät.
- Ein früherer Lauf wurde von Hand mitten im Betrieb abgebrochen (Prozess beendet, kein `finally`), dabei blieb
  der Stub an `0xC1000000` stehen. Das ist der Bereich, den Hacktribe selbst für hochgeladenen Code und die
  LED-Stubs nutzen; das Gerät antwortete danach normal, auch der folgende `--dry-run`. Die Originalbytes dieser
  Stelle waren damit verloren, die späteren Läufe haben den stehengebliebenen Stub als "Original" zurückgeschrieben.
