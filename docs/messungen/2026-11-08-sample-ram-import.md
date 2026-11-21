# Oberer Sample-RAM: einzelner WAV-Import am Gerät

## Gemessen: neuer Ausgangszustand

Rote Electribe 2 Sampler mit Korg 2.02, Hacktribe und dem minimalen
BLECH-SysEx-Messbuild. Auf der separaten Testkarte liegen erzeugte Samples
und die erzeugte Datei `import.wav`. Seit der vorherigen Messung wurde
das Gerät neu gestartet. Das alte RAM-Prüfmuster gilt deshalb nicht weiter.

Die rein lesende Vorprüfung bestätigt die geprüften SysEx- und
Originalstellen sowie STOP und Hauptseite ohne Modalfenster. Es folgt
ein neuer [Füll- und Leerlaufvergleich](2026-11-06-sample-ram-cache-geraet.md)
mit `Wort = ARM-Adresse XOR 0x36E2B951`. Beide Durchgänge bestätigen
alle 396 Blöcke und 6321 Seiten in `0xC274F000..0xC4000000`, rechte
Grenze exklusiv. Spiegel und gecachte Sicht sind ohne Abweichung.

## Gemessen: Ergebnis des manuellen Imports

Vor dem Import sind 40 physische Sample-Zeilen aktiv. Der Zielslot 541,
intern 540, ist nicht geladen. Die erste reine Lese-Beobachtung endet
nach vier Minuten ohne Bedienänderung. Der Import erfolgt anschließend
manuell und wird bestätigt. Seine Bedienfolge liegt damit außerhalb des
Beobachtungsfensters; der Vorherzustand ist bereits gesichert.

Eine neue reine Lese-Prüfung findet wieder STOP und Hauptseite. Sie
vergleicht den tatsächlichen Nachherzustand mit dem gesicherten
Vorherzustand:

| Beobachtung | Ergebnis |
|---|---|
| Aktive physische Zeilen | 40 vorher, 41 danach |
| Neuer logischer Slot | 540, am Gerät 541 |
| Zugeordnete physische Zeile | 540 |
| Name | `import` |
| PCM-Länge im Metadatensatz | 100.000 Bytes |
| Nächster freier DSP-Platz | 27.563.200 vorher, 27.663.200 danach |
| Metadaten der vorherigen 40 aktiven Zeilen | alle Prüfsummen gleich |

Es ist genau eine aktive physische Zeile hinzugekommen. Keine vorher
aktive Zeile fehlt. Die Namens- und Zuordnungstabellen führen den
Zielslot zur neuen geladenen Zeile. Das Ergebnis beruht damit auf der
tatsächlichen Sample-Verwaltung, nicht allein auf einem geschlossenen
Menü. Die Beobachtung ruft nur SEARCH, INFO und READ auf; sie schreibt
weder Karte noch Flash und führt keinen Code über EXEC aus.

## Gemessen: RAM-Vergleich nach dem Import

Das vor dem Import gesetzte Muster wird ohne erneutes Füllen über den
gesamten oberen Bereich verglichen.

| Beobachtung | Betroffene Seiten |
|---|---:|
| Spiegelinhalt weicht vom Muster ab | 0 |
| Gecachter Inhalt weicht vom Muster ab | 0 |
| Beide Sichten enthalten unterschiedliche Werte | 0 |

Alle 396 Blöcke werden bestätigt. Es gibt keinen Timeout. Der erste KiB
des EXEC-Arbeitsbereichs ist nach dem Vergleich wiederhergestellt und
über den Spiegel geprüft. Die Vergleichsprobe schreibt das obere Muster
nicht neu und verwendet keine Karten-, DSP- oder Flash-Schreibfunktion.

## Hergeleitet

Dieser einzelne native WAV-Import hat im untersuchten oberen Bereich
keine beim Nachhervergleich sichtbare Änderung hinterlassen. Der
zusätzliche Eintrag, seine Zuordnung, der Name, die Metadatenlänge und
der vergrößerte DSP-Zeiger bestätigen den abgeschlossenen Import.

## Offen und Zustand nach dem Versuch

Die Bedienfolge wurde nicht durchgehend beobachtet. Audioinhalt und Klang
im DSP wurden nicht zurückgelesen oder verglichen. Gleiche Metadaten der
alten Zeilen sind kein separater Nachweis unveränderter DSP-Audiodaten.

Mehrfachimport, Import einer `.all`, volle Bibliothek, Sample Edit mit
EXIT und WRITE, Löschen und Export stehen noch aus. Kurzzeitige oder
zurückgenommene RAM-Schreibzugriffe sowie alle DMA-Eigentümer sind durch
den Nachhervergleich nicht ausgeschlossen. Es gibt weiterhin keine
allgemeine Freigabe des oberen RAM oder eines neuen Swap-Caches.

Das obere Prüfmuster bleibt für die Messsitzung erhalten. Der importierte
Slot liegt im DSP; WRITE und Gesamtexport wurden nicht betätigt. Vor
normaler Nutzung ist die Messsitzung mit einem Neustart zu beenden.
