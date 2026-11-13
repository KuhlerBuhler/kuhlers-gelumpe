# Oberer Sample-RAM: Sampling und Resampling am Gerät

Stand: 06.11.2026. Rote Electribe 2 Sampler, Korg 2.02 mit Hacktribe und
minimalem BLECH-SysEx-Build mit Upload-Fix. Gleiche Messsitzung und Testkarte
mit 40 erzeugten Samples wie beim
[USB-Lesetest](2026-11-06-sample-ram-usb.md). Dazwischen kein Neustart.

## Gemessen: Aufnahme und Verwerfen

Die lesende Vorprüfung bestätigt die Messfirmware, STOP, Hauptseite und
einen freien MIDI-Port. Ein weiterer vollständiger Vergleich des seit dem
[Fülldurchgang](2026-11-06-sample-ram-cache-geraet.md) erhaltenen Musters
meldet keine Abweichung. Das Muster wird während dieser Folge nicht neu
gesetzt.

Alle Aufnahmen werden von Hand über SHIFT + REC und das Sampling-Fenster
gestartet, mit STOP beendet und mit EXIT verworfen. WRITE wird nicht
betätigt. Die USB-Beobachtung verwendet nach der Geräteerkennung nur INFO
und READ, keine EXEC-Aufrufe während der Aufnahme und keine eigenen
DSP-, Karten- oder Flash-Schreibkommandos. Die native Aufnahme selbst
belegt vorübergehend DSP-Sampleplatz.

Die Beobachtung liest Transportzustand, Fenster, Aufnahmequelle, Mono- oder
Stereoeinstellung und DSP-Frei-Zeiger. Quelle und Kanalmodus kommen aus
`manager + 0x708` und `manager + 0x704`, geprüft über das native Fenster 42
mit VTable `0xC00E3AA8`. Der Transportzustand steht bei
`transport + 0x308`, der DSP-Frei-Zeiger bei `0xC00F9C80`.

| Reihenfolge | Aufnahmequelle | Modus | Zuwachs des DSP-Zeigers in Bytes |
|---|---|---|---|
| 1 | Resampling, Quelle 1 | Mono, Modus 0 | 254.872 |
| 2 | Audio In, Quelle 0 | Mono, Modus 0 | 273.962 |
| 3 | Audio In, Quelle 0 | Stereo, Modus 1 | 703.820 |
| 4 | Resampling, Quelle 1 | Stereo, Modus 1 | 479.984 |

Jeder Lauf zeigt Bereitschaft 10, Aufnahme 11, Abschluss 12 und nach EXIT
wieder Zustand 0 auf der Hauptseite. Der DSP-Zeiger wächst beim Abschluss
und kehrt beim Verwerfen von allen vier Aufnahmen exakt auf 27.563.200
zurück. Die aktiven Zeilen der physischen Sample-Tabelle
`0xC036AD88`, 1000 Zeilen zu je `0x45C` Bytes, werden davor und danach
nach Zeilenidentität und SHA256 verglichen. Die 40 aktiven Zeilen sind
jeweils identisch. Die Aufnahmen sind damit tatsächlich angelaufen und
verworfen, nicht nur ihre Einstellseiten geöffnet worden.

Der erste Lauf war als Audio In Mono vorbereitet, wurde aber mit Quelle 1
gestartet. Die Wahl von Resampling wurde zusätzlich am Gerät bestätigt.
Der ursprüngliche Bericht verweigert deshalb korrekt das vorbereitete
Audio-In-Ergebnis. Die beobachtete Folge wird als Resampling Mono
ausgewertet und bleibt unverändert erhalten. Audio In Mono folgt als
eigener zweiter Lauf.

## Gemessen: RAM-Vergleiche

Der Vorvergleich und die Vergleiche nach allen vier Aufnahmen
bestätigen jeweils alle 396 Blöcke und 6321 Seiten in
`0xC274F000..0xC4000000`, rechte Grenze exklusiv. Das sind 24,69140625 MiB.
Alle drei Änderungskarten bleiben leer: kein Musterunterschied über die
Spiegeladresse, kein Unterschied über die gecachte Adresse und kein
Unterschied zwischen den Sichten. Der erste KiB des EXEC-Arbeitsbereichs
wird jeweils wiederhergestellt. Alle Blöcke werden ohne Timeout oder
Wiederholung bestätigt. Die vor jedem Durchgang doppelt gelesene
Speichertabelle hat durchgehend dieselbe Prüfsumme; das Steuerregister
bleibt `0x0005107D` und beide TCM-Rohwerte bleiben `0x1C`.

## Hergeleitet

Die reale Firmware und der DSP haben die vier Aufnahmewege durchlaufen.
Die Vorher-/Nachher-Vergleiche ergänzen die
[CPU-Spuren aus dem Emulator](2026-11-06-sample-ram-cacheprobe.md), dessen
Aufnahmeende ausdrücklich modelliert war. Die Zeigerzuwächse messen
weder den Karten- noch den RAM-zu-DSP-Durchsatz. Die lesende Beobachtung
ist keine Klangprüfung.

## Offen und Zustand nach dem Versuch

Die Folge prüft kurze Aufnahmen mit anschließendem Verwerfen. Daueraufnahmen, WRITE,
gefüllter DSP-Speicher und andere Firmwarefamilien sind nicht abgedeckt.
Import, Export, Sample-Bearbeitung und Löschen stehen am Gerät noch aus.

Ein Nachher-Vergleich schließt kurzzeitige oder zurückgenommene Änderungen
nicht aus. Aktive TLB, sämtliche DMA-Ziele und vollständiger RAM-Besitz
bleiben offen. Aus dieser Folge folgt keine allgemeine Freigabe der
gesamten rund 47 MiB und keine Freigabe des neuen Swap-Caches.

Das Muster bleibt im oberen Testbereich erhalten. Vor normaler Nutzung
vollständig neu starten. Weitere Messungen derselben Sitzung müssen das
vorhandene Muster prüfen, ohne es neu zu setzen.
