# 82. Vorschau: einen Part ins laufende Pattern holen

Wunsch (30.10.): in der Vorschau (`VIEW:` oder `NEXT:`) ein Pad im Modus PART MUTE entstummen, und der Part fängt an zu spielen,
ohne dass das Pattern gewechselt wird. Stand 2026-10-30: **gebaut, im Emulator geprüft (Hacktribe, rot, blau), am Gerät nichts.**
Marker: **gemessen**, **hergeleitet**, **ungeprüft**.

## Entschieden (30.10.)

- Entstummen von Part N im angesehenen Pattern B kopiert Part N von B ins laufende Pattern A und ersetzt dort Part N, Klang und
  Steps. Er spielt sofort und ist nicht stumm.
- Kopiert wird mit der Firmware-eigenen Funktion Copy Part (Part Util 1/4), nicht mit eigenem Code. Sie nimmt auch die Motion des
  Parts mit.
- EXIT ohne Wechsel: der kopierte Part bleibt im laufenden Pattern bis zum nächsten Patternwechsel. Nichts geht in die Bank, auf die
  Karte oder ins Flash.
- Stummschalten in der Vorschau bleibt wie bisher: das Mute gilt in der Ansicht und geht beim Wechsel mit
  ([Vorschau-Pads](../messungen/2026-10-29-vorschau-pads.md)).
- Ein zweiter Druck auf einen schon geholten Part schaltet ihn im laufenden Pattern stumm, ein dritter wieder an, wie ein Pad ohne
  Vorschau. Die Ansicht zeigt dabei dasselbe Mute.
- Beim Wechsel lädt B ganz normal, mit den Mutes, die auf den Pads standen.

## Wie es geht

- Der Pad-Druck, der in der Ansicht einen Part entstummt, geht weiter an die Firmware, gemerkt als "Kopie wartet".
- Dort, wo der Hauptbildschirm beim Pad das Mute setzt (UI-Task, `0xC0060D34`, blau `0xC00577A4`), ruft der Patch Copy Part
  (`0xC00667D4`, blau `0xC005C49C`) mit B und Part N, dann das Mute "an". (gemessen, [Messung](../messungen/2026-10-30-vorschau-part-reinholen.md))
- Copy Part nimmt die Quelle aus dem Pattern im RAM, wenn sie die gewählte Nummer ist. In der Ansicht ist das B, darum steht für den
  Aufruf die laufende Nummer dort. (gemessen)
- EXIT beim Einschalten: wie die Firmware, das Pad schaltet das Mute im laufenden Pattern. (gemessen)

## Grenzen

- Die Kopie ersetzt Part N in A ganz, auch dessen Steps und Motion. Was dort live geändert war, ist weg, bis A neu geladen wird.
- Das laufende Pattern weicht danach von seiner Bank ab, die WRITE-Taste atmet. Wer jetzt WRITE drückt, speichert A mit dem
  geholten Part.
- Stereo-Paare: Copy Part behandelt sie selbst, nicht geprüft. (ungeprüft)
- Ist der Motion-Speicher voll, zeigt die Firmware ihr Fehlerfenster wie bei Copy Part. (hergeleitet, ungeprüft)
- Für die Dauer des Aufrufs steht in der gewählten Nummer die laufende. Der Haken am Sequenzende liest sie in der Ansicht nicht.
  (hergeleitet)

## Am Gerät noch zu prüfen

1. Pattern spielt, ein anderes am Rad ansehen, PART MUTE, einen stummen Part entstummen: spielt er sofort, mit dem Klang aus B?
2. Hört man beim Kopieren einen Knacks oder eine Lücke, in diesem Part oder in anderen?
3. Zweiter Druck: stumm, dritter: wieder an.
4. EXIT: der Part bleibt. Danach MENU auf B: B lädt, mit den Mutes der Pads.
5. Mit Sync Group, mit einem Stereo-Sample, mit Motion im Quell-Part.
6. Blaue Electribe: dasselbe.
