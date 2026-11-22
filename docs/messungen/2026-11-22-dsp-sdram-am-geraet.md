# DSP-SDRAM am roten Gerät: zwei vollständige Lesevergleiche

Stand 22. November 2026. **Am Gerät gemessen:** Electribe 2 Sampler, Hacktribe 2.02 mit Versionsmarker BLECH 1.4.8, über USB-MIDI am Linux-Rechner. Die [Ergebnisdatei](2026-11-22-dsp-sdram-am-geraet.json) enthält ausschließlich Bereiche, Prüfsummen, Zähler und Zeitangaben. Kein Firmware- oder Sampleinhalt ist enthalten.

## Ergebnis

Beide roten Kandidatenfenster aus dem [statischen und nativen Modellnachweis](2026-11-20-dsp-sdram-freiraum.md) wurden zweimal vollständig aus dem laufenden DSP gelesen. **In beiden Fenstern unterscheiden sich null Byte zwischen den Durchgängen.** Zusammen wurden je Durchgang 1.494.484 Byte erfasst. Nach Ausrichtung auf 4-KiB-Grenzen bleiben die bereits berechneten 1.490.944 Byte, also 1,421875 MiB.

| Bereich, Ende exklusiv | Byte je Durchgang | Byte ungleich null | Geänderte Byte im zweiten Durchgang |
|---|---:|---:|---:|
| `0x01C816EC` bis `0x01D00000` | 518.420 | 388.758 | 0 |
| `0x01F11B40` bis `0x02000000` | 976.064 | 731.854 | 0 |

Die Bereiche sind nicht leer oder durchgehend null. Die Herkunft ihrer vorhandenen Daten wurde nicht bestimmt. Ein späterer Nutzer muss seine ausdrücklich zugewiesene Fläche selbst initialisieren; gleiche Momentaufnahmen sind dafür kein Ersatz.

## Ablauf und Kontrollen

Vor dem ersten Schreiben wurden sechs Codefingerabdrücke geprüft, darunter der vorhandene DSP-Lesewrapper und seine Sperrfunktionen. Alle passen zum eigenen Hacktribe-Original. Die 896 Byte des ARM-Arbeitsfensters ab `0xC1000000` wurden gesichert und vor dem Einrichten nochmals unverändert gelesen.

Ein eigener 40-Byte-ARM-Helfer rief die unveränderte Firmwarefunktion `0xC00141F8` mit deren regulärer Sperre auf. Die Parameter lagen bei `0xC1000040`, der Ausgabebuffer bei `0xC1000080`. Ein Transfer umfasste höchstens 768 Byte. Vor jedem Transfer wurde der ARM-Ausgabebuffer mit einem eigenen adressabhängigen Muster gefüllt und geprüft; ein vollständig unverändert gebliebenes Muster hätte zum Abbruch geführt. Sämtliche USB-Leseantworten wurden anhand von Adresse, Länge und CRC-32 geprüft.

Die 48 Byte der laufenden DSP-Heap-Tabelle bei `0x01F02438` dienten vor und nach den Fenstern als unabhängige Kontrolle des Lesewegs. Beide Kontrollen stimmen überein:

| Heap | Laufzeitbasis | Laufzeitlänge |
|---|---|---:|
| 0 | `0x01D00000` | `0xFFFFF` |
| 1 | `0xFF904600` | `0x1D20` |
| 2 | `0xFFB00000` | `0xF` |
| 3 | `0x01E00000` | `0xFFFFF` |

Damit ist insbesondere die verkleinerte L1-Heapgrenze auch am Gerät gelesen. Die beiden bestehenden SDRAM-Heaps bleiben belegt und werden nicht zur Kandidatenfläche gezählt.

Die Durchgänge liefen nacheinander, jeweils zuerst unten und dann oben. Unten dauerten sie rund 29 Sekunden, oben rund 55 Sekunden; der gesamte Aufruf einschließlich Kontrollen und Wiederherstellung dauerte rund 169 Sekunden. Alle 3.896 Helferaufrufe antworteten mit Rückgabewert null. Es wurden keine DSP-Testmuster, Flash- oder SD-Schreibbefehle, Tastenbefehle oder Effektwechsel gesendet. Der vorhandene Gerätezustand wurde weder als Wiedergabe noch als maximale Last klassifiziert.

Nach Abschluss wurden alle 896 Byte des ARM-Arbeitsfensters zurückgeschrieben und verglichen. Eine zweite, unabhängig geöffnete USB-Verbindung bestätigte anschließend dieselbe vollständige SHA-256 wie vor dem Helfer. Das Gerät antwortete weiterhin auf INFO und READ.

## Zuordnung zum tatsächlichen Gerätestand

Der heute gelesene eingebettete DSP-Bootstrom hat die SHA-256 `a4dc5b4f634a611d4eaf44e8cdde0d3dc5087e59ed3e6b77ead3781e4a2d481c`. Zwei CRC-geprüfte ARM-Lesungen nach den DSP-Momentaufnahmen stimmen überein. Alle 157 Loaderheader und die vollständige Länge von 271.008 Byte passen. Kein Loaderziel und keiner der dort deklarierten Heaps überschneidet die Kandidatenfenster; die Heap-Tabelle stimmt mit der direkt gelesenen laufenden DSP-Tabelle überein.

Dieser Gerätestand unterscheidet sich vom am 20. November gelesenen Gerät und vom damaligen vollständigen Modellstand, obwohl der Versionsmarker weiterhin BLECH 1.4.8 nennt. Die Zuordnung erfolgt deshalb über Codefingerabdrücke, Bootstrom-Prüfsumme und die direkt gelesene Heap-Tabelle. Die früheren Modellläufe werden nicht als vollständige Ausführung dieses heutigen Gerätebuilds ausgegeben.

## Was der Vergleich belegt und was offen bleibt

**Gemessen:** Beide Fenster sind über den regulären DSP-Leseweg erreichbar und bei zwei vollständigen, zeitlich getrennten Lesedurchgängen bytegleich. Die geprüfte ARM-Arbeitsfläche ist vollständig wiederhergestellt.

**Hergeleitet:** Die ausgewerteten Loaderziele des heutigen Bootstroms und die heute gelesenen Standard-Heaps belegen diese Fenster nicht.

**Offen:** Reine Lesezugriffe auf die Kandidaten werden dadurch nicht sichtbar. Schreibzugriffe, die ihren ursprünglichen Wert zwischen zwei Abfragen wiederherstellen, sind ebenso wenig ausgeschlossen. Die Aufnahmen sind blockweise und nicht atomar; sie sind keine fortlaufende Zugriffsaufzeichnung. Maximale Stimmenzahl, alle Effektkombinationen, Aufnahme, längerer Musikbetrieb, Fehlerfälle und das blaue Gerät wurden hier nicht geprüft. Zusätzliche DSP-Codeausführung, Zeitreserve und Klangqualität wurden am Gerät nicht gemessen.

Der Gerätevergleich ergänzt daher den statischen und nativen Modellnachweis positiv, ist aber weiterhin **keine allgemeine Freigabe für beliebige neue DSP-Funktionen**. Eine konkrete Erweiterung braucht eine feste Speicherreservierung, einen passenden Ladeweg und Prüfungen ihrer tatsächlichen Last. Zusätzlicher DSP-RAM erweitert außerdem nicht automatisch den Platz im gespeicherten Firmwareabbild.

[Vollständige Metadaten](2026-11-22-dsp-sdram-am-geraet.json), [DSP-Modellnachweis](2026-11-20-dsp-sdram-freiraum.md), [ARM- und Plugin-Budget](2026-11-20-firmware-speicherbudget.md).
