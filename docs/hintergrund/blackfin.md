# Blackfin: was der Emulator-Worker über den DSP weiß

Befunde zum [DSP](../glossary.md#dsp) der Electribe, die beim Bau des Blackfin-Workers im [Emulator](../emulator.md)
herauskamen: Start, Speicherzugriffe, DMA, Systemsteuerung, RTOS-ROM, Bindung der Sample-Bibliothek und die beiden Simulatoren.
Alles lief im Simulator oder im Emulator mit erzeugten Programmen, nichts am Gerät. Die ursprünglichen Messnotizen stehen in
der Git-Historie (`git show origin/develop:docs/messungen/<datei>`); die Seite nennt sie unter jedem Befund als Quelle.

Markierungen: **gemessen** (im Simulator oder Emulator beobachtet), **hergeleitet** (aus Handbuch, Header oder Befehlssatz),
**offen**.

Die Peripherie-Modelle selbst stehen in den Messungen
[HOSTDP-FIFO und DMA1](../messungen/2026-11-14-blackfin-host-fifo.md),
[SPORT0 und der native Audiotakt](../messungen/2026-11-14-blackfin-sport0.md) und
[gemeinsame Modellzeit](../messungen/2026-11-14-blackfin-modellzeit.md); der Aufbau des Kerns in
[QEMU als DSP-Kern](../messungen/2026-11-16-qemu-dsp-kern.md).

## Start des DSP

**Native Systemsteuerung (gemessen).** Mit einem Stummel für den ROM-Aufruf läuft der originale DSP-Start durch beide
`bfrom_SysControl`-Aufrufe der Funktion bei `0xFFA04E24`. Die Argumente kommen vom originalen DSP-Code:

| Register | Erster Aufruf | Zweiter Aufruf |
|---|---|---|
| `VR_CTL` | `0x30B0` | `0x30B0` |
| `PLL_CTL` | `0x2A00` | `0x2A00` |
| `PLL_DIV` | 5 | 4 |
| `PLL_LOCKCNT` | `0x0200` | `0x0200` |

`PLL_CTL = 0x2A00` heißt MSEL 21. Bei 25 MHz Quarz sind das 525 MHz Kern und 131 MHz Bus, bei 24,576 MHz rund 516 MHz
(hergeleitet, die Quarzfrequenz ist offen). Quelle: Messung 2026-11-14/blackfin-syscontrol.

**ROM-Aufruf `0xEF000038` (hergeleitet).** Der von Analog Devices veröffentlichte ROM-API-Header (Linux-Kern 4.16,
`arch/blackfin/include/asm/bfrom.h`) ordnet `0xEF000038` der Funktion `bfrom_SysControl` zu. `R0 = 0x711` fordert einen
Schreibzugriff auf `VR_CTL`, `PLL_CTL`, `PLL_DIV` und `PLL_LOCKCNT` an. `R1` zeigt auf eine Struktur mit fünf 16-Bit-Feldern,
`R2` ist reserviert (null). Die Registersteuerung steht im Kapitel 18 des BF52x-Hardwarehandbuchs. Rückgabewert und
vorübergehende Registerwirkungen sind nicht belegt; ein Aufruf in das ROM ohne bekannte Antwort bleibt ein sichtbarer Startfehler,
keine Nullantwort. Quelle: Messung 2026-11-14/blackfin-rtos-rom.

**Upload und Initialisierung sind getrennte Zustände (Entscheidung).** Die ARM-Funktion `0xC0011AB8` bestätigt den Abschluss
ihrer SPI-Übertragung und prüft nicht den Zeiger, den der DSP-Code später bei `0xFF9031D8` ablegt (nach der Initialisierung steht
dort `0x01C722A0`, vorher null). Darum gilt im Emulator: ein korrekter Strom darf den Upload abschließen, ohne einen
initialisierten DSP zu behaupten. Ein kaputter Strom oder ein Workerfehler darf keinen Upload-Erfolg veröffentlichen. Die
Bereitschaftsprüfung bleibt eine getrennte, begrenzte Diagnose. Die Host-Port-Statusantwort `0x85` bedeutet nur
Transportbereitschaft. Quelle: Messung 2026-11-14/blackfin-boot-ruecklesen.

**Direktes Laden (gemessen).** Wird das DSP-Programm direkt in den Speicher gelegt (Adresse `file = ram - 0xC0000000 + 0x100`),
laufen die Boot-ROM-Initialisierungsblöcke nicht. Sechs Initialisierungsfunktionen laufen dann bis zu ihrem echten Rücksprung
(7732 Einzelschritte). Der direkte Start bei `0xFFA00000` bleibt im virtuellen Modus bei `0xFFA00090` (Interrupt-Rückkehr) ohne
Bereitschaftsantwort. Quelle: Messung 2026-11-14/blackfin-boot-ruecklesen.

## Speicherzugriffe und DMA

**Speicher-DMA (hergeleitet).** Beim BF52x-Modell liegt der Datenpfad der Speicher-DMA (MDMA) unter `0xFFC00F00` und
`0xFFC00F40`. Die gleich aussehenden `0xFFC00E00` und `0xFFC00E40` sind normale DMA-Kanäle. Quelle: Messung
2026-11-14/blackfin-speicherzugriffe.

**Beobachter für Datenzugriffe (gemessen).** Der Worker kann ein Adressfenster beobachten und zählt Lesen und Schreiben von
Kern und DMA getrennt (erfolgreiche Zugriffe und Bytes im Fenster, dazu Adresse, Breite und Ursprung des letzten Treffers; beim
Kern der PC, bei DMA Registerbasis und aktueller Deskriptor). Er liefert Summen und den letzten Treffer, keine zeitlich geordnete
Spur. Befehlsholen, Deskriptorabrufe, Zugriffe der Prüfschnittstelle, L1-Testzugriffe über MMU-Register und direkte Schreibzugriffe
der nachgebildeten ROM-Funktionen zählen nicht. Null Treffer heißt deshalb nicht Speicherstille. Quelle: Messung
2026-11-14/blackfin-speicherzugriffe.

**Schreibzugriff über die Grenze zum ersten User-Sample (gemessen im Emulator).** Mit dem vollständig korrigierten Worker zeigt die
originale rote Firmware nach 800 ms Modellzeit einen 4 Byte breiten MDMA-Schreibzugriff ab `0x00365EBE`. Zwei Bytes überlappen
das erste User-Sample bei `0x00365EC0`. Es gibt keine ARM-Assertion und keine DSP-Ausnahme. Vollständige PCM-Vergleiche müssen
deshalb auch das erste Halbwort behalten. Die Ursache ist **offen**; die erste PCM-Abweichung im gekoppelten roten Originalstart
bleibt eine eigene Untersuchung und wird nicht durch angepasste Testdaten verdeckt. Quelle: Messung
2026-11-14/blackfin-dma-grenzen und 2026-11-14/blackfin-speicherzugriffe. Verwandt:
[SDRAM-Freiraum](../messungen/2026-11-20-dsp-sdram-freiraum.md).

## HOSTDP-Register

Hergeleitet aus dem BF52x-Hardwarehandbuch (Seiten 8-26 bis 8-32) und den veröffentlichten Registerdefinitionen
(`defBF522.h`, Linux-Kern 4.16):

| Adresse | Register | Rücksetzwert |
|---|---|---|
| `0xFFC03400` | `HOST_CONTROL` | `0x0400` |
| `0xFFC03404` | `HOST_STATUS` | `0x000C` |
| `0xFFC03408` | `HOST_TIMEOUT` | `0` |

- Die MMRs sind 16 Bit breit; das Timeoutfeld hat 11 Bit. Das Modell erlaubt zusätzlich nullerweiterte 32-Bit-Lesungen wie die
  übrigen GNU-MMR-Modelle und weist 32-Bit-Schreibzugriffe ab.
- `HOST_STATUS`: `DMA_CMPLT` wird durch eine geschriebene Eins gesetzt, `HSHK` ist beschreibbar, `HIRQ`, `HOSTDP_TOUT` und
  `HOSTRD_DONE` werden durch eine geschriebene Eins quittiert. Nur-Lese-Bits ändern sich dadurch nicht.
- `BTE` folgt der Timeoutfreigabe in `HOST_CONTROL`. Das Resetbit liest sich als null. Ein Softreset setzt den Status zurück,
  erhält Steuerung und Timeout und nimmt anstehende Interruptsignale zurück.
- Der Konfigurationsstatus ist als atomarer, untätiger Zustand nachgebildet: Einschalten erlaubt Konfiguration, HRDY-Override sperrt
  sie. Eine zeitgenaue Rücksetzsequenz während eines laufenden Transfers ist **nicht geprüft**.

Die Statuswerte `0x018C` und `0x008C` und die Quittierung durch die Handler stehen in
[HOSTDP-FIFO und DMA1](../messungen/2026-11-14-blackfin-host-fifo.md). Quelle: Messung 2026-11-14/blackfin-hostdp.

## RTOS und ROM

**Fehler im GNU-Simulator bei parallelen Instruktionen (gemessen, behoben).** Bei einer Addition oder Subtraktion schrieb der
GNU-Kern das Zielregister sofort, ein paralleler Speicherzugriff las deshalb den neuen statt den alten Wert. In der
Stackeinrichtung bei `0xFFA0AFAA` landete so die untere Stackadresse statt des Stackendes im Register. Der spätere Stackrahmen
überschrieb die virtuelle Funktionstabelle des Task-Objekts, die Folge war der ungültige Aufruf bei `0xFFA0BE6C`. Der Builder
stellt Additions- und Subtraktionsergebnisse in dieselbe verzögerte Schreibwarteschlange wie die anderen parallelen
Ergebnisse. Sechs erzeugte Gegenproben (Add und Sub, mit und ohne Sättigung, an beiden Überlaufgrenzen): vier schlagen mit dem
alten Kern fehl, alle sechs bestehen mit dem korrigierten. Der native Start erreicht danach den ROM-Aufruf `0xEF000038`.
Quelle: Messung 2026-11-14/blackfin-rtos-rom.

**ROM-Fenster (gemessen).** Die mitgelieferten ROM-Tabellen für den BF527 sind leer. Der Builder bildet leere Tabellen nicht
ab. Vor jeder Instruktion im Fenster `0xEF000000` bis `0xEFFFFFFF` hält der Prozess an und meldet PC, letzte Instruktion,
`RETS` und alle 54 lesbaren Register. Ein unbekanntes Ziel beendet die Sitzung mit Fehler, auch wenn dort ein Haltepunkt gesetzt
ist. Quelle: Messung 2026-11-14/blackfin-rtos-rom.

## Bindung der Sample-Bibliothek an native DSP-Aufträge

Regel für native DSP-Aufträge des Sample-Swap (gemessen im Emulator und mit erzeugten Daten):

- DSP-Registeraufträge (Schreiben nach `0xFF900018`, 64 Halbwörter über `0xC00142D8`) bleiben gültig, wenn ein unabhängiger
  Dateileser seine Epoche ändert. Beobachteter Fehlalarm: im Stock-Dauerwechsel wechselte nur die Epoche eines fremden Lesers von
  328 auf 329, Task, Bibliotheksgeneration, Modus und Sitzung blieben gleich, Zeitgrenze und Pollbudget waren nicht erschöpft.
- Sample-Daten und der eigene Swap-Schritt brechen bei fremden Epochen weiterhin ab. Die Bindung gilt für jede native Spanne, die
  `[0x00365EC0, 0x01C65EC0)` überschneidet, und für den Swap-Schritt. Überlaufende Bereiche und andere Aufrufer bleiben streng.
- Nur die beiden bekannten nativen Sample-Funktionen dürfen bei einer Spanne vollständig außerhalb dieses Bereichs unabhängig von
  Datei- und Cache-Epochen arbeiten. Task, IRQ-Zustand, Ressourcenbesitz, terminaler Fehlerzustand, Zeitgrenze und Pollbudget
  bleiben geschützt.
- Der Ressourcenerwerb reicht die Bindung an den Transaktionskontext weiter. Die Entscheidung liegt im bereits reservierten
  Stackbereich bei Kontextoffset 120, es wird kein zusätzlicher RAM belegt. Wartefristen sind nicht erhöht, ein gesetzter
  DSP-Fehler wird nicht zurückgesetzt.
- Hergeleitet: die nativen Sample-Funktionen halten die DSP-Adresse bei `FP-16` und die Halbwortzahl bei `FP-22`; die
  Ressourcenaufrufe liegen bei `0xC0014248` und `0xC00142D4`. Eine bestehende Prüfung der Originalbytes sichert die Frames beider
  roten Firmwarefassungen.
- Gegenproben (49 gezielte ARM-Prüfungen): beide Richtungen an den Bereichsgrenzen, Adressüberlauf, Taskwechsel, fremde
  Schrittbesitzerschaft, gesperrte IRQs, bestehende Zeitgrenze. Der Stock-Dauerwechsel besteht mit acht Wechseln und
  identischen PCM-Daten.
- **Offen:** Gerätetests mit genau dieser kombinierten Firmware (Start, Auswahl bisher ungeladener Samples, wiederholte Pattern-
  und Chain-Wechsel, ausklingende Stimmen, Import, Bearbeiten, WRITE). Aus der Emulatorprüfung folgt keine Freigabe der
  RAM- und DMA-Nutzung.

Quelle: Messung 2026-11-12/native-dsp-bibliotheksbindung.

## Die beiden Simulatoren

**Der GNU-Simulator ist die Referenz (hergeleitet).** Der QEMU-Port (github vapier/qemu, Zweig `bfin`, Commit `ae8fe9a`) rechnete
ohne Patch nur 17 von 76 Vergleichen gleich zum GNU-Simulator. An jeder abweichenden Stelle lag QEMU falsch, nachgeprüft über
Einzelschritt und Befehlssatz. Damit ist die Frage beantwortet, welcher Simulator beim Filterkern richtig liegt: der
GNU-Simulator. Mit `tools/dsp/qemu-bfin.patch` rechnen alle 38 prüfbaren Funktionen bit-gleich. Die Fehlerklassen von QEMU:

- `SIGNEXTEND` für 16-Bit-Konstanten (auf arm64 falsch, wie im GNU-Simulator).
- `Rx = ASHIFT Ry BY Rz.L (S)`: Befehl fehlt, sättigendes Schieben (Hilfsfunktion `ashift32_sat`).
- Mehrfachbefehl mit Registerkonflikt (`R0 = [P0++] || [I1++] = R0`): spätere Spalten sahen das neue R0.
- MAC und MULT: Produkt ins Akku (`A0 = R1.H * R0.H`) nicht vorzeichenerweitert ab Bit 31, Runden und Sättigung auf 16, 32 und
  40 Bit fehlten.
- Akku schieben: `A1 >>> 15` ohne Vorzeichenerweiterung auf 40 Bit.
- `Rx = Ry << imm (S)` schob um `-imm`.
- 32-Bit-Add und Sub mit `(S)` ohne Sättigung.

Quelle: Messung 2026-11-16/qemu-bfin-vergleich.

**Bau des GNU-Simulators auf macOS (gemessen).** Die Erzeugung von `sim_modules_detected` benutzt eine `sed`-Anweisung ohne
abschließendes Semikolon. Das macOS-`sed` lehnt sie ab, die Pipeline meldet wegen der folgenden Sortierung trotzdem Erfolg, die
Modulliste bleibt leer, und der Hardware-Modus stürzt in `sim_hw_parse` ab. Mit der portablen Schreibweise enthält die Liste
`sim_install_hw`. Die mitgelieferte alte zlib baut mit dem verwendeten macOS-SDK nicht, der Builder nimmt die System-zlib. Quellstand
ist GNU GDB 15.2, der Builder prüft die SHA-256 des Archivs vor dem Entpacken. Quelle: Messung 2026-11-14/blackfin-boot-ruecklesen.

**Der DSP schläft nie (gemessen).** Jeder Sync läuft 1,5 bis 2,5 Zyklen je Befehl, keiner endet in `IDLE`. Echtzeit bräuchte bei
rund 2 Zyklen je Befehl etwa 200 Mio. Befehle je Sekunde, also das 25-fache des GNU-Workers. Die heißen Stellen sind der
RTOS-Kern (Queues, Sperren mit `CLI`/`STI`, Taskwechsel um `0xFFA0AAA8`, `0xFFA0B6F8`, `0xFFA0B94C`) und eine Task-Schleife
`0xFFA05104` bis `0xFFA0516E`, die `0x01F0E7F4` aufruft, abgibt und von vorn beginnt. Hergeleitet: Korg lässt den Leerlauf als
Dauerschleife laufen, nicht mit `IDLE`. Der Anteil gegenüber der Audio-ISR ist nicht gemessen. Quelle: Messung
2026-11-16/dsp-sim-tempo.

**Poll-Vorlauf im Emulator (gemessen).** Die Firmware wartet in `0xC001462C` auf den DSP und liest dabei `DSP_CTRL` zweimal je
Durchlauf, mit Schreibzugriffen auf den Stack. Der Poll-Vorlauf (`tools/emu/machine.py`, `POLL_READS = 4096`, mit `0` aus) rechnet
einen Durchlauf in einem zweiten Unicorn aus einer Kopie nach, wenn der gleiche Status wiederkehrt. Er zählt nur, wenn Register,
Flags und alle geschriebenen Stellen dem Ausgangszustand gleichen. Dann rechnet der Worker die DSP-Schritte bis zu jedem künftigen
Lesezugriff am Stück, und ganze Durchläufe entfallen. Zahlen stehen im [Emulator](../emulator.md#tempo-des-emulators).
Quelle: Messung 2026-11-16/dsp-sim-tempo.
