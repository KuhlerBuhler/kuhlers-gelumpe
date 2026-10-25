# Idee 25: Mehr Sample-Speicher

Stand: Forschung und begrenzter DSP-Transfer. Das echte DSP-Limit ist noch nicht gemessen. Zurück zu den [Ideen](../ideen.md).

Der Sample-Speicher ist vermutlich physisch begrenzt (DSP-SDRAM, Flash). Ein Weg ist Streaming oder Paging von der SD-Karte: die 25 MB als Cache, bei Bedarf laden, alle Samples der Karte anzeigen (lange Samples bedeuten Ladezeit). Kompression hilft dem Speicherplatz auf der Karte, nicht der Menge, die gleichzeitig spielbar ist.

Nächster Schritt: das Limit messen, dann einen Haken in den Sample-Manager der Firmware setzen. Vorarbeit zu Speicherbereichen: [Speicherbereiche](../speicherbereiche.md), [Werks-Sample-Flash](../messungen/2026-10-07-werks-sample-flash.md).

## Swappen über den freien RAM (24.10.)

Wunsch: eine `e2sSample.all` mit rund 50 MB. Die eine Hälfte liegt wie heute im DSP, die andere im freien ARM-RAM, und
ein Patch tauscht Samples je nach Bedarf zwischen beiden aus.

| Aussage | Status |
|---|---|
| `0xC274F000` bis `0xC4000000` (24,7 MiB) nutzt die Firmware in keiner gemessenen Phase | gemessen im Emulator (Messung vom 24.10.), am Gerät beim Spielen bestätigt ([RAM frei](../messungen/2026-10-22-ram-frei.md)) |
| Der DSP spielt aus seinem eigenen Speicher, rund 25 MB | hergeleitet, Grenze nicht gemessen |
| Wie schnell Samples über den Host-Port in den DSP gehen | rund 11 MiB/s gestoppt und 10 MiB/s beim Spielen, erste Geräteversuche ([Messung](../messungen/2026-10-25-sample-swap.md)) |
| Wo und wie der DSP ein Sample ablegt, und ob er weiterspielen kann, während ein anderer Platz beschrieben wird | offen ([Idee 26](26-dsp-erfassen.md), [Idee 52](52-ton-im-emulator.md)) |

Ablauf, als Vorschlag: beim Start lädt die Firmware wie bisher, ein Patch liest den Rest der Datei in den freien RAM.
Wird ein Sample gebraucht, das nicht im DSP liegt (Pattern-Wechsel, Sync-Gruppe, Auswahl im Part), tauscht der Patch
es gegen eines, das gerade kein Part benutzt. Ob das mitten im Spielen geht oder nur zwischen Patterns, entscheidet
das Tempo des Host-Ports.

## Ladepfad und erste Prüfung (25.10.)

Die [Untersuchung zum Sample-Swap](../messungen/2026-10-25-sample-swap.md) beschreibt den Ladepfad,
den Host-Port und die Platzverwaltung. Im isolierten ARM-Test gibt Löschen nur am Ende DSP-Platz zurück;
ein Swap braucht eine eigene Verwaltung. Vor dem Bau fehlen Durchsatz und eine Aufnahme unter Wiedergabe
am Gerät. Das Testwerkzeug dafür ist vorbereitet. Ein nicht mehr ausgewähltes Sample kann noch ausklingen.

## RAM-Besitz und Timeout (25.10.)

Die [Fortsetzung der Untersuchung](../messungen/2026-10-25-sample-swap-timeout.md) zeigt:
Der untere Teil der beim Spielen unbenutzten rund 47 MiB gehört weiterhin dem Arbeitsbuffer.
`IMPORT ALL PATTERN` beschreibt ihn bereits im Emulator. Nur der obere Bereich bleibt ein
Cache-Kandidat; Sampling und Resampling sind dort ohne echten Aufnahmeabschluss nicht freigeprüft.
Der neue begrenzte DSP-Transfer und das Messwerkzeug aktivieren deshalb noch keinen Sample-Cache.

Für den späteren Bau gilt: keine Größenobergrenze für die Datei auf der Karte, im DSP nur der
aktive Satz. Vorausgeladen werden das aktuelle Pattern, seine Nachbarn und das Kettenziel.
Ist der nächste Satz beim Wechsel nicht fertig, spielt das aktuelle Pattern eine Runde weiter.
Je Pattern sind etwa 10 bis 12 MB vorgesehen. Der Dateikopf liefert die Slot-Offsets; Namen
stehen in den einzelnen Sample-Metadaten und werden bei Bedarf gelesen. DMA bleibt zunächst aus.
High Speed mit 50 MHz setzt einen getrennten Test mit einer entbehrlichen microSD voraus.
