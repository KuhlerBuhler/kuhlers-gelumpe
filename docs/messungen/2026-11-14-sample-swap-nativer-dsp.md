# Sample-Swap mit ausgeführtem DSP-Code

Die [gemeinsame Modellzeit](2026-11-14-blackfin-modellzeit.md) wird mit dem
vollständigen BLECH-Patchsatz des Sample-Swap-Zweigs verbunden. Der DSP startet
weiterhin über den echten Reset- und RTOS-Pfad. Alle Samples und Patternangaben
dieser Prüfung werden erzeugt. Es gibt keinen Gerätezugriff und keine Audioausgabe.

## Gemessen

Die erzeugte Bibliothek enthält die Slots 500, 501 und 502 mit 4000, 2000 und
4000 PCM-Bytes. Das DSP-Budget wird nur im Prüfabbild auf 6144 Bytes begrenzt.
Damit passt die Bibliothek nicht gleichzeitig in den DSP. Das aktuelle Pattern
verwendet zuerst Slot 500; die übrigen Parts wählen die Werkswellenform null.

Ein erster Lauf der roten Korg-Grundlage ergibt:

| Schritt | Geladene Slots | DSP-Basis des gewählten Samples | PCM |
|---|---|---:|---|
| Start mit Slot 500 | 500 | `0x00365EC0` | erste zwei Bytes abweichend |
| Auswahl von Slot 501 | 500, 501 | `0x00366E60` | vollständig gleich |
| Auswahl von Slot 502 | 501, 502 | `0x00365EC0` | vollständig gleich |

Beim anschließenden Pad-Anschlag zeigt Wort 10 des Stimmenblocks auf die
neue Basis von Slot 502. Das Gate-Kontrollwort wird gesetzt. ARM-Assertions
und DSP-Ausnahmen treten dabei nicht auf. Der erste Lauf prüft Slot 501 noch
vor der letzten Auslagerung; sein Zustand danach ist damit nicht belegt.

Ein erster Hacktribe-Lauf zeigt bei allen drei gelesenen Samples vollständige
PCM-Gleichheit und dieselbe Auslagerung. Das Gate bleibt nach weiteren 120 ms
bei gehaltenem Pad gesetzt. Dieser Wert ist ein Kontrollwort und kein
nachgewiesener Zeiger auf das natürliche Ende der Sample-Wiedergabe.

### Gegenprobe der ersten PCM-Abweichung

Dieselbe erzeugte Karte wird mit unveränderter roter Originalfirmware geladen.
Auch dort sind ausschließlich die ersten beiden Bytes von Slot 500 null statt
des erzeugten Werts. Slot 501 und 502 stimmen vollständig. Die Gegenprobe mit
gültigen Werkswellenformen in den übrigen 15 Parts zeigt dasselbe Ergebnis.

Der ARM überträgt bei `0xC0014848` zunächst das richtige Halbwort `0xECDA`.
Ein eigener Beobachter erfasst anschließend Speicher-DMA auf Kanal `0x100`:
vier Byte Nullen ab `0x00365EBE` überlappen das erste User-Halbwort. Die
Konfiguration ist `0x7607`, Wortbreite zwei Byte, Anzahl zwei, Schrittweite zwei.
Der DSP-Kern schreibt dieses Halbwort in der Gegenprobe nicht selbst.

### DMA-Gegenproben und Pool-Grenze

Nach den [Korrekturen des DMA-Modells](2026-11-14-blackfin-dma-grenzen.md)
bleibt die Überlappung auch mit richtigen Deskriptorzeigern, Kanalabschaltung
und begrenzten Quellzeilen bestehen. Der unveränderte rote Originalstart
schreibt nach 800 ms Modellzeit weiterhin vier Bytes ab `0x00365EBE`.

Die zur Laufzeit geladene DSP-Funktion bei `0xFFA04A94` schreibt den Startpunkt
des Auftrags. Eine gesonderte Diagnose nach dem echten Reset- und RTOS-Start
liest `B2 = 0x003082C0` und `L2 = 0x0005DC00`. Der Ring endet damit genau bei
`0x00365EC0`. Für diese Diagnose wird der ARM angehalten und der DSP bis zum
Haltepunkt weiter ausgeführt; sie ist keine zusätzliche gemeinsame Zeitmessung.

Die Platzsuche des lokalen Prototyps beginnt einen ausgerichteten Block von
32 Bytes oberhalb dieser Grenze. Bestehende Samplebereiche werden weiterhin ab
der physischen Untergrenze eingesammelt. Auch ein alter Bereich, der über den
neuen Anfang reicht, bleibt damit belegt. Leere alte Einträge dürfen keinen
späteren Kandidaten unter die neue Grenze setzen. Das nutzbare Budget zählt
Datenbytes; seine Obergrenze wird vor der Adressaddition begrenzt.

Der ursprüngliche Loader lädt das erste aktive Sample selbst und benutzt dafür
seinen freien DSP-Zeiger. Im Swap-Modus wird dieser Zeiger beim erfolgreichen
Öffnen der Bibliothek nur aufwärts auf die neue Grenze geklemmt. Ohne diesen
Schritt bleibt das erste Sample an der alten Basis, und später fehlt durch
die Lücke ein zusammenhängender Platz. Kleine Bibliotheken und der normale
Ladeweg ohne Swap behalten ihr bisheriges Verhalten.

