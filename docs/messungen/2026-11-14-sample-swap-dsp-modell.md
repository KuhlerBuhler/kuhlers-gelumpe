# Sample Swap mit dem DSP-Modell prüfen

## Gemessen im Emulator

Geprüft wurde der unveränderte Swap-Stand `99ebf44c` auf der Grundlage von
1.4.5 mit dem Host-Port-Modell aus dem Entwicklungsstand `b0be0c50`.
Der ARM-Emulatorkern ist in beiden Ständen bytegleich. Das neue Modell wurde
vor dem Einschalten jeder Prüfmaschine angeschlossen. Start- und
Ergebniscaches waren ausgeschaltet. Die Karten, Patterns und Samples der
Swap-Fälle wurden erzeugt. Es gab keinen Gerätezugriff.

Nach den unten beschriebenen Korrekturen des Prüfaufbaus bestehen:

| Prüfung | Stock | Hacktribe |
|---|---:|---:|
| Swap-Testgruppen | 40 | 40 |
| Bestehende Swap-Prüfungen | 156 | 156 |
| Zusätzliche Modellprüfungen | 136 | 136 |
| Stimmenadresse nach tatsächlicher Auslagerung | 13 | 13 |
| Start, Pad, PLAY/STOP und Host-Protokoll | 4 | 4 |

Die 26 Modulprüfungen des DSP-Modells bestehen ebenfalls. Eine unabhängige
Stock-Gegenprobe umfasst sechs Fälle: Original, nativer Feature-Modus und
aktiver Swap, jeweils mit einem eingebauten Klang und einem User-Sample.
Alle 16 Vergleiche dieser Gegenprobe bestehen.

Die bestehenden Fälle prüfen Start, große Bibliotheken, bedarfsgesteuertes
Nachladen, Pattern- und Chain-Wechsel, RAM-Vorausladen, Aliase, Namen,
Import, WRITE, Löschen, Wiederanlauf und absichtliche Fehler. Die zusätzlichen
Prüfungen lesen das Speicherbild des neuen Modells. Sie vergleichen PCM mit
den erzeugten Wellenformen und dem bisherigen Schreibmitschnitt. Positive
Fälle prüfen außerdem Übertragungsgrenzen, Modellfehler und vollständige
Rahmen. Endet eine Beobachtung mitten in einem Rahmen, laufen höchstens
200 ms Gerätezeit weiter; ein Rahmen wird nicht künstlich abgeschlossen.

### Zwei Annahmen im Prüfaufbau

Der native Lesetest `native_read_ready_unmasked` hinterlegt seine Testwörter
bisher direkt in `machine.dsp_mem`. Das neue Modell kennt dort bereits das
hochgeladene Sample und liefert dieses zurück. Im ersten Lauf scheitert
deshalb der erwartete PCM-Vergleich, während Ressourcenfreigabe, Stack und
Fehlerzustand korrekt bleiben. Im Wiederholungslauf werden die vorhandenen
Testwörter auch im Speicherbild des neuen Modells hinterlegt. Alle 23
nativen Gegenproben bestehen danach auf beiden roten Firmwarefassungen.

Die Namensprüfung enthält absichtlich eine Karte mit vollständig geleertem
Slot-Index. Eine erste zusätzliche Prüfung verlangte auch dort mindestens
ein residentes PCM. Die richtige Gegenprobe verlangt keine Sample-Uploads.
Diese strengere Prüfung des leeren Falls besteht zusammen mit den drei
bestehenden Namensprüfungen auf beiden Fassungen. Die ersten Rohbefunde
bleiben getrennt von diesen Wiederholungen erhalten.

### Sample-Adresse in der tatsächlichen Stimme

Ein zusätzlicher Fall begrenzt den DSP-Platz auf 6144 Byte. Sample 500
belegt zunächst 4000 Byte. Danach wird über das Sample-Rad 501 mit 2000 Byte
aktiviert. Für 502 mit 4000 Byte muss das inzwischen unbenutzte Sample 500
weichen. Sample 501 bleibt geschützt. Sample 502 landet wieder am Anfang
des Sample-Bereichs.

