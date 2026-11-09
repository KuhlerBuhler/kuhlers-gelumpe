# Sample-Swap: Schutz direkter PCM-Schreibzugriffe

Stand: 09.11.2026. Gemessen im Emulator mit erzeugten Samples und eigenen
roten Originalen, Korg 2.02 und unverändertem Hacktribe 2.02. Keine
Geräteaktion, kein Klang und kein neuer RAM- oder DMA-Nachweis.

## Gemessen: Fehler und Gegenprobe

Die [vorherige Gegenprobe](2026-11-05-sample-pcm-schreibpfade.md) verändert
64 Byte über den nativen DSP-Schreiber. Namen, Metadaten und Playback bleiben
gleich. Vor dieser Korrektur bleibt die physische Änderungsmarke null und
das Sample darf verdrängt werden. Beide roten Originale reproduzieren das.

Mit dem Bereichsschutz besteht dieselbe unveränderte Gegenprobe: Die
Audiodaten ändern sich weiterhin, aber die physische Zeile wird vor der
Signaturprüfung markiert und `can_evict` verweigert ihre Freigabe. Die
Bibliotheksdatei bleibt bytegleich.

## Hergeleitet und im Emulator geprüft: Schreibgrenze

Der gemeinsame native Schreiber beginnt bei `0xC00146B4`. Seine Aufrufer
haben die Ressource bereits erworben. `r1` enthält das DSP-Byteziel, die
unteren 16 Bit von `r3` die Halbwortzahl. Dieser Schreiber überträgt genau
diese Anzahl. Eine zusätzliche Aufrundung wäre falsch: Bei 17 Wörtern ab
Byte 30 eines 64-Byte-Samples endet der Zugriff genau am
nächsten Sample und darf dieses nicht sperren.

Die darüberliegende API `0xC0014284` benutzt bei 17 Wörtern zwei
überlappende Aufrufe mit je 16 Wörtern. Die Vereinigung umfasst 34 Byte.
Bei null bis 15 Wörtern ruft sie den Schreiber nicht auf. Der
Sample-Helfer kann dagegen zum Ersetzen eines kurzen Anfangs einen ganzen
32-Byte-Block schreiben. Entscheidend sind die Argumente, die tatsächlich
bei `0xC00146B4` ankommen.

Der Haken prüft die dann gültigen physischen Metadatenzeilen. Jede aktive
Nutzerzeile mit überlappender Spanne wird dauerhaft als verändert markiert.
Aliasse auf dieselbe physische Zeile teilen den Schutz. Überlaufende
Adressspannen oder beschädigte aktive Ausdehnungen werden konservativ
behandelt. Ein fremder Schreibzugriff in freien Nutzerraum entwertet
auch einen noch nicht veröffentlichten Swap-Auftrag. Vorbereitete
Entscheidungen und die Schutzrevision werden vor den Audiodaten verworfen.
Ein bereits gesetztes Änderungsbit ersetzt die erneute Revision nicht.

Register, Stack und Interruptzustand bleiben erhalten. Die Markierung
bleibt nach einem Teiltransfer mit Timeout bestehen. Für interne
DSP-Kommandobereiche außerhalb der Nutzerbank und Aufrufe ohne
Datenwörter werden keine Sample-Zeilen gesperrt. Der eigene begrenzte
Swap-Transport behält seine vorhandene Auftragsprüfung.

## Hergeleitet und im Emulator geprüft: Ausgangsversion beim Laden

Ein pauschales Ausnehmen aller Schreibzugriffe während des Starts wäre
unsicher. Der konkrete Parser-Aufruf darf nur seine eigene bereits
reservierte Zeile beschreiben. Dazu werden der native Aufrufweg, der
Parser- beziehungsweise Cursor-Rahmen, die Rückkehr zu `ss_boot_parse`,
der gespeicherte Slot, die physische Zuordnung, die Ausdehnung und die
noch passende Schutzrevision geprüft. Es darf kein Swap-Auftrag offen sein.
Die bestehende Prüfung des Parser-Rahmens wird gemeinsam verwendet.

Nur die so belegte Zeile ist ausgenommen. Weitere überlappende Zeilen
werden trotzdem geschützt. Ein fremder DSP-Schreiber während des
Gesamtladens verändert die Revision. Danach darf der Parser keine saubere
Ausgangsversion mehr veröffentlichen. Fehlender Nachweis führt zum Schutz.

