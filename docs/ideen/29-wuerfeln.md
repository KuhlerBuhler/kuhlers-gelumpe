# Idee 29: Patterns würfeln

Stand: entschieden am 2026-10-15, das Würfeln soll eine Funktion in der Firmware werden, nicht im Editor. Die Editor-Version (Seite Pattern-Werkzeuge) bleibt mit Code und Tests im Repo, steht aber nicht mehr in der Navigation ([Entscheidung](../entscheidungen.md)). **Die Firmware-Version ist gebaut, der Patch Würfeln (SHIFT + PART ERASE würfelt eine Melodie für den gewählten Part, [Messung](../messungen/2026-10-16-wuerfeln.md), im Emulator geprüft, am Gerät nichts bestätigt).** Entschieden für die Firmware: nur Melodien, kein Drum-Modus. Am Gerät ist nichts davon gehört. Zurück zu den [Ideen](../ideen.md).

Einen Drum- oder Melodie-Part aus wenigen Reglern würfeln und als Pattern-Dump (`0x40`, am Gerät belegt, [Geräteprotokoll](../messungen/2026-10-08-geraeteprotokoll.md)) oder in eine Sicherung schicken. Der Würfel liegt in `src/dice.mjs`, die Bedienung beschreibt [Pattern-Werkzeuge](../set/pattern-werkzeuge.md).

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
