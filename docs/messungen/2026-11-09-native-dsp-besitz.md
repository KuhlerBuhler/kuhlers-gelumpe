# Native DSP-Aufträge: Besitzer nach dem Warten prüfen

Stand: 2026-11-09. **Gemessen im Emulator**, **hergeleitet aus dem Code**
und **offen** sind getrennt. Kein Gerätezugriff, kein Klang- oder DMA-Nachweis.
Die Prüfung verwendet die bekannten Originale der roten Sampler-Firmware
2.02, Stock und Hacktribe. Die blaue Synth-Firmware wird vom Sample-Swap
weiterhin abgewiesen.

## Ausgangslage

Die [PCM-Korrektur](2026-11-09-sample-pcm-bereichsschutz.md) schützt die
physisch beschriebenen Sample-Zeilen. Eine weitere Lücke lag davor:
Ein nativer Auftrag konnte auf Ressource 1 warten und danach trotz geänderter
Bibliothek oder Generation weitermachen. Außerdem konnte ein neuer Aufruf
einen bereits aktiven Wiederherstellungsrahmen ersetzen.

**Gemessen im Emulator:** Vier Gegenproben scheitern am bisherigen Code.
Geänderte Generation, Betriebsart oder Schrittfreigabe verhindern den
Auftragskörper nicht. Ein während des Erwerbs eingetragener fremder Rahmen
wird überschrieben. Die Daten und Aufrufrahmen dieser Gegenproben sind erzeugt.

## Hergeleitet: Erwerb und Veröffentlichung

`tools/patch/native_dsp_acquire.py` übernimmt den initialisierten Erwerb.
Die unveränderte Firmware liefert diese Funktionen und Zustände:

| Zweck | Adresse |
|---|---|
| Ursprünglicher, unbegrenzt wartender Erwerb | `0xC0000D80` |
| Freigabe mit Bedienung bestehender Warteschlangen | `0xC0000CA8` |
| Verzögerung des aktuellen Tasks | `0xC0000B78` |
| Zähler von Ressource 1 | `0xC06A2480` |
| Aktueller Task | `0xC06A289C` |
| Betriebssystemzähler in Millisekunden | `0xC06A292C` |

Die ursprünglichen Erwerbs-, Freigabe- und Verzögerungsfunktionen haben in
beiden geprüften Originalen dieselben Prüfsummen. Der Builder prüft auch die
Verzögerungsfunktion, bevor er den Patch erzeugt. Für Datei-Adressen gilt
`file = ram - 0xC0000000 + 0x100`.

Vor dem Warten wird der Task festgehalten. Bibliotheksgebundene Aufträge
halten zusätzlich Betriebsart, Generation, Sitzung, Schrittfreigabe,
Schrittbesitzer und die vier Wörter des Dateibesitzers fest. Vor jedem
Versuch und nach dem Erwerb müssen diese Werte noch passen. Ein unabhängiger
nativer Steuerauftrag bindet sich an Task, gültigen Aufrufkontext und
Fehlerzustand, jedoch nicht an eine fremde Bibliothek.

Bei belegter Ressource wartet der Task jeweils eine Millisekunde über die
native Verzögerungsfunktion. Nach 1.000 Betriebssystem-Ticks oder spätestens
1.000 Erwerbsversuchen endet das Warten. Das setzt einen funktionierenden
Scheduler voraus. Ein vollständig angehaltener Scheduler ist damit nicht
gegen einen eigenen Stillstand abgesichert.

Nur der freie Zählerwert 1 wird unter gesperrten IRQs auf 0 gesetzt.
Ein erfolgreicher Erwerb übergibt genau eine Belegung bei weiterhin gesperrten
IRQs. Der unmittelbar folgende Aufrufer prüft den globalen Rahmen erneut,
veröffentlicht den eigenen Stapelrahmen und stellt den ursprünglichen
Interrupt-Zustand wieder her. Ein vorhandener Rahmen wird nicht ersetzt.
Die Freigabe läuft über die native Funktion, damit deren wartende Aufträge
weiter bedient werden.

`INSTEP_TASK` nutzt das letzte freie Wort vor der unverändert bei `0xA0`
beginnenden Fehlertabelle. Eine gesetzte globale Schrittfreigabe reicht für
einen fremden Task nicht mehr aus. Native Sample-Lese- und Schreibaufträge
bleiben unabhängig von diesem optionalen Schrittbezug begrenzt.

## Hergeleitet: getrennte Abbrüche

- Vor dem DSP-Zugriff: nur den eigenen Aufruf abbrechen. Keine Änderung von
  Bibliothek, Generation, Fehlerzustand oder fremdem Rahmen. Ein nativer
  Sample-Aufruf liefert Fehler 4 an den vorhandenen prüfenden Aufrufer.
- Bereits erworben, aber nicht veröffentlichbar: nur die eigene Belegung
  genau einmal bei freigegebenen IRQs zurückgeben.
- Echter Fehler nach Beginn des Protokolls: den eigenen Rahmen abwickeln,
  den bisherigen verriegelten Transportfehler erhalten und nur die eigene
  Belegung freigeben. Eine geliehene Belegung bleibt beim äußeren Aufrufer.
- Fremde Poll-, Abschluss- oder Freigabeaufrufe verbrauchen weder das Budget
  noch den Rahmen des Besitzers.

Der normale Übergang eines laufenden Transports von Fehlerzustand 1 nach 0
ist kein verriegelter Fehler. Erst Werte ab 2 verhindern weitere Zugriffe.
Vor der Initialisierung bleibt der bisherige native Startpfad erhalten.
Der neue Erwerbsablauf ersetzt daher nicht jeden Kernel-Aufruf im System.

