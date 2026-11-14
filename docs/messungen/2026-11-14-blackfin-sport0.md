# Blackfin: SPORT0 und der native Audiotakt

Fortsetzung der [HOSTDP-Prüfung](2026-11-14-blackfin-hostdp.md).

## Hergeleitet

Das
[BF52x-Hardwarehandbuch](https://www.analog.com/media/en/dsp-documentation/processor-manuals/ADSP-BF52x_hwr_rev1.2.pdf),
Kapitel 24, beschreibt SPORT0, seine Datenregister, die FIFOs und den
DMA-Anschluss. Die veröffentlichten
[SPORT-Definitionen](https://raw.githubusercontent.com/torvalds/linux/v4.16/arch/blackfin/include/uapi/asm/bfin_sport.h)
benennen die Bitfelder; die
[BF522-Registerdefinitionen](https://raw.githubusercontent.com/torvalds/linux/v4.16/arch/blackfin/mach-bf527/include/mach/defBF522.h)
enthalten die MMR-Adressen.

Die rote Originalfirmware setzt `TCR2` und `RCR2` auf `0x031F`:
32-Bit-Wörter, sekundärer Datenkanal und Stereo-Framingsignal. Ein vollständiger
Stereo-Frame enthält deshalb vier Wörter. DMA3 empfängt und DMA4 sendet;
beide benutzen `X_COUNT=16` und `X_MODIFY=4`. Ein DMA-Block enthält vier
Stereo-Frames und 64 Bytes. Bei 48 kHz dauert der Empfang eines Blocks
rund 83,33 Mikrosekunden. Vorfüllung des Sendefifos und tatsächliche
Übertragung sind unterschiedliche Zeitpunkte.

Das Modell bekommt den externen Prüftakt ausdrücklich übergeben. Die
Prüfläufe verwenden 48 kHz und 516096000 Modellzyklen pro Sekunde.
Die zweite Zahl passt zur nativen Core-Timer-Periode `0x7E000` unter der
Annahme eines Millisekundenticks. Sie ist eine ausgewiesene Taktannahme,
keine neue Messung des Quarzes oder der Laufzeit am Gerät.

## Gemessen mit erzeugten Programmen

SPORT0 ist ein eigenes GNU-Hardwaregerät, kein gewöhnlicher RAM-Bereich.
Es besitzt begrenzte Empfangs- und Sendefifos, Registerzugriffe und
W1C-Fehlerstatus. Die Frame-Ereignisse wecken den vorhandenen DMA-Kanal.
Dessen Deskriptoren bestimmen Ziel, Blocklänge und Interrupt. Der
Interrupt-Handler wird über SIC und CEC ausgeführt und kehrt mit `RTI`
zurück. Es gibt keinen direkten Aufruf einer Audiofunktion.

Standardmäßig erhält der Eingang Nullen. Der zweite Modus liefert volle
32-Bit-Wörter aus einem festen LCG mit Startwert eins:

```text
state = (1664525 * state + 1013904223) modulo 2^32
```

Der Zustand wird je empfangenem Wort weitergeschaltet. Zusätzliche
Statusabfragen und andere Grenzen der Ausführungsscheiben verändern die
Folge nicht. Es gibt keine Audioausgabe; der Ausgang wird nur gezählt und
in einer Prüfsumme erfasst. Takt und Eingangsart sind je Sitzung fest.

Die Gegenproben decken unter anderem Folgendes ab:

- Empfang erst nach den richtigen Frame-Grenzen und Übertragungsende nach 16 Wörtern.
- Zwei synthetische Ringdeskriptoren mit unterschiedlichen Empfangszielen.
- Bruchteile von Modellzyklen ohne anwachsenden Taktfehler.
- Begrenzte FIFOs, Abschalten und Schreibschutz gemeinsamer Register im Betrieb.
- Reproduzierbares Rauschen über unterschiedliche Ausführungsscheiben.
- Abbruch bei falscher Wortbreite, Schrittweite oder DMA-Richtung.
- Ein quittierter Interrupt wird einmal verarbeitet; ein nicht quittierter Pegel meldet sich nach `RTI` erneut.
- Eine neue Interruptzuordnung wirkt auch bei bereits anstehender Quelle.
- Ein nicht erreichter Verarbeitungseinsprung oder ein Abbruch bleibt ein fehlgeschlagener Prüflauf.

71 gezielte Modulprüfungen bestehen mit dem gebauten GNU-Kern. Der
Worker verwendet die Versionskennung `BFIN5`; ältere Worker werden vor
der ersten Anforderung abgewiesen und müssen neu gebaut werden.

`npm test` besteht mit 1614 Prüfungen bei 166 ausgelassenen Prüfungen.
Der abschließende vollständige Browserlauf besteht mit 353 Prüfungen bei
einer ausgelassenen Prüfung; die neun Dokumentationsprüfungen bestehen.
Ein erster Browserlauf hatte einen Timeout bei der Versionsanzeige auf der
Startseite. Die vollständige betroffene Datei bestand anschließend mit
vier Prüfungen, danach auch der vollständige Browserlauf. Die Ursache des
einmaligen Timeouts ist offen.

Dabei wurden Fehler im vorhandenen GNU-DMA- und Interruptmodell sichtbar.
`CURR_DESC_PTR` zeigte auf den nächsten statt auf den aktuellen
Deskriptor. Die Wortbreite wurde vor dem Laden des Deskriptors ermittelt.
Eine falsche Kombination aus DMA-Richtung und Peripheral Map wurde als
erfolgreiche Übertragung behandelt. Die neuen Gegenproben schlagen davor
fehl und bestehen nach der Korrektur am Modell.

Der Interruptverteiler meldete außerdem einen noch anliegenden Pegel
mehrfach als neuen Aufruf. In einem erzeugten Vollduplexfall wurde der
Handler zweimal statt einmal gezählt. Das Modell fasst jetzt beide
SIC-Bänke je IVG zusammen, meldet Pegelwechsel und berücksichtigt beim
Rücksprung weiterhin anliegende Quellen. Diese funktionale, unmittelbare
Quittierung bildet keine SCLK- oder Synchronisationslatenzen nach.

## Gemessen beim nativen RTOS-Start

Die private rote Originalfirmware 2.02 wird als Startstrom geladen und
anschließend ab `0xFFA00000` ausgeführt. Ihr Reset, ihre Task-Erzeugung und
die beiden belegten SysControl-Aufrufe laufen unverändert. Nur das Laden
des Startstroms ersetzt den Ladeanteil des nicht verfügbaren Boot-ROMs.

Der Start erreicht jetzt die Audioverarbeitung mit einem nativen
Task-Stack in Bank B. Bei `0xFFA0141A` wurden echte Aufrufe aus
`0xFFA0020A` beobachtet. Der Rücksprung zeigt auf `0xFFA0020E`, der
Sample-Index läuft jeweils von null bis drei. Vier Aufrufe gehören zu
einem Empfangsblock. Der Stackzeiger liegt dabei bei `0xFF905368`;
`SEQSTAT` ist null. Der Einsprung wird lediglich als Haltepunkt beobachtet,
niemals von außen gesetzt oder direkt aufgerufen.

Mit Nullen und mit LCG-Eingang wurden jeweils 128 abgeschlossene Aufrufe
beobachtet. Beide Läufe übertragen bis zu diesem Haltepunkt je 544
Empfangs- und Sendewörter bei 136 Stereo-Frames. Das schließt die Frames
während der Initialisierung ein.

Heap 1 beginnt laut nativer Tabelle bei `0xFF904600`, hat vor einer
Verkleinerung durch den Effektpatch `0x39FF` Bytes und die Kennung eins.
Während des nativen Starts und der Verarbeitung ändern sich dort 2560
Bytes. Das Steuerwort bei Heap-Basis plus `0xC` enthält anschließend
`0xFF9054E0`, passend zum früheren
[Gerätebefund](2026-11-13-stufe2-speicher.md#heap-1-und-der-erste-versuch).
Alle beobachteten Stackzeiger liegen innerhalb dieses Heaps. Die beiden
Eingangsmodi erzeugen dieselbe Heapbelegung. Der Prüflauf legt weder
Taskobjekte noch Stacks anstelle des RTOS an.

Eine zusätzliche private Kopie der roten Originaldatei bekam ausschließlich
den vorhandenen Stufe-2-Speicherpatch mit seinen sieben geprüften Stellen.
Auch damit liefen der native Start und 128 Verarbeitungsaufrufe mit
LCG-Eingang durch. Heap 1 ist dann `0x1D20` Bytes groß und endet vor
Stufe 2 bei `0xFF906320`. Sein Belegungszeiger bleibt `0xFF9054E0`;
der beobachtete Task-Stack passt in den verkleinerten Heap.
Das ist eine Prüfung des Starts und der untätigen Verarbeitung, keine
Abnahme aller aktiven Effektpaare.

Ein geändertes Bereitschaftswort allein gilt weiterhin nicht als
vollständiger DSP-Start. Auch die hier beobachteten Verarbeitungsschritte
belegen keine vollständige Kopplung an alle ARM-Aufträge.

Der Lauf lässt sich mit eigenen Dateien wiederholen:

```bash
python3 tools/dsp/build_blackfin.py "$BFIN_SDK"
tools/emu/.venv/bin/python tools/dsp/blackfin_probe.py \
  --worker "$BFIN_SDK/blackfin-worker" --vsb "$E2_STOCK_VSB" \
  --sport-core-hz 516096000 --sport-input lcg \
  --observe-frames 128 --frame-entry 0xFFA0141A
```

`--observe-frames` zählt abgeschlossene Aufrufe dieser DSP-Funktion,
keine frei gewählte Blockgröße. Für jeden gezählten Aufruf muss der nächste
native Einsprung erreicht werden. Ein abgelaufenes Budget ist ein Fehler.
Ohne `--sport-input lcg` werden Nullen eingespeist.

## Offen

- Der SPORT-Prüfpfad gilt für das untersuchte externe 32-Bit-Stereoformat mit sekundärem Kanal. Andere Formate und Multichannel-DMA werden abgewiesen.
- Die Simulation arbeitet auf Frame-Ebene. Einzelne Bitflanken, zusätzliche Halteregister und deren Untertakte sind kein Hardwaretimingnachweis.
- Der geprüfte Datenpfad benutzt DMA. Interrupts für reine CPU-Bedienung der Datenregister sind nicht abgenommen.
- HOSTDP-Datenfifo und Host-DMA sind weiterhin nicht an den vollständigen ARM-Verkehr angeschlossen. Der bisherige Host-Transportzugriff auf gemeinsamen DSP-Speicher bleibt davon getrennt.
- Natürliche Stimmenenden, aktiver Effektverkehr, eigenes Part-Speichergebiet und Argumente brauchen eigene Replays. Rauschen am Eingang allein weist keinen benutzten Effekt nach.
- Die Heap- und Stackgrenzen müssen bei den späteren Effekt-Replays mitgeprüft werden; es gibt keine pauschalen Ausnahmen für diese Bereiche.
- Die Startdiagnose liest derzeit den Startstrom am Ort der roten Firmware. Der Versuch mit der blauen Originaldatei wird schon am ungültigen Startkopf abgewiesen und ist kein gescheiterter nativer Synth-Start. Dessen Zuordnung muss gesondert ergänzt werden.
- Kein Gerät wurde in dieser Prüfung angesprochen. Audio, echtes BUSY-Verhalten und DMA-Besitz am Gerät bleiben eigene Nachweise.