## Gemessen: Prüfungen

| Prüfung | Ergebnis |
|---|---|
| Unveränderte ursprüngliche PCM-Gegenprobe | auf beiden roten Originalen bestanden |
| Kleine und dynamische Startladung, jeweils mit und ohne fremden PCM-Zugriff | auf beiden Originalen bestanden |
| Native Grenzen bei 16, 17 und `0x10010` Wörtern sowie leere Aufrufe | auf beiden Originalen bestanden |
| Direkter gemeinsamer Schreiber mit 17 und null Wörtern, echte Zieladressen aufgezeichnet | auf beiden Originalen bestanden |
| Teiltransfer mit Timeout | Schutz bleibt auf beiden Originalen erhalten |
| Geänderte physische Belegung an der Rückkehr vom Ressourcenerwerb | die neue Belegung wird auf beiden Originalen geschützt |
| Erzeugter ARM-Code, Alias-, Rahmen-, Register- und Bereichsprüfungen | 47 Tests bestanden |
| Zusätzliche deterministische Bereichsgegenproben | 100 bestanden |
| Größte gemeinsame Überlappung | 499 Nutzerzeilen geschützt, 27.544 ARM-Instruktionen |
| Startprüfungen Stock und Hacktribe | je 15 Startfälle und sechs statische Prüfungen bestanden |
| Native DSP-Wartepfade beider roten Builds | bestanden |
| Browserlauf mit ausdrücklich aktivierter nativer Stock-Firmware | 288 bestanden, keine Auslassung |
| Vollständiger Unit-Lauf, Wiederholung mit unveränderten Prüfgrenzen | 1.395 bestanden, 161 übersprungen, kein Fehler |

Ein erster vollständiger Unit-Lauf endet mit einem 60-Sekunden-Timeout
eines Python-Unterprozesses im unveränderten Transport-Kompositionstest.
Isoliert besteht dieselbe Prüfung mit unveränderter Grenze in 0,314 Sekunden.
Anschließend besteht der gesamte Unit-Lauf. Der ursprüngliche Fehler bleibt
im Protokoll erhalten; seine genaue Ursache ist nicht nachgewiesen.

Die Zahl der ARM-Instruktionen ist keine Messung der echten
Interrupt-Latenz. Die Prüfung liest keine Audiodaten zurück, fragt keine
Karte ab und benötigt keinen neuen veränderlichen RAM-Bereich.

Die nativen Fälle stehen in `tools/emu/sample_protection_cases.py` und
laufen über die vorhandene Schutzgruppe von `tools/emu/swap_cases.py`.
Die frühere separate PCM-Gegenprobe ist jetzt Teil dieser Gruppe.

```sh
tools/emu/.venv/bin/python tools/emu/sample_protection_cases.py --patched OWN_PATCHED.VSB --pcm-write
tools/emu/.venv/bin/python tools/emu/sample_protection_cases.py --patched OWN_PATCHED.VSB --pcm-boot
tools/emu/.venv/bin/python tools/emu/sample_protection_cases.py --patched OWN_PATCHED.VSB --pcm-edges
```

Alle Samples, Quelldaten und Kartenabbilder werden erzeugt. Originale,
Binärausgaben und vollständige Protokolle liegen außerhalb des Repos.
Die erzeugte Patchdatei hat nun 132 Haken. Die vorhandene
`data/patches/verified.json` ist damit für den kombinierten Stand veraltet;
eine vollständige Release-Prüfung wird durch diese Teilprüfung nicht ersetzt.

## Offen

- Tatsächliche Interrupt-Latenz des Bereichsschutzes am Gerät.
- Erneute Besitzerprüfung nativer Aufträge nach Ressourcenwarten und
  Begrenzung des gesamten Ressourcenwartens.
- Schutzrevision bei der Veröffentlichung neuer Aufnahmen. Diese schreibt
  intern im DSP und läuft nicht durch den hier geprüften Blockschreiber.
- Vollständige RAM-/DMA-Freigabe und der vollständige Swap-Gerätetest.

Die reine PCM-Schutzlücke des geprüften ARM-Blockpfads ist damit im Emulator
abgedeckt. Das ist keine Freigabe des gesamten Sample-Swaps zur Veröffentlichung.
