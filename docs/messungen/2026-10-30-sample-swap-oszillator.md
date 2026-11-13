# Sample-Swap: ungeladene Samples am OSC-Drehgeber wählen

Stand: 30.10.2026. **Gemessen im Emulator** mit erzeugten Samples auf
Stock 2.02 und Hacktribe. Kein Gerät, Klang oder DMA. Ergänzung zur
[Part-Auswahl](2026-10-29-sample-swap-exit-parts.md).

## Gemessen vor der Korrektur

Die bisherigen Part-Prüfungen setzen die gewünschte Nummer direkt in
den Pattern-Record und rufen anschließend die native Aktualisierung auf.
Das belegt nicht, dass der OSC-Drehgeber einen ungeladenen Slot erreicht.

Ein echter Encoder-Auftrag mit sechs indizierten Slots 500 bis 505 und
verkleinertem DSP-Budget startet mit einzig geladenem Slot 500. Der erste
Schritt nach rechts wählt Slot 0, der nächste Slot 1. Der indizierte
Slot 501 wird übersprungen und bleibt ungeladen. Sein Namenscache zeigt
weiter `Sample502` statt des erzeugten Dateinamens. Beide Builds verhalten
sich gleich und melden keinen Assert.

Die positive Kontrolle lädt 500 und 502: Der gleiche Encoder-Auftrag
wählt 502 und überspringt 501. Nach getrenntem Nachladen von 501 erreicht
derselbe Schritt diesen Slot samt richtigem Namen.

## Hergeleitet und durch den Auswahlpfad bestätigt

`0xC0040D50` sucht ab r0 einschließlich in Richtung r1, also eins oder
minus eins, mit Umlauf über die logischen Nummern 0 bis 998. Im Loop
hält r4 den logischen Kandidaten. Der Aufruf bei `0xC0040DB4` übergibt
dagegen den nativen Importschlüssel an `0xC004E3CC`.

Diese Funktion löst die Zuordnungstabellen auf und liest bei
`0xC004E3E0` das Geladen-Flag `META + 11`. Rückgabe null führt über
`0xC0040DBC` zum nächsten Kandidaten. Der echte Encoder-Versuch
beobachtet genau diesen Zugriff beim übersprungenen Slot 501.

Im normalen OSC-Auswahlpfad folgt kein Kategoriegleichheitsfilter.
Eine getrennte Kategorie-Navigation hat weitere Ladeprüfungen; deren
vollständiges Verhalten ist hier nicht belegt.

## Gebaut und gemessen nach der Korrektur

`ss_choice` umschließt nur diesen Auswahlaufruf. Das ursprüngliche
Ergebnis bleibt erhalten. Nur bei bisheriger Rückgabe null darf im
Swap-Modus eins ein logischer Nutzer-Slot von 500 bis 998 mit vorhandenem
Datei-Indexeintrag gewählt werden. Andere Modi, Werkssamples, leere und
ungültige Slots behalten den nativen Auswahlweg.

Der Haken liest nur den Index. Er schreibt weder ein Geladen-Flag noch
Stimmen- oder PCM-Daten und führt keine Dateizugriffe aus. Die bestehende
Part-Sperre verweigert weiterhin die Übernahme, bis die PCM vollständig
übertragen und veröffentlicht ist. Der native Aufruf und der Iterator
stimmen an den abgesicherten Stellen in beiden Originalen überein.

Der dauerhafte Encoder-Fall in
[swap_cases.py](../../tools/emu/swap_cases.py) verwendet fünf erzeugte
Dateieinträge mit einer Lücke bei 502 und ein zu kleines DSP-Budget.
Er wählt tatsächlich 500 nach 501, dann nach 503 und zurück nach 501.
Alle Auswahlaufträge erreichen ihr Ziel. PCM und Namen stimmen danach;
die Bibliotheksdatei bleibt bytegleich. Schreibbeobachter belegen die
noch alte Part-Auswahl beim Anfordern und keine neue tatsächliche
Part-Bindung vor dem Geladen-Flag. Der Fall scheitert vor der Korrektur
und besteht danach auf beiden roten Builds.

Die ARM-Matrix in
[test_sample_swap.py](../../tools/patch/test_sample_swap.py) prüft
zusätzlich Modi, Grenzen, leere Indexeinträge und die erhaltenen nativen
Ergebnisse und Iteratorregister. Beim wechselnden eigenen Modellcode
wird der Übersetzungscache vor der Ausführung geleert.

## Offen

Der vollständige Patchsatz mit diesem Haken besteht sämtliche 742
Prüfungen für Stock und 717 für Hacktribe, jeweils ohne Fehler. Die
zusätzliche Kategorie-Navigation sowie Klang, echte Stimmenlebensdauer
und alle DMA-Modi am Gerät bleiben offen. Diese Messung belegt den
normalen OSC-Drehgeber und ersetzt keine Freigabe für 1.4.
