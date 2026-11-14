# Blackfin: Datenzugriffe von Kern und DMA beobachten

Fortsetzung der [gemeinsamen Modellzeit](2026-11-14-blackfin-modellzeit.md).
Alle Prüfungen laufen im Simulator mit erzeugten Daten. Kein Gerät wird angesprochen.

## Gemessen

Der Worker `BFIN8` kann ein zusammenhängendes Adressfenster beobachten. Vier
getrennte Zähler erfassen Datenlesen und Datenschreiben durch den DSP-Kern
sowie durch DMA. Gezählt werden erfolgreiche Zugriffe und die im Fenster
liegenden Bytes. Ein vier Byte breiter Zugriff, der nur zwei Bytes des Fensters
trifft, zählt daher als ein Zugriff mit zwei beobachteten Bytes.

Jede Gruppe hält außerdem Adresse, volle Zugriffsbreite und Ursprung des letzten
Treffers fest. Beim Kern ist der Ursprung der PC. Bei DMA sind es die
Registerbasis des Kanals und zusätzlich der aktuelle Deskriptorzeiger.
Das erneute Setzen des Fensters löscht die Zähler; Länge null schaltet es aus.
Die Abfrage verändert weder Speicher noch Modellzeit.

Ab `BFIN9` hält der Beobachter den Anfang des aktiven Deskriptors getrennt vom
Hardwarezeiger `CURR_DESC_PTR`. Dessen korrigierte Antwort und die Gegenproben
stehen unter [DMA-Grenzen und Deskriptoren](2026-11-14-blackfin-dma-grenzen.md).

Sechs gezielte Prüfungen mit erzeugten Programmen bestehen:

- Ein Kernprogramm schreibt und liest ein Wort, das ein kleineres Fenster überlappt.
- Lesen über die Prüfschnittstelle zählt nicht als DSP-Zugriff und lässt die Zeit stehen.
- Zurücksetzen und Abschalten entfernen vorherige Treffer.
- MDMA schreibt vier Bytes über eine Fenstergrenze; beide betroffenen Bytes werden erfasst.
- HOSTDP überträgt 16 Wörter in beide Richtungen; die Datenzugriffe werden als DMA erfasst.
- Ein nicht abgebildeter Kern-Schreibzugriff setzt weiterhin den echten Ausnahmezustand, zählt aber keine geschriebenen Bytes.

Ungültige oder überlaufende Fenster werden vor dem Worker-Aufruf zurückgewiesen.
Ein älterer Worker wird mit dem Hinweis auf einen nötigen Neubau abgewiesen.
Nach der Korrektur der Fehlerfall-Zählung bestehen alle 133 Blackfin-Modulprüfungen.
Die abschließende vollständige Unit-Prüfung besteht mit 1617 erfolgreichen und
166 übersprungenen Tests. Die Browserprüfung besteht mit 353 erfolgreichen
und einem übersprungenen Test. Die unabhängige Nachprüfung des Beobachters
findet keine verbleibende schwere Abweichung.

Ein vorheriger vollständiger Unit-Lauf hatte einen Verbindungsabbruch
(`ECONNRESET`) in der Prüfung des lokalen Proxys. Die betroffene Datei besteht
einzeln, danach auch der vollständige Lauf. Dafür wurde kein Server- oder
Seitencode verändert; die Ursache des einzelnen Verbindungsabbruchs ist offen.

## Hergeleitet

Die Beobachtung sitzt an den Datenzugriffen des GNU-Kernmodells und den
Pufferzugriffen der DMA-Kanäle. Die bestehenden Übertragungen bleiben erhalten.
Es werden weder Ersatzwerte geliefert noch Zugriffe auf vermeintlich harmlose
Bereiche ausgeblendet.

Der Datenpfad der Speicher-DMA ist bei diesem BF52x-Modell unter
`0xFFC00F00` und `0xFFC00F40` erreichbar. Die gleich aussehenden Adressen
`0xFFC00E00` und `0xFFC00E40` gehören hier zu normalen DMA-Kanälen.

## Offen und Grenzen

Die Abfrage liefert Summen und den letzten Treffer, keine vollständige,
zeitlich geordnete Spur. Der Deskriptor kann nach dem erfassten Zugriff bereits
verändert sein. Befehlsholen, Deskriptorabrufe und Zugriffe der
Prüfschnittstelle werden nicht als Datenzugriffe mitgezählt. Das gilt auch
für gesonderte L1-Testzugriffe über MMU-Register sowie direkte Schreibzugriffe
der nachgebildeten ROM-Funktionen. Null Treffer bedeuten daher keine allgemeine
Speicherstille. Ein beobachteter Sample-Lesezugriff beweist weder richtigen Klang
noch eine bestimmte Stimme.
Ein Zeitraum ohne solche Treffer ersetzt keinen allgemeinen Nachweis über
Stimmenenden und ausklingende Effekte.

Die erste PCM-Abweichung beim gekoppelten roten Originalstart bleibt eine
eigene Untersuchung. Sie wird weder ausgeblendet noch durch passende Testdaten
verdeckt. Ein Schreibzugriff der Speicher-DMA über die Grenze vom Werksbereich
zum ersten User-Sample ist dabei bereits beobachtet; seine Ursache ist offen.
