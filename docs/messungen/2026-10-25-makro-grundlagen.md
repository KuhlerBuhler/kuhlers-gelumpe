# Grundlagen für native Bedienmakros (25.10.)

Gemessen im Emulator mit den eigenen Originaldateien von Hacktribe, rotem Sampler und blauem Synth, jeweils 2.02.
Keine Verbindung zum Gerät. Die Makrofunktion mit Übersicht, Aufnahme und Wiedergabe ist noch nicht eingebaut.
Der Versuch prüft den Eingangsweg, einen weckbaren Aufrufweg, das Tempo und einen festen Speicherbereich für
[Idee 61](../ideen/61-makros.md).

Die [Messmetadaten](2026-10-25-makro-grundlagen.json) enthalten nur Prüfsummen, Adressen, Zustandswerte und
Zeitmessungen. Firmware, Pattern und Event-Dateien werden nicht gespeichert. Die virtuelle Karte und der
Recorder-Vergleich bleiben im Arbeitsspeicher des Messprogramms.

## Reproduzieren

`tools/emu/macro_cases.py` nimmt unveränderte eigene VSB-Dateien. Für neue Synth-Adressen vergleicht es den
roten und blauen Code mit `fwmap`; bekannte Adressen kommen weiterhin aus `synthaddr`. Neue Zuordnungen
stehen zunächst nur als Messbefund in den Metadaten, nicht als ungeprüfte Ergänzung der Gerätetabelle.

```bash
tools/emu/.venv/bin/python tools/emu/macro_cases.py research \
  --vsb "$E2_HACKTRIBE_VSB" --build hacktribe
tools/emu/.venv/bin/python tools/emu/macro_cases.py research \
  --vsb "$E2_STOCK_VSB" --build stock
tools/emu/.venv/bin/python tools/emu/macro_cases.py research \
  --vsb "$E2_SYNTH_VSB" --build synth --reference-vsb "$E2_STOCK_VSB"
tools/emu/.venv/bin/python tools/emu/macro_cases.py verify-research \
  --report docs/messungen/2026-10-25-makro-grundlagen.json
python3 -m unittest discover -s tools/patch -p 'test_macros.py'
```

Mit `--report` lässt sich eine andere Metadatendatei wählen. `--sections input,tempo,memory` lässt den
Recorder-Vergleich aus. Ein solcher Teillauf macht einen älteren Recorder-Nachweis nicht wieder aktuell.
Die Prüfung verlangt alle drei Builds, vollständige Fälle und dieselben Quellenstände je Messabschnitt.
Änderungen am Messprogramm, Vertrag, verwendeten Emulatorcode, den Synth-Zuordnungen oder an den
deklarierten Speicherbesitzern machen die entsprechenden Nachweise ungültig.

## Zeit und Tasks

**Gemessen:** Unicorn 2.1.4, `SLICE=2000`, Zeitstempel aus `machine.time_ns`. Der ursprüngliche
1-kHz-Interrupt wurde in einem Fenster von 1000 ms jeweils 1000-mal aufgerufen. Die Zählung geschieht
zusätzlich zur Zeitmessung. Ein Zeitstempel kann bei der hinterlegten Annahme von 5 ns je ARM-Befehl um
höchstens etwa 10 Mikrosekunden vom betrachteten Befehl abweichen. Das ist keine Laufzeitmessung am Gerät.

Der normale Panel-Eingang liegt im Sampler bei `0xC002837C`, in der CsTask. Die Rohdaten einer Nachricht
stehen am übergebenen Objekt ab `+12`, fünf Byte lang. Der Vergleich sendet Drehgeber, Regler, SHIFT,
Pad-Druck und Loslassen sowie Touchpad über den normalen Panel-UART. Die Reihenfolge blieb erhalten.

Der RAM-Versuch benutzt diesen Weg:

