# Oberer Sample-RAM: cachebewusste Probe und native Puffer

Stand: 06.11.2026. Neue Probe zunächst mit erzeugten Daten und im
Emulator geprüft. Der danach gesondert freigegebene
[Füll- und Leerlaufvergleich am Gerät](2026-11-06-sample-ram-cache-geraet.md)
ist erfolgreich; die weiteren Betriebsarten stehen am Gerät noch aus.
Voraus geht die erfolgreiche
[CPU-/Tabellendiagnose](2026-11-06-sample-ram-mmu.md).

## Gemessen im Modell

`tools/device/sample_ram_cache.py` trennt neue Messoperationen von der
alten, weiterhin gesperrten Füllprobe. Die drei eingefrorenen Füll-/Prüfblöcke
bleiben bytegleich. Neue Blöcke sind höchstens 64 KiB groß und vollständig
innerhalb `0xC274F000..0xC4000000`. Task-Stack und erster KiB des
EXEC-Arbeitsbereichs gehören nicht zu dieser Zielspanne.

Die Zulassung verlangt den aktuellen SysEx-Patch mit Upload-Fix und eine
frische doppelte Tabellenlesung. Host und ARM prüfen das gemessene
Steuerregister `0x0005107D` sowie beide TCM-Rohwerte `0x0000001C`. Der
ARM-Code prüft zuerst den CPU-Typ, dann die TCM-Register und danach weitere
Abbildungs- und UI-Voraussetzungen. Ein abweichendes TCM-Overlay wird damit
nicht als gewöhnlicher DDR-Bereich zugelassen. Es wird keine unbekannte
TCM-Bitbedeutung angenommen und keine Konfiguration umgeschaltet.

Die Fülloperation schreibt das adressabhängige Muster über die gecachte
Adresse, reinigt nur ihre 32-Byte-Zeilen, leert den Schreibpuffer und prüft
das Ergebnis über den Spiegel. Die Prüfoperation liest zuerst den ganzen
Block über den Spiegel. Danach vergleicht sie je Wort beide Sichten und
das erwartete Muster, ohne Cachebereinigung. Drei Seitenkarten trennen
physische Änderungen, gecachte Änderungen und unterschiedliche Inhalte.
Gleiche Änderungszahlen verdecken damit nicht verschiedene Wortwerte.
Ein Kartenwert zählt abweichende 32-Bit-Wörter pro 4-KiB-Seite bis höchstens
255; die Zahl betroffener Seiten bleibt genau.

Die erzeugten Tests beobachten CPU-Änderungen nur im Cache, simulierte
DMA-Änderungen nur im RAM, Bereichs- und Zeilengrenzen sowie falsche
CPU-/UI-/Tabellenzustände. Unbestätigte Aufrufe stoppen auch nach einem
vorher erfolgreichen Block ohne weitere Lese- oder Restore-Befehle.
Bestätigte Fehler erlauben nur die Wiederherstellung des eigenen
Arbeitsbereichs; anschließend wird auch dessen Spiegelsicht verglichen.

14 neue Cache-/ARM-/Hostprüfungen, acht Prüfungen der Modusauswertung und
37 bestehende Diagnoseprüfungen bestehen mit erzeugten Daten. Die native
SysEx-Prüfung besteht für beide roten Minimalbuilds: Muster veröffentlichen,
beide Sichten unterscheiden und nach unbestätigtem zweitem Block stoppen.
CP15, Cache und physischer Spiegel sind dabei eingespeiste Modelle.

## Gemessen im Emulator: beide roten Originale

`tools/emu/sample_ram_modes.py` führt je 13 Abläufe auf Korg 2.02 ohne
Hacktribe und auf Hacktribe aus. Die Startbibliothek enthält 40 erzeugte
Samples mit zusammen 24.000.000 PCM-Bytes. Beide Sitzungen dauern rund
230 emulierte Sekunden und enden ohne Assertion oder fehlgeschlagene Aktion.

