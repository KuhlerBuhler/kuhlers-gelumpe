# SysEx-Puffer mit unveränderten 32-KiB-Blöcken

Status: **hergeleitet und im Emulator sowie nativ gemessen**.
Kein Gerätetest und keine Freigabe einer Test-VSB.

## Vergleich und Umfang

Ausgangspunkt ist der bereits geprüfte Operanddecoder aus
`83d5036e34d5573da578c409d322a5560a908a86`, beschrieben in der
[Decodermessung](2026-10-21-patch-effizienz-decoder.md).
Der SysEx-Quellstand ist `7fbd90e6c5287bbafe2126a7dbadd7e3b798ae2b`.
Die bisherigen Profile bleiben unverändert. Ein gesondertes Vergleichspaket
ergänzt native Transfermessungen mit dem eingefrorenen bisherigen Generator.
So wird der Decodergewinn nicht erneut dem Puffer zugerechnet.

Die Änderung betrifft den eigenen Puffer des
[SysEx-Patches](../../tools/patch/blech_sysex.py).
Anfragen, Antworten, CRC, Schutzregeln, Protokollversion, Dateipfade und
maximale Blockgröße bleiben gleich. Die drei Manifeste werden aus den
Generatoren neu erzeugt. Synth-Adressen werden weiterhin mit `fwmap.py`
aus den eigenen Originalen zugeordnet und an den vorgesehenen Codestellen
auf gleichen Code geprüft.

## Herleitung des Platzbedarfs

FILE READ braucht mit 20 Byte den längsten Antwortkopf für Daten. Ein voller
Block enthält 32768 Datenbytes. Die größte Rohantwort hat damit 32788 Byte.
Das 7-Bit-Packing braucht ein zusätzliches Byte je angefangenen sieben
Rohbytes, hier 4684 Gruppenbytes. Sieben Rahmenbytes vor den Daten und das
Abschlussbyte ergeben insgesamt 37480 Byte auf der Leitung.

Weitere drei Byte decken die Rundung des Rohdatenanfangs auf eine Wortgrenze
ab. Der konservative Mindestbedarf beträgt 37483 Byte. Auf eine Grenze von
256 Byte aufgerundet benötigt der Puffer 37632 Byte, also 36,75 KiB.

| Bereich | Bisher, KiB | Neuer Stand, KiB |
|---|---:|---:|
| Zustand | 0,25 | 0,25 |
| Nachrichtenpuffer | 55,75 | 36,75 |
| Dateiobjekt, Pfade und Name | 4,00 | 4,00 |
| SysEx insgesamt reserviert | 60,00 | 41,00 |

BUF bleibt bei `0xC0191100`. Sein Ende liegt jetzt bei `0xC019A400`.
Der getrennte Dateibereich bleibt bei `0xC019F000` bis `0xC01A0000`.
Dazwischen werden 19456 Byte zusammenhängend frei, also genau 19 KiB.
Die VSB behält ihre Größe. Daraus entsteht Platz für weitere Patches;
ein größerer Sample-Speicher oder schnellerer Sample-Import und Export
wird damit nicht belegt.

Für beide Datenantwortköpfe H = 16 und H = 20 und jede angeforderte Länge
n von 0 bis 32768 prüft der Test diese Grenzen:

```text
R = H + n
G = ceil(R / 7)
S = align_down(BUFFER_REQUIRED - n, 4) - H
S >= 7 + G
8 + R + G <= BUFFER_REQUIRED
```

Die erste Bedingung schützt noch ungelesene Rohbytes beim vorwärts laufenden
Packen im selben Puffer. Die zweite hält den fertigen Rahmen im Puffer.
Das sind 65538 Längen-/Kopfpaare. Bei einem kurzen FILE READ sinkt die
Antwortlänge; die strengere Grenze für die volle angeforderte Länge reicht
weiterhin aus. DATA-Anfragen brauchen höchstens 32768 entschlüsselte Bytes.
Kurze Anfragen und Antworten liegen im separaten Zustandsspeicher.
FLASH bleibt auf 4096 Byte pro Anfrage begrenzt.

## Prüfungen und ihre Reichweite

[Die native Matrix](../../tools/patch/test_blech_sysex_buffer.py) führt den
erzeugten ARM-Code auf selbst erzeugten Daten aus. Datei-, Flash- und
Ausgabefunktionen werden an ihrer Firmware-Schnittstelle modelliert.
Die Portkennungen 1 für USB und 2 für DIN werden beide geprüft.

Die Matrix enthält alle acht Kommandos und die Längen
0/1/2/6/7/8/63/64/127/255/256/4096/8192 sowie 32762 bis 32769, soweit das
jeweilige Kommando die Länge zulässt. Geprüft werden Antwortbytes, Packing,
CRC, Dateiinhalte, EOF, kurze Lesezugriffe, Fehler beim Öffnen, Lesen,
Schreiben, Positionieren und Schließen, Schreibfolgen ohne Anmeldung,
Bereichsgrenzen, Plugin-Namen, Ordnergrenzen und EXIT.
Schutzmarken halten Zugriffe auf den freigegebenen Bereich und die Grenzen
der verwendeten Speicherbereiche sichtbar fest. Die Wächter gelten für den
in diesem Satz noch unbelegten Bereich; eine spätere Belegung durch andere
Patches ist nicht Bestandteil dieser Messung.

