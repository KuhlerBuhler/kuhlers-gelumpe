# Idee 103: Rettung, Ablauf in der richtigen Reihenfolge

Stand: Durchgang der Seite "Rettung" im Browser (Desktop und Handy), Vergleich mit [Rettung](../rettung.md) und den Fällen aus dem Hilfekanal bis 8. November. Der neue Ablauf ist gebaut und im Browsertest geprüft, am Gerät nichts. Zurück zu den [Ideen](../ideen.md).

Die Seite fragte Dinge doppelt, hängte einen Dateischritt als Knopf zwischen Antworten, ließ "Ist gespeichert" ohne Datei zu, schickte Geräte, die nicht bis ins Menü starten, ins Menü und endete bei "Klappt nicht" mit "Probier nichts auf eigene Faust" und einem englischen Link. Die Reihenfolge am Gerät ist: Farbe, was gerade läuft, welche Datei, welcher Ordner, Prüfung der Karte, Update.

## Was falsch war, je Weg

Verlauf: jede Zeile Befund, Beleg als gemessen (Seite im Browser gesehen), gelesen (Daten und Code), offen.

| Weg | Befund | Beleg |
|---|---|---|
| alle | Die Farbe wurde je Weg an anderer Stelle gefragt (`color:starts`, `color:update`, `back:color`, `samples:way`), danach die Firmware als "Gerät und Firmware" mit Produktnamen, ohne "Weiß ich nicht" | gemessen |
| alle | Der Ordner stand als Textpfad, "hacktribe" im Pfad lasen viele als "ich will Hacktribe", dabei gilt der Ordner der Firmware, die gerade läuft | Hilfekanal, gelesen |
| alle | "Liegt drauf" stand gleichwertig neben der Prüfung der Karte, und die Prüfung fehlte bei den Wegen über das Menü (`folder:*`) ganz | gelesen |
| alle | Das erste "Klappt nicht" führte direkt zum Melden, ohne die Karte noch einmal zu prüfen | gemessen |
| alle | Der Weg setzte einen Computer mit Kartenleser voraus, das stand erst mitten im Weg; am Handy gab der Knopf "SD-Karte wählen" keine Rückmeldung | gemessen, Handy |
| Sie startet, aber etwas spinnt | Nach dem Rückspielen kein Wort zu Patterns und Samples, kein Schritt zur Sicherung | gemessen |
| Sie startet, aber etwas spinnt | "Samples klingen falsch" hatte hier keinen Einstieg | gemessen |
| Gar nichts | Der Notausgang mit EXIT beim Einschalten kam in diesem Weg nie vor, "Jetzt geht sie" führte zu "Drauf ist jetzt die Firmware, die du zurückgespielt hast", obwohl keine Datei im Spiel war | gemessen |
| Gar nichts | "Immer noch nichts" endete mit "Probier nichts auf eigene Faust" und dem Link zur englischen Debrick-Anleitung, ohne Kontakt | gemessen |
| 00 | Nach "Es bleibt bei 00" und der Karte fehlte das Flachbandkabel, das die Doku nennt; "Klappt nicht" endete bei "Mist" | gelesen |
| SOFTWARE UPDATE, press ENTER | Keine Antwort für "Es kommt keine Update-Frage". Hacktribe und BLECHTRIBE nehmen beide Gerätekennungen an und fragen fast nie, dort ist die Karte nicht der Weg | gelesen (Doku, Emulator) |
| Invalid File | Beim Weg über Korgs Datei wurden Farbe und Hacktribe gefragt, danach die Firmware ein zweites Mal; "Datei neu kopieren" fehlte, obwohl es bei jemandem half | gemessen, Hilfekanal |
| Invalid File, blau mit Hacktribe | Text mit "Sampler-Code", "Kopf", "zwei Bytes", die Datei kam über einen Knopf, der wie eine Antwort aussah, "Ist gespeichert" ging ohne Datei | gemessen |
| No File, Menü | Vier Absätze Checkliste vor der Frage, dieselben Hinweise standen noch einmal im Kartenschritt; "Wieder No File" führte ohne Prüfung zum Melden | gemessen |
| Samples | Die Seite fragte erst die Farbe, dann die Firmware, dann noch einmal, was läuft; der Weg für eine blaue nur mit Hacktribe stand hinter dem Patcher-Text, in falscher Reihenfolge; Ende "ohne BLECHTRIBE" war falsch, wenn BLECHTRIBE aufgespielt wird | gemessen |
| Zurück zu Korgs Original | Der Download kam, bevor klar war, ob Korgs Datei oder die mit dem Sampler-Kopf gebraucht wird; die Seite fragte die Firmware bis zu dreimal | gemessen |
| Download | Link auf die Produktseite statt auf die Seite der Datei, keine Version, kein Dateiname | gelesen |
| Datei | Der Dateischritt war ein Knopf, kein Upload | gemessen |

