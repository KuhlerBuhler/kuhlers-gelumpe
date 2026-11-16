# QEMU als DSP-Kern: Hybrid-Worker hinter BFIN9

Fortsetzung von [QEMU-Port gegen GNU-Simulator](2026-11-16-qemu-bfin-vergleich.md).
Alles lief im Simulator auf dem Mac. Kein Gerät wurde angesprochen.

Marker: **gemessen** (Befehl lief, Zahl abgelesen), **gelesen** (Quelltext),
**hergeleitet** (aus Gemessenem und Gelesenem geschlossen), **geschätzt**.

## Kurz

- Der QEMU-Worker ist ein Hybrid: QEMU führt die Blackfin-Befehle aus, der
  GNU-Simulator läuft im selben Prozess als Bibliothek und behält Geräte, CEC,
  Zeit und das Protokoll BFIN9. Speicher ist geteilt, nicht kopiert.
- Alle 175 Worker-Tests sind mit ihm grün (Gruppen kern 27, host 81, dma 58,
  fork 9), ohne Eintrag in `qemu_gnu_only.txt` (**gemessen**).
- Ein Fallauf (0,3 s Modellzeit) endet bit-gleich mit dem GNU-Worker: gleiche
  JSON-Ausgabe, 123520781 DSP-Zyklen, gleiche PC, gleicher SPORT-Hash
  (**gemessen**).
- Tempo im Fallauf: 6,7 s statt 13,6 s (**gemessen**, Last 8 bis 15 auf dem
  Mac). Die Rechenzeit in QEMU ist dabei klein; den Rest teilen sich das
  Warten auf den ARM und der Aufwand je Anfrage im GNU-Simulator (Abschnitt 4).

## 1. Weg: Hybrid statt neuer Geräte

Die Phasen 3 und 4 des Plans sahen vor, HOSTDP, SysControl, SIC/CEC, DMA,
MDMA und SPORT als QEMU-Geräte nachzubauen. Der Hybrid spart das: der
GNU-Simulator bleibt der Rahmen, nur die Befehlsausführung wandert.

- Der GNU-Motor (`blech_bfin_engine`, Takt je Zyklus, Ereignisse, Wächter)
  gibt die Befehle zwischen zwei GNU-Ereignissen an QEMU ab
  (`tools/dsp/blackfin_hybrid.c.inc`). Budget = Zyklen bis zum nächsten
  Ereignis, höchstens bis Ende der Anfrage.
- QEMU zieht je Befehl die GNU-Taktkosten ab (`CYCLE_DELAY` aus
  `bfin-sim.c` im Prädekoder nachgebaut, `qemu-worker.patch`) und hält vor dem
  ersten Befehl an, der das Budget nicht mehr hat, an der Halte-PC oder nach
  N Befehlen (Wächter). Ein Lauf überschreitet nie das nächste Ereignis, also
  liegen Interrupts, DMA und Gerätezugriffe auf denselben Zyklen wie bei GNU
  (**hergeleitet**, durch den bit-gleichen Fallauf gestützt).
- An GNU zurück gehen: Zugriffe außerhalb von RAM (MMRs, über einen
  `tlb_fill`-Haken), CEC-Rückkehr und Modi, Systemregister, `CYCLES`,
  Ausnahmen, unbekannte Befehle, Sprung in den ROM. GNU führt diesen einen
  Befehl aus, danach rechnet wieder QEMU.
- Beobachtete Speicherfenster (Op 16) mappt QEMU nur ausführbar, Daten
  laufen dort über GNU, das sie zählt.
- `CLI` immer und `STI`, solange kein gelatchter Interrupt frei wird, rechnet
  QEMU über einen Rückruf in den GNU-CEC (`blech_cec_fast`). Ohne den Rückruf
  gab es 4415006 Rückgaben an GNU in 0,3 s, mit ihm 511 (**gemessen**). Das ausgelassene GNU-Ereignis findet in diesem Fall nichts
  (**gelesen**, `_cec_raise` mit `ivg == -1`).

