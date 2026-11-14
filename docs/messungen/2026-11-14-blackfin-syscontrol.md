# Blackfin: SysControl und RTOS-Start

## Hergeleitet aus der ROM-Schnittstelle

Das vollständige
[BF52x-Hardwarehandbuch](https://www.analog.com/media/en/dsp-documentation/processor-manuals/ADSP-BF52x_hwr_rev1.2.pdf)
beschreibt `bfrom_SysControl` auf den Seiten 18-31 bis 18-33.
Der Rückgabewert in `R0` stammt von einem intern aufgerufenen
`bfrom_OtpRead`. Einzelbitwarnungen werden unterdrückt. Die Fehlercodes
stehen auf Seite 4-25; der veröffentlichte
[ROM-API-Header](https://raw.githubusercontent.com/torvalds/linux/v4.16/arch/blackfin/include/asm/bfrom.h)
definiert `OTP_SUCCESS` als null.

Der Stub bildet den normalen Registerzugriff mit fehlerfreiem OTP ab.
Diese OTP-Bedingung ist eine ausgewiesene Modellannahme, keine Lesung des
Geräts. Reset, Schlafzustände, OTP-Fehler und die Werkseinstellung der
Spannung werden nicht als unterstützte Aufrufe behandelt.
`PLL_STAT` ist nur lesbar. Nicht ausgewählte Strukturfelder und Register
bleiben erhalten. Unterstützte Aufrufe kehren über ihr originales `RETS`
zurück; unbekannte ROM-Einsprünge bleiben Fehler mit vollständigen Registern.

Die Taktübergänge sind atomare Zustandsänderungen im Modell. Analoge
Spannungsänderungen, PLL-Einschwingzeiten und deren Interruptzeitpunkte
sind damit nicht nachgewiesen.

## Gemessen mit erzeugten Programmen

Ein erzeugtes Blackfin-Programm ruft `0xEF000038` auf und speichert danach
den zurückgegebenen Wert. Es bekommt null zurück und liest die geänderten
MMRs aus demselben Simulator. Ein weiterer Lauf prüft alle 31 nicht leeren
Auswahlen der fünf lesbaren Register: Nur die gewählten 16-Bit-Felder der
Struktur dürfen sich ändern.

Nicht unterstützte Flags, ein von null verschiedenes reserviertes Argument,
ein Schreibauftrag für `PLL_STAT`, ein Wechsel in einen nicht modellierten
Stromsparmodus oder eine Rückkehr ins ROM brechen vor dem ersten
MMR-Schreibzugriff ab. Ein unbekannter ROM-Aufruf bleibt auch bei
angeschlossenem SysControl-Modell ein harter Fehler.

65 Modulprüfungen bestehen mit dem gebauten GNU-Kern. Die Tests enthalten
nur selbst erzeugte Programme und Werte.

Die abschließende Unitprüfung besteht mit 1611 Prüfungen bei 166
ausgelassenen Prüfungen; die neun Dokumentationsprüfungen bestehen.
Der Browser-Gesamtlauf hat 352 bestandene Prüfungen, einen Fehler und eine
ausgelassene Prüfung. Der Namenstest im Baukasten las einmal `Mein` statt
`Mein Delay`. Die anschließend allein wiederholte vollständige Testdatei
besteht mit drei Prüfungen. Die Ursache dieses Browserbefunds ist offen;
ein insgesamt grüner Browserlauf wird damit nicht behauptet.

## Gemessen am nativen Start im Simulator

Mit dem Stub durchläuft der originale Start beide SysControl-Aufrufe aus
der Funktion bei `0xFFA04E24`:

| Register | Erster Aufruf | Zweiter Aufruf |
|---|---|---|
| `VR_CTL` | `0x30B0` | `0x30B0` |
| `PLL_CTL` | `0x2A00` | `0x2A00` |
| `PLL_DIV` | `5` | `4` |
| `PLL_LOCKCNT` | `0x0200` | `0x0200` |

Die Argumente kommen vom originalen DSP-Code. Es gibt weder einen direkten
Aufruf der späteren Initialisierung noch erzeugte Task- oder Ereignisobjekte.

## Gemessener SIGNBITS-Fehler

Nach dem ersten ROM-Aufruf wartete der Start zunächst unbegrenzt auf einen
RTOS-Auftrag. Der Core-Timer war aktiv, und sein originaler Handler bei
`0xFFA0A6D8` wurde ausgeführt. Nach zehn Ticks setzte er den Interrupt 14.
Dieser blieb jedoch in `ILAT` stehen, weil die gesicherte Interruptmaske
falsch war.

Bei `0xFFA0A16E` führt der DSP `SIGNBITS` und einen Speicherzugriff parallel
aus. GNU schrieb das halbe Zielregister sofort. Der Speicherzugriff
sicherte deshalb das neue Ergebnis `5` anstelle der vorherigen
Interruptmaske `0xF75F`. Beim Wiederherstellen fehlte dadurch unter anderem
die Freigabe für Interrupt 14.

Der Builder stellt die vier SIGNBITS-Varianten in die verzögerte
Schreibwarteschlange. Zehn erzeugte Gegenproben für ganze Register,
Registerhälften und beide Akkumulatoren schlagen vorher fehl und bestehen
danach. Die oberen 16 Bits bleiben erhalten. Für Akkumulatoren gilt die
eigene Normalisierung mit dem Ergebnisbereich minus acht bis 31, wie in der
[Blackfin-Programmierbeschreibung](https://www.analog.com/media/en/dsp-documentation/processor-manuals/Blackfin_pgr_rev2.2.pdf)
beschrieben. Diese Korrektur verändert weder die Firmware noch deren
Interruptmaske durch einen Eingriff von außen.

## Hergeleitete Laufgrenze

Der originale Start enthält Wartezeiten von 10, 20, 200 und 100 RTOS-Ticks.
Im Modell steht die Core-Timer-Periode auf `0x7E000`, also 516096.
Allein 330 Perioden benötigen damit mehr als 170 Millionen Modellzyklen.
Die Instruktionszahl hängt von den ausgeführten Befehlen ab. Die vorherige
Grenze von zehn Millionen Instruktionen reicht nicht für alle Wartephasen.

Die Startdiagnose bekommt standardmäßig 250 Millionen native Schritte;
erlaubt sind höchstens 500 Millionen. Zusätzlich gilt eine Wandzeitgrenze
von fünf Minuten. Ein abgelaufenes Zeit- oder Schrittbudget bleibt ein
fehlgeschlagener Start. Es werden keine Wartezeiten übersprungen und keine
Timerstände auf den erwarteten Wert gesetzt.

## Gemessene Ereigniszyklen und Ausführungsgrenzen

Der Anschluss rief anfangs `sim_resume` für jede einzelne Instruktion auf.
Der dabei nach einem Ereigniszyklus ausgelöste Debuggerhalt unterbrach bei
mehrzykligen Instruktionen die restliche Ereignisverarbeitung. Eine erzeugte
Schleife mit 100 Sprüngen zählte 500 Prozessorzyklen, ihr Core-Timer aber nur
100. Damit war dieser Weg auch für Timerprüfungen ungeeignet.

Die Schritt-, Haltepunkt- und ROM-Grenzen werden nun vor jeder Instruktion
in der GNU-Ausführungsschleife geprüft. Zwischen zwei Instruktionen werden
alle zugehörigen Ereigniszyklen verarbeitet. Ein Halt setzt den nächsten
Prozessor ausdrücklich auf denselben Kern; das verhindert einen zusätzlichen
Ereignistakt beim Fortsetzen. Die erzeugte Gegenprobe stimmt danach über
zwei Ausführungsscheiben mit jeweils 500 Prozessor- und Timerzyklen überein.
ROM-Einsprünge bleiben vor ihrer ersten Instruktion sichtbar, auch genau an
der Schrittgrenze. Abbrüche außerhalb dieser gesetzten Grenzen sind Fehler.

Eine Million erzeugte Schleifensprünge benötigen in einem einzelnen Lauf
rund 0,026 Sekunden Wandzeit. Das ist ausschließlich die Geschwindigkeit
dieses Rechners, keine DSP-Durchsatzmessung und kein Hardwarezeitnachweis.
Die Prozessschnittstelle trägt jetzt `BFIN3`; ältere Hilfsprogramme müssen
neu gebaut werden.

## Gemessene nächste Startgrenze

Der native Start erreicht nach 6206534 Schritten nach der ersten
16-Schritt-Scheibe die Instruktion bei `0x18F90`. Bis zu diesem Halt wurden
beide SysControl-Aufrufe durchlaufen; `SEQSTAT` ist null. Die Instruktion
schreibt 16 Bit nach `0xFFC03404`, dem Register `HOST_STATUS`.

Für diese Register fehlt dem gewählten GNU-Gerätemodell die HOSTDP-Abbildung.
Wird der Zugriff ausgeführt, folgt die Ausnahme `0x2E`; `RETX` zeigt auf
`0x18F90`. Die Firmware bleibt danach in ihrer Ausnahmebehandlung. Auch
250 Millionen Schritte erzeugen dann keine Bereitschaftsantwort. Der
Prüflauf endet mit Status 1. Dies ist keine bestandene Initialisierung.

Am Halt vor diesem Zugriff sind gegenüber dem geladenen Zustand weiterhin
525 geänderte Bytes in Bank B beobachtet. Die vollständig gestarteten
Tasks, ihre Stacks und spätere Überlagerungen sind damit nicht geprüft.

Ein HOSTDP-Modell muss die in Kapitel 8 dokumentierten Reset-, Nur-Lese-,
Setz- und Quittierungsregeln beachten. Eine gewöhnliche RAM-Abbildung oder
eine feste Erfolgsantwort würde die fehlende Peripherie verdecken.

## Wiederholen

```sh
python3 tools/dsp/build_blackfin.py "$BFIN_SDK"
export BFIN_WORKER="$BFIN_SDK/blackfin-worker"
PYTHONPATH=tools/emu tools/emu/.venv/bin/python -m unittest test_blackfin_backend test_blackfin_stream test_blackfin_syscontrol test_dsp_model test_bootcache
python3 tools/dsp/blackfin_probe.py --worker "$BFIN_WORKER" --vsb "$E2_STOCK_VSB"
```

SDK, private Firmware, entpackte Daten und Rohspuren bleiben außerhalb des
Repositorys. Die Startdiagnose weist das OTP- und Taktmodell im Ergebnis aus.

## Offen

- Der vollständige native Initialisierungsabschluss und der gekoppelte
  ARM/DSP-Lauf.
- HOSTDP mit seinen drei MMRs, Statusregeln, Interrupts und Transferzuständen.
- Die endgültige Heap- und Task-Stackbelegung nach allen Startaufträgen.
- Die IFX-Gegenprobe auf ungeraden Parts mit vollständiger Schreibspur.
- Weitere ROM-Funktionen, falls der native Ablauf sie tatsächlich erreicht.
- OTP-Fehlerfälle, Stromsparmodi und zeitgenaue PLL-, DMA- und SPORT-Ereignisse.

Es gab keinen Gerätezugriff und keine Änderung an einer Firmwaredatei.
