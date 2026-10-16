# Die Seite Pattern-Werkzeuge

Zwei Werkzeuge im Editor, beide auf Patterns: Übergänge zwischen zwei Patterns bauen
([Generator](uebergaenge.md)) und einen Part würfeln ([Idee 29](../ideen/29-wuerfeln.md)). Die
Seite ist kein Pattern-Editor: sie liest, rechnet eine Vorschau und gibt das Ergebnis weiter. Die
geladene Datei wird nie verändert. Am Gerät ist nichts davon gehört, im Emulator und im Browser
gegen das simulierte Gerät ist es durchgespielt.

Die Seite ist vorerst versteckt, siehe [Entscheidungen](../entscheidungen.md#navigation): sie
erscheint nur mit `?labs` an der Adresse.

## Woher die Patterns kommen

- eine **Pattern-Sicherung** (`.e2sallpat`) oder eine **einzelne Pattern-Datei** (`.e2spat`), die
  du auf der Seite auswählst. Sie verlässt deinen Rechner nicht.
- der **Pattern-Puffer** des verbundenen Geräts: "Vom Gerät holen" neben der Auswahl legt eine
  Kopie ab ("Gerät, Kopie 1: Name"). Für A und B vom Gerät holst du zweimal, mit dem anderen
  Pattern dazwischen am Gerät. Das Gerät verbindest du im Bereich Gerät, den Emulator
  (wenn er läuft) mit "Mit Emulator verbinden" auf der Seite.

Ohne Datei und ohne Verbindung sagt die Seite, was fehlt, und gibt nichts aus.

## Übergänge

Du wählst A und B, die Seite rechnet die Übergänge neu, sobald du eine Option änderst. Die Optionen
sind die des Generators: Zahl der Übergänge, Richtung, Tempo, Master-FX-Pad, Filter, Tal, Akzent,
die Parts von B, Ausdünnen vor dem Abgang, Insert-Motion, Chain To. Nicht auf der Seite sind
`--mfx`, `--keep`, `--drop`, `--leave-max`, `--clip` und `--label`: der Name steht dafür je
Übergang im Feld.

Die Vorschau zeigt:

- eine Tabelle der Steps je Part für A, jeden Übergang und B (in Klammern: gemutet),
- je Übergang, was der Generator getan hat, in Worten,
- den Effekt-Wechsel beim Sprung nach B (hergeleitet, am Gerät nicht gemessen),
- die ausführliche Übersicht, dieselbe wie `UEBERSICHT.txt` der Befehlszeile.

Die **Plätze** der Übergänge schlägt die Seite aus den freien Patterns der Sicherung vor (frei
heißt: kein Part hat Sample und Step zugleich). Du kannst sie ändern; ein Platz auf A oder B, ein
doppelter oder einer außerhalb der Sicherung wird mit einem Satz abgewiesen. Ohne Plätze gibt es
kein Chain To, denn Chain To sind Platznummern.

## Würfeln

Das Würfeln schreibt die Steps **eines** Parts in eine Kopie des Basis-Patterns. Records werden
bearbeitet, nie gebaut: es braucht ein Pattern, das es schon gibt, und der Part braucht dort ein
Sample. Geändert werden nur die Steps dieses Parts (An, Trigger, Velocity, Gate, Note), dazu auf
Wunsch Swing, Länge, Name, Tonart und Tonleiter und der Mute des Parts. Alles andere bleibt Byte
für Byte.

| Regler | Wirkung |
|---|---|
| Art | Drums: eine Note (C4, die Tonhöhe des Samples), starke Zählzeiten zuerst. Melodie: Noten aus der Tonleiter, meist in Schritten, selten ein Sprung |
| Dichte | Anteil der Steps des Patterns, die eine Note bekommen (0 bis 100 Prozent) |
| Seed | ganze Zahl; derselbe Seed mit denselben Reglern und demselben Basis-Pattern gibt dieselben Bytes |
| Tonleiter, Grundton, tiefste Oktave, Umfang | nur Melodie; 16 Tonleitern, deren Töne eindeutig sind (die Raga- und anderen Listen des Geräts, deren Töne die Liste nicht nennt, fehlen) |
| Gate-Länge, Velocity-Spielraum | Mittelwert des Gates (Anteil von 96) und wie weit die Velocity streut |
| Länge | 1 bis 4 Takte oder wie das Pattern |
| Swing | optional, -48 bis 48 |
| Tonart und Tonleiter ins Pattern | schreibt `pattern.key` und `pattern.scale` mit der Nummer aus der Liste des Geräts (nur Melodie) |

Die Vorschau ist das Step-Raster des Editors. Ein Schritt, den du dort änderst, gilt für dieses
Ergebnis, bis du Regler bewegst oder neu würfelst. Das Gate geht nur bis 96, 127 (Tie) schreibt der
Würfel nicht.

## Namen

Jedes erzeugte Pattern hat ein Namensfeld. Das Namensfeld im Pattern-Block ist 16 Zeichen lang
(gemessen, [Pattern-Diff](../messungen/2026-09-16-pattern-diff.md)); die Seite lässt nur druckbares
ASCII zu, mehr bietet die Namenseingabe am Gerät nicht (hergeleitet, nicht geprüft). Ein leeres
oder nicht darstellbares Feld lässt den erzeugten Namen stehen ("PRE" und Name von B und Zähler bei
Übergängen, "DICE" und Seed beim Würfeln) statt "Init Pattern".

## Ausgabe

Jedes Ergebnis geht an drei Orte, immer erst durch den Linter (`checkTransition`, `checkRoll`; ein
Befund mit Stufe Fehler sperrt die Ausgabe, eine Warnung steht dabei):

- **`.e2spat` speichern**, eine Datei je Pattern. Wie sie ins Gerät kommt, steht in
  [Pattern aufspielen](pattern-aufspielen.md).
- **In Sicherung einsetzen und speichern**: eine Kopie der geladenen Sicherung mit den neuen
  Patterns auf ihren Plätzen. Ein belegter Platz fragt vorher, die geladene Datei bleibt
  unverändert. Mit "A auf den ersten Übergang zeigen lassen" steht Chain To auch in A. Die Kopie
  gehört per IMPORT ALL PATTERN aufs Gerät und ersetzt dort alle 250 Patterns.
- **An Gerät senden**, ein Pattern nach dem anderen, in den Pattern-Puffer. Der Weg ist der
  des Pattern-Sendens (`0x40`, [Geräteprotokoll](../messungen/2026-10-08-geraeteprotokoll.md)): der Puffer wird vorher
  gesichert, der Türsteher prüft, du bestätigst, das Ergebnis wird zurückgelesen, und
  "Senden zurücknehmen" holt den alten Puffer zurück. Dauerhaft wird das Pattern erst mit WRITE am
  Gerät, auf dem Platz, den du dort wählst. Bei einem echten Gerät läuft jede Sendung vorher durch
  den Emulator, wie bei allen Änderungen.