| Ablauf | Geprüfter Abschluss |
|---|---|
| Start | 40 geladene Samples |
| PLAY und Patternwechsel | laufender Transport, geänderte echte Patternnummer, danach STOP |
| Sampling mono/stereo | je acht emulierte Sekunden, eingespeister DSP-Endwert, Slotanzahl, aktive Metadatenidentitäten und Frei-Zeiger nach Verwerfen unverändert |
| Resampling mono/stereo | ebenso, zusätzlich echter nativer PLAY-Startzweig |
| WAV-Import | Zielslot geladen, Name `imp`, PCM-Länge 100.000 Bytes |
| SAMPLE EDIT mit EXIT | Startpunkt geändert und zurückgenommen |
| SAMPLE EDIT mit WRITE | Änderung nach WRITE und anschließendem EXIT erhalten |
| Einzelexport | neue Datei `501_imp.wav`, gültiges RIFF und erwartete bearbeitete PCM-Länge |
| Gesamtexport | geänderte vollständige Bank, genaue Slotliste, erwarteter Name und PCM-Länge, erneutes Lesen nach Rückkehr zur Hauptseite |
| Gesamtimport über IMPORT SAMPLE | alle sechs erzeugten Zielslots mit erwartetem Namen und je 24.000 PCM-Bytes geladen |
| Löschen | gewählter Slot tatsächlich ungeladen, aktive Anzahl um eins kleiner |

Der Wächter ist vor dem ersten CPU-Befehl bis zum Ende aktiv. Er erfasst
exakt `0xC274F000..0xC4000000` und `0xC674F000..0xC8000000`, jeweils für
Lesen und Schreiben. In beiden Sitzungen gibt es dort keinen CPU-Zugriff.
Die tatsächlich beobachteten Grenzen stehen im Bericht. Der untere
Arbeitspuffer wird in diesen neuen Sitzungen nicht kontinuierlich erfasst;
seine Zuordnung stammt aus der getrennten Codeanalyse und den bestehenden
breiten Messungen.

Zunächst breit instrumentierte große Läufe wurden vor Abschluss beendet.
Die ersten gezielten großen Läufe stoppten korrekt, weil das Messskript
nach fester Zeit vor Ende des Gesamtexports weiterging. Der abschließende
Ablauf wartet begrenzt und ohne weitere Tastendrücke auf die erwartete
fertige Datei und liest sie nach EXIT erneut. Nur die erfolgreichen
Wiederholungen belegen die vollständige Modusfolge.

`npm test` besteht mit 1374 bestandenen und 161 ausgelassenen Tests ohne
Fehler. `npm run test:e2e` besteht mit 285 bestandenen und einem ausgelassenen
Test ohne Fehler. Dies ist keine Freigabe des Sample-Swaps auf dem Gerät.

## Hergeleitet aus beiden roten Originalen

Die folgenden ARM-Pfade sind in Korg 2.02 und Hacktribe an den geprüften
Stellen bytegleich. Der Nachweis betrifft die angegebenen Pfade und ist
kein Ausschluss beliebiger DMA-Eigentümer.

| Vorgang | Einstieg und Aufrufer | Belegter Datenweg |
|---|---|---|
| Aufnahme/Resampling | `0xC0082F1C(transport, start_play)`; `0xC0082FBC` bei Resampling; UI-PLAY `0xC0083000` | `0xC0013D98(1, mode, source, DSPcursor)` baut Hostkommando `0x3B`; CPU schreibt über den Host-Port, kein ARM-Aufnahmepuffer übergeben |
| Aufnahmeende | `0xC0082D40` ruft `0xC004F128(physical_index, mode, source)` | DSP-Endbriefkasten `0xFF903210` über `0xC004E23C` und `0xC00141F8`; danach CPU-Metadaten und Frei-Zeiger |
| Einzel-/Gesamtimport | `0xC003644C` / `0xC00364F0`, gemeinsamer Parser `0xC0035B10` | `0xC00369F0` liefert `0xC0D3A940..0xC273AA40`; Kartenlesen in Blöcken bis 64 KiB, dann `0xC004EF28` zum Host-Port |
| Einzel-/Gesamtexport | `0xC0039CC4` / `0xC0039E68`, WAV-Schreiber `0xC0039B2C` | derselbe untere Arbeitspuffer, DSP-Lesen über `0xC004EDDC`, `f_write` bei `0xC009DFB8` |
| Slice-Vorbereitung | `0xC00395E4` über `0xC0050208` | derselbe Arbeitspuffer; Extent plus zwei Bytes muss strikt unter `0x01A00100` liegen, Blöcke bis `0x8000` 16-Bit-Wörter |
| Start/End/Loop und Tune/Level | `0xC004E63C`, `0xC004E710`, `0xC004E7E8`, `0xC007F980`, `0xC007F8A8` | niedrige Metadatentabellen, keine hier gezeigte DMA-Programmierung |
| Löschen | Command `0x24`, `0xC0039588` über `0xC0035994`, `0xC004E4EC`, `0xC004E558` | Metadaten deaktivieren und gegebenenfalls letzten DSP-Zeiger zurücksetzen, keine PCM-Verschiebung |
| SD-FIFO | Lesen `0xC00180F0`, Schreiben `0xC0017F18`, Controller `0x01C40000` | CPU kopiert aus `base+0x28` beziehungsweise nach `base+0x2C`; kein EDMA-Deskriptor in diesen Schleifen |