Das PCM dort stimmt mit Sample 502 überein. Nach dem tatsächlichen
Pad-Anschlag enthält die neue Stimme dessen DSP-Adresse in Wort 10. Die
Sample-Felder stimmen mit einer getrennten Referenz überein, die direkt mit
502 startet. Der beobachtete Zielzeiger wird erst nach vorhandener Residency
an den DSP übertragen.

Die statische Part-Vorlage enthält noch nicht den vollständigen
Sample-Deskriptor. Maßgeblich ist hier der Stimmenblock nach dem Anschlag.
Auch die Gegenprobe mit Korgs Original zeigt dieses Verhalten. Nach
Berücksichtigung der tatsächlichen Sample-Basis stimmen die geprüften
Stimmenfelder von Original, nativem Feature-Modus und aktivem Swap überein.

Bei User-One-Shots bleibt das Modell-Gate nach Loslassen und STOP teilweise
offen, ebenso auf dem Original. Das belegt keine Regression durch Swap.
Das natürliche Ende der Stimme wird damit weiterhin nicht nachgebildet.

## Hergeleitet

Das angeschlossene `tools/emu/dsp_model.py` ist ein Host-Port-Modell. Es
wertet bekannte Nachrichten aus, hält das von der CPU geschriebene
DSP-Speicherbild und beantwortet daraus die unterstützten Lesezugriffe.
Das ist stärker als die frühere Nullantwort, führt aber das DSP-Programm
nicht aus. Die Firmwarekopien wurden für diese Prüfung nicht verändert.

Die Antwort auf DSP-Steuerzugriffe bleibt im ARM-Emulator konstant
`0x85`. Reale BUSY-Zeiten, Durchsatz und die Reaktion des tatsächlichen DSP
auf einen Timeout sind dadurch nicht neu gemessen. Die bestehenden
Timeout-Gegenproben erzwingen ihre Wartezustände weiterhin ausdrücklich.

Das Modell setzt keine allgemeine Kapazitätsgrenze für DSP-SDRAM durch.
Die Zusatzprüfungen kontrollieren deshalb die beobachteten Sample-Uploads
und die vorhandenen Swap-Fälle kontrollieren die residenten Bereiche.
DSP-interne Schreibzugriffe durch laufende Effekte werden nicht ausgeführt.

Der getrennte Blackfin-Simulator und seine Wiedergabe von Aufzeichnungen
sind damit nicht automatisch Teil des ARM-Emulators. Die Rückkopplung seiner
Antworten ist im geprüften Entwicklungsstand nicht gebaut.

## Offen

- Klang und natürliche Ausklänge am Gerät.
- Die vom DSP erzeugten PCM bei Aufnahme und Resampling. Die geprüften
  Aufnahmefälle stellen diese Daten selbst bereit und prüfen CPU- und
  Kartenwege.
- Echte DSP-BUSY-Zeiten, Durchsatz und Fehlerreaktionen.
- Vollständiger RAM- und DMA-Besitz sowie DSP-interne Speicherüberschneidungen.
- Die dauerhafte Einbindung des neuen Modells in die Swap-Prüffälle. Diese
  Messung hat das Modell in einem getrennten Prüflauf angeschlossen.

Die Modellprüfung findet keinen neuen Firmwarefehler. Sie ersetzt weder
die Geräteabnahme noch eine Releasefreigabe. Die allgemeine Prüfung des
Features bleibt deshalb offen.

Die früheren [Unit-, Browser- und Integrationsprüfungen](2026-11-12-native-dsp-bibliotheksbindung.md)
wurden hier nicht erneut ausgeführt. App- und Firmwarequellen bleiben
unverändert; neu ist diese Messung mit dem DSP-Modell.
