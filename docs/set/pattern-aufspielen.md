# Einzelne Patterns auf die Electribe bringen

Im Emulator mit der virtuellen SD-Karte durchgespielt (Belege:
`docs/messungen/2026-10-10-pattern-kette-import.md`). **Am Gerät nichts
geprüft, kein Gerätezugriff.** Die Tastenfolge ist die, die im Emulator lief;
das Gerät sollte dieselben Seiten zeigen.

## Kurz

Eine `.e2spat` von der Karte geht mit DATA UTILITY, 3 IMPORT PATTERN in das
**gerade angewählte Pattern**. Alle anderen Patterns bleiben, wie sie sind.
Danach WRITE, WRITE, sonst ist der Import beim nächsten Patternwechsel weg.

## Was die Datei braucht

- Endung `.e2spat`, genau 16640 Byte (256 Byte Kopf mit `KORG` und
  `e2sampler`, dann der Pattern-Block). Der Generator schreibt das so.
  Zu kurze Dateien oder ein fehlender Kopf: "Error / Invalid Data File".
- Name beliebig (Leerzeichen gehen), Ordner beliebig: Wurzel der Karte oder
  ein Unterordner. Der Browser zeigt Ordner und nur `.e2spat`-Dateien, ohne Endung.
- Kein bestimmter Ordner, kein `KORG/hacktribe/` nötig.

## Schritte

1. Die `.e2spat`-Dateien auf die SD-Karte kopieren (zum Beispiel in einen
   Ordner `TRANS`). Karte ins Gerät, das Kartensymbol erscheint oben rechts.
2. Auf dem Hauptbildschirm mit dem VALUE-Regler das Pattern anwählen, das
   überschrieben werden soll. Ein freier Platz, zum Beispiel 201. **Dieses
   Pattern wird überschrieben.** Die Chain-Ziele in den Übergängen sind
   Slot-Nummern, die Datei muss also genau in dem Slot landen, für den sie
   erzeugt wurde (steht im Dateinamen, `T1_201_...` gehört in Slot 201).
3. MENU, dann EDIT◄ bis oben "Data Util 28/29, DATA UTILITY" steht (vom
   Pattern-Menü aus zweimal EDIT◄; das Menü öffnet an der zuletzt benutzten
   Seite, die Seitenzahl oben im Display sagt, wo man ist).
4. MENU (ENTER). Mit EDIT► bis "Data Util 3/14, IMPORT PATTERN" (ab
   Funktion 1 zweimal).
5. MENU: "SELECT SOURCE, [ Enter ] : Card". MENU: der Dateibrowser, Ordner oben.
   Ein Ordner öffnet mit MENU, darin steht "Upper Folder" an erster Stelle.
   VALUE blättert, MENU auf der Datei importiert.
6. Das Display geht auf den Hauptbildschirm und zeigt den Namen der Datei als
   Patternnamen, mit Tempo und, falls gesetzt, "201 -> 202". Das ist erst der
   Bearbeitungspuffer.
7. WRITE: "select DESTINATION" mit Nummer und Name des Patterns, das
   überschrieben wird (der angewählte Platz, mit VALUE änderbar). WRITE noch
   einmal speichert ("Working..."). EXIT bricht ab.
8. Für das nächste Pattern: VALUE auf den nächsten Platz, wieder ab Schritt 3.

Reihenfolge am Pult: erst alle Übergänge importieren und speichern, dann
spielen. Kette A -> T1 -> T2 -> B läuft nur, wenn A auf T1 zeigt. In der
Datei von A steht das nur mit `--chain-a` (siehe Generator); sonst am Gerät
auf A die Seite CHAIN TO (Pattern-Menü 14/29) auf den Platz von T1 stellen und
A mit WRITE speichern, oder die Übergänge von Hand anspielen.

## IMPORT ALL PATTERN

DATA UTILITY, 4 IMPORT ALL PATTERN liest eine `.e2sallpat` und **ersetzt alle
250 Patterns**. Im Emulator gemessen: nach 20 bis 30 Sekunden "IMPORT ALL
PATTERN / OK", danach steht der Inhalt der Datei im Pattern-Speicher, ohne
WRITE. Das ist nur sinnvoll, wenn die Datei dein ganzes Set trägt, zum
Beispiel die vom Generator mit `--all-out` geschriebene Kopie deiner
Sicherung mit den Übergängen in freien Slots. Vorher eine frische Sicherung
(EXPORT ALL PATTERN) ziehen. Der Weg über einzelne Imports ist der
eingeschränktere und deshalb der bessere.
