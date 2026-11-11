# Idee 29: Patterns würfeln

Stand: entschieden am 2026-10-15, das Würfeln soll eine Funktion in der Firmware werden, nicht im Editor. Die Editor-Version (Seite Pattern-Werkzeuge) bleibt mit Code und Tests im Repo, steht aber nicht mehr in der Navigation ([Entscheidung](../entscheidungen.md)). **Die Firmware-Version ist gebaut, der Patch Würfeln (SHIFT + PART ERASE würfelt eine Melodie für den gewählten Part, [Messung](../messungen/2026-10-16-wuerfeln.md), im Emulator geprüft, am Gerät nichts bestätigt).** Entschieden für die Firmware: nur Melodien, kein Drum-Modus. Am Gerät ist nichts davon gehört. Zurück zu den [Ideen](../ideen.md).

Einen Drum- oder Melodie-Part aus wenigen Reglern würfeln und als Pattern-Dump (`0x40`, am Gerät belegt, [Geräteprotokoll](../messungen/2026-10-08-geraeteprotokoll.md)) oder in eine Sicherung schicken. Der Würfel liegt in `src/dice.mjs`, die Bedienung steht unten unter [Bedienung im Editor](#bedienung-im-editor).

Gebaut (im Editor, versteckt):

- Dichte, Tonleiter, Grundton, Oktavlage und Umfang, Gate, Velocity-Spielraum, Swing, Länge und Seed; derselbe Seed gibt dieselben Bytes (Test gegen den Generator, auch im Browser),
- Vorschau im Step-Raster, Namensfeld,
- Ausgabe als `.e2spat`, als Kopie der Sicherung oder in den Pattern-Puffer, immer durch Linter und Türsteher und mit Bestätigung.

Grenzen und Entscheidungen:

- Es wird nur bearbeitet, nie gebaut: der Würfel braucht ein vorhandenes Pattern als Basis und schreibt nur die Steps eines Parts, dazu auf Wunsch Swing, Länge, Name, Tonart und Tonleiter und den Mute des Parts. Das Sample des Parts wählt er nicht.
- Die Tonleitern sind die 16 der Liste des Geräts, deren Töne eindeutig sind. Die Töne stammen aus der Musiktheorie, nicht vom Gerät; Raga, Arabic, Spanish und die anderen, die die Liste nicht ausschreibt, fehlen.
- Drums spielen nur C4 (die Tonhöhe des Samples). Melodien bleiben in der Tonleiter, mehr Regeln hat die Melodie nicht.

Offen:

- am Gerät anhören und hören, ob die Dichten und Velocities taugen,
- ~~das Würfeln als Funktion in der Firmware~~ gebaut als Patch (`data/patches/dice.json`, `tools/patch/dice.py`, `tools/emu/dice_cases.py`): SHIFT + PART ERASE würfelt den gewählten Part, Töne aus Tonart und Tonleiter des Patterns (die Tonleitertabelle der Firmware), Pausen und Noten auf der 16tel-Folge, Gates mit gelegentlichem Tie, innerhalb der Pattern-Länge und des LAST STEP des Parts. Nichts im Flash, das Pattern bleibt ungespeichert bis WRITE. Unterschied zum Editor-Würfel: nur Melodien (keine Drum-Dichte, keine Regler für Swing, Länge, Seed), der Zufall kommt aus Timer3, die Töne aus den Graden der Firmwaretabelle bis zwei Oktaven über C3 plus Tonart.
- Dazu offen: eine Menüseite DICE (das Wort `DC_SETTING` liegt bereit), eine Rückmeldung im Display, am Gerät hören, ob Dichte, Gates und Sprünge taugen.

## Bedienung im Editor

Die Seite Pattern-Werkzeuge (nur mit `?labs` an der Adresse) ist kein Pattern-Editor: sie liest, rechnet eine Vorschau und gibt das Ergebnis weiter. Die geladene Datei wird nie verändert. Am Gerät ist nichts davon gehört, im Browser gegen das simulierte Gerät ist es durchgespielt.

Das Basis-Pattern kommt aus

- einer **Pattern-Sicherung** (`.e2sallpat`) oder einer **einzelnen Pattern-Datei** (`.e2spat`), die du auf der Seite auswählst. Sie verlässt deinen Rechner nicht.
- dem **Pattern-Puffer** des verbundenen Geräts: "Vom Gerät holen" neben der Auswahl legt eine Kopie ab ("Gerät, Kopie 1: Name"). Das Gerät verbindest du im Bereich Emulator unter "Echtes Gerät", den Emulator (wenn er läuft) mit "Mit Emulator verbinden" auf der Seite.

Ohne Datei und ohne Verbindung sagt die Seite, was fehlt, und gibt nichts aus.

Das Würfeln schreibt die Steps **eines** Parts in eine Kopie des Basis-Patterns. Records werden bearbeitet, nie gebaut: es braucht ein Pattern, das es schon gibt, und der Part braucht dort ein Sample. Geändert werden nur die Steps dieses Parts (An, Trigger, Velocity, Gate, Note), dazu auf Wunsch Swing, Länge, Name, Tonart und Tonleiter und der Mute des Parts. Alles andere bleibt Byte für Byte.

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

Die Vorschau ist das Step-Raster des Editors. Ein Schritt, den du dort änderst, gilt für dieses Ergebnis, bis du Regler bewegst oder neu würfelst. Das Gate geht nur bis 96, 127 (Tie) schreibt der Würfel nicht.

Das Namensfeld im Pattern-Block ist 16 Zeichen lang (gemessen, [Pattern-Diff](../messungen/2026-09-16-pattern-diff.md)); die Seite lässt nur druckbares ASCII zu, mehr bietet die Namenseingabe am Gerät nicht (hergeleitet, nicht geprüft). Ein leeres oder nicht darstellbares Feld lässt "DICE" und den Seed stehen statt "Init Pattern".

Das Ergebnis geht an drei Orte, immer erst durch den Linter (`checkRoll`; ein Befund mit Stufe Fehler sperrt die Ausgabe, eine Warnung steht dabei):

- **`.e2spat` speichern.** Auf die Karte kopieren, am Gerät das Pattern anwählen, das überschrieben werden soll, dann MENU, DATA UTILITY, 3 IMPORT PATTERN, Quelle Card, die Datei wählen. Das importiert in den Bearbeitungspuffer; erst WRITE, WRITE speichert, sonst ist der Import beim nächsten Patternwechsel weg. Im Emulator durchgespielt ([Messung](../messungen/2026-10-10-pattern-kette-import.md)), am Gerät nicht geprüft.
- **In Sicherung einsetzen und speichern**: eine Kopie der geladenen Sicherung mit dem neuen Pattern auf seinem Platz. Ein belegter Platz fragt vorher, die geladene Datei bleibt unverändert. Die Kopie gehört per IMPORT ALL PATTERN aufs Gerät und ersetzt dort alle 250 Patterns; vorher eine frische Sicherung (EXPORT ALL PATTERN) ziehen.
- **An Gerät senden**, in den Pattern-Puffer. Der Weg ist der des Pattern-Sendens (`0x40`, [Geräteprotokoll](../messungen/2026-10-08-geraeteprotokoll.md)): der Puffer wird vorher gesichert, der Türsteher prüft, du bestätigst, das Ergebnis wird zurückgelesen, und "Senden zurücknehmen" holt den alten Puffer zurück. Dauerhaft wird das Pattern erst mit WRITE am Gerät, auf dem Platz, den du dort wählst. Bei einem echten Gerät läuft jede Sendung vorher durch den Emulator, wie bei allen Änderungen.