Die erzeugten Prüfungen von Platzsuche, Startzeiger und Sample-Schutz bestehen
mit 179 Fällen. Beide roten Originale erzeugen denselben Patch. Die Verlagerung
der Platzsuche nutzt einen bereits reservierten Codebereich und dessen
bestehende Größen- und Kollisionsprüfungen. Der Gerätetest dieser abgeleiteten
Grenze bleibt offen; kein PCM-Präfix wird aus dem Vergleich genommen.

### Abschließender nativer Vergleich

Die neuen vollständigen Kandidaten beider roter Grundlagen bestehen alle 14
Prüfungen mit dem vollständig korrigierten Worker. Alle erzeugten Codebereiche
werden zusätzlich mit dem aktuellen Builder verglichen; ein veralteter Kandidat
wird vor dem Start abgewiesen. Zwei erzeugte Gegenproben prüfen diese Zuordnung.

| Schritt | Geladene Slots | Sample-Basis | Stock-PCM | Hacktribe-PCM |
|---|---|---:|---|---|
| Start und Kontrolle vor der Auswahl | 500 | `0x00365EE0` | vollständig gleich | vollständig gleich |
| Auswahl von Slot 501 | 500, 501 | `0x00366E80` | vollständig gleich | vollständig gleich |
| Auswahl von Slot 502 | 501, 502 | `0x00365EE0` | vollständig gleich | vollständig gleich |
| Erneute Kontrolle beider verbleibender Samples | 501, 502 | wie oben | vollständig gleich | vollständig gleich |

Die beiden verbleibenden Bereiche überlappen sich nicht. Genau eine neue Stimme
wird beim Pad-Anschlag geöffnet; ihre Sample-Adresse entspricht der neuen Basis
von Slot 502. Gemeinsame Modellzeit, echter DSP-Start, native Host-Port-Transfers
und fehlerfreie ARM-/DSP-Ausführung werden in demselben Lauf geprüft.

Trotzdem bleiben die beobachteten Kern- und DMA-Lesezugriffe im PCM-Bereich des
angeschlagenen Samples sowohl im ersten 20-ms-Abschnitt als auch nach weiteren
120 ms bei null. Der Prüffall meldet deshalb ausdrücklich keinen Nachweis eines
natürlichen Sample-Endes. Die erfolgreichen Prüfungen gelten für Start,
Transport, Belegung und Stimmenadresse, nicht für den vollständigen Audiopfad.

Beide vollständigen Kandidaten bestehen außerdem die 16 normalen Startfälle
von `tools/emu/check.py --quick`. Die gemeinsame Zeit wird dabei gesondert im
nativen Prüffall geprüft; die normalen Startfälle ersetzen ihn nicht.

### Abschließende Prüfungen

Die vollständige Unit-Prüfung des kombinierten Stands besteht mit 1603
erfolgreichen und 172 übersprungenen Tests. Die Browserprüfung besteht mit
339 erfolgreichen und einem übersprungenen Test. Die gezielte Prüfung mit dem
privaten Worker besteht mit 166 Blackfin- und Swap-Modulfällen. Die 179
Prüfungen von Platzsuche, Startzeiger und Schutz laufen zusätzlich mit erzeugten
ARM-Daten. Die unabhängige Nachprüfung findet nach den Korrekturen keine
verbleibende schwere Abweichung im geprüften Umfang.

Neun gesonderte Prüfungen je roter Grundlage bestehen außerdem mit dem
bisherigen Host-Port-Modell: normales Laden, erster aktiver Satz, Start mit
EXIT, Auslagerung, erhaltene Namen, Auswahl nach dem Laden, Vorausladen der
Nachbarn, Cache-Besitz bei Bildschirmwechsel und vollständige PCM-Gleichheit.
Dieser Vergleich ersetzt die nativen DSP-Läufe nicht.

Der lesende Blick auf die MIDI-Portliste des Linux-Rechners zeigt zum Abschluss
keinen verfügbaren Electribe-Port. Es werden keine Befehle an das Gerät gesendet.
Der nächste Gerätevergleich braucht deshalb eine erneute Verbindung und den
passenden geprüften Testbuild auf einer Testkarte.

## Hergeleitet

Die Abweichung entsteht auch ohne Sample-Swap. Sie ist daher noch kein
Nachweis eines Fehlers im Swap-Transport. Ebenso wenig ist sie damit harmlos
oder erklärt: Der DMA-Auftrag und sein Besitzer müssen weiter verfolgt werden.
Kein PCM-Präfix wird beim Vergleich ausgeblendet.

Die [Zugriffsbeobachtung](2026-11-14-blackfin-speicherzugriffe.md) kann die
nächsten Gegenproben ohne Ersatzwerte begleiten. Der neue Prüffall
`tools/emu/blackfin_swap_cases.py` liest beide verbleibenden Samples nach der
Auslagerung nochmals vollständig und prüft nicht überlappende Grenzen. Vor
dem Pad-Anschlag liest er alle 24 Gate-Blöcke und verlangt genau eine neu
geöffnete Stimme mit der richtigen Sample-Adresse.

## Offen

- Ursache und Gerätevergleich des überlappenden Speicher-DMA-Auftrags.
- Tatsächliche PCM-Lesezugriffe beim Spielen und das Ende dieser Zugriffe. Dafür fehlt der Vergleich der Stimmenkonfiguration mit dem Gerät.
- Natürliche Stimmenenden und ausklingende Effekte. Ein Gate-Wert reicht dafür nicht.
- Große reale Bibliotheken, Live-Wechsel, Kartenlaufzeiten und vollständiger RAM-/DMA-Besitz am Gerät.

Die Prüfung belegt bisher Transport, Tabellenwechsel und eine Stimmenadresse.
Sie ist keine Freigabe des gesamten Sample-Swap und kein Klangnachweis.
