# Blackfin: echter Start und fehlende ROM-Funktionen

Fortsetzung:
[Blackfin: SysControl und RTOS-Start](2026-11-14-blackfin-syscontrol.md).
Der dort beschriebene Stub klärt den unten noch offenen normalen ROM-Aufruf.

## Gemessen im Simulator

Die Startdiagnose lädt den Startstrom der privaten roten Originalfirmware
2.02 vom Host in den DSP-Speicher und startet bei `0xFFA00000`.
Füllblöcke werden vollständig geladen. Die Umrechnung bleibt
`file = ram - 0xC0000000 + 0x100`.
Danach läuft der originale Reset- und RTOS-Code im Hardware-Modus des
GNU-Simulators. Direkte Aufrufe einzelner Initialisierungsfunktionen und
erzeugte Task-Objekte ersetzen diesen Ablauf nicht.

Der native Start erreicht jetzt:

| Beobachtung | Wert |
|---|---|
| ROM-Einsprung, vor seiner ersten Instruktion angehalten | `0xEF000038` |
| Letzte ausgeführte Aufrufstelle | `0xFFA04E58` |
| Rücksprungregister `RETS` | `0xFFA04E5A` |
| `R0` | `0x00000711` |
| `R1` | `0x01E00954` |
| `R2` | `0` |
| `SP`, `FP` | `0x01E00938`, `0x01E00960` |
| `SEQSTAT` | `0` |

Die Diagnose endet mit Fehlerstatus. Dies ist weder ein abgeschlossener
RTOS-Start noch eine bestandene DSP-Initialisierung. Die vollständigen
Registerprotokolle bleiben außerhalb des Repositorys.

Ein gesonderter Halt unmittelbar vor dem Aufruf bei `0xFFA04E58` wird nach
9852 weiteren Schritten nach der ersten 16-Schritt-Scheibe erreicht.
Bis dahin verändert der native Start bereits 525 Bytes im Bereich
`0xFF904600` bis `0xFF904A64`. Die Kontrolllesung davor enthält dort null.
Das zeigt bereits vom echten Start benutzten Speicher in Bank B; die
Zwischenräume und spätere Stacknutzung sind damit nicht als frei belegt.
Der Start wurde für diese Lesung angehalten, nicht über den ROM-Aufruf
hinweg fortgesetzt.

## Gemessener Fehler im GNU-Kern

Der vorherige ungültige virtuelle Funktionsaufruf bei `0xFFA0BE6C` entstand
davor durch die Umsetzung paralleler Instruktionen. Bei einer Addition oder
Subtraktion schrieb der GNU-Kern das Zielregister sofort. Ein paralleler
Speicherzugriff las dadurch den neuen statt des ursprünglichen Werts.

In der Stackeinrichtung bei `0xFFA0AFAA` wurde so die untere Stackadresse
statt des Stackendes abgelegt. Der spätere Stackrahmen überschrieb die
virtuelle Funktionstabelle des Task-Objekts. Der ungültige Funktionsaufruf
war eine Folge davon.

Der Builder stellt die betroffenen Additions- und Subtraktionsresultate
in dieselbe verzögerte Schreibwarteschlange wie die anderen parallelen
Resultate. Sechs erzeugte Gegenproben prüfen Addition und Subtraktion,
jeweils mit und ohne Sättigung sowie an beiden Überlaufgrenzen.
Vier Fälle schlagen mit dem vorherigen Kern fehl; mit dem korrigierten
Kern bestehen alle sechs. Der native Start erreicht anschließend den oben
genannten ROM-Aufruf. Es wurde kein Sprungziel im DSP-Programm ersetzt.

## Gemessene ROM-Abbruchprüfung

Die mitgelieferten ROM-Tabellen für den gewählten BF527 sind leer.
GNU bildete trotzdem einen ROM-Bereich ab, aus dem ungültige Bytes gelesen
werden konnten. Der Builder lässt leere Tabellen nicht mehr abbilden.

Vor der Ausführung einer Instruktion im Fenster `0xEF000000` bis
`0xEFFFFFFF` hält der Prozess an. Er meldet PC, letzte ausgeführte
Instruktionsadresse, `RETS` und alle 54 über die Simulator-Schnittstelle
lesbaren Register. Ein unbekanntes Ziel beendet die Sitzung mit Fehler;
es gibt weder eine Nullantwort noch eine Fortsetzung über Modellantworten.
Auch ein ausdrücklich dort gesetzter Haltepunkt darf diesen Fehler nicht
in einen erfolgreichen Halt umwandeln. Dasselbe gilt, wenn die letzte
erlaubte Instruktion genau in das ROM springt.

Erzeugte Programme prüfen den direkten ROM-Einsprung, einen echten
indirekten Aufruf samt Rücksprungadresse und den Haltepunktfall. Die
Gegenproben für fehlende Registerangaben und den Haltepunkt waren vor der
Korrektur rot. Eine weitere Prüfung beendet einen erzeugten Hilfsprozess
mit Status 139: Die Anfrage schlägt fehl und die Sitzung bleibt geschlossen.
Ein solcher Abbruch gilt nicht als bestandener Replay.
Eine Initialisierung ohne ausgeführte Schritte bricht ebenfalls mit Fehler
ab, statt unbegrenzt denselben Haltezustand abzufragen.

