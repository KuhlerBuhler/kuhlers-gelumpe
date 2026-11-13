# Sample-Swap: EXIT und Part-Auswahl bei Fehlern

Stand: 29.10.2026. Beleg: `measure:2026-10-29/sample-swap-exit-parts`.
Fortsetzung der [Pufferkorrektur](2026-10-29-sample-swap-puffer.md).
Alle Samples, Journale und Pattern der Versuche sind selbst erzeugt.

## Gemessen vor der Korrektur

Die zusätzliche ARM-Prüfung zeigt acht fehlschlagende Teilfälle. Zwei
betreffen die EXIT-Umgehung der Wiederherstellung. Sechs betreffen die
native Part-Fortsetzung im Kartenfehlermodus bei intaktem DSP: Werkssample,
bereits geladenes Nutzersample und leere Auswahl werden an beiden Haken
unnötig verweigert.

Ein eigener nativer Versuch mit gehaltenem EXIT und beschädigtem Journal
erreicht im bisherigen Ablauf Modus 2. Das Sample wird nicht normal
geladen, obwohl EXIT die Swap-Erweiterung umgehen soll. Die Sammlung und
das Journal bleiben unverändert.

Ein zweiter Fehlerfall lässt EXIT genau beim nativen Öffnen der Sammlung
los. Eine erste frühe EXIT-Prüfung ohne festgehaltene Entscheidung erreicht
dadurch Modus 1, obwohl sie die Wiederherstellung übersprungen hat. Das
beschädigte Journal ist dabei noch vorhanden. Der neue ARM-Fall und der
native Versuch reproduzieren diesen zusätzlichen Fehler.

## Hergeleitet: EXIT vor der Wiederherstellung entscheiden

Der Lader prüft den bestehenden DSP-Fehler und schließt einen bereits
offenen Swap-Leser weiterhin vor einem neuen Zugriff. Nach der begrenzten
Pfadprüfung entscheidet er über EXIT, bevor er die Journal-Wiederherstellung
aufruft. Gewähltes EXIT führt zum nativen Öffnen und bleibt bis zur
Rückgabe in Modus 0, auch wenn die Taste währenddessen losgelassen wird.

Der Rückweg überspringt weder einen fehlgeschlagenen Leserabschluss noch
einen gespeicherten DSP-Fehler. Bei einem späteren Bibliotheksaufruf kann
das Schließen des alten Lesers deshalb weiterhin nötig sein. Das ist
keine Zusage, dass jeder warme Aufruf ohne Dateioperation auskommt.

## Hergeleitet: Kartenfehler und DSP-Fehler unterscheiden

Die Part-Prüfung behandelt Modus 1 und Modus 2 nach denselben Regeln.
Ein gesetzter DSP-Fehler verweigert die native Aktualisierung vor jeder
Auswahl. Bei intaktem DSP bleiben Werkssamples, leere Plätze und bereits
geladene Nutzersamples nach den bisherigen Prüfungen nutzbar. Ein noch
nicht geladener indizierter Nutzerplatz bleibt gesperrt.

Die Änderung betrifft die beiden Part-Haken. Sie ersetzt weder die noch
fehlende Begrenzung aller nativen DSP-Wartewege noch die kontrollierte
Abbruchbehandlung eines dauerhaft unerfüllbaren Patternwechsels.

## Gemessen nach der Korrektur

- Alle 77 ARM-Tests bestehen. Die Matrix prüft beide Part-Haken,
  gesunde und gestörte DSP-Verbindung sowie die Auswahl in Modus 1 und 2.
- Die EXIT-Prüfung bestätigt auch das Loslassen während des Öffnens,
  erfolgreiches und fehlgeschlagenes Schließen eines alten Lesers sowie
  den weiterhin gespeicherten DSP-Fehler.
- Stock und Hacktribe bestehen jeweils acht native Integritätsprüfungen.
  Dazu gehören die bisherigen Cache- und Veröffentlichungsfälle und die
  neuen EXIT- und Part-Fehlerfälle.
- Mit beschädigtem Journal bleibt EXIT in Modus 0. Das erzeugte Sample
  ist geladen, sein Name stimmt und die Datei samt Journal bleibt erhalten.
  Das gilt auch beim Loslassen von EXIT während des Dateiöffnens. Für
  diesen Versuch liegt die Sammlung ausdrücklich über dem verkleinerten
  Swap-Schwellwert; eine kleine Datei würde den Fehler nicht erkennen.
- Im Kartenfehlermodus führt die echte native Part-Aktualisierung die
  Auswahl des Werksplatzes 400 und des geladenen Nutzerplatzes 500 aus.
  Die tatsächliche Part-Auswahl folgt dem gewünschten Wert. Nutzerplatz
  501 ist im Versuch nicht geladen und wird verweigert. Bei gesetztem
  DSP-Fehler werden alle drei Ziele verweigert, die tatsächliche Auswahl
  bleibt erhalten und der Aufruf schreibt nichts an den DSP-Port.

Der native Namensvergleich liest das bereits gemessene Namensfeld, nicht
die festen Kopfdaten am Beginn des Namensrecords. Die anfängliche falsche
Feldposition im neuen Prüffall wurde korrigiert, bevor ein bestandener
nativer Nachweis festgehalten wurde.

Die Fälle liegen in [test_sample_swap.py](../../tools/patch/test_sample_swap.py)
und [swap_integrity_cases.py](../../tools/emu/swap_integrity_cases.py).

## Offen

Die vollständigen Patch-, Unit- und Browserprüfungen des neuen Gesamtstands
stehen noch aus. Die grünen vollständigen Läufe vor diesen Ergänzungen
gehören zum vorherigen Stand mit alleiniger Pufferkorrektur.

Der kontrollierte Abbruch unmöglicher Ziele, verlorene Ladeaufträge,
die native Timeout-Einbindung und der vollständige dauerhafte Speicherweg
bleiben offen. Klang, reale Stimmen und DMA werden nicht nachgebildet.
Am Gerät wurde für diese Korrektur nichts ausgeführt.
