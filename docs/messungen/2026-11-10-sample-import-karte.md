# WAV-Import in die Sample-Datei

Die Gegenprobe zur [bisherigen Menüfunktion](2026-11-09-sample-import-menue.md)
läuft mit erzeugten WAVs und erzeugten Karteninhalten auf dem roten Sampler.
Die Karte bleibt im bestehenden Format `e2sSample.all`. Der Synth ist
nicht Teil der Prüfung.

## Gemessen im Emulator

Beim Menüimport auf einen freien Slot wird die WAV im Kartenformat angehängt.
Die Prüfung vergleicht den gesamten bisherigen Dateiteil: Nur die vier Bytes
des neuen Slot-Offsets ändern sich. Die neuen PCM-Bytes stimmen exakt mit der
WAV überein. Beim Import selbst wird kein DSP-Platz reserviert und die PCM
bleiben unverändert. Der Name ist über die native Namensabfrage sichtbar.
Bei der anschließenden Auswahl kommen die neuen PCM in den DSP.

Ohne vorhandene Datei legt derselbe Menüpfad die erste Bibliothek an, sofern
der Sample-Ordner vorhanden ist. Ist der vorgeschlagene Slot auf der Karte
belegt, wird der Import abgewiesen, auch wenn der DSP den Slot gerade nicht
hält. Die Bibliothek bleibt bytegleich.

Die große Stock-Gegenprobe wächst von 54.562.848 auf 54.604.080 Bytes.
Für den Import steht der nächste freie DSP-Platz im Modell am Ende des
Nutzerbereichs (`0x01C65EC0`); der Zeiger bleibt während des Imports dort.
Die Audiodaten sind nach einem Neustart erneut bytegleich. Das Modell
belegt den dateibasierten Import ohne DSP-Reservierung. Es misst keinen
tatsächlich gefüllten DSP und keine Echtzeit auf der Karte.

Der Test mit einem nachgebildeten Aufnahmezustand lässt den WAV-Import
abbrechen. In der Gegenrichtung verhindert ein belegter Importbesitz den
Einstieg in den nativen Aufnahmestart. Beides prüft die CPU-Pfade; der
Emulator zeichnet keinen Ton auf.

## Hergeleitet

Der Aufruf bei `0xC0038DE0` läuft in der nativen Befehlsaufgabe. Der
Startpfad hält den Bibliothekspfad schon bei der Existenzprüfung
`0xC0038D50` fest. Der Besitz für Import und Aufnahmestart wird geprüft
und gesetzt, bevor einer der Pfade unterbrochen werden kann. Import prüft
außerdem den nativen Transportzustand und beginnt nur bei STOP ohne
Aufnahmeergebnis. Start mit gedrückter EXIT-Taste behält den nativen Weg.

Die Slotprüfung benutzt zunächst den geprüften Kartenindex. Der Schreiber
prüft den Zielslot zusätzlich gegen den beim Schreiben gelesenen Index.
Er aktualisiert den Index erst nach dem Schreiben und der Prüfung des
neuen Blocks. Ein Fehler beim Schließen der WAV bleibt ein Fehler, auch
wenn der neue Slot bereits auf der Karte steht und die erneute
Katalogprüfung ihn danach lesen kann. Es gibt keine Flash-Schreibzugriffe
durch den neuen Import.

## Offen

Klang, Live-Wechsel, tatsächliche Kartenlaufzeiten und Schreibverhalten
bei Stromverlust brauchen eine getrennte Prüfung am Gerät. Die
Standardauswahl des Gerätemenüs kann einen belegten Slot vorschlagen;
für den Import muss ein freier Slot gewählt werden. Ein Überschreiben
über dieses Menü ist nicht freigegeben.