## Hergeleitet aus der öffentlichen ROM-Schnittstelle

Der von Analog Devices veröffentlichte
[ROM-API-Header im Linux-Kern](https://raw.githubusercontent.com/torvalds/linux/v4.16/arch/blackfin/include/asm/bfrom.h)
ordnet `0xEF000038` der Funktion `bfrom_SysControl` zu.
`R0 = 0x711` fordert einen Schreibzugriff auf `VR_CTL`, `PLL_CTL`,
`PLL_DIV` und `PLL_LOCKCNT` an. `R1` zeigt auf eine Struktur mit fünf
16-Bit-Feldern; `R2` ist reserviert und hier null.
Die Registersteuerung ist im Kapitel 18 des
[BF52x-Hardwarehandbuchs](https://www.analog.com/media/en/dsp-documentation/processor-manuals/ADSP-BF52x_hwr_rev1.2.pdf)
beschrieben.

Damit sind Name und Argumentaufbau hergeleitet. Der ausgewertete Header
belegt allein weder den vollständigen Rückgabewert noch alle vorübergehenden
Registerwirkungen. Es ist deshalb noch kein Stub eingesetzt, der diesen
Aufruf als erfolgreich beantwortet. Der fehlende Vertrag bleibt ein
sichtbarer Startfehler.

## Prüfgrenzen

Die früheren direkten Funktions- und Frameaufrufe aus dem
[ersten Prototyp](2026-11-14-blackfin-boot-ruecklesen.md) belegen ausgeführten
DSP-Code, aber keine tatsächliche Heap- oder Task-Stackbelegung. Der
verkürzte Initialisierungsmodus wurde aus `blackfin_probe.py` entfernt.

Für die Abnahme müssen der originale RTOS-Start und seine Speicherbelegung
sichtbar bleiben. Besonders relevant sind Heap 1 und Task-Stacks in Bank B
ab `0xFF904600`, die Heap-Tabelle bei `0x01F02440` und die in
[Stufe 2: eigener Speicher](2026-11-13-stufe2-speicher.md) dokumentierten
Überschneidungen. Diese Bereiche sind nach dem hier erreichten Zwischenhalt
noch nicht vollständig initialisiert und geprüft.

Schreibprüfungen dürfen den eigenen Part-Slot, Argumente und
Koeffizientenzeiger nicht pauschal ausnehmen. Die Gegenprobe für den
IFX-Handler bei `0x18AF0` auf ungeraden Parts bleibt Bestandteil der noch
ausstehenden Prüfung. Ein Segfault oder eine fehlende Schreibspur ist
dabei ein Fehlschlag, kein unauffälliges Ergebnis.

## Stand der Prüfungen

26 Prüfungen des Anschlusses und 30 bestehende Modell- und Cacheprüfungen
bestehen mit dem tatsächlich gebauten GNU-Kern. Die neun
Dokumentationsprüfungen bestehen ebenfalls. Der Browserlauf besteht mit
353 Prüfungen bei einer ausgelassenen Prüfung. Die abschließende
Unitprüfung besteht mit 1610 Prüfungen bei 166 ausgelassenen Prüfungen.
Diese Ergebnisse heben den roten nativen Start nicht auf.

Die Prozessschnittstelle trägt die Kennung `BFIN2`; ältere gebaute Prozesse
werden abgewiesen und müssen mit dem aktuellen Builder neu gebaut werden.

## Wiederholen

```sh
python3 tools/dsp/build_blackfin.py "$BFIN_SDK"
export BFIN_WORKER="$BFIN_SDK/blackfin-worker"
PYTHONPATH=tools/emu tools/emu/.venv/bin/python -m unittest test_blackfin_backend test_blackfin_stream test_dsp_model test_bootcache
python3 tools/dsp/blackfin_probe.py --worker "$BFIN_WORKER" --vsb "$E2_STOCK_VSB"
npm test
npm run test:e2e
```

Das SDK und die private Firmware liegen außerhalb des Repositorys.
Der Diagnosebefehl endet beim beschriebenen ROM-Aufruf absichtlich mit
Status 1. `--virtual` ist nur eine getrennte Instruktionsdiagnose ohne die
Interrupt-Hardware des RTOS-Pfads.

## Offen

- Den vollständigen Vertrag jedes erreichten ROM-Aufrufs belegen und dessen
  Wirkung mit einem einzeln geprüften Stub abbilden.
- Reset und RTOS bis zur Initialisierung durchlaufen lassen; Heap und
  Task-Stacks nachweisen.
- Danach den gekoppelten ARM/DSP-Lauf, Part-Wechsel und Replays samt
  vollständigen Schreibprüfungen wiederholen.
- DMA, SPORT, natürliche Stimmenenden, Hardwarezeit und Klang bleiben
  gesonderte Nachweise.

Es gab keinen Gerätezugriff und keine Firmwareänderung. Dieser Stand gibt
weder Sample Swap noch die Speicheraufteilung von Stufe 2 frei.
