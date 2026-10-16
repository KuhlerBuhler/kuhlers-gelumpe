# Geräteprotokoll: Suche, RAM lesen und Pattern-Abfrage

**Gemessen am Gerät, 8. Oktober 2026:** Electribe 2 Sampler 2.02 mit
Hacktribe, USB am Linux-Laptop, ALSA/RtMidi via Python mido. Kanal aus der
Suchantwort, keine Annahme im Messskript. Neue Nachrichten und Decoder
zuerst gegen tatsächliches SimDevice, Kanal 9, mit dem vorhandenen
Simulationsabbild geprüft; auch sofortiger Abbruch bei Timeout getestet.
Am Gerät wurden ausschließlich Suche, RAM-Lesen und Pattern-Request
verwendet; keine Schreib-, Flash- oder Execute-Befehle.

Kurz:
- Die Gerätesuche antwortet mit 15 Byte, RAM-Lesen und Pattern-Abfrage
  liefern vollständige Antworten (Zeiten in der Tabelle unten).
- RAM-Schreiben mit 256-Byte-Teilnachrichten ist mehrfach geprüft; größere
  Nachrichten blieben über den ersten Sendeweg ohne Bestätigung.
- Die fehlenden Bestätigungen bei 3.584 und 4.096 Byte sind keine belegte
  Gerätegrenze: Mit eigenem getaktetem ALSA-Sender wurden 52.400 Nutzbytes in
  einer Nachricht angenommen.
- Der Editor schreibt weiter nur 256-Byte-Teilnachrichten und gibt das
  Schreiben nur nach geprüften Firmware-Signaturen frei.

## Gerätesuche

**Gemessen am Gerät:** Fünf identische Antworten, 15 Byte einschließlich
F0/F7. Nullbasierte Positionen: Byte 4 = 9 (Kanal), Byte 6 = 0x24 (Sampler),
Byte 10 = 0x02, Byte 11 = 0x02, Byte 12/13 = 0x00/0x00.
Der Simulator liefert dagegen eine 13-Byte-Suchantwort; der vorhandene
Parser akzeptiert die reale längere Antwort und liest dieselben Positionen.
Die Paarung 2/2 allein identifiziert keinen bestimmten Hacktribe-Build.
Ein passender RAM-Layout-/Firmwarebezug bleibt zusätzlich notwendig.

## Antwortzeiten

**Gemessen am Gerät:** Je fünf erfolgreiche Messungen je Zeile.
Zeit ab Aufruf der ALSA-Ausgabe bis zum Eingang der vollständigen
SysEx-Antwort im Callback, monotone Nanosekundenuhr. Transport und Treiber
sind enthalten. MIDI-Realtime wird separat gezählt: während dieser Messung
25 Clock-Nachrichten. Es gab keinen Timeout und keinen Wiederholungsversuch.

| Anfrage | Nutzdaten | Minimum ms | Median ms | Maximum ms |
|---|---:|---:|---:|---:|
| Gerätesuche | 0 | 0.907 | 1.909 | 1.986 |
| RAM lesen | 4 | 1.873 | 1.917 | 1.951 |
| RAM lesen | 256 | 1.776 | 2.049 | 3.613 |
| RAM lesen | 524 | 3.853 | 4.068 | 4.803 |
| RAM lesen | 4096 | 20.449 | 21.301 | 21.410 |
| RAM lesen | 16384 | 79.598 | 80.064 | 80.835 |
| Pattern anfordern | 16384 | 79.242 | 79.837 | 80.613 |

**Grenze des Nachweises:** Das sind Linux-USB-Messungen, keine garantierten
Maximalzeiten unter jeder Last und keine DIN-/Chrome-/Windows-Messungen.
Die bestehenden Wartezeiten dürfen nicht auf diese Maxima verkürzt werden.
Eine Pattern-Abfrage (Request 0x10, Antwort 0x40) ist von der Bestätigung
eines an das Gerät gesendeten Pattern-Dumps (0x40) zu unterscheiden.

