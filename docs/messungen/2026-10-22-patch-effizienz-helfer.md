# Gemeinsame CRC, Speicherfüllung und kombinierte Rechenbefehle

Status: **offline untersucht und im Emulator nativ gemessen**.
Keine Gerätemessung und keine Freigabe einer Test-Firmware.

## Vergleich und Umfang

Vergleichsbasis ist der geprüfte Stand des
[verkleinerten SysEx-Puffers](2026-10-21-patch-effizienz-sysex.md),
Firmwarequellen `7fbd90e6c5287bbafe2126a7dbadd7e3b798ae2b`.
Die untersuchten Änderungen stehen in
`615a85d3a6c89e9a1d9fe9c55ebdf6482df5cade` einschließlich des vorherigen
Rechenbefehls-Commits. Bereits gemessene Gewinne von Decoder, Pad-Geometrie
und Multiplikation werden hier nicht erneut zugerechnet.

Die vollständigen Prüfungen wurden vor den beiden Commits ausgeführt.
Anschließend stimmen alle 273 überwachten Quellhashes mit den eingecheckten
Dateien und sämtliche sechs Firmwarehashes mit den geprüften Dateien überein.
Die ursprünglichen Erfassungsdaten bleiben unverändert; die gesonderte
Zuordnung zum Commit hält diesen Ablauf fest.

Die [Messdatei](2026-10-22-patch-effizienz-helfer-zahlen.json) enthält
Hashwerte, Größen und Befehlszahlen. Die Zahlen zählen ausgeführte ARM-Befehle.
Sie messen weder ARM926-Taktzyklen noch echte SD-Übertragungszeiten.

## A: Originale und eigene Patches untersuchen

Alle drei Originale wurden vollständig als jeweils 2 MiB Nutzlast mit
524.288 ausgerichteten ARM-Wörtern durchsucht. Der Scan liefert Kandidaten,
keinen Nachweis, dass jedes decodierte Wort tatsächlich Code ist.

| Build | Kleine Rückwärtsschleifen | Exakt gleiche begrenzte Funktionsgruppen |
|---|---:|---:|
| Hacktribe | 810 | 49 |
| Korg rot | 796 | 46 |
| Synth | 697 | 41 |

Ein strenger, mit Positiv- und Negativfällen geprüfter Sucher findet keine
weitere passende Additions-/Verschiebeschleife für eine Multiplikation.
Andere Implementierungen sind damit nicht ausgeschlossen. Der begrenzte
Kontrollflussgraph ab Reset und den Dateisystem-Einstiegen umfasst je Build
5.667 Wörter und zwölf ungeklärte indirekte Sprungstellen. Er enthält bereits
native MUL-, MLA- und SMULL-Befehle.

**Verworfen:** Originalfunktionen allein wegen identischer Bytes entfernen.
Indirekte Aufrufer und adressabhängige Referenzen sind nicht vollständig
geklärt. Langprodukte bleiben erhalten, wenn ihre oberen Ergebnisbits oder
Überträge gebraucht werden. Kein Originalcode wurde für diese Untersuchung
entfernt oder ersetzt.

## B: CRC innerhalb derselben Laufzeit gemeinsam nutzen

GSCR-Prüfung und Kartenlader teilen sich jetzt eine native Streaming-CRC.
Der Aufrufer verwaltet Anfangswert und abschließende Invertierung. Die Routine
verarbeitet je Schleifendurchlauf vier Bits ohne Nachschlagetabelle.
Der Kartenadapter benötigt acht Byte vorübergehenden Stack.

Für 32 KiB sinkt die Befehlszahl der CRC von 1.245.189 auf 851.973,
also um 31,58 Prozent. VM und Kartenadapter zusammen werden acht Byte kleiner.
Bei leeren Kartenabschnitten entstehen wenige zusätzliche Aufrufbefehle.
Ergebnisse, Fehlerprüfungen und Streaming-Zustand bleiben gleich.

