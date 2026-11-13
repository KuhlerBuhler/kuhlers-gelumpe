# Oberer Sample-RAM: Muster und Leerlaufvergleich am Gerät

Stand: 06.11.2026. Rote Electribe 2 Sampler, Korg 2.02 mit Hacktribe und
minimalem BLECH-SysEx-Build mit Upload-Fix. Separate Testkarte mit erzeugten
Samples. Die [cachebewusste Probe](2026-11-06-sample-ram-cacheprobe.md)
wurde zuvor mit erzeugten Daten und im Emulator geprüft. Freigegeben war
nur Muster setzen und unmittelbar ohne Bedienaktion vergleichen.

## Gemessen: Vorprüfung

Das Paket stimmt nach Übertragung auf den Messrechner in allen 15 Dateien
mit dem geprüften Stand überein. Der MIDI-Port hat keine weitere
Verbindung. Die rein lesende Vorprüfung bestätigt die fünf neuen
SysEx-Patchbereiche, die sieben Original-Vergleichsbereiche sowie STOP
und Hauptseite. Es wird keine neue Firmware installiert.

Vor beiden Durchgängen liest die Probe CPU-Kontext und Tabelle erneut.
Jeweils zwei vollständige Tabellenlesungen stimmen überein. Auch die
Tabellen aus Füll- und Prüfdurchgang sind gleich. Das Steuerregister
bleibt `0x0005107D`, die TCM-Rohwerte entsprechen dem freigegebenen Zustand.

## Gemessen: Füllen

Das Muster `Wort = ARM-Adresse XOR 0x73A96C25` wird über die gecachte
Adresse in `0xC274F000..0xC4000000` geschrieben. Die rechte Grenze ist
exklusiv. Das sind 25.890.816 Bytes oder 24,69140625 MiB, aufgeteilt in
396 Blöcke und 6321 Seiten. Der letzte Block ist 4 KiB groß.

Jeder Block wird nach begrenztem Datencache-Clean und Write-Buffer-Drain
über den Spiegel `0xC674F000..0xC8000000` geprüft. Alle 396 Blöcke werden
bestätigt und melden keine Abweichung. Der Arbeitsbereich im ersten KiB
des EXEC-Fensters wird anschließend zurückgeschrieben und auch über
seinen Spiegel geprüft: `scratch_restored=true`.

## Gemessen: unmittelbarer Leerlaufvergleich

Ohne Bedienaktion folgt ein weiterer vollständiger Durchgang mit
demselben Muster. Alle 396 Blöcke und 6321 Seiten werden bestätigt.

| Beobachtung | Betroffene Seiten |
|---|---|
| Spiegelinhalt weicht vom Muster ab | 0 |
| Gecachter Inhalt weicht vom Muster ab | 0 |
| Beide Sichten enthalten unterschiedliche Werte | 0 |

Es gibt keinen Timeout und keinen Wiederholungsversuch. Auch nach dem
Prüfdurchgang ist der Arbeitsbereich zurückgeschrieben und geprüft.
Beide Durchgänge enthalten zusätzlich je 150 bestätigte Aufrufe für
CPU-Kontext und doppelte Tabellenlesung, insgesamt also 1092 bestätigte
EXEC-Aufrufe einschließlich der Zielblöcke.

Die gesamte Füllmessung dauert auf der Hostseite rund 45,8 Sekunden,
der Prüfdurchgang rund 47,9 Sekunden. Darin stecken SSH, SysEx-Übertragung,
Codebau, Vorprüfung und Tabellenlesungen. Das ist keine Messung der reinen
RAM-Geschwindigkeit oder des RAM-zu-DSP-Durchsatzes.

Der Transport steht auf STOP; der Vergleich enthält den für die Probe
notwendigen USB-/MIDI-Steuerverkehr. Er ist kein Lauf ohne jede Ein-/Ausgabe.
Die Probe benutzt keine DSP-, Karten- oder Flash-Schreibfunktionen und
ändert keine MMU-, Cache- oder Domänenkonfiguration. Der bekannte Task-Stack
bleibt ausgespart.

