# Pattern-Kette und Pattern-Import von der Karte, im Emulator gemessen

Stand 2026-10-10. Alles im Emulator (`tools/emu`, virtuelle SD-Karte in einem
temporären Ordner), Firmware `SYSTEM.VSB`, Flash: eigener Dump vom 9.10. Die
eigene Pattern-Sicherung (`electribe_sampler_allpattern.e2sallpat`, gleich dem
Flash-Dump) diente als Vergleich und lag nie auf einer Karte. Die Einzeldatei
(`.e2spat`) wurde aus einem Pattern dieser Sicherung gebaut. **Am Gerät nichts
geprüft, kein Gerätezugriff.**

Markierungen: **gemessen** (im Emulator ausgeführt und am Display oder in der
exportierten Sicherung gesehen), **hergeleitet**.

## Chain To und Chain Repeat im Pattern-Block

- **gemessen:** Chain To liegt in Byte 15104 (`0x3B00`) des Pattern-Blocks, als
  Nummer des Ziel-Patterns von 1 an gezählt. Pattern 191 trägt dort 192, das
  Display zeigt auf der Seite 14 "CHAIN TO" den Wert "192 KOKS" und auf dem
  Hauptbildschirm "191 -> 192". Pattern 64 trägt 65 und zeigt "64 -> 065".
  0 heißt keine Kette (alle Patterns ohne Kette tragen 0).
- **gemessen:** Chain Repeat liegt in Byte 15106 (`0x3B02`). Auf Seite 15
  "CHAIN REPEAT" von Pattern 64 auf 3 gestellt, WRITE, dann EXPORT ALL PATTERN:
  gegenüber der Sicherung ist genau dieses eine Byte geändert (0 zu 3), sonst
  nichts, in keinem anderen Pattern. Der Hauptbildschirm zeigt dann "01/03".
- **gemessen:** Roh 0 und roh 1 zeigt das Gerät beide als 1 (Pattern 64 trägt
  0, Pattern 191 trägt 1, beide zeigen CHAIN REPEAT 1).
- **hergeleitet:** Byte 15105 ist der obere Teil von Chain To (in allen 250
  Patterns 0, die Nummer passt in ein Byte). In der ganzen Sicherung ändern
  sich in diesem Bereich (`0x3B00` bis zum Ende des Blocks) nur 15104 und 15106.
- Gerät zeigt die Seite "CHAIN TO" als 14/29 und "CHAIN REPEAT" als 15/29 im
  Menü, Pattern-Menü Seite 14 und 15.

## IMPORT PATTERN (DATA UTILITY 3/14)

- **gemessen:** DATA UTILITY, Funktion 3: erst "SELECT SOURCE / Enter : Card",
  dann der Dateibrowser ab der Kartenwurzel. Ordner stehen oben, dann nur
  Dateien mit der Endung `.e2spat` (eine `.txt` fehlt in der Liste); die Endung
  wird nicht angezeigt. Ordner lassen sich öffnen ("Upper Folder" ganz oben),
  Namen mit Leerzeichen gehen. VALUE blättert, MENU ist ENTER.
- **gemessen:** Die Datei geht in das **gerade angewählte Pattern** (der
  Hauptbildschirm zeigt danach dessen Nummer mit dem neuen Namen und Tempo).
  Datei in einem Unterordner: gleicher Weg, gleiches Ergebnis.
- **gemessen:** Der Import füllt nur den Bearbeitungspuffer. Ohne WRITE
  zeigt das Gerät nach "Pattern weiter, dann zurück" wieder den alten Inhalt.
  Mit WRITE, WRITE (Fenster "select DESTINATION" zeigt Nummer und Namen des
  Patterns, das überschrieben wird) bleibt es: weiter und zurück zeigt den
  importierten Inhalt.
- **gemessen:** Danach EXPORT ALL PATTERN: 250 Patterns, **genau eines**
  gegenüber der Ausgangssicherung verändert (das Ziel), der Kopf der Datei
  unverändert, und der Block des Ziels ist **Byte für Byte** der aus der
  `.e2spat`.
- **gemessen:** Eine Datei, die kürzer ist als `0x100 + 0x4000` Byte, und eine
  mit genullten ersten 256 Bytes (kein `KORG` / `e2sampler`) bringen
  "Error / Invalid Data File". Die Datei muss also den Kopf tragen, den
  `toSinglePattern` in `src/pattern.mjs` schreibt, und genau 16640 Byte haben.
  Der Dateiname ist gleichgültig.

## IMPORT ALL PATTERN (DATA UTILITY 4/14)

- **gemessen:** gleiche Abfolge wie beim Einzelimport (Quelle Karte, Browser,
  Datei `.e2sallpat`). "Working..." dauert im Emulator zwischen 20 und 30 Sekunden, dann zeigt das Display "IMPORT ALL PATTERN / OK".
- **gemessen:** Nach EXIT (dreimal) und Pattern 6 anwählen steht dort der
  Name, den die importierte Sicherung für Pattern 6 trägt. Ohne WRITE: Import
  All schreibt in den Pattern-Speicher, nicht nur in den Puffer.
- **hergeleitet:** Import All ersetzt alle 250 Patterns durch die der Datei.
  Dafür taugt es nur, wenn die Datei das ganze Set trägt. Für einzelne
  Übergänge ist der Einzelimport der Weg, weil er nur das angewählte Pattern anfasst.