Eine Zusammenlegung mit den getrennt auswählbaren SysEx-, Startbild- und
MFX-Patches wurde nicht übernommen. Sie würde eine neue Abhängigkeit zwischen
binären Besitzern schaffen. Der vorhandene SysEx-Kopierhelfer arbeitet bereits
wortweise. Korgs Füllfunktion hat einen anderen Registervertrag als die VM.
Ein direkter Austausch wäre deshalb falsch.

## C: Ausgerichtete Speicherfüllung

Die eigene Füllroutine behandelt kurze Abschnitte weiterhin byteweise.
Ab 16 Byte richtet sie den Anfang aus, schreibt ganze Wörter und behandelt
die Restbytes einzeln. Alle bisherigen Register- und Flag-Ergebnisse bleiben
gleich. Zugriffe gelten ausschließlich eigenen RAM-Puffern, keinen
Geräteregistern.

| Ausgerichteter Puffer | Vorher, ARM-Befehle | Nachher, ARM-Befehle | Weniger |
|---|---:|---:|---:|
| 160 KiB | 491.523 | 92.177 | 81,25 % |

Die ausdrücklich angenommene Grenze beträgt **112 Byte zusätzlichen Code**,
keinen zusätzlichen reservierten RAM-Bereich und vier Byte vorübergehenden
Stack. Leere Füllungen bleiben gleich teuer; nichtleere Füllungen unter
16 Byte brauchen zwei zusätzliche Befehle. Die tatsächlich gemessenen
Laufzeit-Puffer sind deutlich größer.

Die elf Preset-Blöcke kopieren beim nativen Laden jeweils 176 bis 3.772 Byte,
zusammen rund 19,7 KiB. Die kopierten Bytes stimmen mit den Eingängen überein.
Dieser lokale Byte-Kopierpfad bleibt erhalten. Ein Wortpfad würde zusätzliche
Ausrichtungs- und Restbehandlung sowie einen eigenen Größen- und Vertragsnachweis
brauchen. Der getrennt auswählbare SysEx-Kopierhelfer ist dafür keine gemeinsame
Abhängigkeit. Die Freigabe für zusätzlichen Code gilt für die geprüfte Füllroutine.

Ein gesonderter STM-Prototyp ist vier Byte kleiner und zählt für denselben
großen Puffer 51.220 Befehle. Er benötigt aber 16 Byte Stack und fasst vier
Speicherzugriffe in einem gezählten Befehl zusammen. Ein entsprechender
Taktzeitgewinn ist damit nicht belegt. Er wurde nicht in die Firmware
übernommen und hat keine vollständige Satzprüfung erhalten.

## D: Multiplikation und Addition verbinden

Sieben exakt passende Stellen nutzen MLA: drei im TAP-Patch und vier beim
Ladebild. Pro Ausführung entfällt ein ARM-Befehl und pro Stelle vier Byte Code.
Das spart auf den Samplern 28 Byte, beim Synth ohne Ladebild zwölf Byte.

2.250 feste und 7.002 variable Rechenfälle vergleichen alle Register und Flags
mit der bisherigen Folge. Darunter sind negative Werte und 32-Bit-Überläufe.
Operationen mit benötigten Zwischenergebnissen oder anderer 64-Bit-Semantik
bleiben erhalten. VM-Befehlsbudget, Division und Spieltempo werden nicht geändert.

## Sample-Import und Export getrennt messen

Beide Sampler wurden mit eigenen 16-Bit-Mono-WAVs bei 48 kHz geprüft:
512 und 32.768 Frames, entsprechend 1 und 64 KiB Audiodaten. Je Größe liefen
Startladen, Import und Export vor und nach der Änderung. Das sind zwölf
Vorher/Nachher-Paare mit 24 gültigen Firmwareläufen. Andere Sample-Formate,
große Sample-Sammlungen und echte Kartenzeiten sind damit nicht vermessen.

Beim Import laufen je Datei zehn Leseaufrufe und acht Dateisprünge. Gelesen
werden 2.264 beziehungsweise 66.776 Byte. Korgs bestehende Füllroutine leert
einmal 1.172 Byte Metadaten. Die neue VM-Füllroutine wird weder beim Import
noch beim Export aufgerufen. Ein schnellerer Sample-Import oder Export ist
mit dieser Änderung nicht belegt. Weniger Arbeit im Startfenster entsteht
auch durch die Initialisierung der Plugin-Laufzeit und ist kein Nachweis
für einen schnelleren Sample-Transfer.