1. Ein kleiner Zusatz an `0xC002A7B8` prüft in der PeriodicTask die Fälligkeit. Er ruft nur die
   Task-Variante der vorhandenen Flag-Funktion `0xC0000E9C` mit Flaggruppe 2 und Bit 2 auf.
2. Die CsTask wacht über ihren bestehenden Warteweg auf. Der Zusatz an `0xC002A558` gibt höchstens
   acht bereitliegende Nachrichten an den normalen Panel-Verteiler weiter.
3. Die Firmware gibt Bildschirm- und Transportbedienung selbst an die UiTask weiter. Synthetische
   STOP-, PLAY- und STOP-Eingaben müssen die Zustandsfolge laufend, gestoppt, laufend, gestoppt ergeben.
   Die zugehörigen UI-Aufrufe werden getrennt von den vorherigen körperlichen Eingaben gezählt.

Alle Adressen im Absatz sind Sampler-Adressen. Die geprüften Synth-Zuordnungen stehen in den Metadaten.
Keine Bedienfunktion läuft im Zusatz aus der SeqTask oder aus einem Interrupt. Der Versuch läuft auf der
Originalfirmware ohne Plugin-Laufzeit und nimmt weder deren Rahmenraster noch deren Speicherpool in Anspruch.
Die tatsächliche Einbindung muss die neuen Eingriffe noch bei den gemeinsamen Besitzern registrieren.

**Gemessen:** 24 versetzte einzelne Eingaben und eine Folge von acht gleichzeitig fälligen Nachrichten pro
Build. Die zusätzliche Verzögerung wird gegen dieselbe über UART eingespeiste Folge verglichen. Die
unveränderten Abstände zur Fälligkeit bleiben ebenfalls im Bericht; eine zu frühe Ausführung außerhalb
der Messtoleranz wird abgewiesen. Die UART-Laufzeit wird beim Vergleich nicht stillschweigend der
Wiedergabe zugeschlagen. Die Höchstwerte stehen je Build in den Metadaten.

Beide Zusätze sichern Register und Flags. Die Rückkehrwerte wurden mit den Werten am Eintritt verglichen.
Der eigene feste Zusatz auf dem vorhandenen Task-Stack beträgt 64 Byte je Aufruf. Die tiefste beobachtete
Nutzung einschließlich gerufener Originalfunktionen steht separat im Bericht. Sie ist kein Beweis einer
universellen maximalen Stacktiefe aller Firmwarewege. Der Messvertrag lässt hier höchstens 1024 Byte zu;
die CsTask besitzt laut Deskriptor 18432 Byte, die PeriodicTask 9216 Byte.

Ein aus einer im RAM kodierten und wieder gelesenen GMAC-Datei stammendes EXIT kam mit Makro-Herkunft an.
Ein danach körperlich eingespeistes EXIT kam mit Panel-Herkunft an. **Gemessen ist die Unterscheidung des
Ursprungs**, noch nicht der spätere Abbruch einer vollständigen Makro-Wiedergabe.

## Wirksames Tempo

**Gemessen:** Die normalen Tempofelder reichen für externe Clock nicht aus. Nach intern eingestellten
150 BPM bleiben sowohl das bisher benutzte Zehntel-BPM-Feld als auch das Hundertstel-BPM-Feld des
Taktgebers beim alten Wert, obwohl eingehende MIDI-Clock das wirksame Tempo verändert.

Der verwendbare Messpunkt ist die Periode des Taktgebers:

| Build | Adresse | Einheit |
|---|---|---|
| Hacktribe und Stock | `0xC0340388` | Pikosekunden je 1/2304 Viertel |
| Synth | `0xC0340578` | Pikosekunden je 1/2304 Viertel |

