# Oberer Sample-RAM: Vergleich nach USB-Lesetransfer

Stand: 06.11.2026. Rote Electribe 2 Sampler, Korg 2.02 mit Hacktribe und
minimalem BLECH-SysEx-Build mit Upload-Fix. Gleiche Testkarte und gleiche
Messsitzung wie beim [Füll- und Leerlaufvergleich](2026-11-06-sample-ram-cache-geraet.md).
Freigegeben war ein USB-Lesetransfer mit vollständigem RAM-Vergleich davor
und danach. Sampling wurde nicht gestartet.

## Gemessen

Das Muster `Wort = ARM-Adresse XOR 0x73A96C25` bleibt seit dem ersten
Fülldurchgang erhalten. Es wird vor oder nach dem USB-Transfer nicht neu
gesetzt. Die [cachebewusste Probe](2026-11-06-sample-ram-cacheprobe.md)
prüft jeweils die ganze Spanne `0xC274F000..0xC4000000`, rechte Grenze
exklusiv: 25.890.816 Bytes, 396 Blöcke und 6321 Seiten.

| Beobachtung | Vor USB, betroffene Seiten | Nach USB, betroffene Seiten |
|---|---|---|
| Spiegelinhalt weicht vom Muster ab | 0 | 0 |
| Gecachter Inhalt weicht vom Muster ab | 0 | 0 |
| Beide Sichten enthalten unterschiedliche Werte | 0 | 0 |

Beide Durchgänge bestätigen alle Blöcke ohne Timeout oder Wiederholung.
Der gesicherte erste KiB des EXEC-Arbeitsbereichs wird jeweils
wiederhergestellt und über seinen Spiegel geprüft. Die doppelten
Tabellenlesungen sowie ihre Prüfsummen zwischen den Durchgängen stimmen
überein. Das Steuerregister bleibt `0x0005107D`, beide TCM-Rohwerte
bleiben `0x1C`.

Zwischen diesen Vergleichen werden ab `0xC0D3A940` genau 1.048.576 Bytes
aus dem unteren Arbeitspuffer zum Rechner gelesen: 32 aufeinanderfolgende
Blöcke zu je 32.768 Bytes. Alle Antworten haben die erwartete Adresse,
Länge und gültige CRC. Die Speicherinhalte werden nicht als Datei
gespeichert; protokolliert werden Bytezahl, Prüfsumme und Ablaufdaten.

Der Transfer verwendet nach der Geräteerkennung ausschließlich INFO
(`0x60`) und READ (`0x61`). Einschließlich Vorprüfung und Zustandswachen
sind es zwei INFO- und 204 READ-Kommandos. Die Zustandswache verlangt vor
jedem Datenblock STOP und Hauptseite. Im Transfer selbst gibt es keine
WRITE-, EXEC-, Datei- oder Flash-Kommandos. Die RAM-Vergleiche davor und
danach verwenden dagegen den geprüften EXEC-Messablauf.

Der Transfer dauert auf der Hostseite rund 4,251 Sekunden. Darin stecken
auch die Zustandswachen, Antwortprüfung und Prüfsummenbildung. Die
vollständigen RAM-Vergleiche benötigen rund 48,5 und 49,1 Sekunden mit
Vorprüfung und Tabellenlesungen. Keine dieser Zeiten misst den
Karten- oder RAM-zu-DSP-Durchsatz.

## Hergeleitet

Der geprüfte USB-Lesefall hinterlässt in beiden beobachteten Sichten keine
Abweichung des oberen Musters. Das erweitert den Leerlaufbefund um genau
diese Übertragungsrichtung und Blockgröße.

## Offen und Zustand nach dem Versuch

USB-Schreibtransfers zum Gerät, andere Blockgrößen und Übertragungen
während PLAY sind nicht geprüft. Ein Nachher-Vergleich schließt
kurzzeitige oder zurückgenommene Änderungen nicht aus. Aktive TLB und
weitere DMA-Eigentümer bleiben unvollständig geklärt.

Import, Export, Bearbeiten und Löschen fehlen noch in der echten Gerätefolge.
Die anschließenden [Sampling- und Resampling-Vergleiche](2026-11-06-sample-ram-aufnahme.md)
belegen kurze Aufnahmen mit Verwerfen in beiden Kanalmodi. Sie ersetzen
keinen vollständigen DMA-Besitznachweis. Der Lauf ohne Hacktribe auf echter Hardware fehlt
ebenfalls. Der obere Bereich ist weiterhin nicht als Swap-Cache freigegeben.

Die Testfläche enthält weiter das Muster. Der erste KiB des
EXEC-Arbeitsbereichs ist wiederhergestellt. Vor normaler Nutzung ist ein
vollständiger Neustart nötig; eine weitere Messung in derselben Sitzung
muss das vorhandene Muster prüfen, ohne es neu zu setzen.
