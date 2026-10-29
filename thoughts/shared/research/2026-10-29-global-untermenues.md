# Global in Untermenüs nach Themen: Machbarkeit (29.10.)

Wunsch: die Seiten von GLOBAL PARAMETERS (und die Funktionen von DATA UTILITY) nach Themen gruppieren, etwa "Samples",
"Patterns", "Export", "Import", mit allem, was dazugehört, darunter. Nur recherchiert, nichts gebaut.

## Was es heute gibt (gemessen im Emulator, Hacktribe und blau)

- GLOBAL PARAMETERS ist Bildschirm 9 mit 20 Seiten, Zähler "n/20". Die Seite steht im Parameter-Objekt
  (`[0xC0691240]`, lesen `0xC007B074`, setzen `0xC007B084`), der Konstruktor öffnet auf ihr. EDIT links und rechts sind
  die Slots 4 und 5 (`0xC0064C20`, `0xC0064C28`), sie laufen in einen Schritt mit festem Umbruch bei 20 (`0xC0064BD4`).
  Die 20 Seiten hängen an drei Tabellen mit je 20 Einträgen am Parameter-Objekt und an fünf Stellen im Code
  ([skript-laufzeit.md](../../../docs/hintergrund/skript-laufzeit.md), Abschnitt 5.3).
- DATA UTILITY ist Bildschirm 14 (eine Seite im Ring) und die Funktionsliste Bildschirm 15: 14 Funktionen (blau 11),
  eine Zustandsmaschine mit 40 Zuständen in `0xC0061A24`. Mit welcher Funktion die Liste öffnet, steht in
  `0xC0691228` (blau `0xC056B508`). Die Slots 4 und 5 (`0xC00623C0`, `0xC0062448`) blättern im Kreis.
- Seit 1.3.8 hängen genau diese vier Slots an der Laufzeit: an den Rändern geht es auf Seiten des Bildschirms BLECH
  (PLUGIN RUNTIME, die Exporte, SET INIT PATTERN). Damit ist gezeigt, dass man Bildschirm 9 und 15 von außen auf eine
  bestimmte Seite oder Funktion öffnen und ihr EDIT an jeder Stelle umlenken kann, ohne ihre Tabellen anzufassen.

## Wie es gehen könnte (hergeleitet)

1. **Eine Themenliste vor Global.** MENU auf "Global" (Bildschirm 8) öffnet statt Bildschirm 9 eine Ebene des Bildschirms
   BLECH mit den Themen (SAMPLES, PATTERNS, MIDI, POWER, EXPORT, IMPORT, ...), jede mit `press  [ Enter ]`, so wie heute
   die Liste der Gruppen von BLECH. Dafür ein Haken mehr: der MENU-Slot von Bildschirm 8.
2. **Ein Thema ist eine Liste von Seitennummern.** ENTER auf einem Thema setzt die erste Seite (`0xC007B084`) und öffnet
   Bildschirm 9. Die schon gehakten Slots 4 und 5 schauen in der Liste des Themas nach, welche Seite die nächste ist, statt
   um eins weiterzuzählen; am Ende der Liste geht es im Kreis. Der Zählerhaken zeigt "Thema i/n" statt "n/20". EXIT auf
   Bildschirm 9 geht zurück auf die Themenliste (Slot 2, noch ein Haken).
3. **Funktionen von DATA UTILITY in denselben Themen.** EXPORT und IMPORT sind Funktionen von Bildschirm 15. Ein Thema darf
   auch Funktionsnummern enthalten: ENTER schreibt sie nach `0xC0691228` und öffnet Bildschirm 15, die Slots 4 und 5 lenken
   wie oben innerhalb des Themas. Unsere eigenen Seiten (Exporte, PLUGIN RUNTIME) stehen als Seiten des Bildschirms BLECH
   in derselben Liste. Gemischte Themen (Global-Seiten und Data-Util-Funktionen) wechseln dabei zwischen den Bildschirmen,
   das tun EDIT links und rechts heute an den Rändern schon.

## Grenzen und Risiken

- Die Funktionen von Bildschirm 15 springen in Unterzustände (Dateiauswahl, Fortschritt, Bestätigung). Solange einer läuft,
  sperrt die Liste EDIT (`0xC00623A8`); das muss so bleiben. Ob jede Funktion nach dem Ende wieder auf ihren eigenen
  Zustand zurückkehrt (und nicht auf die Nachbarfunktion), ist nicht gemessen.
- Die Kurzwege der Firmware (Shift + Pad auf Global-Seiten, [Tastenkombinationen](../../../docs/tastenkombinationen.md))
  öffnen Bildschirm 9 auf einer festen Seite, ohne Thema. Dann gilt EDIT wie ohne Themen, oder die Seite muss ihr Thema
  selbst finden. Nicht untersucht.
- Die Themen und welche Seite wohin gehört sind eine Produktentscheidung, keine technische.
- Platz: die Tabellen sind klein (ein Byte je Seite), der Code geschätzt 1 bis 2 KB im Bereich der Laufzeit
  (`0xC0150300` bis `0xC0170000`, dort sind nach 1.3.8 noch gut 80 KB frei).

## Einschätzung

Machbar, ohne die Tabellen der Firmware zu ändern: es ist die Technik von 1.3.8 (Ränder der Seiten auf den Bildschirm BLECH
umlenken), nur mit einer Nachschlagetabelle statt des Randes. Drei Haken mehr (MENU auf Bildschirm 8, EXIT auf 9 und 15),
eine neue Ebene des Bildschirms BLECH und die Themenlisten. Aufwand geschätzt zwei bis drei Tage mit den Emulatorfällen
für rot, Hacktribe und blau, dazu die Gerätetests. Vorher klären: die Themen selbst, und ob die Kurzwege der Firmware ein
Thema mitnehmen sollen. Nach 1.3.8.
