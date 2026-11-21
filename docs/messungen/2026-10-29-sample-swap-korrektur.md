# Sample-Swap: Veröffentlichung und Cache-Deskriptor korrigiert

Stand: 29.10.2026. Beleg: `measure:2026-10-29/sample-swap-korrektur`.
Fortsetzung der [Prüfung des Feature-Diffs](2026-10-29-sample-swap-review.md).
Die zusätzlichen Punkte aus dem
[PR-Kommentar](https://github.com/KuhlerBuhler/kuhlers-gelumpe/pull/166#issuecomment-6487811935)
sind unten getrennt eingeordnet. Es ist keine Freigabe für das Gerät oder 1.4.

## Gemessen: die beiden Fehler vor der Korrektur

Zwei neue ARM-Tests reproduzieren neun fehlgeschlagene Teilfälle im
bisherigen Stand: native Veröffentlichung ohne geschützte IRQ-Maske und
vier veränderte Deskriptorfelder, jeweils vor dem Laden und beim Kopieren.

Eine getrennte Kopie des bisherigen Quellstands und die dazu passenden
Firmwaredateien reproduzieren zusätzlich vier Fehlerfälle mit den nativen
Firmwarefunktionen: UI-Unterbrechung beim Veröffentlichen, verändertes
Loop-Ende, verändertes Sample-Ende und Änderung während der Deskriptorkopie.
Alle vier Fälle schlagen vor der Korrektur fehl. Es werden ausschließlich
erzeugte Samples verwendet. Firmware und Rohprotokolle bleiben außerhalb
des Repos.

## Hergeleitet: Korrektur der Veröffentlichung

Die letzte Generationsprüfung, die Kontextprüfung, das vorübergehende
Setzen des DSP-Frei-Zeigers und die native CPU-Reservierung liegen jetzt
in einem kurzen geschützten Abschnitt. Danach wird der ursprüngliche
IRQ-Zustand wiederhergestellt. DSP-Übertragung und Part-Aktualisierung
bleiben außerhalb.

Ein veralteter Auftrag erreicht die native Reservierung nicht. Ein
unzulässiger Kontext wird vor der Reservierung abgefangen. Auch bei
nativer Verweigerung bleiben Stack, ursprüngliche IRQ-Maske und der
bisherige Frei-Zeiger erhalten.

## Hergeleitet: Korrektur der Cache-Integrität

Beim Vorausladen beginnt die Prüfsumme mit dem ursprünglichen Deskriptor;
danach kommen die normalisierten PCM-Wörter hinzu. Beim späteren Laden aus
dem Cache wird zuerst der Deskriptor in den getrennten Zielbereich kopiert.
Erst die Summe über diese tatsächlich kopierten Metadaten und die PCM wird
mit der erwarteten Cache-Summe verglichen.

Eine veränderte Kopie erreicht deshalb die native Reservierung nicht.
Stattdessen wird die Cache-Generation verworfen. Der Slot bleibt für einen
neuen Versuch von Karte verfügbar und wird nicht als dauerhaft fehlerhaft
markiert. Das Format der vier Wörter je Cache-Verzeichniseintrag bleibt
erhalten. Die Änderung ersetzt keine allgemeine Validierung beliebig
beschädigter RAM-Zeiger und keinen Nachweis über DMA-Zugriffe.

## Gemessen nach der Korrektur

- 67 ARM-Tests bestehen. Dazu gehören ursprüngliche und bereits maskierte
  IRQ-Zustände, alle vier Rückwege der Veröffentlichung sowie die gemeinsame
  Prüfsumme aus Deskriptor und PCM.
- Die vier nativen Fehlerfälle bestehen in beiden roten Builds, zusammen
  acht Fälle. Beschädigte Cache-Metadaten führen zum erneuten Kartenladen;
  das veröffentlichte PCM entspricht danach vollständig den erzeugten Daten.
- Ein zusätzlicher Ablauf zählt 1215 emulierte Befehle mit maskierten IRQs
  während einer erfolgreichen Veröffentlichung. Die native Funktion hebt
  die Maske zwischendurch nicht auf. Das ist keine Zeitmessung am Gerät.
- `npm test` besteht mit 1158 bestandenen und 153 übersprungenen Tests.
- `npm run test:e2e` besteht mit 220 bestandenen und einem übersprungenen
  Test. Die vollständigen Firmwareprüfungen bestehen mit 613 Checks für
  Stock und 588 für Hacktribe. Die neuen Fälle sind als 22. Swap-Gruppe
  in den gemeinsamen Emulator-Check aufgenommen.
- Lokal dauern die vollständigen Firmwareprüfungen rund 2064 Sekunden
  für Stock und 1696 Sekunden für Hacktribe, jeweils mit zwei Prozessen
  und bei gleichzeitig laufenden Prüfungen. Das sind keine CI-Zeiten.

## PR-Kommentar: bestätigt und noch offen

| Punkt | Einordnung |
|---|---|
| Gesamtexport | Bestätigter, bereits dokumentierter Datenverlust-Blocker. Vollständigen Ersatz wie vereinbart bauen; nicht als normale Firmware freigeben. |
| Endloses Wechsel-Gate | Bestätigt für dauerhaft unerfüllbare Ziele. Es braucht einen kontrollierten Abbruch des Auftrags; ein Wechsel mit fehlenden Samples bleibt ausgeschlossen. |
| Part-Aktualisierung in Modus 2 | Die frühe Verweigerung greift auch vor der Unterscheidung von Werks- und Nutzerplätzen. Das ARM-Modell bestätigt die Verweigerung bei intaktem DSP und einer Werksauswahl in Modus 2. Kartenfehler und DSP-Protokollfehler sind getrennt zu behandeln; nach einem DSP-Fehler darf kein neuer DSP-Zugriff zugelassen werden. |
| EXIT und Wiederherstellung | Der Wiederherstellungsdienst läuft vor dem Größen- und EXIT-Check. Der EXIT-Weg muss vor zusätzlichen Patch-Kartenzugriffen liegen. Im Emulator führt ein kaputtes Journal trotz gehaltener EXIT-Taste zu Modus 2 ohne geladene Nutzer-Samples. Der eigene Fehlerfall bestätigt den Befund. |
| Automatische Aktivierung | Der normale rote Patchsatz enthält den Swap ohne gesonderte Wahl. Die gewünschte Trennung vom normalen Satz ist noch umzusetzen. |
| Projekt-RAM | Der Deklarationsvertrag auf develop lehnt den vorgesehenen Bereich ab `0xC3000000` mit 13 MiB wegen des Swap-Besitzes ab. Das ist ein bestätigter Integrationskonflikt, kein Nachweis eines bereits laufenden Projekt-Laders. |
| Deskriptor-Prüfsumme | Mit den oben beschriebenen Fehlerfällen korrigiert. |
| Kopie in den Arbeitspuffer | Zusätzlich im ARM-Modell reproduziert: Eine eingeschobene Pufferübergabe ändert die Generation, die anschließende alte Kopie überschreibt dennoch die neuen Pufferdaten. Dieser eigene Fehler ist noch zu korrigieren. |
| Verlorener POST-Auftrag | Die ausstehende Markierung hat keinen Wiederanlauf. Der native Ringpuffer und sein Aufrufweg liefern keinen einfachen, verlässlichen Erfolgsstatus für eine bloße Prüfung von r0; Wiederanlauf und Fehlerfälle stehen aus. |
| Abtrennung der Grundlagen | Die Wiederherstellung wird bereits beim Start aufgerufen. Schreib- und Importdienst sind noch nicht an die normale Bedienung angebunden. Eine Abtrennung muss diese Abhängigkeit erhalten. Stereo-Korrektur und Testinfrastruktur getrennt einordnen. |
| Anzahl und Dauer | Der bisherige Stand enthält 21 Swap-Gruppen, nach diesen Ergänzungen 22. Die neuen vollständigen Läufe dauern lokal rund 34 beziehungsweise 28 Minuten. Eine CI-Dauer ist daraus noch nicht abgeleitet. |
| Idle-Effekt | Die optionale Kombination überschneidet sich mit dem Transportbereich. Die bestehende RAM-Prüfung weist diese Kombination bereits zurück. Eine gemeinsame Platzaufteilung bleibt offen. |
| develop und Freigabedaten | Der zerstörungsfreie Probe-Merge meldet vier Textkonflikte. Zusätzlich fehlen die neue Beschriftung und die RAM-Abstimmung. `verified.json` wurde nicht als aktuell ausgegeben und muss nach der Integration neu erzeugt werden. |

Der Probe-Merge verändert weder Arbeitsbaum noch Branch. Der Kommentar
führt damit zu zusätzlichen Abnahmebedingungen, nicht zu einer Freigabe
aufgrund der beiden jetzt korrigierten Laufzeitfehler. Klang, Stimmen,
echte Aufnahme, USB-Schreiber und der vollständige neue Speicherweg
bleiben offen. Am Gerät wurde für diese Korrektur nichts ausgeführt.
