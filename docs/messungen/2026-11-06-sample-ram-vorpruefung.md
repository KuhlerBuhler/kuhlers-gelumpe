# Sample-RAM: Vorprüfung am Gerät

Stand: 06.11.2026. Rote Electribe 2 Sampler, Korg 2.02 und Hacktribe.
Die Verbindung läuft über den Linux-Rechner. Am Gerät wurde nur gelesen;
kein RAM-Fülltest, kein EXEC und kein Karten-, DSP- oder Flash-Schreiben
durch das Gerät. Eine separate Testkarte wurde anschließend am Mac vorbereitet.
Die vorbereitete Probe ist im [PCM-Bericht](2026-11-05-sample-pcm-fehler.md)
beschrieben.

## Gemessen: Verbindung und Ausgangsfirmware

- Die Korg-Suche liefert Modell `0x24`, Version `2.02`, MIDI-Kanal 10.
- BLECH INFO meldet CRC-Lesen und höchstens 32.768 Byte je Block.
- Der Bibliothekslader bei `0xC00364F4` entspricht dem eigenen Original.
  Der untersuchte Sample-Swap-Haken ist nicht installiert.
- Der Literalbereich bei `0xC004FAF8` entspricht dem eigenen Hacktribe-Original,
  nicht dem Stock-Original.
- Die ersten 32 Byte des Doom-Laders bei `0xC017CC00` und der Plugin-Laufzeit
  bei `0xC0150300` entsprechen dem untersuchten BLECH-Code. Sie unterscheiden
  sich vom minimalen Messbuild mit ausschließlich BLECH SysEx.
- Beim ersten Lesen ist der Transportzustand 4, beim zweiten 0. Der
  Bildschirmwert ist jeweils 22, das Fensterfeld 0. Die Probe verlangt
  Transportzustand 0 und Bildschirm 1 ohne Fenster. Bildschirm 22 wurde
  in dieser Sitzung nicht weiter zugeordnet.

Die überarbeitete Vorprüfung aus `tools/device/sample_ram_canary.py` wurde
anschließend ausschließlich über eine lesende Verbindung aufgerufen.
Sie verweigert die Messung bei `0xC017CC00`. Die bisherige Prüfung des
Laderhakens allein hätte diese zusätzliche Firmware nicht erkannt.
Es wurde keine Scratch-Routine hochgeladen und kein EXEC angefordert.

## Gemessen im Emulator: ergänzte Abbruchprüfung

Die synthetischen Gegenproben ändern getrennt Doom-Code, Plugin-Code,
Versionsbereich und Variantenliteral. Jeder Fall muss vor dem ersten
Probeaufruf abbrechen. Vor der Ergänzung liefen alle vier Fälle bis zur
Uploadstelle; danach brechen sie davor ab. Eine passende minimale
Vergleichsabbildung besteht die lesende Prüfung. Insgesamt bestehen die
13 synthetischen Prüfungen der RAM-Probe.

Der Protokolltest mit den eigenen Stock- und Hacktribe-Messbuilds besteht
erneut: Füllen und Prüfen über 225 Seiten erfolgen in begrenzten Portionen.
Ein absichtlich verändertes Wort auf der letzten Seite wird erkannt;
die Scratch-Wiederherstellung gelingt. Das sind Emulatorwerte, kein Audio-
oder DMA-Nachweis.

Die abschließenden lokalen Läufe bestehen ebenfalls: `GELUMPE_JOBS=1 npm test`
meldet 1368 bestandene und 161 ausgelassene Tests, `npm run test:e2e`
285 bestandene und einen ausgelassenen Test. Beide Läufe enden ohne Fehler.
Diese Ergebnisse ersetzen die noch ausstehende Geräteprobe nicht.

## Hergeleitet

Die laufende Firmware ist kein minimaler Ausgangsbuild. Das Vorhandensein
zusätzlichen Codes beweist noch keine aktuelle Belegung des oberen RAMs;
die Voraussetzung für das Überschreiben ist damit aber nicht erfüllt.
Die sieben verglichenen Codebereiche sind eine Abbruchprüfung, kein
vollständiger Identitätsnachweis beliebiger Firmware. Der frisch gestartete,
bekannte Messbuild bleibt eine ausdrückliche Voraussetzung.

Der Hacktribe-Messbuild, das eigene Vergleichsoriginal und die erzeugten
Testdateien liegen in einem getrennten temporären Verzeichnis auf Linux.
Alle sieben übertragenen Dateien wurden nach Größe und SHA-256 geprüft.
Zum Zeitpunkt der Vorprüfung wurden sie weder installiert noch auf eine
Gerätekarte kopiert.

