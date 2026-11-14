# Blackfin: HOSTDP-FIFO und DMA1

Fortsetzung von [SPORT0 und dem nativen Audiotakt](2026-11-14-blackfin-sport0.md).

## Hergeleitet

Das
[BF52x-Hardwarehandbuch](https://www.analog.com/media/en/dsp-documentation/processor-manuals/ADSP-BF52x_hwr_rev1.2.pdf),
Kapitel 8 und Tabelle 6-7, beschreibt den Host-Port und seine Zuordnung
zu DMA1. Die [Anwendungsnotiz EE-337](https://www.analog.com/media/en/technical-documentation/application-notes/EE-337.pdf)
bestätigt das Konfigurationsformat und die unterschiedlichen Wortbreiten
von BF52x und BF54x.

Der BF52x-FIFO hält 16 Wörter zu je 16 Bit. Sieben Wörter richten einen
Auftrag ein: Host-Konfiguration, Adresse unten und oben, X-Anzahl,
X-Schrittweite, Y-Anzahl und Y-Schrittweite. Erst der vollständige
Deskriptor darf an den DMA gehen. Die Host-Konfiguration wird semantisch
übersetzt; sie wird nicht als gleich aufgebautes `DMA_CONFIG` behandelt.

Bei Host-Schreibaufträgen kommt der Abschlussinterrupt nach dem Schreiben
in den DSP-RAM über DMA1. Bei Host-Leseaufträgen darf `HOSTRD_DONE` erst
nach dem letzten abgeholten FIFO-Wort anstehen. `0x2C` ist der Steuerbefehl
`DMA FINISH`. Die im Handbuch ausdrücklich ignorierten Steuerbefehle
ab `0x3C` bleiben wirkungslos.

## Gemessen an ARM-Code und bisherigem Modell

Die rote Originalfirmware 2.02 liest für ihre Bereitabfrage das Bit eins
bei GPIO-Basis `0x01E26000` plus `0x98`. Das entspricht GPIO 6.1.
Die Abfrage bei `0xC001716C`, aufgerufen über `0xC00145F0`, invertiert
dieses Bit. Der bisherige ARM-Emulator schaltet es bei jeder Abfrage um.
Sein fester Host-Status `0x85` und dieses Umschalten sind Modellannahmen.

Ein Mitschnitt der originalen ARM-Anweisungen über eine Modellsekunde
mit erzeugtem leerem Flash erfasst 585 vollständige Deskriptoren:

| Eigenschaft | Beobachtet |
|---|---|
| Host schreiben, `0xAB` | 441 Aufträge |
| Host lesen, `0xA9` | 144 Aufträge |
| 16 Wörter | 461 Aufträge |
| 32 Wörter | 38 Aufträge |
| 64 Wörter | 86 Aufträge |
| X-Schrittweite | immer zwei |
| Y-Anzahl und Y-Schrittweite | immer null |

Dieser Mitschnitt benutzt noch den bisherigen DSP-Ersatz. Er belegt die
vom ARM ausgegebenen Rahmen, keine tatsächlich ausgeführten DSP-Transfers.
Die Arbeitskopie und alle Rohspuren liegen außerhalb des Repositorys.

## Gemessen mit erzeugten Gegenproben

Der neue Buszugang erreicht das HOSTDP-Hardwaregerät im GNU-Kern.
Steuerwörter und Datenzugriffe haben getrennte Eingänge. Der Port hält
einen begrenzten FIFO und übergibt den vollständigen Auftrag an DMA1.
Der DMA-Kanal führt den Speichertransport aus. Der Port kopiert seine
Nutzdaten nicht direkt in den Ziel-RAM.

104 gezielte Modulprüfungen bestehen. Die ersten 16 FIFO-Gegenproben
schlagen vor dem Busanschluss fehl. Weitere Gegenproben zeigen vor ihrer
Korrektur veraltete Kanalbesitzer, unerlaubte Moduswechsel und das Verlieren
eines wartenden Deskriptors.

Geprüft werden insbesondere:

- Vor Wort sieben beginnt kein DMA; vor seinem Lauf ändern FIFO-Schreibwörter keinen Ziel-RAM.
- Der FIFO nimmt höchstens 16 Wörter auf. Zwei Abschnitte ergeben genau 32 übertragene Wörter.
- Schutzwörter unmittelbar vor und hinter dem Ziel bleiben erhalten.
- Nach DMA-Vorfüllung steht noch kein Leseabschluss an; erst das letzte abgeholte Wort setzt ihn.
- Erzeugte DSP-Interrupt-Handler zählen den Aufruf, quittieren die Quelle und kehren mit `RTI` zurück.
- Eine Folgekonfiguration bleibt getrennt, bis der erste Auftrag nativ quittiert ist.
- Reset verwirft wartende Arbeit. Schreibendes `DMA FINISH` verwirft den Host-FIFO und meldet den Abbruch über DMA1.
- Quittierung gibt den Kanalbesitz frei. Spätere Registerprogrammierung gehört einem neuen Auftrag, auch bei identischen Werten.
- Moduswechsel während aktiver oder wartender Arbeit brechen vor der Änderung ab; ein ausdrücklicher Reset bleibt möglich.
- Ungültige Größen, MMIO-Ziele, falsche Richtung und nicht unterstützte Datenzugriffe brechen ab.

Der Kanalbesitzer wird beim nativen Programmieren eines neuen DMA-Auftrags
ungültig. Ein alter Host-Auftrag darf einen inzwischen ersetzten
Deskriptor weder quittieren noch stoppen. Schreib- und Leseberechtigungen
lassen sich getrennt ändern; bereits zulässig angenommene Schreibwörter
werden dadurch nicht verworfen.

## Gemessen mit der roten Originalfirmware im Simulator

Nach dem echten Reset-/RTOS-Start läuft ein eigenständiger DSP-Prüffall
mit LCG-Eingang. Er überträgt 16 erzeugte Wörter über FIFO und DMA1 nach
`0x01000000` und liest sie über denselben Bus zurück. Alle Wörter stimmen.
Der FIFO ist vor dem DMA-Lauf voll. `HOSTRD_DONE` ist vor dem Leeren null
und nach dem letzten Lesen eins.

Die originalen Handler quittieren beide Richtungen. Nach dem Schreiben
steht `HOST_STATUS` auf `0x018C`, nach dem Lesen auf `0x008C`; `DMA_RDY`
ist jeweils wieder gelöscht. `SEQSTAT` ist null. Der Prüfpfad setzt keine
Quittierungsbits von außen und ruft keinen Handler direkt auf.

Ein zusätzlicher erzeugter Postfachauftrag benutzt Kopf `0x106`, Befehl
eins, einen Eintrag und Parameter `0x2E5`. Seine Nutzdaten sind das selbst
gewählte 32-Bit-Wort `0x12345678`. Der Rahmen kommt über den FIFO nach
`0xFF900A34`. Danach läuft der DSP nativ weiter. Beim Rücklesen über den
FIFO steht der Wert am zugehörigen Parameterort `0xFF800B94`.
`SEQSTAT` bleibt null. Das belegt hier die Übergabe vom DMA-Interrupt an
den ausgeführten Postfachcode, ohne direkten Aufruf des Setzers.

Die Prüfung lässt sich mit einer eigenen roten Originaldatei wiederholen:

```bash
python3 tools/dsp/build_blackfin.py "$BFIN_SDK"
tools/emu/.venv/bin/python tools/dsp/blackfin_probe.py \
  --worker "$BFIN_SDK/blackfin-worker" --vsb "$E2_STOCK_VSB" \
  --sport-core-hz 516096000 --host-transport fifo \
  --host-address 0x01000000
```

Dabei werden 32 Bytes der eigenen DSP-Emulatorsitzung als Prüfbereich
überschrieben. Ein fehlender nativer Abschluss oder falsche Daten sind
ein Fehler. Der Worker verwendet die Versionskennung `BFIN6`.

## Abschließende Prüfungen

`npm test` besteht mit 1615 bestandenen und 166 ausgelassenen Prüfungen,
ohne Fehler. `npm run test:e2e` besteht mit 353 bestandenen und einer
ausgelassenen Prüfung, ebenfalls ohne Fehler. Die 104 gezielten Modulprüfungen
wurden zusätzlich mit dem neu gebauten Worker ausgeführt.

Beide vollständigen Läufe liefen nacheinander. Wegen der hohen Rechnerlast
benutzte der Unitlauf die dokumentierte serielle Ausführung mit
`GELUMPE_LOAD_GATE=off GELUMPE_JOBS=1 npm test -- --test-concurrency=1`.
Die Testauswahl blieb vollständig.

## Kompatibilitätsauswahl

`BlackfinPort` und die Startdiagnose wählen weiterhin ausdrücklich
`host_transport='compatibility'` als Vorgabe. Diese Auswahl verwendet den
bisherigen direkten Speichertransport und den angenommenen Status `0x85`.
Die Auswahl `fifo` verwendet ausschließlich den neuen Buszugang. Ein
Fehler führt zum Abbruch, nicht zum Wechsel in die Kompatibilitätsauswahl.

Ohne gemeinsame Modellzeit ist `fifo` ein eigenständiger DSP-Prüfpfad.
Im hier geprüften FIFO-Zwischenstand verweigert `Machine` seinen ARM-Anschluss ausdrücklich. Damit
können die alte GPIO-Annahme und der neue Datenpfad nicht versehentlich
als vollständige native Kopplung gelten.

## Offen

- Gemeinsame ARM-/DSP-Modellzeit, unterbrochenes `IDLE` und die tatsächliche GPIO-/FRDY-Kopplung folgen gesondert.
- Die Kompatibilitätsvorgabe bleibt erhalten, bis gekoppelte Fälle auf Hacktribe, roter und blauer Originalfirmware bestehen.
- Unterstützt sind zunächst 16 Bit, Little Endian, lineare A9/AB-Aufträge und Vielfache von 16 Wörtern bei Schrittweite zwei.
- Aktives lesendes `DMA FINISH`, Burst-Timing, aktiviertes Bus-Timeout und andere Datenformate werden ausdrücklich abgewiesen.
- Die aus Host-Aufträgen erzeugten DMA-MMR-Werte sind hergeleitet und wurden nicht am Gerät rückgelesen.
- Noch kein Audio-, Durchsatz-, Stimmenende- oder vollständiger Effekt-Nachweis. Kein Gerät wurde angesprochen.

Die [gemeinsame ARM-/DSP-Modellzeit mit GPIO](2026-11-14-blackfin-modellzeit.md) setzt diese Untersuchung fort.