## RAM-Leseantwort

**Gemessen am Gerät:** Bei sämtlichen 25 RAM-Lesungen steht Byte 6 auf
0x54, Byte 7 auf 0x52, Byte 8 auf 0x00. Nutzdaten beginnen bei Byte 9.
Die Antworten wurden vollständig dekodiert und auf die angefragte Länge
geprüft. SimDevice verwendet für Byte 7/8 bisher 0x00/0x00;
`parseReadRam()` überspringt beide Bytes und dekodiert die reale Antwort richtig.
**Vermutung:** Byte 7 enthält das ursprüngliche Anfragekommando; dessen
Bedeutung außerhalb von RAM-Lesungen wird hier nicht verallgemeinert.

## MFX-Menülänge als Instruktion

**Gemessen am Gerät:** Fünf RAM-Lesungen von vier Byte bei 0xC003EFE4
liefern identisch das LE-Instruktionswort **0xE3A00032**, `mov r0, #50`.
Der vorhandene RAM-Dump und das Simulationsabbild enthalten dasselbe Wort.
Damit ist 0xC003EFE4 das niederwertige Immediate-Byte einer ARM-Instruktion.

**Schutzvorschlag:** Vor einer Änderung das gesamte Wort lesen und mit dem
für die geladene Firmware erwarteten Wort vergleichen. Ausschließlich das
niederwertige Byte für die validierte Menülänge ändern; die oberen 24 Bit
müssen 0xE3A000 sein. Vorzustand sichern und das gesamte Wort zurücklesen.
Ein plausibler Zähler allein reicht nicht als Instruktionsprüfung.

Roh-Patternbackup und Messprotokoll liegen außerhalb des Repositories.

## RAM-Schreibbestätigungen und erste Größengrenze

**Gemessen am Gerät:** Schreibtests erfolgten nach Bestätigung, dass weder
Aufnahme noch Wiedergabe läuft. Die gesamte MFX-Tabelle (100 × 524 Byte)
wurde vorab gesichert. Gesendet wurden ausschließlich die zuvor gelesenen
Originalwerte an denselben Tabellenanfang 0xC00B4F30; keine Parameterwerte
wurden absichtlich verändert. SimDevice Kanal 9 prüfte zuvor sämtliche
geplanten Größen, Rücklesen, Nachbar-Sentinels und sofortigen Timeout-Abbruch.

**Gemessen am Gerät:** 16, 256, 268 und 524 Byte je dreimal sowie 1.024 und
2.048 Byte je einmal erfolgreich: Adress-ACK, Daten-ACK, danach exaktes
Rücklesen. Die Erfolgs-ACK lautet F0 42 39 00 01 24 21 F7; 0x39 enthält
hier den ermittelten Kanal 9.

| Bestätigung | Anzahl | Minimum ms | Median ms | Maximum ms |
|---|---:|---:|---:|---:|
| Schreibadresse | 15 | 159.908 | 163.940 | 186.974 |
| Schreibdaten | 14 | 159.840 | 161.969 | 165.925 |

**Gemessen am Gerät:** Die nächste Adressnachricht für 4.096 Byte wurde noch
bestätigt. Auf die zugehörige Datennachricht (4.690 Byte einschließlich
F0/F7 und 7-Bit-Packing) kam innerhalb von sechs Sekunden keine Antwort.
Das Skript stoppte sofort. Keine weitere Geräteanfrage, keine Wiederholung,
kein automatischer Restore und kein Pattern-Dump wurden danach gesendet.

**Gemessene Untergrenze:** Eine einzelne RAM-Datennachricht mit 2.048
Nutzbytes / 2.349 MIDI-Bytes ist angenommen und zurückgelesen worden.
**Nicht daraus ableitbar:** dass 2.048 Byte die exakte Höchstgröße sind oder
jede Nachricht oberhalb davon scheitert. Das nächste fehlgeschlagene
Messintervall endet bei 4.096 Byte. Ob der Empfänger hing oder die Nachricht
im Transport verloren ging, wurde nach dem vorgeschriebenen Stopp nicht
durch erneute Geräteanfragen untersucht.