## Gemessen: neuer Ausgangszustand nach Neustart am 08.11.2026

Der bestätigte Neustart beendet die Gültigkeit des alten Prüfmusters.
Mit derselben Testkarte wird deshalb ein neuer Ausgangszustand erfasst.
Die geprüften SysEx- und Originalstellen entsprechen wieder dem minimalen
Messbuild; STOP, Hauptseite und geschlossenes Modalfenster sind bestätigt.
Diese Stellenprüfung ist kein vollständiger Vergleich des gesamten
Firmwareabbilds.

Das neue Muster lautet `Wort = ARM-Adresse XOR 0x36E2B951`. Füllen und
unmittelbarer Leerlaufvergleich bestätigen jeweils alle 396 Blöcke im
gleichen oberen Bereich. Spiegel und gecachte Sicht melden keine
abweichende Seite und keine unterschiedlichen Werte. Der erste KiB des
EXEC-Arbeitsbereichs ist nach beiden Durchgängen wiederhergestellt.

Eine anschließende reine Lese-Beobachtung wartet vier Minuten auf den
manuellen Import der erzeugten Datei `import.wav` in den freien Slot 541.
In diesem Fenster bleibt die Bedienung unverändert auf STOP und Hauptseite;
ein Import wird nicht beobachtet. Das ist weder eine bestandene
Importprüfung noch ein nachgewiesener Fehler des Importers. Die
Importprüfung war damit zunächst offen. Der anschließend bestätigte Import
und sein RAM-Nachhervergleich sind [gesondert gemessen](2026-11-08-sample-ram-import.md).
Das neue Muster bleibt für die weitere Messsitzung erhalten.

## Hergeleitet

Das Muster wurde im untersuchten Bereich veröffentlicht und beim
anschließenden Vergleich in beiden Sichten unverändert gelesen. Im
beobachteten Leerlauf gibt es damit keinen nachgewiesenen konkurrierenden
Schreiber. Die begrenzte Cachepflege und der Diagnoseablauf funktionieren
in diesem Gerätelauf über die ganze Zielspanne.

## Offen und Zustand nach dem Versuch

Die obere Testfläche enthält weiterhin das Muster und wurde nicht auf
ihren vorherigen Inhalt zurückgesetzt. Der gesicherte erste KiB ist
wiederhergestellt. Vor normaler weiterer Nutzung ist die Messsitzung mit
einem vollständigen Neustart zu beenden.

Dieser Versuch beweist weder vollständigen RAM-Besitz noch Freiheit in
allen Betriebsarten. Weitere Importfälle, Export, Bearbeiten und Löschen
stehen noch aus. Der spätere [einzelne WAV-Import](2026-11-08-sample-ram-import.md)
bestätigt seinen neuen Eintrag und einen unveränderten RAM-Vergleich.
Die nachfolgenden [Sampling- und Resampling-Vergleiche](2026-11-06-sample-ram-aufnahme.md)
prüfen kurze echte Aufnahmen mit Verwerfen, keinen vollständigen DMA-Besitz.
Der nachfolgende
[USB-Lesetransfer mit 1 MiB](2026-11-06-sample-ram-usb.md) wurde separat
geprüft; USB-Schreibtransfers bleiben offen. Die
aktive TLB und mögliche andere Eigentümer sind damit nicht vollständig
geklärt. Auch kurzzeitige oder zurückgenommene Änderungen sind durch
einen Nachher-Vergleich allein nicht ausgeschlossen.

Es ist weiterhin kein neuer Sample-Swap-Cache freigegeben. Der tatsächliche
Stock-Lauf ohne Hacktribe bleibt ebenfalls offen; die erfolgreichen
Stock-Prüfungen dieses Messaufbaus stammen aus dem Emulator.