Interne 120 und 150 BPM ergeben 217013888 beziehungsweise 173611111 ps. Der Umrechnungsvertrag liefert
12000 beziehungsweise 15000 Hundertstel-BPM. Bei exakt eingespeisten 120 BPM über DIN verändert sich die
Periode entsprechend der bekannten Millisekunden-Auflösung des Korg-Folgers. Der bisherige Tempowert
bleibt dabei 150 BPM. Siehe auch [Sequencer-Timing](../hintergrund/sequencer-timing.md).

**Gemessen:** Der Wert ist auch bei gestopptem Sequencer verfügbar. Bei ausbleibender externer Clock bleibt
die zuletzt ermittelte Periode stehen. Die spätere Makrofunktion braucht daher zusätzlich eine ausdrücklich
geprüfte Clock-Ausfallerkennung. Ein alter Periodenwert darf nicht als Beleg für weiter eingehende Clock gelten.

**Festgelegter Vertrag:** vorzeichenlose Q32.32-Viertel, Zeit null bei der ersten Aktion, gleiche Phasen
behalten ihre Dateireihenfolge. Die Referenzrechnung arbeitet mit Mikrosekunden und Hundertstel-BPM und
führt den Divisionsrest mit. Vier 4/4-Takte entsprechen bei 120 BPM acht Sekunden und bei 150 BPM 6,4 Sekunden.
Eine native Rechnung muss ausreichend breite Zwischenwerte verwenden; die Python-Referenz begrenzt das
Ergebnis auf 64 Bit, nicht ihren Multiplikations-Zwischenwert. Tempoänderungen sind an ihrem tatsächlichen
Zeitpunkt zu teilen, nicht rückwirkend auf den ganzen letzten Zeitabschnitt anzuwenden.

## Fester Speicher

**Gemessen:** Der folgende Kandidat ist in allen drei Originalen mit FF gefüllt und überschneidet weder
geschriebene Bytes noch deklarierte RAM-Flächen der bestehenden passenden Patches:

| Bereich, Ende exklusiv | Byte | Verwendung |
|---|---:|---|
| `0xC019A400` bis `0xC019C400` | 8192 | eigener Code |
| `0xC019C400` bis `0xC019E400` | 8192 | 512 Ereignisse zu 16 Byte |
| `0xC019E400` bis `0xC019F000` | 3072 | Zustand und begrenzte Arbeitsdaten |

Der Speichervertrag steht einmal in `tools/patch/macro_contract.py`. Der spätere Builder muss die Flächen
wirklich deklarieren und seine Codegröße dagegen prüfen. Der Befund reserviert sie noch nicht im
veröffentlichten Patch. Aufnahme und Wiedergabe können denselben Ereignispuffer nutzen; Overdub ist nicht
vorgesehen. Eine bestimmte Zahl von Sekunden folgt aus 512 Ereignissen nicht: Warten verbraucht keinen
Eintrag, dichte Bewegungen schon. Die Aufnahme muss bei vollem Puffer sichtbar enden.

Kein Speicher oberhalb des Firmware-Abbilds wird beansprucht. Der große Import-/Exportpuffer, fremde Stacks
und der Plugin-Pool sind ausgeschlossen. Der Karten-Guard `card_gate.py` merkt nur Kartenverfügbarkeit;
er bietet keine Dateisperre. Der gemeinsame sichere Dateiweg bleibt für das spätere Speichern zu bestimmen.

## GMAC-Vertrag

**Festgelegt, noch kein Geräte-Dateiweg:** Little Endian, Version 1, 64 Byte Header, danach 16 Byte pro
Ereignis. Die CRC32 nach IEEE deckt die ganze Datei ab, während ihr eigenes Feld als null behandelt wird.

| Offset | Inhalt |
|---:|---|
| 0 | `GMAC`, vier Byte |
| 4 | Version, u16 |
| 6 | Headerlänge 64, u16 |
| 8 | Ereigniszahl, u32 |
| 12 | Nutzdatenlänge, u32 |
| 16 | Endphase, u64 Q32.32 |
| 24 | CRC32, u32 |
| 28 | Generation, u32, für die spätere Auswahl zweier gültiger Speicherstände |
| 32 | Name: 1 bis 31 druckbare ASCII-Zeichen, nullterminiert und auf 32 Byte mit null aufgefüllt |