**Schutzvorschlag:** Für den Editor bis zur weiteren Eingrenzung weiterhin
die bereits mehrfach geprüften 256-Byte-Teilnachrichten verwenden.
Die Firmware-/Flash-Bereiche wurden nicht beschrieben. Das vollständige
MFX-Backup liegt außerhalb des Repositories; die fehlgeschlagene letzte
Nachricht verhindert einen abschließenden Vergleich der gesamten Tabelle
und ihrer Nachbarn in diesem Lauf.


## Nachprüfung ohne Neustart und engere Größengrenze

**Gemessen am Gerät:** Nach der ausbleibenden
4-KiB-Bestätigung lief die Oberfläche weiter. Die erste neue
Gerätesuche erhielt eine acht Byte lange Antwort mit Funktionsbyte 0x26;
der Prüfablauf stoppte vor RAM-Lesungen und Pattern-Schreiben. Eine separate,
ausschließlich lesende Gerätesuche erhielt danach wieder die vollständige
15-Byte-Suchantwort, Kanal 9, Version 2/2, nach 2,391 ms. Kein Neustart
war zwischen diesen Beobachtungen erforderlich.

**Gemessen offline:** Der Empfänger kann bei 0xC0027594..0xC002759C den
Status 0x26 setzen, wenn der aufgerufene Empfangspfad 0xF7 zurückliefert.
**Vermutet:** Die erste Antwort hing mit einer unvollständigen großen
Nachricht zusammen; die genaue Zuordnung und Ursache sind nicht bewiesen.

**Gemessen am Gerät:** Vor der nächsten Schreibserie entsprach der SHA-256
der gesamten MFX-Tabelle exakt dem ursprünglichen Backup. Damit ist auch
nach dem ersten fehlgeschlagenen 4-KiB-Test die gesamte Tabelle unverändert
zurückgelesen worden. Die Nachbarbytes wurden in diesem Vergleich nicht
gegen die erste Sicherung geprüft.

**Gemessen am Gerät:** 2.304, 2.560, 2.681, 2.682, 2.816 und 3.072 Nutzbytes
wurden jeweils einmal als unveränderte Originaldaten geschrieben: je zwei
Erfolgs-ACKs und anschließendes exaktes Rücklesen. Daten-ACKs kamen nach
162,932 bis 164,002 ms. 3.072 Nutzbytes entsprechen 3.519 MIDI-Bytes.
Auch 3.074 MIDI-Bytes wurden angenommen; eine behauptete harte Grenze bei
3.072 MIDI-Bytes wäre damit widerlegt.

**Gemessen am Gerät:** Für 3.584 Nutzbytes / 4.104 MIDI-Bytes kam noch das
Adress-ACK, aber innerhalb sechs Sekunden kein Daten-ACK. Sofortiger Stopp,
keine weitere Geräteabfrage und keine Wiederholung in diesem Lauf.
**Gemessene Untergrenze:** 3.072 Nutzbytes pro Datennachricht; nächster
fehlgeschlagener Test bei 3.584 Nutzbytes. Die exakte Höchstgröße und eine
mögliche Abhängigkeit vom Sendeweg bleiben damit unbewiesen.

## Pattern-Dump: Objektversatz und Transportfehler

**Gemessen am Gerät:** Nach Auswahl des als leer geltenden Patterns 167
zeigte der Objektzugriff auf 0xC06B2798. Dort liegen vier Byte Objektkopf;
die Pattern-Daten mit PTST beginnen bei **0xC06B279C**. Das erste
Prüfskript verglich irrtümlich ab dem Objektkopf und stoppte vor dem
Senden. Daraus abgeleitete Glide-Werte und Verlustbehauptungen wurden
verworfen; sie waren um vier Byte versetzt.