## 2. Entscheidungen zu Phase 0

| Punkt | Entscheidung | Beleg |
|---|---|---|
| 0.1 Schrittsteuerung | Eigene Schleife: das Board ruft `cpu_exec` aus dem GNU-Motor, Budget im TCG-Prolog jedes Befehls; kein `icount` | `run_stops_at_a_requested_pc`, `rom_entry_at_the_instruction_budget_is_still_a_failure` grün (**gemessen**) |
| 0.1 Overhead | rund 0,65 µs je QEMU-Lauf inklusive Rechnen | 1,13 Mio. Läufe, 159 von 1431 Samples des Hauptfadens in `cpu_exec` bei 6,7 s (**hergeleitet** aus `sample`) |
| 0.2 Fork | `fork()` des ganzen Prozesses wie bisher; QEMU läuft einfädig (`-accel tcg,thread=single`), der Motor auf dem Hauptfaden | Gruppe fork 9/9 grün (**gemessen**) |
| 0.3 Kanal | unverändert aus `blackfin_worker.c` auf dem Hauptfaden, stdin/stdout und `--channel` | Kanal-Test in Gruppe fork grün (**gemessen**) |
| 0.6 Taktmodell | GNU-Taktkosten in QEMU, gleiche Synchronpunkte | Fallauf bit-gleich, Abweichung 0 Zyklen (**gemessen**) |
| 0.7 Anfragegrößen | 1,13 Mio. QEMU-Läufe für 121,8 Mio. Zyklen, im Mittel 108 Zyklen je Lauf; eine Op-18-Verteilung wurde nicht aufgezeichnet | `BLECH_HYBRID_STATS` (**gemessen**) |

## 3. Was nur GNU kann

Nichts in den Worker-Tests. Im Hybrid bleibt GNU ohnehin für Geräte und
Sonderbefehle zuständig; `qemu_gnu_only.txt` ist leer.

Offen (**hergeleitet**, nicht getestet): QEMU prüft im Port keine
Ausrichtung (`gen_align_check` kehrt früh zurück). Ein falsch ausgerichteter
Zugriff auf RAM löst daher keine Ausnahme aus, GNU schon. Die Firmware tut das
im Fallauf nicht (sonst wäre der Lauf nicht bit-gleich), ein fehlerhafter
Patch aber vielleicht.

## 4. Wohin die Zeit geht

`sample` am QEMU-Prozess, 3 s mitten im Fallauf, Hauptfaden 1431 Samples
(**gemessen**):

| Teil | Samples |
|---|---:|
| Warten auf den ARM (`blech_ring_read`, `poll`) | 591 |
| `sim_resume` gesamt | 660 |
| davon `sim_module_resume` / `suspend` (`getrusage`, Uhr) | 255 |
| davon QEMU (`cpu_exec`) | 159 |

Der Aufwand je Anfrage (`setjmp` mit Signalmaske, `getrusage`) liegt im
GNU-Rahmen und trifft beide Worker gleich. Er ist die nächste Stellschraube
(Phase 6), nicht die Befehlsausführung.

## Nachstellen

```bash
python3 tools/dsp/build_qemu.py ~/gelumpe-dsp/worker --jobs 6
BFIN_WORKER=~/gelumpe-dsp/worker/qemu-bfin-worker tools/dsp/qemu_worker_tests.sh alle
tools/emu/.venv/bin/python tools/emu/blackfin_cases.py --vsb <hacktribe SYSTEM.VSB> \
  --worker ~/gelumpe-dsp/worker/qemu-bfin-worker --core-hz 516096000 --seconds 0.3
```

`BLECH_HYBRID_STATS=<präfix>` schreibt je Worker-Prozess die Zähler (QEMU-Läufe,
QEMU-Zyklen, GNU-Schritte, Rückgaben) nach `<präfix>.<pid>`. Das kostet bei
jeder Anfrage einen Dateizugriff und verfälscht die Laufzeit (81 s statt
6,7 s), also nur zum Zählen.