## Gemessen: separate Testkarte vorbereitet

Die bereitgestellte 2-GB-SD-Karte ist mit MBR und FAT32 formatiert. Im
Hauptverzeichnis sind vor dem Kopieren nur Mac-Verwaltungsordner sichtbar.
Die Formatierung und vorhandene Ordner bleiben erhalten; es wird nichts
gelöscht oder überschrieben.

Vier Dateien mit zusammen 50.304.204 Byte werden neu angelegt:

- `KORG/hacktribe/System/SYSTEM.VSB`: der minimale Hacktribe-Messbuild.
- `KORG/hacktribe/Sample/e2sSample.all`: die erzeugte Testbibliothek.
- `KORG/electribe sampler/Sample/e2sSample.all`: dieselbe erzeugte Bibliothek
  für den alternativen ursprünglichen Kartenpfad.
- `import.wav`: die erzeugte Importprobe.

Größen und SHA-256 stimmen nach dem Schreiben mit dem geprüften Paket
überein. Nach regulärem Aushängen und erneutem Einbinden werden alle vier
Dateien nochmals vollständig gelesen und geprüft. Spotlight verhindert
den ersten Aushängeversuch; der nächste reguläre Versuch gelingt.
Es wird kein erzwungenes Aushängen verwendet. Anschließend wird die Karte
erfolgreich ausgeworfen. Das ist eine Kartenprüfung, kein Firmware-Update
und keine RAM-Messung am Gerät.

## Gemessen: Update meldet No file

Beim Updateversuch meldet das Gerät `No file`. Die erste Testkarte enthält
den Messbuild nur unter `KORG/hacktribe/System/SYSTEM.VSB`.
Eine anschließende lesende Geräteprüfung liefert:

| Bereich | Gelesener Text |
|---|---|
| `0xC00A5656` | `blechtribe` |
| `0xC00A5678` | `KORG/blechtribe/` |
| `0xC00A5690` | `System` |

Die Codebereiche `0xC00307B0` mit 212 Byte und `0xC0035720` mit 112 Byte
stimmen mit dem eigenen Hacktribe-Original überein. Der native Updatepfad
ruft den Basisordner-Helfer und den System-Helfer auf und ergänzt
`/SYSTEM.VSB`. Hergeleitet aus diesem Code und den gelesenen Pfadtexten
sucht die laufende BLECH-Firmware somit
`KORG/blechtribe/System/SYSTEM.VSB`. Die bisherige Anleitung verwechselt
den zukünftigen minimalen Hacktribe-Ausgangsbuild mit der aktuell laufenden
BLECH-Firmware. Der Messbuild selbst trägt den passenden Sampler-Dateikopf
mit `0x53` an Offset `0x12` und `0x24` an Offset `0x2E`.

Auf derselben Testkarte wird die unveränderte Messdatei zusätzlich am
gemessenen BLECH-Pfad angelegt. Die ursprünglichen vier Dateien bleiben
erhalten. Nach regulärem Aushängen und erneutem Einbinden stimmen alle
fünf Dateien nach Größe und SHA-256; die Karte wird wieder ausgeworfen.
Das korrigierte Archiv enthält beide Systempfade. Der erneute Updateversuch
am Gerät bleibt offen.

Die Kartenanleitung ist korrigiert. Der vorhandene Patcher-Helfer
`cardFolder("blech")` in `src/patcher.mjs` enthält noch dieselbe falsche
Zuordnung zu Hacktribe; diese Zuordnung ist ein gesonderter offener
Korrekturpunkt vor der Freigabe.

## Offen: eigentliche RAM-Messung

Die Testkarte ist vorbereitet. Erforderlich bleiben die Installation des
passenden minimalen Messbuilds über den normalen Updater und ein frischer Start.
Die spätere Sitzung mit installiertem Messbuild und verweigerter CPU-Prüfung
steht im [Cache-Bericht](2026-11-06-sample-ram-cache.md).
Danach folgt die vorbereitete Folge aus einem Füllen und getrennten Prüfungen
nach Sampling, Resampling, Import, Export und USB. Jeder Probeaufruf erfolgt
bei STOP auf der Hauptseite; erst nach Prozessende weiterbedienen.

Die Freigabe der Fläche ab `0xC274F000` ist am Gerät weiterhin nicht nachgewiesen.
Unveränderte Canaries würden außerdem keine vollständige Besitzer-, Leser-
oder DMA-Freiheit beweisen. Der neue Swap bleibt bis zu diesen Nachweisen
und den übrigen offenen Punkten ohne Gerätefreigabe.