Der Aufnahmestart liest Quelle und Mono/Stereo aus Manager `+0x708` und
`+0x704`. Das zweite Argument von `0xC0082F1C` erlaubt PLAY-Start; es wählt
nicht die Quelle. Das Hostkommando enthält sieben 16-Bit-Nutzwörter; der
Sendehelfer rundet die Übertragung auf 16 Wörter auf. DSP-Adressen sind
keine ARM-DDR-Zeiger.

Der WAV-Schreiber nimmt `R1 = FIL*`, `R2 = Deskriptor*`, `R3 = DSP-Byteoffset`
und die PCM-Bytezahl als fünftes Stackargument. Eingangs-R0 wird für die
Pufferzuordnung nicht verwendet. Der Code sichert R1 bei `0xC0039B38` als
Dateizeiger und verwendet ihn bei den späteren `f_write`-Aufrufen.

## Hergeleitet: vollständige Bedienpfade

Gesamtimport hat keinen eigenen DATA-UTILITY-Menüpunkt. Der echte
Importbrowser auf Bildschirm 39 akzeptiert WAV und `.all`. Bei `.all`
erscheint die Bestätigung „Import All Samples“. Command `0x12` führt über
`0xC0038D80` zum Gesamtlader. Dessen anderer direkter Aufrufer ist der
Startpfad bei `0xC0038D60`.

SAMPLE EDIT verwendet die Bildschirme 37 und 38. Der native Auswahlpfad
`0xC007EC74(manager, delta, notify)` setzt den geladenen logischen Slot.
ENTER öffnet die Bearbeitung und Command `0x20` erzeugt den echten
Snapshot. WRITE, Taste `0x0E`, erzeugt ohne weitere ENTER-Bestätigung
Command `0x25`; EXIT erzeugt Command `0x21`. Der Dispatcher liefert dabei
den gültigen Kontext. Direkte Aufrufe des Commandhandlers mit einem
erfundenen Objekt wären kein Nachweis dieses Bedienpfads.

Die vollständig gelesene Sample-Edit-Menütabelle enthält keine eigenen
NORMALIZE- oder TRUNCATE-Seiten. Start, Ende und Loop sind echte Menüpunkte.

## Offen

Die erfolgreiche CPU-Modusfolge verwendet erzeugte Bibliotheken und WAVs.
Sampling und Resampling haben nur einen eingespeisten DSP-Endwert;
es gibt weder Klang noch echte Aufnahme-DMA. Eine geschlossene Seite allein
belegt kein Verwerfen: Slotanzahl und DSP-Zeiger müssen zurückkehren.

Cache-Lesezugriffe können spätere schmutzige Zeilen verdrängen. Ein
Nachher-Vergleich erkennt weder jeden kurzzeitigen Schreibzugriff noch
zurückgenommene Änderungen. Deshalb bleiben CPU-Schreibtrace und weitere
Besitzanalyse notwendig. ADC-/SPORT-/DSP-DMA, weitere ARM-DMA-Eigentümer
und der physische USB-Übertragungsweg sind noch nicht vollständig belegt.
Die in den SD-Schleifen fehlende EDMA-Nutzung schließt andere DMA nicht aus.
Globale Literalwerte allein belegen keinen Puffer; scheinbare obere
Adressen können auch Gleitkommakonstanten sein.

Die weiteren Bedienabschnitte bleiben bis zu ihrer gesonderten Freigabe aus.
Kein Musterergebnis wird allein als Freigabe eines Swap-Caches gewertet.
Der erste echte Lauf mit Muster und unmittelbarem Leerlaufvergleich
ist [bestätigt](2026-11-06-sample-ram-cache-geraet.md). Auch der getrennte
[USB-Lesetransfer](2026-11-06-sample-ram-usb.md) mit 1 MiB in
32-KiB-Blöcken aus dem unteren Arbeitspuffer ist geprüft. Beide
RAM-Vergleiche bleiben ohne Abweichung. Gespeichert werden nur Bytezahl,
Prüfsumme und Ablaufdaten, keine Speicherinhalte. Die Bedienabschnitte mit
Import, Export, Bearbeiten und Löschen sowie USB-Schreibtransfers fehlen
noch am Gerät. Die [kurzen Sampling- und Resampling-Aufnahmen mit
Verwerfen](2026-11-06-sample-ram-aufnahme.md) sind inzwischen in Mono und
Stereo geprüft, jeweils ohne Musterabweichung. WRITE und längere Aufnahmen
sind damit nicht abgedeckt.