**Gemessen am Gerät:** Die korrigierte vollständige RAM-Lesung von
16.384 Byte ab 0xC06B279C stimmt exakt mit der dekodierten
PatternRequest-Antwort überein. Alle 16 Glide-Werte sind null. Beide
Sicherungen liegen außerhalb des Repositories.

**Gemessen in SimDevice:** Der korrigierte Prüfablauf wurde auf Kanal 9
mit der vorgeschriebenen eigenen SYSTEM.VSB gegen echte SimDevice-
Verarbeitung geprüft: unverändertes Pattern, Beobachtung ohne Bestätigung,
Bestätigungsauswertung über eine ergänzte Testantwort und Abbruch vor
jedem Pattern-Dump bei nicht-null Glide. Die ergänzte Bestätigung beweist
nur die Auswertung des Skripts, keine Gerätebestätigung.

**Gemessen am Host:** Beim anschließenden Versuch, den unveränderten
Pattern-Dump (18.733 MIDI-Bytes) zu senden, meldete RtMidi/ALSA:
`MidiOutAlsa::sendMessage: error sending MIDI message to port.`
Der Ablauf stoppte sofort; keine nachfolgende Pattern- oder RAM-Anfrage.
Das interne Reportfeld `pattern_sent: true` bezeichnet hier nur den
begonnenen Sendeversuch, keine bestätigte vollständige Zustellung.
Eine Schreibbestätigung oder deren Ausbleiben nach vollständig zugestelltem
Pattern-Dump ist durch diesen Lauf nicht gemessen.

**Am Gerät beobachtet:** Anschließend stand
„receive midi error“ im Display. Der genaue Zeitpunkt und die Zuordnung
zum 3.584-Byte-RAM-Test oder Pattern-Sendeversuch sind nicht erfasst.
Weitere Schreibtests wurden gestoppt.

**Gemessen am Gerät:** Nach dem 3.584-Byte-RAM-Test antwortete zunächst
wieder eine acht Byte lange Nachricht mit Funktionsbyte 0x26 auf die
Gerätesuche. Die getrennte nächste Gerätesuche lieferte die korrekte
15-Byte-Antwort nach 1,885 ms. Dies beweist eine wieder antwortende
Gerätesuche, keine allgemeine Fehlerfreiheit nach großen Nachrichten.

**Vermutet:** Die bisher beobachtete Größenbegrenzung könnte im
Host-/USB-Sendeweg liegen. Eine reine Gerätegrenze ist damit nicht bewiesen.


## Gegenprobe ausschließlich zwischen virtuellen ALSA-Ports

**Gemessen am Host, ohne Gerätezugriff:** Auf demselben Laptop wurden
synthetische SysEx-Nachrichten zwischen zwei neu erstellten, eindeutig
benannten virtuellen ALSA-Ports übertragen. Kein Hardware-Port wurde
geöffnet. Installiert: python-rtmidi 1.5.8, RtMidi 5.0.0, mido 1.3.3.
2.349, 3.519, 4.104 und 4.690 MIDI-Bytes kamen jeweils vollständig und
bytegenau an. Bei 18.733 MIDI-Bytes entstand derselbe
`MidiOutAlsa::sendMessage: error sending MIDI message to port.`;
am virtuellen Empfänger kam keine vollständige Nachricht an.

**Daraus belegt:** Der fehlgeschlagene große Pattern-Sendeaufruf ist
auch ohne Electribe reproduzierbar. Dieser Ablauf misst daher noch keine
Pattern-Dump-Unterstützung oder Bestätigungszeit des Geräts.
**Nicht daraus ableitbar:** Die Ursache des fehlenden ACK bei 4.104 oder
4.690 MIDI-Bytes am echten Gerät: Virtuelle Übertragung prüft weder USB-
Treiber noch Gerätelimits.

