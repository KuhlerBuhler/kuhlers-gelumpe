# Idee 25: Mehr Sample-Speicher

Stand: Idee. Das Limit ist noch nicht gemessen. Zurück zu den [Ideen](../ideen.md).

Der Sample-Speicher ist vermutlich physisch begrenzt (DSP-SDRAM, Flash). Ein Weg ist Streaming oder Paging von der SD-Karte: die 25 MB als Cache, bei Bedarf laden, alle Samples der Karte anzeigen (lange Samples bedeuten Ladezeit). Kompression hilft dem Speicherplatz auf der Karte, nicht der Menge, die gleichzeitig spielbar ist.

Nächster Schritt: das Limit messen, dann einen Haken in den Sample-Manager der Firmware setzen. Vorarbeit zu Speicherbereichen: [Speicherbereiche](../speicherbereiche.md), [Werks-Sample-Flash](../messungen/2026-10-07-werks-sample-flash.md).
