# Blackfin: Grenzen und Deskriptoren der Speicher-DMA

Fortsetzung der [Datenzugriffsbeobachtung](2026-11-14-blackfin-speicherzugriffe.md).
Alle Prüfungen laufen mit erzeugten Daten im Emulator. Kein Gerät wird angesprochen.

## Offline

Grundlage ist das
[BF52x-Hardwarehandbuch, Revision 1.2](https://www.analog.com/media/en/dsp-documentation/processor-manuals/ADSP-BF52x_hwr_rev1.2.pdf),
Kapitel 6. Die Zählregister verwenden null für 65536 Elemente. Bei zweidimensionaler
Übertragung wählt `DI_SEL`, ob jede innere Zeile oder erst der vollständige äußere
Durchlauf eine Fertigmeldung auslöst. Eine innere Zeile mit genau einem Element ist
im zweidimensionalen Betrieb verboten.

Die Abschnitte 6-86 und 6-87 beschreiben den Deskriptorzeiger: Nach dem Abruf
steht `CURR_DESC_PTR` auf dem Anfang des Blocks plus zweimal dessen Wortanzahl.
Er zeigt dann weder auf den gerade gelesenen Blockanfang noch auf den nächsten
verketteten Block. Im Arraybetrieb wird `NEXT_DESC_PTR` ignoriert; im kleinen
Listenformat bleibt dessen obere Adresshälfte erhalten.

Ein eingelesener Deskriptor mit gelöschtem `DMAEN` startet keine Datenübertragung.
Das gilt auch am Übergang vom vorherigen Block. Ein bereits laufender Quellkanal
rechtfertigt keine weiteren Schreibzugriffe eines so abgeschalteten Zielkanals.

## Gemessen

Die Gegenproben zeigen mehrere voneinander unabhängige Fehler im bisherigen
GNU-Modell. Der Worker `BFIN9` korrigiert die Datenwege an der Quelle:

- Eine Zielanforderung endet spätestens an der noch verfügbaren Quellzeile. Ein abgeschalteter Quellkanal liefert keine Daten.
- Negative Schrittweiten verarbeiten jedes Element an seiner wirklichen Adresse; beide Kanalbreiten müssen übereinstimmen.
- Nullzählung überträgt alle 65536 Elemente beziehungsweise Zeilen.
- Zweidimensionale Fertigmeldung und Interrupt folgen der gewählten inneren oder äußeren Grenze.
- Deskriptorzeiger folgen dem tatsächlich eingelesenen Format und seiner ursprünglichen Wortanzahl, auch wenn der neue Block seine Konfiguration ändert.
- Ein abgeschalteter Folgedeskriptor beendet die Übertragung ohne zusätzliche Datenzugriffe.
- Fehlende oder nur teilweise lesbare Deskriptoren und Datenbereiche führen zum Fehler. Sie werden nicht als leerer FIFO behandelt.

Die drei neuen Zeigerprüfungen scheitern vor der Korrektur mit zwei Abweichungen
und einem Abbruch. Zwei zusätzliche Abschaltprüfungen zeigen vor der Korrektur
unerlaubte Zielschreibzugriffe. Nach den Korrekturen bestehen alle 161
Blackfin-Modulprüfungen, darunter 27 gezielte Speicher-DMA-Fälle.
Zusätzliche Gegenproben prüfen abgeschaltete Quellkanäle und ihre Folgedeskriptoren.

Der unveränderte Quellstand von GNU 15.2 lässt sich mit denselben Transformationen
bearbeiten. Zweifaches Anwenden erzeugt identische Dateien; die erzeugte DMA-Datei
stimmt mit der gebauten Fassung überein.

Die vollständige Unit-Prüfung besteht mit 1618 erfolgreichen und 166
übersprungenen Tests. Die unabhängige Prüfung des DMA-Decoders findet nach der
Abschaltkorrektur keine verbleibende schwere Abweichung im geprüften Umfang.
Die abschließende Browserprüfung besteht mit 353 erfolgreichen und einem
übersprungenen Test. Ein vorheriger vollständiger Lauf hatte einen Timeout bei
der Anzeige einer älteren BLECH-Version auf der Startseite. Die vier Tests der
betroffenen Datei bestehen einzeln, danach auch der vollständige Lauf. Die
Ursache dieses einzelnen Timeouts ist offen; Seitencode wurde dafür nicht verändert.

Die erneute Gegenprobe mit der unveränderten roten Originalfirmware und dem
vollständig korrigierten Worker bestätigt nach 800 ms Modellzeit weiterhin
einen vier Byte breiten MDMA-Schreibzugriff ab `0x00365EBE`. Zwei Bytes
überlappen das erste User-Sample bei `0x00365EC0`. ARM-Assertions und
DSP-Ausnahmen treten dabei nicht auf.

## Hergeleitet

Der Beobachter hält den Anfang des aktiven Deskriptors getrennt vom sichtbaren
Hardwarezeiger fest. Dadurch bleibt ein Speicherzugriff seinem Auftrag zugeordnet,
ohne eine falsche Registerantwort für die laufende Firmware zu liefern.

Eine Anpassung der Firmware-Speichervergabe darf einen Simulatorfehler nicht
verdecken. Die bereits beobachtete Überlappung am ersten User-Sample wird deshalb
nach diesen Modellkorrekturen erneut geprüft. Vollständige PCM-Vergleiche behalten
auch das erste Halbwort bei.

## Offen und Grenzen

Die Datenwege bleiben auf die ausdrücklich unterstützten Übertragungen begrenzt.
Beliebige Schrittweiten, andere SPORT-Formate und ein großer Deskriptor aus nur
einem Wort werden mit Fehler beendet. Das zuletzt genannte Format ist im
Hardwarehandbuch zulässig, in diesem Modell aber nicht umgesetzt.

Eine gemeinsame Modellzeit ist kein Nachweis genauer Buslaufzeiten oder des
RAM-/DMA-Besitzes am Gerät. Natürliche Stimmenenden, tatsächlicher Verbrauch von
User-PCM und ausklingende Effekte bleiben gesondert zu prüfen.
