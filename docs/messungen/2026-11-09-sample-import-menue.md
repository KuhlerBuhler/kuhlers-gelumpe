# WAV-Import: Was das Gerätemenü an den Sample-Lader übergibt

Gegenprobe im Emulator mit erzeugter WAV und erzeugter Sample-Sammlung. Der
rote Sampler läuft mit vollständigem BLECH-Patchsatz auf Stock 2.02 und
Hacktribe. Der [Speicherdienst](2026-10-27-sample-store.md) und der Importbefehl des Menüs
sind noch getrennte Wege.

## Gemessen

- `Menü -> DATA UTILITY -> IMPORT SAMPLE` ruft bei `0xC0038DE0` den
  WAV-Import bei `0xC003644C` auf. Der Befehl läuft in Task `0xC06A2564`.
  In `r0` steht `SD:/imp.wav`, in `r1` der nullbasierte Zielslot. Ohne
  Drehen am Zielwähler kommt 500 an; zwei Schritte weiter kommt 502 an.
- Sind die Slots 501 bis 506 in der Datei belegt und nur Slot 506 im DSP,
  schlägt das Menü trotzdem Slot 501 vor. Die Übernahme ruft den Import
  mit `r1=500` auf. Der native Weg reserviert DSP-Platz und lädt 40.000
  PCM-Bytes. Die Datei bleibt dabei bytegleich.
- In einer weiteren Gegenprobe ist Slot 503 auch auf der Karte frei. Der
  Import meldet am Rückkehrpunkt `0xC0038DE4` Erfolg und legt das Sample
  im DSP an. Der Name erscheint, aber auf der Karte steht weiterhin
  der alte Index ohne den neuen Slot. Das Verhalten tritt auf Stock und
  Hacktribe auf.
- Ohne `.all`, bei vorhandenem Ordner, erreicht der Startbefehl die
  Existenzprüfung bei `0xC0038D50` mit
  `SD:KORG/blechtribe/Sample/e2sSample.all`. Der Lader bei
  `0xC00364F0` läuft nicht. Die 128 Pfadbytes des Swap-Zustands bleiben
  beim Startwert `0xFF`.

Die Gegenprobe für das gewünschte Verhalten steht in
[`tools/emu/sample_import_menu_cases.py`](../../tools/emu/sample_import_menu_cases.py).
Sie verlangt, dass nur der Indexeintrag des gewählten Slots und der neue
Block geschrieben werden, der Name ohne DSP-Reservierung verfügbar ist und
die später angeforderten DSP-Bytes exakt der erzeugten WAV entsprechen.
Der bisherige Import scheitert an dieser Prüfung.

## Gemessen: Fehler beim Schließen der WAV-Quelle

Der Speicherdienst hängt die erzeugte WAV an die Bibliothek an. Die Gegenprobe
lässt anschließend nur das Schließen der WAV-Quelle einmal fehlschlagen.
Vor der Korrektur meldet der Import zwar Fehler 4, gibt das gemeinsame
Dateiobjekt aber als frei aus. Ein zweiter Import verwendet es und ändert die
Bibliothek. Die Korrektur hält das Dateiobjekt bis zur bestätigten Schließung
gesperrt. Der zweite Import wird mit Fehler 4 abgewiesen, der gespeicherte
Eintrag bleibt bytegleich, und die Katalogprüfung schließt die alte Quelle
beim Wiederholungsversuch. Der ursprüngliche Fehler bleibt als Fehler gemeldet.

## Gemessen: Abgelehnter Import und Swap-Modus

Stock und Hacktribe lehnen über das Menü eine erzeugte WAV mit ungültigem
Audioformat ab. Bei einer kleinen Bibliothek bleibt die Datei bytegleich.
Ohne Bibliothek entsteht keine Datei. In beiden Fällen bleibt der
reguläre Modus aktiv und der Dateibesitz wird freigegeben. Die
[DSP-Auswahl nach einem Quellfehler](#gemessen-fehler-beim-schließen-der-wav-quelle)
liefert die Gegenprobe: Ein bereits auf der Karte bestätigter neuer Slot
aktiviert Swap trotz der Fehlermeldung und bleibt bis zur Auswahl ungeladen.

Im ARM-Modell bleibt auch ein bereits aktiver Swap nach einer Ablehnung
aktiv. Ein vorher vorhandener, plötzlich fehlender Index oder ein
gemeldeter Erfolg ohne bestätigten Zieleintrag hält den Wechsel gesperrt.

## Hergeleitet

Der numerische Zielslot am Import-Einstieg unterscheidet einen Vorschlag des
Menüs nicht von einer absichtlichen Auswahl. Der Dateipfad muss deshalb den
Zielslot gegen den geprüften Kartenindex prüfen. Das Überschreiben eines
belegten Slots braucht eine nachgewiesene Bestätigung; eine DSP-freie Zeile
reicht dafür nicht. Die Pfadübergabe für eine neue Bibliothek muss auch dann
greifen, wenn der Gesamtlader wegen der fehlenden Datei gar nicht startet.

## Offen in diesem Stand

Der Kartenimport im Menü ist noch nicht angeschlossen. Vor dem Schreiben
muss auch die Überschneidung mit der nativen Aufnahmeveröffentlichung
ausgeschlossen werden. Der beobachtete Task des WAV-Imports allein beweist
das nicht. Kartenfehler, eine erste Bibliothek ohne vorhandene Datei sowie
die genaue PCM beim späteren Anwählen werden gegen den neuen Pfad geprüft,
sobald dieser eingebaut ist. Das echte Gerät war an diesen Proben nicht beteiligt.

Der [Anschluss am Folgetag](2026-11-10-sample-import-karte.md) prüft den
Kartenimport im Gerätemenü.
