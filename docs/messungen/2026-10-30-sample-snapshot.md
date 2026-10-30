# Einzelnes Sample aus dem DSP dauerhaft speichern

Stand: 30.10.2026. **Gemessen im Emulator** mit erzeugten Samples,
ohne Gerät, Klang oder Aufnahme-DMA. Ergänzung zu den
[nativen Speichergrenzen](2026-10-30-sample-speichergrenzen.md).

## Gemessen und hergeleitet: vollständige PCM und Dateireihenfolge

Der native Snapshot `0xC004EBD4` liefert mit fünftem Stackargument null
die vollständige physische PCM-Belegung aus Basis und Länge der
Metadatenzeile. Der bearbeitete Wiedergabestart verkürzt diesen Bereich
nicht. Im Deskriptor wird `+56` null und `+40` relativ zur PCM-Basis.
Die Länge bei `+60` ist eine Byteanzahl, `+65 == 1` bedeutet Stereo,
`+72` enthält die Samplerate.

Der native WAV-Schreiber `0xC0039B2C` setzt 16 Bit und liest über
`0xC004EDDC` fortlaufend höchstens 32768 Halbwörter pro Block. Die
gelesenen Bytes werden ohne Kanalumordnung geschrieben. Ein Frame
umfasst bei Mono zwei, bei Stereo vier Byte.

Acht Fälle mit unterschiedlichen linken und rechten Kanalwerten und
mehr als 64 KiB bestehen auf beiden roten Originalen: importierte Mono-
und Stereo-PCM sowie erzeugte Mono- und Stereo-Aufnahmeabschlüsse,
jeweils mit linearem Rücklesen und nativem Dateiexport. Der normale
Einzelexport verwendet dagegen Snapshot-Argument eins und kann einen
Wiedergabe- oder Slice-Ausschnitt speichern.

## Gebauter Rückleser

[sample_snapshot.py](../../tools/patch/sample_snapshot.py) verbindet den
vollständigen nativen Snapshot mit `store_put`. Sein Reader erzeugt
blockweise RIFF/fmt/data und den vollständigen korg/esli-Datensatz.
Slot und Metadatenindex werden auf den logischen Zielslot normalisiert,
die Importnummer auf dessen Wert plus 50. DSP-Basis und PCM werden mit dem vorhandenen begrenzten
Transport gelesen. Nicht auf 32 Byte liegende Belegungsgrenzen bleiben
erhalten; ungerade Byteabfragen werden über einen ausgerichteten
Zwischenpuffer bedient.

Der Aufrufer muss den Dateibesitz und die Sample-Belegung halten und
`0x10600` Byte getrennten Arbeitsspeicher bereitstellen. Dieser Bereich
darf weder den Schreibpuffer noch die Zustandsfläche des Kartenschreibers
überlagern. Das Modul installiert selbst keine Menühaken und reserviert
keinen produktiven RAM-Bereich.

Die ARM-Modellprüfungen umfassen vollständige Mono- und Stereo-Einträge,
alle Eintragsgrenzen und ungerade Leseabschnitte, fehlerhafte Deskriptoren,
Kanal- und Framegrenzen, DSP- und Kartenfehler sowie kurze und teilweise
DSP-Übertragungen. Ein Teilfehler veröffentlicht keinen neuen Slotindex;
ein bereits geschriebener Teilblock bleibt höchstens unerreichbar am Ende.

## Unveränderten Inhalt nicht erneut anhängen

Der gemeinsame ARM-Schreiber und der Browser-Schreiber vergleichen
einen bestehenden Eintrag vor dem Anhängen blockweise mit der neuen
Quelle. Gleichheit bedeutet gleiche Länge und gleiche Bytes des
vollständigen Eintrags, einschließlich PCM und Metadaten. Dann werden
weder Daten noch Journal noch Index geschrieben. Ein veränderter letzter
PCM-Wert oder ein veränderter Name reicht weiterhin für eine neue Version.

Ein fehlgeschlagenes Vergleichslesen meldet einen Fehler und beginnt
keinen neuen Anhang. Der Vergleich liegt vor der Prüfung zusätzlicher
Dateikapazität. Ein unveränderter Eintrag kann deshalb auch in einer
Datei mit `0xFFFFFFFF` Byte bestätigt werden, ohne sie zu vergrößern.
Diese Grenze wird mit verstreuten erzeugten Blöcken geprüft, ohne eine
vollständige 4-GB-Datei im RAM aufzubauen.

## Offen

Die gesonderte native Adapterprüfung besteht auf beiden roten Builds.
Sie benutzt den echten Snapshot, DSP-Transport und FatFs: Ein veränderter
Name und vollständige Mono- beziehungsweise Stereo-PCM werden angehängt,
geprüft und nach Neustart korrekt geladen. Das direkt folgende gleiche
Speichern lässt die Datei bytegleich und ruft `f_write` keinmal auf.
Diese Adapterprüfung verwendet ursprüngliche identische Zuordnungen.
Ein zusätzlicher Gegenversuch auf beiden Builds belegt die nötige
Normalisierung der Importnummer: Logisch 500 liegt im RAM über Import
651 in Zeile 601. Ein unveränderter Dateiwert 651 lässt den Slot nach
Neustart auf die ungeladene Zeile zeigen. Ausschließlich Dateifeld `+20`
auf 550 geändert stellt Name und PCM korrekt wieder her. Der Adapter
normalisiert dieses Feld inzwischen ebenfalls; der neue Modellfall
besteht. Ein permanenter nativer Neustartfall mit dieser Zuordnung und
dem korrigierten Adapter fehlt noch.

Der gebaute Laufzeitpatch besteht sämtliche 742 Prüfungen für Stock und
717 für Hacktribe, jeweils ohne Fehler. Der getrennte Snapshotadapter
ist darin noch nicht eingebunden. Die bestätigten Sample-Menüs,
die Versionszuordnung beim Ersetzen und die gemeinsame Freigabe von
Cache und Dateien sind noch nicht an diesen Adapter angeschlossen.
Ein erfolgreicher Adapterversuch belegt daher noch kein Sample-WRITE
über die normalen Bedienelemente. Der Gesamtexport bleibt bis zur
fertigen Ablösung ein Veröffentlichungsblocker.

Reale Aufnahme, Resampling, Stimmenausklang und DMA fehlen weiterhin.
Es gibt dadurch keine Freigabe für das Gerät oder die Veröffentlichung.