Ein Ereignis enthält Phase u64, fünf unveränderte Panel-Byte und drei reservierte Nullbytes. Die erste
Phase ist null, weitere Phasen sind monoton und nicht größer als die Endphase. Mehr als 512 Einträge,
falsche Längen, CRC, Typen, Indizes und reservierte Bytes werden abgewiesen. Die Reglerwerte bleiben
absolut, Drehgeber-Deltas relativ, Pad-Werte behalten beide ursprünglichen Datenbytes. STOP als
Recorder-Steuerung gehört nicht in die Datei. Ein aufgezeichnetes EXIT bleibt dagegen zulässig.
Systemkontext und verbotene Menüaktionen benötigen zusätzlich eine Prüfung beim tatsächlichen Ausführen.

Der Header enthält keinen Anfangszustand, keine Pattern-Daten und keinen Auftrag zur Wiederherstellung.
Die spätere Wiedergabe muss erreichte musikalische Änderungen beibehalten.

## Vergleich mit Korgs Event Recorder

**Gemessen auf Hacktribe:** Acht Aufnahmen über die normale Oberfläche: leerer Vergleich, Sample-Rad,
LEVEL, Modus, Menü, Part-Auswahl, Pattern-Auswahl und Part-Mute. Die Prüfung verlangt in jedem Fall die
beobachtbare Bedienwirkung. Sample-Rad, LEVEL und Mute müssen zusätzliche Recorder-Daten erzeugen.
Die Feldadressen für Sample, LEVEL und Mute kommen direkt aus `data/map/pattern.mjs`.

Die Dateien für Modus-, Menü- und Part-Auswahl haben dieselbe Länge wie der leere Vergleich. Unterschiede
einzelner Bytes können auch von Zeitstempeln stammen. Das ist ein Befund dieser Fälle, kein Nachweis, dass
jede denkbare Bedienfolge im Event Recorder unmöglich wäre. Pattern-Vorwahl und laufendes Pattern werden
getrennt beobachtet.

Jede Aufnahme enthält den vollständigen Anfangspatternblock im RAM. Beim Abspielen einer solchen Aufnahme
wurde Sample 20 vorher eingestellt, beim Start stand dort wieder 0 und nach dem Ende wieder 20. Es trat
kein Firmware-Assert auf. Der Zwischenklang im DSP wurde nicht geprüft. Für ein relatives Makro wären die
aufgenommenen drei Rastungen stattdessen auf den aktuellen Wert anzuwenden und die Änderung beizubehalten.
Darum wird der vorhandene Event Player für die Makro-Wiedergabe nicht übernommen.

## Grenzen

- Kein Hörtest, keine Messung von Cache- und DSP-Laufzeiten am Gerät und keine allgemeine Latenzgarantie.
- Keine fertige Aufnahme-Engine, kein MAKROS-Menü, kein Kartenformat im Gerät und kein installierter Patch.
- Die feste Codefläche muss auch für den vollständigen Ausbau reichen; aktuell ist nur der begrenzte
  Aufrufversuch ausgeführt. Weitere Task-Haken und Haltezustände brauchen ihre eigenen Fälle.
- Clock-Ausfall, lange Menü-/Ladevorgänge, gleichzeitige körperliche Eingaben und die Kontextgrenze für
  Systemaktionen sind für die vollständige Wiedergabe noch zu prüfen.

**Bestätigte Bedienung:** STOP behält seine normale Transportwirkung und beendet während einer
Makroaufnahme zusätzlich den Mitschnitt. Bei Makrowiedergabe stoppt STOP den Sequencer, bricht aber
nicht das Makro ab. Dafür ist EXIT vorgesehen.