**Gemessen:** Metadaten, Dateiaufrufe mit Ergebnissen, SD-Kommandos und
exportierte Dateien stimmen in allen zwölf Vergleichen überein. Die Zählung
umfasst ganze Menüfenster; Dateifunktions-Abschnitte enthalten auch
Treiber- und Scheduler-Arbeit. Echte SD-Wartezeit lässt sich daraus nicht
isolieren, weil das Modell sie nicht vollständig nachbildet.

**Modellgrenze:** Zum DSP geschriebene Sample-Audiodaten werden im Emulator
nicht behalten. Beim Export liefert dieses Modell Null-Audio. Die erste
Prüfung gegen das Eingangs-Audio schlug deshalb auf beiden Firmwareständen
fehl. Der korrigierte Versuch verlangt die bekannte Null-Ausgabe mit genauer
Länge, richtige Dateistruktur und identische Exporthashes vor/nachher.
Er belegt keine Audioqualität und ersetzt keinen Gerätetest. Die ursprünglichen
Diagnoseprotokolle bleiben erhalten; der Produktcode des Emulators und die
Firmwareprüfungen wurden dafür nicht geändert.

## Gemeinsame Wirkung und Prüfungen

Das native Laden und Prüfen aller elf Preset-Plugins benötigt je Build
3.404.110 statt 2.113.220 Befehle, also 37,92 Prozent weniger.
Diese Messung beginnt mit den Plugin-Bytes im Speicher und enthält keinen
SD-Zugriff. App-Bilder und Zustände stimmen mit der Vergleichsbasis überein.
Die größte gemessene Mehrarbeit einer übrigen Szene bleibt unter 0,21 Prozent
und damit innerhalb der Grenze von einem Prozent.

| Build | Vollständige Prüfungen | Nettocode zusätzlich | RAM zusätzlich | Frei danach | Größte Lücke |
|---|---:|---:|---:|---:|---:|
| Hacktribe | 459/459 | 76 Byte | 0 | 55,34 KiB | 19 KiB |
| Korg rot | 484/484 | 76 Byte | 0 | 55,14 KiB | 19 KiB |
| Synth | 363/363 | 92 Byte | 0 | 454,88 KiB | 322,26 KiB |

Die Profilmatrix umfasst 18 unabhängige Starts und 126 Messfenster mit
1.350 abgeschlossenen App-Bildern und 216 Vorlaufbildern. Native
SysEx-Kommandos, Ergebnisse, Dateizugriffe und Befehlszahlen bleiben gleich.
Die bereits dokumentierten Grenzen des USB-Modells gelten weiter.

| Abschließende Suite | Bestanden | Fehler | Ausgelassen |
|---|---:|---:|---:|
| Native Helfer | 8 | 0 | 0 |
| Unit-Suite | 962 | 0 | 143 |
| Browser-Suite | 164 | 0 | 1 |
| Dokumentationsprüfung | 9 | 0 | 0 |

Die nativen Prüfungen enthalten zusätzlich 120 CRC-Vektoren, aufgeteilte und
leere CRC-Abschnitte, 144 Kartenadapter-Vektoren in drei Speicherlayouts sowie
752 Füllfälle. Sie prüfen Ausrichtung, Restbytes, Wächterbereiche, Register,
Flags und Stack-Schreibgrenzen. Alle Pflichtfälle der Firmwareprüfungen laufen.
Die vorgesehenen optionalen Auslassungen der Gesamtsuiten bleiben unverändert.
Schwere Testgruppen liefen nacheinander, mit höchstens zwei Arbeitern.

Die gemeinsame Codeprüfung und die Geräteabnahme in Phase 6 bleiben offen.
Kein Gerät wurde angesprochen, keine SD-Karte beschrieben und keine Firmware
veröffentlicht. Originale, VSBs, Rohprofile und Befehlsprotokolle liegen
außerhalb des Repositorys im privaten Messpaket
BLECH-Performance-ABCD-2026-10-22.