Zusätzlich durchläuft
[die DIN-Prüfung](../../tools/emu/sysex_cases.py) den echten Firmwareparser,
die emulierte UART und das virtuelle Dateisystem. Sie enthält zerstückelte
Anfragen und DATA bis 32 KiB, Überlängen, Formatfehler und erneute Anfragen.
Auf dem Synth werden RAM-Schreibanmeldungen weiterhin abgelehnt.

Der Emulator besitzt keinen USB-Controller. Der native Nachweis bis zur
unveränderten USB-Befehlsschnittstelle ist kein Test von USB-Endpunkten,
USB-Rückstau oder echter USB-Übertragungszeit. Diese Teile bleiben bei der
gesonderten Geräteabnahme in Phase 6. Die Transfermessung zählt nur
ARM-Befehle innerhalb des eigenen SysEx-Codes, keine SD-Latenz oder
Ausführungszeit der externen Treiber.

## Bestehende Eigenheit des Parsers

Zu kurze und überlange abgeschlossene Anfragen erhalten Korgs Formatfehler
`0x26`. Fehlt das Abschlussbyte F7 vollständig, verbraucht der Parser die
nächste INFO-Anfrage bis zu deren Abschlussbyte ohne INFO-Antwort. Erst die
zweite INFO-Anfrage funktioniert wieder.

Die Diagnose zeigt dieses Verhalten vor und nach der Pufferänderung.
Die Tests halten es ausdrücklich fest. Der Pufferpatch verändert den
ursprünglichen Parser nicht.

## Ergebnisse

Alle drei vollständigen Sätze bestehen ohne Kurzprüfung und ohne Ergebniscache.
Die überwachten Quellen bleiben unverändert. Kein Pflichtfall wurde ausgelassen.

| Build | Vollständige Prüfungen |
|---|---:|
| Hacktribe | 459/459 |
| Korg rot | 484/484 |
| Synth | 363/363 |

Die native Transfermessung enthält drei identische Wiederholungen je Build.
Median und Höchstwert sind jeweils gleich. Anfragevektoren, Antwortbytes und
Dateizugriffe stimmen mit dem bisherigen Stand überein.

| Build | Kommandos je Wiederholung | ARM-Befehle vorher | ARM-Befehle nachher | Änderung, Prozent |
|---|---:|---:|---:|---:|
| Hacktribe | 490 | 84.718.660 | 84.718.660 | 0,0000 |
| Korg rot | 490 | 84.719.140 | 84.719.140 | 0,0000 |
| Synth | 452 | 71.559.896 | 71.559.896 | 0,0000 |

Die allgemeine Profilmatrix enthält zusätzlich 18 unabhängige Starts mit
126 Messfenstern, 1350 abgeschlossenen App-Bildern und 216 Vorlaufbildern.
Alle übrigen Szenen bleiben innerhalb des Budgets von höchstens einem Prozent
Mehrarbeit. App-Zustände und Bildpuffer bleiben gleich. Das Erfassungsprotokoll
und die Plugin-Eingaben stimmen mit der Decoder-Vergleichsbasis überein.

Die folgende Platzbilanz gilt innerhalb der bestätigten freien Firmwarebereiche.
Code und Daten bleiben auf allen drei Builds gleich groß. Reserviertes RAM
und insgesamt belegter Platz sinken jeweils um genau 19 KiB.

| Build | Code/Daten, KiB | RAM vorher / nachher, KiB | Frei nachher, KiB | Größte Lücke nachher, KiB |
|---|---:|---:|---:|---:|
| Hacktribe | 82,28 | 440,87 / 421,87 | 55,42 | 19,00 |
| Korg rot | 82,48 | 440,87 / 421,87 | 55,21 | 19,00 |
| Synth | 65,32 | 388,71 / 369,71 | 454,96 | 322,26 |

Bei beiden Samplern ist der freigegebene 19-KiB-Bereich jetzt die größte Lücke.
Der Synth besitzt weiterhin eine größere bestehende Lücke; der neue Bereich
kommt dort getrennt hinzu. Die Größen und Grenzen stehen auch in der
[Messdatei](2026-10-21-patch-effizienz-sysex-zahlen.json).

| Abschließende Suite | Bestanden | Fehler | Ausgelassen |
|---|---:|---:|---:|
| Native SysEx-Prüfungen | 7 | 0 | 0 |
| Gezielte Node-Tests mit allen drei Originalen | 60 | 0 | 0 |
| Unit-Suite | 962 | 0 | 143 |
| Browser-Suite | 164 | 0 | 1 |
| Abschließende Dokumentationsprüfung | 9 | 0 | 0 |

Die Gesamtsuiten liefen nacheinander mit höchstens zwei Testdateien gleichzeitig.
Die Firmwareprüfungen und Profile verwendeten höchstens zwei rechnende Worker.
Die Gesamtsuite-Auslassungen sind die vorgesehenen optionalen Prüfungen.
Keine Prüfung wurde für die Pufferänderung deaktiviert.

Phase 5 ist automatisch geprüft. Gemeinsame Codeprüfung und Geräteabnahme in
Phase 6 bleiben offen. Kein Gerät wurde angesprochen, keine SD-Karte beschrieben
und keine Firmware veröffentlicht. Originale, VSBs, Rohprofile und vollständige
Befehlsprotokolle liegen außerhalb des Repositorys im privaten Messpaket
BLECH-Performance-SysEx-2026-10-21. Hier stehen nur eigene Messwerte und Hashes.