## Vorher und nachher je Weg

Nachher gilt überall: Farbe einmal am Anfang, Firmware einmal dort, wo sie gebraucht wird, jede Antwort wird weitergetragen (`set` und `ask` in `data/rescue.mjs`). Ist beides schon bekannt, sei es aus einer früheren Antwort oder von der angesteckten Electribe, wird die Frage übersprungen.

### Gar nichts

- Vorher: Netzteil prüfen, vier Antworten, "Jetzt geht sie" zu "Firmware zurückgespielt", "Immer noch nichts" zu "nichts auf eigene Faust".
- Nachher: Farbe, Netzteil prüfen, EXIT beim Einschalten halten, Antworten "Jetzt geht sie", "Mit EXIT startet sie" (weiter zur Ursache), 00, Update-Frage, "Immer noch nichts". Das Ende nennt Foto und Kontakt, die Debrick-Anleitung nur für Fortgeschrittene.

### 00

- Vorher: warten, bei 00 Farbe, Download, Karte, Update, bei "Klappt nicht" Ende.
- Nachher: Farbe, warten; bleibt es bei 00: Download der Datei für die Farbe, Ordner als Baum, Prüfung der Karte zuerst, Update. Beim ersten "Klappt nicht" die Prüfung noch einmal, beim zweiten die Frage, was das Display zeigt. Bei 00 kommt das Flachbandkabel und der Kontakt.

### SOFTWARE UPDATE, press ENTER

- Vorher: Farbe, bei blau Hacktribe, Download, Karte, ENTER.
- Nachher: gleich, dazu der Satz, dass die Abfrage immer in diesem Ordner sucht, und die Antwort "Es kommt keine Update-Frage" (Menü oder EXIT).

### Invalid File und No File

- Vorher: Farbe, Wann, danach wieder Farbe, Hacktribe, Download, Firmware, Pfad, "Liegt drauf".
- Nachher: Farbe, Wann, erst Datei neu kopieren (Invalid File), dann Firmware (mit "Weiß ich nicht": Datei in alle drei Ordner), Ordner als Baum mit dem Satz, dass der Ordner nach der laufenden Firmware heißt, Prüfung der Karte, Update. Zweites No File: Prüfung noch einmal, drittes: Kontakt.

### Sie startet, aber etwas spinnt

- Vorher: EXIT, ohne Karte, Dateien umbenennen, sonst Sicherung, Farbe, Download, Firmware, Pfad.
- Nachher: Farbe, EXIT, ohne Karte, Dateien umbenennen, sonst Sicherung mit Satz zu Patterns und Samples und Link zur Pattern-Sicherung, Firmware, Pfad. Dazu die dritte Antwort "Meine Samples fehlen oder klingen falsch".

### Samples

- Vorher: Weg nur für "aus Versehen Hacktribe", Farbe nach dem Patcher-Text.
- Nachher: Farbe, Ist oder war Hacktribe drauf (Nein oder "Weiß ich nicht" führt zur Prüfung der Firmware), Habe ich e2sSample.all, was läuft, bei einer blauen nur mit Hacktribe zuerst Korgs Datei mit dem Sampler-Kopf, sonst der Patcher; das Ende sagt, dass BLECHTRIBE läuft.

### Zurück zu Korgs Original

- Vorher: Farbe, bis zu dreimal Firmware, Download vor der Entscheidung, Knopf für die Datei.
- Nachher: Farbe, Hinweis zu Patterns und Sicherung, was läuft (Korgs Original: nichts zu tun), blau: mit Hacktribe oder nicht (ohne "Weiß ich nicht"-Sackgasse), Download der Seite der Datei mit Version 2.02 und Dateinamen, bei Hacktribe das Upload-Feld für Korgs `SYSTEM.VSB` (wie im Patcher), Ordner, Prüfung, Update.

## Noch offen

- Ob eine blaue mit Hacktribe sich der App als rote meldet, ist offen; deshalb nimmt die Seite nur eine blaue ohne Rückfrage, eine rote lässt sie bestätigen.
- Ob es eine Tastenkombination beim Einschalten gibt, die SOFTWARE UPDATE erzwingt: die Doku kennt keine ([Tastenkombinationen](../tastenkombinationen.md)), die Tabelle dort führt nur in Testseiten. Die Seite nennt deshalb keine.
- Wie die Beschriftung der Geräte genau lautet, die die Farbfrage nennt ("electribe sampler", "electribe"): Hinweis aus dem Hilfekanal, am Gerät nicht gegengelesen.
- Dass "Datei in alle drei Ordner" bei unbekannter Firmware nichts schadet, ist hergeleitet (das Update liest nur den Ordner der laufenden Firmware), am Gerät nicht geprüft.
- Die Texte der Seite sind in Deutsch und Englisch neu geschrieben; in den übrigen neun Sprachen steht für die neuen Schlüssel der englische Text.
