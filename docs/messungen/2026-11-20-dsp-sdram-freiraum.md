# DSP-SDRAM: Belegung, Grenzprüfung und geprüfte Kandidaten

Stand 20. November 2026. **Offline und im nativen [DSP](../glossary.md#dsp)-Modell geprüft**, kein Gerätezugriff. Firmwarequellen: develop `ba814034c43a879890c96a21e1a530823692b499`. Für alle drei Originale wurden die bekannten SHA-256 geprüft. Rohdaten, extrahierte Programme und Disassemblierungen blieben außerhalb des Repositorys. Die [Ergebnisdatei](2026-11-20-dsp-sdram-freiraum.json) enthält nur Messwerte, Bereiche und Prüfsummen.

## Ergebnis und Geltungsbereich

Es gibt inzwischen konkrete, durch statische Belegung und native Start-/Audioleerlaufläufe gestützte Kandidaten. Auf 4-KiB-Grenzen gerundet ergeben sich **1.490.944 Byte, 1,421875 MiB gemeinsam** für Stock, Hacktribe und nativen Synth. Beim nativen Synth kommen neun MiB hinzu, insgesamt **10.928.128 Byte, 10,421875 MiB**.

Diese Zahlen sind **kein bereits im Produkt reservierter Bereich und keine Gerätefreigabe für eine neue DSP-Funktion**. Nachgewiesen ist: Die bekannten Loader- und Standard-Heapbereiche überschneiden diese Fenster nicht; die vollständigen Testmuster blieben bei den unten beschriebenen nativen Modellläufen unverändert; die Beobachter meldeten dort keine CPU-, DMA- oder ausgeführten Befehlszugriffe. Vier zusätzliche gekoppelte ARM/DSP-Läufe mit einer aktiven Stimme sind inzwischen ebenfalls geprüft. Maximale Stimmenzahl, sämtliche Effektkombinationen und das reale Gerät sind weiterhin nicht abgedeckt.

| Build | Geprüfte rohe Fenster, Ende jeweils exklusiv | Zusammen auf 4 KiB ausgerichtet |
|---|---|---:|
| Stock und Hacktribe | `[0x01C816EC, 0x01D00000)` und `[0x01F11B40, 0x02000000)` | 1.490.944 Byte |
| Nativer Synth | `[0x01381354, 0x01D00000)` und dasselbe obere Fenster | 10.928.128 Byte |

Die ausgerichteten gemeinsamen Bereiche sind `[0x01C82000, 0x01D00000)` mit 516.096 Byte und `[0x01F12000, 0x02000000)` mit 974.848 Byte. Beim nativen Synth beginnt das untere Fenster bereits bei `0x01382000` und umfasst 9.953.280 Byte. Die obere blaue Loaderregion endet schon bei `0x01F11888`; die zusätzlichen 696 Byte bis zur gemeinsamen Prüfgrenze wurden nicht als weitere modellgeprüfte Kapazität gezählt.

## Statischer Nachweis am Originalstrom

Die vollständigen Loaderströme wurden einschließlich großer Füllblöcke, Init-Phasen und Überlagerungsreihenfolge erfasst. Alle Headerprüfungen, Payloadlängen und Endmarken passen; hinter dem letzten Block bleiben keine unberücksichtigten Bytes innerhalb der deklarierten Stromlänge. Stock und Hacktribe enthalten denselben ursprünglichen DSP-Strom mit 157 Blöcken, Synth einen anderen mit 154 Blöcken. Kein Loader-Zielintervall überlappt die beiden jeweiligen Kandidaten.

Die ganze Heap-Tabelle ab `0x01F02438` ist in allen drei Originalen identisch:

| Heap | Basis | Länge im Original | Zweck/Grenze |
|---|---|---:|---|
| 0 | `0x01D00000` | `0xFFFFF` | SDRAM-Allocatorbereich |
| 1 | `0xFF904600` | `0x39FF` | L1-Allocator, unter anderem RTOS-Stacks |
| 2 | `0xFFB00000` | `0xF` | Kleiner L1-Bereich |
| 3 | `0x01E00000` | `0xFFFFF` | Zweiter SDRAM-Allocatorbereich |

Der aktuelle rote [Stufe-2-Patch](../../tools/patch/stage2_memory.py) begrenzt Heap 1 auf `0x1D20` Byte und belegt dahinter seinen bereits bekannten Zustand und Koeffizienten. Die beiden SDRAM-Heaps bleiben unverändert. Die frühere blaue Kandidatenspanne von rund 11,5 MiB war deshalb zu weit: Auch dort liegen nachweislich diese beiden Heaps.

Der originale Start setzt SP auf `0xFF904600`, anschließend USP und FP. Der Startstack liegt damit nicht am oberen SDRAM-Ende. Für später erzeugte Task-Stacks wurde zusätzlich der Standard-Allokator verfolgt.

**Offline nachgeprüft:** Der rote Allokator bei `0x01F0FDAC`, sein blaues Gegenstück bei `0x01F0FD20`, berechnet die verbleibende Heapgröße, vergleicht die Anforderung ohne Vorzeichen und liefert bei Überschreitung `-1`. Erst nach erfolgreicher Prüfung wird der Cursor erhöht. Normale Allokationen wachsen daher nicht über die deklarierten Heapenden in die Kandidaten hinein. Dies schließt keine absichtlich neue Heapregistrierung, Speicherkorruption oder beliebigen Debug-Schreibzugriff aus.

### Die Adresse genau am unteren Lückenanfang

Im Effektbaustein `0x2E` steht tatsächlich ein Zeiger auf den unteren Lückenanfang. Er ist bei diesem Deskriptortyp eine **exklusive Code-Endadresse**, kein zweiter Funktionsanfang:

| Build | Codeanfang | Exklusives Ende | Kopierlänge |
|---|---|---|---:|
| Rot | `0x01C81068` | `0x01C816EC` | `0x684`, 1.668 Byte |
| Synth | `0x01380CD0` | `0x01381354` | `0x684`, 1.668 Byte |

Der Lader liest Start und Ende, bildet ihre Differenz und kopiert genau diese Länge in Schritten von höchstens 64 Byte. Er liest für diesen Block kein Byte ab dem exklusiven Ende. Die alte Deutung von Deskriptorfeld `+0x1C` als generell zweitem Funktionszeiger war für diese Variante falsch. Der betreffende Kopierpfad prüft außerdem die Blocklänge gegen `0x7D0`; mehr freies SDRAM hebt solche bestehenden Ladergrenzen nicht automatisch auf.

### Aktuelle ARM-Schreibwege

Der aktuelle [blaue Sample-Import](../../tools/patch/user_samples.py) hält seine Grenze bei `PCM_END = 0x01365AE0`. Er berechnet die gepolsterte Endadresse und weist zu große Samples vor dem DSP-Schreiben ab. Er erweitert den blauen PCM-Bereich nicht auf 25 MiB und belegt damit die zusätzliche Kandidatenfläche nicht. Der zugehörige [Ablehnungsfall](../../tools/emu/user_samples_cases.py) prüft eine zu große Datei und anschließendes gültiges Laden.

Zusätzlich wurden die vollständigen aktuellen BLECH-Sätze privat auf die Originale angewandt, einschließlich frisch gebauter Laufzeitpatches. Ihre DSP-Ströme sind bytegleich mit den geprüften Eingaben: bei Stock/Hacktribe Original plus Stufe-2-Patch, bei Synth der Originalstrom. Das verifiziert den tatsächlich enthaltenen DSP-Programmstand. Die DSP-Einzelläufe spielen die ARM-Befehle nicht vollständig nach. Für die unten beschriebenen vier aktiven Fälle wurde zusätzlich die vollständig gepatchte aktuelle ARM-Firmware gekoppelt gestartet.

## Nativer Modellnachweis

Die bisherigen Einzelharnesses mappten 64 MiB und legten Testcode bei `0x03000000` ab. Für diese Prüfung wurde eine private GNU-Prüffassung verwendet, deren SDRAM bei **32 MiB endet**. Bestehende Quellen und gemeinsame Werkzeuge wurden nicht verändert.

Die Speicherbeobachtung war vor dem ersten nativen Befehl aktiv und blieb über Start und Beobachtungszeit erhalten. Gezählt wurden CPU-Datenzugriffe, DMA-Zugriffe und tatsächlich ausgeführte Befehle in jedem Fenster. Debug-Lesen zur Auswertung zählt nicht als Firmwarezugriff; die Loaderziele sind separat erfasst.

Jedes ganze Kandidatenfenster wurde mit eigenem Code-/Daten-Testmuster belegt. Die Codewörter dienten im Firmwarelauf als passive Markierung; eigene Kontrollen führten Code im Fenster tatsächlich aus. Nach den Läufen wurden die ganzen Fenster zurückgelesen und die Prüfsummen verglichen.

| Laufgruppe | Fälle | Native Audioaufrufe nach Initialisierung | Ergebnis in jedem Kandidaten |
|---|---:|---:|---|
| Stock mit Stufe 2, beide Fenster | 2 | je 128 | Testmuster unverändert, alle Zugriffszähler null |
| Hacktribe mit Stufe 2, beide Fenster | 2 | je 128 | Gleiches Ergebnis |
| Synth, beide Fenster | 2 | je 128 | Gleiches Ergebnis |
| Stock mit Stufe 2 und Synth, beide Fenster verlängert | 4 | je 47.999 in einer vollständigen Modellsekunde | Gleiches Ergebnis |

Die kurze Gruppe deckt nur rund 2,7 ms Audioaufrufe ab. Die verlängerten Läufe umfassen jeweils genau 516.096.000 zusätzliche Modellzyklen nach Initialisierung, bei der verwendeten Taktannahme eine Modellsekunde. SPORT verarbeitet dabei je 48.000 Stereo-Frames mit deterministischem LCG-Eingang. Die 47.999 Audioeinsprünge sind der tatsächlich beobachtete Wert an der Periodengrenze. Das ist fortlaufender Audioleerlauf, keine Volllast aus spielenden Stimmen und Effekten.

Stock und Hacktribe haben bytegleiche gepatchte DSP-Ströme. Die verlängerten Stock-Läufe prüfen deshalb denselben DSP-Eingang; eine gesonderte vollständige Hacktribe-ARM-Ausführung wird daraus nicht behauptet. Synth verwendet seinen eigenen natürlichen Audioeinsprung bei `0xFFA01406`, rot `0xFFA0141A`.

### Kontrollen gegen einen wirkungslosen Beobachter

- In jedem der drei unterschiedlichen Fenster wurden eigene CPU-Lese-/Schreib- und DMA-Lese-/Schreibzugriffe erzeugt und erkannt.
- Die eigene Codeprobe erzeugt genau sieben gezählte Befehle im Kandidaten. Der zusätzliche Audioeinsprungzähler wurde mit einem eigenen Einsprung geprüft.
- CPU-Schreiben, Befehlsabruf sowie DMA-Lesen und DMA-Schreiben bei `0x02000000` wurden abgewiesen. Oberhalb der gewählten 32-MiB-Modellgrenze gibt es keine unbemerkte Ausweichfläche.
- Alle primär gewerteten Firmwareläufe initialisierten das RTOS ohne DSP-Ausnahme und hielten ihre vollständigen Testmuster unverändert.

Frühe Versuche mit einer kollidierenden Beobachterabfrage und zunächst falschem blauen Audioeinsprung wurden nicht als bestandene Nachweise verwendet. Die Ergebnisdatei enthält nur die klar zugeordneten gültigen Läufe und die nötigen Kontrollen.

## Gekoppelte ARM/DSP-Prüfung mit aktiver Stimme

Zusätzlich bestanden vier Fälle mit den vollständig aktuellen gepatchten Stock- und Synth-Abbildern, jeweils unteres und oberes Kandidatenfenster. Die Eingabe-Prüfsummen stimmen mit dem privaten Neubau der vollständigen Standardsätze überein. Jeder Fall startet ARM und DSP frisch, erreicht den Hauptbildschirm, öffnet Stimme 0 über einen Pad-Druck und läuft anschließend 140 ms Modellzeit weiter.

| Build, jeweils beide Fenster | Beleg für aktive Verarbeitung | Kandidatenergebnis |
|---|---|---|
| Stock | Eigenes Testsample mit 4.000 Byte PCM ist korrekt geladen; die aktive Stimme zeigt darauf; DMA liest nachweislich dessen Daten | Keine CPU-/DMA-/Befehlszugriffe, ganzes Testmuster unverändert |
| Nativer Synth | Die eigene native Synth-Stimme wird geöffnet; unabhängiger Beobachter meldet CPU-Lesen ihres Stimmenkontexts, ohne eine PCM-Stimme zu unterstellen | Gleiches Ergebnis |

Vor dem Pad waren die erfassten SPORT-Ausgabewörter null, danach enthielt die Ausgabe beim Stock 5.954 und beim Synth 13.356 von null verschiedene Wörter. Innerhalb jedes Builds sind die aufgenommenen Ausgabedaten zwischen unterem und oberem Testfenster bytegleich. Diese Rohslotbeobachtung belegt DSP-Ausgabeaktivität, keine Lautsprecherzuordnung oder gemessene Klangqualität.

Alle vier Fälle liefen ohne ARM-Assertion, Reset oder DSP-Ausnahme. Frühere rote Fälle mit Original-ARM plus Stufe-2-Patch bleiben ergänzend erhalten; für die hier gewertete aktuelle Matrix werden die vollständig gepatchten Abbilder verwendet. Die jeweilige zweite Beobachtung des PCM- oder Stimmenbereichs setzt den Kandidatenbeobachter nicht zurück.

## Was damit noch nicht bewiesen ist

Das Modell ersetzt das Laden durch das echte Boot-ROM und bildet bekannte SysControl-/OTP-Aufrufe nach. Nicht vollständig abgedeckt sind maximale Stimmenzahl, alle Effektwechsel und -kombinationen, Aufnahme, alle Hostbefehle, Fehlerzustände, Versorgungsvorgänge sowie das reale Speicher- und Cacheverhalten. Die aktiven Fälle erfassen jeweils eine Stimme im voreingestellten Effektzustand. Ein Zeit- oder Klangbudget für einen neuen Algorithmus ist ebenfalls nicht gemessen.

Daher ist die Aussage enger als eine allgemeine Freigabe: **bekannte statische Besitzer sowie die geprüften nativen Start-/Audioleerlaufpfade und die genannten gekoppelten Ein-Stimmen-Fälle verwenden die Kandidaten nicht**. Das ist ein neuer positiver Nachweis, nicht mehr bloß eine Suche nach Nullfolgen. Für einen konkreten produktiven DSP-Baustein müssen sein Bereich ausdrücklich reserviert, der Lader und Prüfer angepasst sowie seine eigentlichen Arbeitslasten und das Gerät geprüft werden.

## Was das für neue Funktionen bedeutet

Das fast volle L1-Fenster bedeutet nicht, dass dem Gerät insgesamt nur acht Codebytes bleiben. In den geprüften SDRAM-Kandidaten lässt sich im Modell zusätzlicher Code ausführen und mit CPU oder DMA auf Daten zugreifen. Der gemeinsame ausgerichtete obere Bereich allein umfasst 952 KiB.

Die gespeicherte Firmware ist eine weitere Grenze: DSP-Code muss auch im VSB-Bootstrom oder über einen neuen Ladeweg untergebracht werden. Zusätzliches DSP-Programmpayload würde normalen Platz im Firmwareabbild mit ARM-Erweiterungen teilen. Ein per Füllbefehl initialisierter Datenpuffer braucht dagegen nicht seine ganze Laufzeitgröße als gespeichertes Payload. Aus 1,42 MiB modellgeprüftem DSP-RAM folgen deshalb nicht 1,42 MiB zusätzlich speicherbarer Programmcode im bestehenden Abbild.

## Nachtrag vom 22. November: rotes Gerät gelesen

Die [anschließende Gerätemessung](2026-11-22-dsp-sdram-am-geraet.md) hat beide roten Kandidatenfenster inzwischen zweimal vollständig aus dem laufenden DSP gelesen. Zwischen den Durchgängen unterscheiden sich null Byte. Die laufende Heap-Tabelle bestätigt außerdem die beiden bestehenden SDRAM-Heaps und den auf `0x1D20` verkleinerten L1-Heap. Der ARM-Arbeitsbuffer wurde vollständig wiederhergestellt und über eine neue Verbindung geprüft. Das ergänzt diesen Modellnachweis; es ersetzt keine fortlaufende Zugriffsaufzeichnung oder Volllastprüfung. Der tatsächliche Gerätestand ist in der neuen Messung separat über Prüfsummen zugeordnet.

[ARM-Bilanz und bisherige DSP-Grenzen](2026-11-20-firmware-speicherbudget.md), [Stufe-2-Speicher](2026-11-13-stufe2-speicher.md), [DSP-Aufbau](../hintergrund/dsp-erster-blick.md), [vollständige Zahlen, Kontrollen und Hashes](2026-11-20-dsp-sdram-freiraum.json).