Die Erwerbsgrenze von einer Sekunde ist getrennt von der bestehenden
100-ms-Grenze des DSP-Protokolls. Unabhängige native Steueraufträge behalten
ihre bisherigen Protokoll-Warteschleifen. Diese Korrektur begrenzt deren
Ressourcenerwerb, nicht pauschal jedes DSP-Kommando.

## Gemessen im Emulator

Die vollständigen roten Ausgaben enthalten jeweils alle 29 Patches des
BLECH-Satzes. Die neuen Fälle stehen in `tools/emu/native_dsp_owner_cases.py`
und laufen über die vorhandene native DSP-Gruppe in `tools/emu/swap_cases.py`.
Eigene ARM-Aufrufe stellen die Konkurrenz her; Kernel, Scheduler,
Warteschlange und nativer Sample-Leser laufen dabei aus der Firmware.

| Gegenprobe | Ergebnis auf beiden roten Originalen |
|---|---|
| Erwerb nach Freigabe durch einen anderen Task | bestanden |
| Keine Freigabe | Abbruch nach 1.000 Betriebssystem-Ticks, Bibliothekszustand unverändert |
| Bibliotheksgeneration während des Wartens geändert | Abbruch ohne DSP-Zugriff, anschließender gültiger Aufruf erfolgreich |
| Bereits wartender ursprünglicher Kernel-Aufruf | wartet, wird freigegeben und beendet sich vor dem neuen Erwerb |
| Nativer Sample-Leser bei geänderter Generation | Fehler 4, kein DSP-Zugriff, Zustand der neuen Generation erhalten |
| Nativer Sample-Leser bei belegter Ressource | Fehler 4 nach 1.000 Ticks, kein DSP-Zugriff, nächster Versuch erfolgreich |
| Bisherige native DSP-Fälle einschließlich verzögertem DSP, Stereo und Teiltransfer | alle 17 bestanden |

Im Konkurrenzfall wartet Task `0xC06A2544`; Task `0xC06A2564` führt den
eingeschobenen ursprünglichen Freigabeaufruf aus. Für den Warteschlangenfall
kommt `0xC06A25E4` hinzu. Die drei Task-Adressen werden im Test beobachtet,
nicht im Patch als zulässige Besitzer festgeschrieben.

Die 23 nativen Fälle und alle 22 Fälle des PCM-Schutzes bestehen pro Build.
Die Startprüfung besteht jeweils mit 15 Startfällen und sechs statischen
Prüfungen. `npm test` besteht mit 1.395 erfolgreichen und 161 übersprungenen
Tests, ohne Fehler. `npm run test:e2e` besteht mit 287 erfolgreichen Tests
und einer Auslassung. Der dort ohne Firmwarevariable übersprungene Test
mit echter Stock-Firmware besteht anschließend separat, ausdrücklich mit
dem eigenen Original und `E2_EMU_REQUIRED=1` aktiviert. Es wird keine
Prüfgrenze erhöht und kein fehlerhafter Fall übersprungen.

**Gemessen mit erzeugtem ARM-Code:** Der freie Erwerb benötigt 112
Instruktionen ohne Bibliotheksbindung und 292 mit Bindung. Der Helfer nutzt
96 Stapelbytes; der Wiederherstellungsrahmen reserviert 144 Bytes einschließlich
16 Bytes für ausgehende Argumente. Die Messung ist keine Aussage über echte
Interrupt-Latenz. Code und Zustand bleiben in den bestehenden reservierten
Bereichen; es wird kein zusätzlicher Sample-RAM freigegeben.

| Codebereich | Belegt | Noch frei |
|---|---:|---:|
| `0xC019A400` bis `0xC019C400` | 7.868 Bytes | 324 Bytes |
| `0xC019C400` bis `0xC019E000` | 5.544 Bytes | 1.624 Bytes |

Drei unabhängige Codeprüfungen von Architektur, Aufrufrückkehr und Risiken
haben keine offenen Befunde. Eine zu strenge Annahme der Timeout-Gegenprobe
ist korrigiert: Neben der Tickgrenze gilt auch die Grenze der Erwerbsversuche.
In den beiden gemessenen Firmware-Läufen endet das Warten nach 981
Verzögerungsaufrufen und 1.000 Ticks.

## Offen

Diese Korrektur schließt die Besitzerprüfung nach dem Ressourcenwarten und
das unbegrenzte Warten an diesem Erwerbspfad. Aufnahme und Resampling müssen
neue Veröffentlichungen weiterhin mit einer Schutzrevision versehen, damit
vorbereitete Auslagerungen ungültig werden. Der vollständige Nachweis des
RAM-Besitzes einschließlich DMA sowie die kombinierte Geräteprüfung bleiben
offen. Ebenso bleiben die in der [Gesamtprüfung](2026-11-09-sample-swap-pruefung.md)
genannten Speicher- und Ladeanschlüsse außerhalb dieser Korrektur.

Der vorhandene vollständige Prüfnachweis in `data/patches/verified.json`
wird durch diese Teilprüfung nicht erneuert. Vor einer Veröffentlichung
bleibt die vollständige Prüfung der drei Originale erforderlich.

Es wird keine neue Firmware installiert, keine Karte beschrieben und keine
Flash-Schreibfunktion ergänzt. Die Ergebnisse geben das gesamte Swap-Feature
noch nicht zur Veröffentlichung frei.
