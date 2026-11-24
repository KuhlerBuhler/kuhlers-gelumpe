# Emulator-Takt: 1000 Timer-Interrupts je Sekunde

Alles im [Emulator](../glossary.md#emulator) (`tools/emu/machine.py`, Unicorn 2.1.4) mit
[`SYSTEM.VSB`](../glossary.md#vsb) und dem eigenen Flash-Dump. Kein Gerätezugriff.
Markierungen: **gemessen**, **hergeleitet**, **offen**.

## Takt unabhängig von der Scheibenlänge

Der Emulator rechnet in Scheiben (`SLICE`, höchstens 20000 Befehle zu je 5 ns, also 100 µs) und
prüft nur am Scheibenende, ob ein Interrupt fällig ist.

- **Gemessen:** Ein Zähler, der nur am Scheibenende vergleicht und höchstens eine Kante je Scheibe
  meldet, lieferte den 1-kHz-Timer-Interrupt (INT 21) nur 872-mal je Sekunde Gerätezeit und den
  Bildschirm-Takt (`UiTask`, `0xC006F178`) 21-mal statt 25-mal.
- **Umsetzung:** Eine Scheibe endet an der nächsten Timer-Kante oder dem nächsten UART-Byte
  (`slice_length`), im Interrupt-Handler läuft sie nur `ISR_STEP` = 256 Befehle, damit ein
  weiterer anstehender Interrupt gleich folgt, und ein Prozessor im Warten-auf-Interrupt
  ([WFI](../glossary.md#wfi)) springt bis zum nächsten Ereignis (`run_slice`). Abfrageschleifen auf den
  Timer-Registern halten die Scheibe an der nächsten Kante an. `SLICE` ist nur noch die Obergrenze.
- **Gemessen:** Der Boot kostet damit keine Zeit: 5 s Gerätezeit brauchen mit `SLICE = 2000` und
  mit `20000` je 7,0 bis 7,2 s CPU-Zeit. Eine kleine Scheibe als Vorgabe lässt dagegen die Tempo-Rate
  einbrechen, wenn die Firmware dauernd rechnet (Muster-Sicherung auf eine Karte, Flash lesen):
  `SLICE = 2000` brachte 0,07 der Echtzeit, `20000` bleibt bei 1,0.

| Scheibe | Timer-Interrupts je s | Bildschirm-Takt je s |
|---|---|---|
| 20000 | 1000,0 | 25,0 |
| 2000 | 1000,0 | 25,0 |
| 500 | 1000,0 | 25,0 |

`tools/emu/test_timer.py` zählt 1 s Gerätezeit ab 2 s und verlangt 1000 und 25 mit höchstens 1 %
Abweichung für 20000 (Vorgabe), 200000 und 500. Ohne `E2_VSB` wird er übersprungen, mit
`E2_EMU_REQUIRED=1` ist das ein Fehler.

## SD-Karte: der Karten-Interrupt

- **Gemessen:** Kommt der Karten-Interrupt (INT 16) sofort nach dem Ende einer Scheibe, bleibt die
  Firmware nach CMD12 (STOP) hängen (kein Verkehr zum Bedienfeld, dann Assertion in
  `AM180xMMSDCardController.cpp`, Zeile 228 und 413). Der Interrupt-Handler (`0xC001DB60`) liest ST0
  (Lesen löscht) vor der Abfrageschleife des Vordergrunds und nimmt ihr die Antwort weg.
- **Ursache, gemessen:** Das Modell hob den Interrupt bei jedem Blick erneut, solange noch Daten im
  FIFO lagen, auch für ein Stück, dessen Interrupt schon kam und das die Task gerade abholte. Dieser
  zweite Interrupt blieb im AINTC stehen und kam erst nach CMD12.
- **Umsetzung:** Der Interrupt kommt einmal je 64-Byte-Stück (`sdcard.py`, `raised`), und der
  Karten-Interrupt wird nur einmal je 100 µs Gerätezeit angesehen (`MMC_IRQ_NS`). Mit einem Blick
  alle 2 µs kam die Assertion früher in der ersten Sekunde der Ordnerkopie, jetzt nicht mehr
  (`migrate_cases.py`, `case_card_interrupt`). Das ist ein Modell, kein Befund vom Gerät: **offen**,
  wie die Firmware am Gerät die Antwort zwischen Handler und Abfrage aufteilt.

## Prüfungen, die vom Takt abhängen (`mfx_cases.py`)

- Die DSP-Übertragungen zweier getrennt gebooteter Geräte werden verglichen. Die Effekt-Puffer
  wechseln (`0xFF900018` und `0xFF900098`) und ihre Schreibzeiger laufen in einem Ring von
  `0x8000` Wörtern (**hergeleitet** aus den Zeigerwerten 32768 bis 65535). Zwei Starts, die sich um
  einige Übertragungen unterscheiden, liegen an verschiedenen Stellen. `same_dsp` lässt deshalb einen
  Versatz für die ganze Liste zu; Befehle und alle übrigen Wörter müssen gleich sein.
- Der Musterwechsel beim Spielen wirkt am Ende des Takts. Wann der Takt endet, hängt vom Start ab
  (3,8 bis 4,8 s nach dem Drehen); die Prüfung wartet darum, bis die Nummer wechselt (höchstens 15 s).

## Zeitwerte anderer Messungen

Werte, die die Firmware aus ihren Timer-Interrupts ableitet (Raten, Dauern von Bildschirm-, LED- und
Sequencer-Abläufen), gelten nur mit dem richtigen Takt. Byte-Zeiten von UART und SPI und Messungen
am Gerät sind davon nicht betroffen. Nicht neu gemessen und **offen**, weil sie mit dem alten Takt
entstanden: der Tick-Haken ab 341 ms in `2026-10-10-mfx-umschalter.md`, die Zeiten für Gate-Arpeggiator,
PART ERASE und TAP in `../tastenkombinationen.md`, "Working..." mit 20 bis 30 s in
`2026-10-10-pattern-kette-import.md`.