**Quellenprüfung:** [RtMidi 5.0.0, MidiOutAlsa::sendMessage](https://github.com/thestk/rtmidi/blob/5.0.0/RtMidi.cpp#L2234)
vergrößert den MIDI-Encoderpuffer, gibt die beobachtete Fehlermeldung aber
bei negativem Rückgabewert von `snd_seq_event_output()` aus. Die konkrete
ALSA-Fehlernummer ist durch die bisherige Meldung nicht erfasst.


## Offline-Ursache und geprüfter Transportansatz

**Gemessen am Host:** Eine diagnostische Instrumentierung des virtuellen
Tests erfasste bei `snd_seq_event_output()` einen Ausgabepuffer von
16.384 Byte und beim 18.733-Byte-Dump Rückgabewert **-22 / EINVAL**.
Die 28 Byte ALSA-Ereignisverwaltung kommen zur MIDI-Länge hinzu.
Nur den Ausgabepuffer auf 65.536 Byte zu vergrößern beseitigte diesen
Rückgabefehler, lieferte aber weiterhin keine vollständige Nachricht
am virtuellen Empfänger. Damit ist Puffervergrößerung allein kein
nachgewiesener vollständiger Fix.

**Gemessen am Host:** Den MIDI-Encoder auf höchstens 256 Byte je
ALSA-Ereignis zu begrenzen, beseitigte ebenfalls den Sendeaufruf-Fehler;
ohne Taktung kam aber nicht jede größere Nachricht vollständig an.
Mit zusätzlichem `snd_seq_drain_output()` nach jedem Ereignis und
2 ms Pause kamen alle fünf Größen **2.349, 3.519, 4.104, 4.690 und
18.733 MIDI-Bytes** am virtuellen Empfänger vollständig und bytegenau
als jeweils eine SysEx-Nachricht an. Rückgabefehler von Event-Ausgabe
und Drain wurden geprüft. Hardware-Ports wurden nicht geöffnet.

**Implementierungsvorschlag:** Die Linux-Sendestrecke muss große SysEx
als begrenzte ALSA-Ereignisse mit kontrolliertem Abfluss übertragen;
F0/F7 stehen nur am Anfang/Ende der gesamten Nachricht. Das gehört in
den ALSA-Transport, nicht in Pattern-Daten oder Firmware. Die hier
verwendete diagnostische LD_PRELOAD-Instrumentierung bleibt ein
Versuchsaufbau außerhalb des Repositories und ist keine Produktlösung.

**Grenze des Nachweises:** 256 Byte / 2 ms sind ausschließlich am
virtuellen ALSA-Sendeweg geprüft. Daraus folgt noch keine geprüfte
Gerätesicherheit oder Bestätigung des Pattern-Dumps. Kleine RAM-
Teilnachrichten bleiben für reale Schreibzugriffe die geprüfte Wahl.


## Eigener ALSA-Sender und erfolgreicher Pattern-Dump

**Implementiert:** [Linux-Sender](../../tools/alsa-sysex.md) als eigenständiges
Werkzeug mit begrenztem Encoder (256 Byte), geprüftem Abfluss und 2 ms
Abstand. Keine LD_PRELOAD-Ersetzung. Eine explizite ALSA-Verbindung öffnet
den Hardware-Ausgang vor der Übertragung; direkte Ereignisse ohne diese
Verbindung lieferten beim ersten Zugriff `drain output: No such device
(-19)`. Dieser erste Versuch stoppte bereits beim Senden der Gerätesuche.
Der [Linux-Kernel](https://github.com/torvalds/linux/blob/master/sound/core/seq/seq_midi.c)
öffnet den RawMIDI-Ausgang über die Port-Verbindung; ein Ereignis ohne
geöffneten Ausgang kann -ENODEV liefern.

**Gemessen offline:** Kompiliert mit C11, `-Wall -Wextra -Werror`.
Fünf Integrationstests zwischen virtuellen ALSA-Ports bestehen: alle fünf
Nachrichtengrößen bytegenau, mido-Adapter mit vollständigem großen Frame,
Abweisung beschädigter Frames, anderer MIDI-Nachrichten und ungültiger
Ziele. Kein Hardware-Port wird durch diese Tests ausgewählt. Der
Pattern-Prüfablauf wurde zuvor erneut gegen SimDevice, Kanal 9, mit
der eigenen SYSTEM.VSB geprüft.

**Gemessen am Gerät:** Der unveränderte Dump des am Gerät ausgewählten,
leeren Patterns 167 wurde über den neuen Sender übertragen. Die Electribe
antwortete vollständig mit **F0 42 39 00 01 24 23 F7** nach **183,377 ms**
ab Beginn des Sendeaufrufs, einschließlich Prozessstart und Taktung.
0x23 ist die hier gemessene Pattern-Bestätigung; RAM-Schreiben antwortete
mit 0x21. Es handelt sich um je einen konkreten Firmware-/USB-Messweg,
nicht um eine plattformübergreifende Zeitgarantie.

**Gemessen am Gerät:** Vor dem Senden stimmten 16.384 Byte rohes Pattern-RAM
ab 0xC06B279C exakt mit der dekodierten PatternRequest-Antwort überein;
alle Glide-Werte waren null. Nach der 0x23-Antwort wurden PatternRequest
und dasselbe RAM erneut gelesen. Beide Rücklesungen stimmen exakt mit den
Sicherungen überein. Das PatternRequest-Rücklesen dauerte 72,969 ms.
Keine Speicherfunktion am Gerät, Flash- oder Firmware-Schreiboperation.

**Gemessen am Host:** Das vollständige Ergebnis wurde gespeichert, danach
hing der Python-Prüfprozess beim Aufräumen des MIDI-Empfängers
(Prozesszustand futex_do_wait; kein nativer Senderprozess mehr vorhanden).
Er wurde gezielt beendet. Der erfolgreiche ACK-/Rücklese-Nachweis stammt
aus dem bereits fertig geschriebenen Report, nicht aus dem Exit-Status
dieses Prüfprozesses. Eine Ursache für den Empfänger-Cleanup-Hänger ist
hier nicht nachgewiesen.


## Große RAM-Nachrichten über den getakteten Sender

**Gemessen am Gerät:** Nach bestandener SimDevice-Prüfung auf Kanal 9
mit dem vorgeschriebenen Abbild und erweitertem virtuellem Transporttest
wurden unveränderte MFX-Daten über den eigenen ALSA-Sender geschrieben.
Vor dem ersten Schreiben wurde die gesamte Tabelle erneut gelesen und
gegen den ursprünglichen SHA-256 geprüft; Nachbarbytes wurden gesichert.
Die Zeiten laufen ab Beginn des Sendeaufrufs einschließlich Prozessstart,
getakteter Übertragung und anschließendem Polling des Empfängers. Alle
Adress- und Datenbestätigungen waren die vollständige Antwort mit
0x21. Jede Größe wurde unmittelbar bytegenau zurückgelesen.

| RAM-Nutzbytes | MIDI-Bytes | Daten-ACK nach ms |
|---:|---:|---:|
| 3.584 | 4.104 | 201,776 |
| 4.096 | 4.690 | 202,244 |
| 8.192 | 9.371 | 248,025 |
| 16.384 | 18.733 | 319,766 |
| 32.768 | 37.458 | 484,368 |
| 52.400 | 59.894 | 684,319 |

**Gemessen am Gerät:** Nach allen Schreibtests stimmen die gesamte
52.400-Byte-MFX-Tabelle und beide 16-Byte-Nachbarbereiche exakt mit dem
Vorzustand überein. Der Prüfprozess mit callback-freiem RtMidi-Empfang
beendete sich normal mit Exit-Code 0.

**Belegt:** 52.400 RAM-Nutzbytes sind in einer einzelnen SysEx-Datennachricht
angenommen worden. Die zuvor fehlgeschlagenen Größen 3.584 und 4.096 Byte
funktionieren mit diesem Sendeweg; sie sind keine belegte Gerätegrenze.
**Nicht gemessen:** Ein absolutes Nachrichtenmaximum oberhalb der gesamten
MFX-Tabelle. Über deren Grenze wurde nicht geschrieben. Der Editor bleibt
bewusst bei 256-Byte-Teilnachrichten; ein anderer Sendeweg ist dadurch
nicht automatisch für große Nachrichten freigegeben.

## Lesend geprüfte Firmware-Fingerabdrücke

**Gemessen am Gerät und offline:** Die folgenden SHA-256 stimmen zwischen
aktueller RAM-Lesung, vorhandenem 128-MiB-RAM-Dump und eigener SYSTEM.VSB
überein. Die Leseanfragen und Dekodierung wurden zuvor gegen SimDevice
geprüft. Die Hashes enthalten keine Firmware-Nutzbytes im Repository.

| RAM-Adresse | Länge | SHA-256 |
|---|---:|---|
| 0xC0000040 | 64 | 0ecfbf472eb414c359f29af80817ad36cac542fe94b1f4e3cd4fe078a50e6de0 |
| 0xC017059C | 512 | 94975043805a3baa09d4916636d9ba93c9ab7c367efbf7b8d8d8e1b848219470 |

**Gemessen offline:** In den ersten 64 Bytes ab 0xC0000000 unterscheiden
sich Bytes +0x34/+0x35 zwischen laufendem RAM und dem Abbild. Dieser
Abschnitt wurde als feste Abbild-Signatur verworfen.
**Vermutet:** Initialisierung verändert dort Vektordaten; eine genaue
Zuordnung dieser beiden Bytes ist hier nicht nachgewiesen.

## Schutzprüfungen im Editor

**Implementiert und getestet:** `data/devices.mjs` enthält das gemessene
Versionspaar und beide Code-Signaturen. Eine passende Versionsantwort
allein gibt Schreiben nicht frei. `DeviceSession.connect()` prüft beide
Signaturen lesend; ein fehlender oder abweichender Nachweis lässt das Gerät
nur lesbar. Das identifiziert den vermessenen Code an diesen Stellen,
es ist keine vollständige Integritätsprüfung des gesamten RAM.

**Implementiert und getestet:** Vor MFX-Menüänderung und Undo wird das
vier Byte lange ARM-Instruktionswort gelesen. Seine oberen 24 Bit müssen
0xE3A000 entsprechen und das bestehende Immediate im erlaubten Bereich
1..100 liegen. Nur das niederwertige Zählerbyte wird geschrieben. Das
anschließende Rücklesen verifiziert alle vier Byte. Dieselbe Prüfung gilt
für Änderungen der Firmware-Datei über die Gerätekarte. Die Angabe
0xE3A00032 bleibt der gemessene Ausgangswert; ein bereits zulässig
geänderter Zähler wird nicht fälschlich als fremder Opcode behandelt.

**Implementiert und getestet:** RAM-Schreibbestätigungen müssen exakt
0x21 auf dem gewählten Kanal tragen; Fehlerantworten wie 0x26 zählen
nicht als Erfolg. Ein synchroner Sendeaufruf-Fehler räumt die wartende
Transaktion auf. Pattern-Senden und Wiederherstellen warten auf 0x23
mit dem konservativen Pattern-Zeitlimit, danach folgt vollständiges
Rücklesen. SimDevice erzeugt die gemessene Pattern-Bestätigung ebenfalls.

**Gemessen in SimDevice:** Mit der eigenen SYSTEM.VSB auf Kanal 9 wurden
die Produktionssignaturen geprüft, die geladene Datei identifiziert und
eine geschützte MFX-Menüänderung sowie Undo erfolgreich ausgeführt.
Die produktiven Editor-Schreibprüfungen wurden nicht durch einen neuen
Menüänderungstest am echten Gerät ersetzt; reale Schreibtests in diesem
Abschnitt betreffen ausschließlich unveränderte MFX-Tabellendaten.
